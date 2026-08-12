import os
import time
import httpx
import mimetypes
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DoclingInference:
    """Inference class for interacting with the Docling API server."""

    def __init__(self):
        """Initialize the Docling inference class with server configuration."""
        # Remove trailing slash from base_url if present to avoid double slashes in URLs
        self.base_url = os.getenv("DOCLING_BASE_URL", "").rstrip("/")
        self.headers = {}
        # Note: Docling server uses DOCLING_SERVE_API_KEY for authentication if set

    def _get_content_type_from_name(self, filename: str) -> str:
        """
        Get the content type from a file name.

        Args:
            filename: The name of the file.

        Returns:
            The content type string.
        """
        content_type, _ = mimetypes.guess_type(filename)
        if content_type is None:
            return "application/octet-stream"
        return content_type

    def convert_document(self, source: str, to_formats: list = None, **options) -> Dict[str, Any]:
        """
        Convert a document synchronously from a URL or local file path.

        Args:
            source: The URL or local file path of the document to convert.
            to_formats: List of output formats (e.g., ["md", "json", "html"]).
            **options: Additional conversion options.

        Returns:
            A dictionary containing the conversion result.
        """
        if to_formats is None:
            to_formats = ["md"]

        url = f"{self.base_url}/v1/convert/source"

        # Determine if source is a URL or file path
        if source.startswith("http"):
            payload = {
                "http_sources": [{"url": source}],
                "options": {
                    "to_formats": to_formats,
                    **options
                }
            }
        else:
            # Read the file and convert to base64
            with open(source, "rb") as f:
                import base64
                file_data = base64.b64encode(f.read()).decode('utf-8')

            payload = {
                "file_sources": [{"base64_string": file_data, "filename": Path(source).name}],
                "options": {
                    "to_formats": to_formats,
                    **options
                }
            }

        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()

    def convert_document_async(self, source: str, to_formats: list = None, **options) -> str:
        """
        Submit a document conversion task asynchronously.

        Args:
            source: The URL or local file path of the document to convert.
            to_formats: List of output formats (e.g., ["md", "json", "html"]).
            **options: Additional conversion options.

        Returns:
            The task ID for the conversion task.
        """
        if to_formats is None:
            to_formats = ["md"]

        url = f"{self.base_url}/v1/convert/source/async"

        # Determine if source is a URL or file path
        if source.startswith("http"):
            payload = {
                "http_sources": [{"url": source}],
                "options": {
                    "to_formats": to_formats,
                    **options
                }
            }
        else:
            # Read the file and convert to base64
            with open(source, "rb") as f:
                import base64
                file_data = base64.b64encode(f.read()).decode('utf-8')

            payload = {
                "file_sources": [{"base64_string": file_data, "filename": Path(source).name}],
                "options": {
                    "to_formats": to_formats,
                    **options
                }
            }

        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            task_data = response.json()
            return task_data["task_id"]

    def poll_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Poll the status of an async conversion task.

        Args:
            task_id: The ID of the task to poll.

        Returns:
            A dictionary containing the task status.
        """
        url = f"{self.base_url}/v1/status/poll/{task_id}"

        with httpx.Client() as client:
            response = client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    def get_result(self, task_id: str) -> Dict[str, Any]:
        """
        Fetch the result of a finished conversion task.

        Args:
            task_id: The ID of the task to get the result for.

        Returns:
            A dictionary containing the conversion result.
        """
        url = f"{self.base_url}/v1/result/{task_id}"

        with httpx.Client() as client:
            response = client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    def convert_document_with_polling(self, source: str, to_formats: list = None, **options) -> Dict[str, Any]:
        """
        Convert a document asynchronously and poll until completion.

        Args:
            source: The URL or local file path of the document to convert.
            to_formats: List of output formats (e.g., ["md", "json", "html"]).
            **options: Additional conversion options.

        Returns:
            A dictionary containing the conversion result.
        """
        if to_formats is None:
            to_formats = ["md"]

        # Submit async task
        task_id = self.convert_document_async(source, to_formats, **options)

        # Poll until completion
        while True:
            task_status = self.poll_task_status(task_id)
            task_status_str = task_status.get("task_status", "")

            if task_status_str in ("success", "failure"):
                break

            time.sleep(5)  # Wait 5 seconds before polling again

        # Get the result
        return self.get_result(task_id)
