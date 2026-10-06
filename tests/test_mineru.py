import httpx

from core.mineru import MinerUInference


def _response(method, url, status_code, payload=None, headers=None):
    return httpx.Response(status_code, json=payload, headers=headers, request=httpx.Request(method, url))


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs.get("headers", {})))
        return next(self.responses)


def test_upload_sends_authentication_to_same_origin_target(tmp_path):
    source = tmp_path / "document.pdf"
    source.write_bytes(b"pdf")
    client = FakeClient([
        _response("POST", "http://mineru:8000/v1/uploads", 200, {
            "id": "upload_1", "status": "pending", "upload_url": "/uploads/upload_1", "upload_headers": {},
        }),
        _response("PUT", "http://mineru:8000/uploads/upload_1", 200, {}),
        _response("POST", "http://mineru:8000/v1/uploads/upload_1/complete", 200, {
            "file": {"id": "file_1"},
        }),
    ])
    mineru = MinerUInference(base_url="http://mineru:8000", api_key="secret")

    assert mineru._upload(client, source) == "file_1"
    assert client.calls[1][2]["Authorization"] == "Bearer secret"


def test_cross_origin_redirect_strips_authorization_header():
    client = FakeClient([
        _response("GET", "http://mineru:8000/v1/files/file_1/content", 302, headers={"location": "https://assets.example/file"}),
        _response("GET", "https://assets.example/file", 200),
    ])
    mineru = MinerUInference(base_url="http://mineru:8000", api_key="secret")

    mineru._request(client, "GET", "/v1/files/file_1/content", stage="artifact download")

    assert "Authorization" not in client.calls[1][2]
