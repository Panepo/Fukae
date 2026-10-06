"""MinerU V1 client used as the PDF fallback parser."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx


class MinerUError(RuntimeError):
    """A MinerU failure whose message is safe to expose in task errors."""

    def __init__(self, stage: str, message: str) -> None:
        self.stage = stage
        super().__init__(f"MinerU {stage} failed: {message}")


@dataclass(frozen=True)
class MinerUResult:
    """Artifacts returned by a completed MinerU parse job."""

    structured_content: dict[str, Any] | list[Any] | None
    markdown: str | None
    zip_bytes: bytes | None


class MinerUInference:
    """Synchronous client for the self-hosted MinerU 4 V1 API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        tier: str | None = None,
        timeout: float | None = None,
        poll_interval: float | None = None,
        poll_timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url if base_url is not None else os.getenv("MINERU_BASE_URL", "")).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("MINERU_API_KEY")
        self.tier = tier if tier is not None else os.getenv("MINERU_TIER", "standard")
        self.timeout = timeout if timeout is not None else float(os.getenv("SERVER_TIMEOUT", "180"))
        self.poll_interval = poll_interval if poll_interval is not None else float(os.getenv("MINERU_POLL_INTERVAL", "1"))
        self.poll_timeout = poll_timeout if poll_timeout is not None else float(os.getenv("MINERU_POLL_TIMEOUT", "1800"))
        self._features: dict[str, set[str]] | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def parse_pdf(self, path: str | Path) -> MinerUResult:
        """Upload, parse, and retrieve structured output for one PDF."""
        if not self.enabled:
            raise MinerUError("configuration", "MINERU_BASE_URL is not configured")

        file_path = Path(path)
        features = self.discover_capabilities()
        output_formats = ["zip"]
        if "structured_content" in features["output_formats"]:
            output_formats.insert(0, "structured_content")
        elif "markdown" in features["output_formats"]:
            output_formats.insert(0, "markdown")
        else:
            raise MinerUError("capability discovery", "service does not support structured_content or markdown output")

        with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
            file_id = self._upload(client, file_path)
            job = self._request_json(
                client,
                "POST",
                "/v1/parse/jobs",
                json={
                    "files": [{"source": {"type": "file_id", "file_id": file_id}}],
                    "tier": self.tier,
                    "output_formats": output_formats,
                },
                stage="job submission",
            )
            completed_job = self._wait_for_job(client, job)

            files = completed_job.get("files")
            if not isinstance(files, list) or len(files) != 1 or not isinstance(files[0], dict):
                raise MinerUError("job result", "completed job has no single file result")
            output_files = files[0].get("output_files")
            if not isinstance(output_files, dict):
                raise MinerUError("job result", "completed job has no output artifacts")

            structured_content = self._download_json_artifact(client, output_files.get("structured_content"))
            markdown = self._download_text_artifact(client, output_files.get("markdown"))
            zip_bytes = self._download_bytes_artifact(client, output_files.get("zip"))
            return MinerUResult(structured_content, markdown, zip_bytes)

    def discover_capabilities(self) -> dict[str, set[str]]:
        """Fetch and cache the server's advertised V1 capabilities."""
        if self._features is not None:
            return self._features
        with httpx.Client(timeout=self.timeout) as client:
            payload = self._request_json(client, "GET", "/v1/health", stage="health discovery")
        features = payload.get("features")
        if payload.get("status") != "ok" or not isinstance(features, dict):
            raise MinerUError("health discovery", "malformed health response")
        self._features = {
            "output_formats": {value for value in features.get("output_formats", []) if isinstance(value, str)},
            "sources": {value for value in features.get("sources", []) if isinstance(value, str)},
        }
        return self._features

    def _upload(self, client: httpx.Client, path: Path) -> str:
        sha256sum = _sha256_file(path)
        mime_type = mimetypes.guess_type(path.name)[0] or "application/pdf"
        upload = self._request_json(
            client,
            "POST",
            "/v1/uploads",
            json={
                "filename": path.name,
                "bytes": path.stat().st_size,
                "mime_type": mime_type,
                "purpose": "parse",
                "sha256sum": sha256sum,
            },
            stage="upload creation",
        )
        completed_file = upload.get("file")
        if upload.get("status") == "completed" and isinstance(completed_file, dict):
            file_id = completed_file.get("id")
            if isinstance(file_id, str):
                return file_id

        upload_id = upload.get("id")
        upload_url = upload.get("upload_url")
        if not isinstance(upload_id, str) or not isinstance(upload_url, str):
            raise MinerUError("upload creation", "response did not include an upload target")
        target = urljoin(f"{self.base_url}/", upload_url)
        headers = upload.get("upload_headers") if isinstance(upload.get("upload_headers"), dict) else {}
        if _same_origin(self.base_url, target):
            headers = {**headers, **self._auth_headers()}
        self._request_bytes(client, "PUT", target, content=path.read_bytes(), headers=headers, stage="upload content")

        complete = self._request_json(client, "POST", f"/v1/uploads/{upload_id}/complete", stage="upload completion")
        completed_file = complete.get("file")
        if not isinstance(completed_file, dict) or not isinstance(completed_file.get("id"), str):
            raise MinerUError("upload completion", "response did not include a file id")
        return completed_file["id"]

    def _wait_for_job(self, client: httpx.Client, job: dict[str, Any]) -> dict[str, Any]:
        job_id = job.get("job_id")
        if not isinstance(job_id, str):
            raise MinerUError("job submission", "response did not include a job id")
        deadline = time.monotonic() + self.poll_timeout
        while True:
            status = job.get("status")
            if status == "completed":
                return job
            if status in {"partial", "failed", "canceled"}:
                raise MinerUError("parse job", f"job ended with status {status}")
            if status not in {"queued", "running"}:
                raise MinerUError("parse job", "job response has an unknown status")
            if time.monotonic() >= deadline:
                raise MinerUError("parse job", "job did not complete before the poll timeout")
            time.sleep(self.poll_interval)
            job = self._request_json(client, "GET", f"/v1/parse/jobs/{job_id}", stage="job polling")

    def _download_json_artifact(self, client: httpx.Client, artifact: Any) -> dict[str, Any] | list[Any] | None:
        data = self._download_bytes_artifact(client, artifact)
        if data is None:
            return None
        try:
            import json
            parsed = json.loads(data)
        except (UnicodeDecodeError, ValueError) as exc:
            raise MinerUError("structured content download", "artifact is not valid JSON") from exc
        if not isinstance(parsed, (dict, list)):
            raise MinerUError("structured content download", "artifact must be a JSON object or list")
        return parsed

    def _download_text_artifact(self, client: httpx.Client, artifact: Any) -> str | None:
        data = self._download_bytes_artifact(client, artifact)
        if data is None:
            return None
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MinerUError("markdown download", "artifact is not UTF-8 text") from exc

    def _download_bytes_artifact(self, client: httpx.Client, artifact: Any) -> bytes | None:
        if artifact is None:
            return None
        if not isinstance(artifact, dict) or not isinstance(artifact.get("file_id"), str):
            raise MinerUError("artifact download", "artifact reference is malformed")
        return self._request_bytes(client, "GET", f"/v1/files/{artifact['file_id']}/content", stage="artifact download")

    def _request_json(self, client: httpx.Client, method: str, url: str, *, stage: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._request(client, method, url, stage=stage, json=json)
        try:
            payload = response.json()
        except ValueError as exc:
            raise MinerUError(stage, "server returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise MinerUError(stage, "server returned a malformed response envelope")
        return payload

    def _request_bytes(self, client: httpx.Client, method: str, url: str, *, stage: str, content: bytes | None = None, headers: dict[str, str] | None = None) -> bytes:
        response = self._request(client, method, url, stage=stage, content=content, headers=headers)
        return response.content

    def _request(self, client: httpx.Client, method: str, url: str, *, stage: str, json: dict[str, Any] | None = None, content: bytes | None = None, headers: dict[str, str] | None = None) -> httpx.Response:
        target = urljoin(f"{self.base_url}/", url)
        request_headers = headers if headers is not None else self._auth_headers()
        try:
            response = client.request(method, target, json=json, content=content, headers=request_headers)
            if response.is_redirect:
                redirect_target = response.headers.get("location")
                if not redirect_target:
                    raise MinerUError(stage, "redirect did not include a location")
                target = urljoin(target, redirect_target)
                redirect_headers = request_headers if _same_origin(self.base_url, target) else _without_credentials(request_headers)
                response = client.request(method, target, json=json, content=content, headers=redirect_headers)
            response.raise_for_status()
            return response
        except MinerUError:
            raise
        except httpx.HTTPStatusError as exc:
            raise MinerUError(stage, f"server returned HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise MinerUError(stage, f"transport error ({type(exc).__name__})") from exc

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_origin(first: str, second: str) -> bool:
    first_url = urlparse(first)
    second_url = urlparse(second)
    return (first_url.scheme, first_url.netloc) == (second_url.scheme, second_url.netloc)


def _without_credentials(headers: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() != "authorization"}
