from fastapi.testclient import TestClient

from api import server


def test_auth_verify_requires_a_valid_bearer_key(monkeypatch):
    monkeypatch.setattr(server, "BEARER_KEY", "test-key")
    client = TestClient(server.app)

    assert client.get("/auth/verify").status_code == 401
    assert client.get("/auth/verify", headers={"Authorization": "Bearer wrong-key"}).status_code == 401

    response = client.get("/auth/verify", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    assert response.json() == {"authenticated": True}


def test_frontend_entry_and_removed_legacy_routes(monkeypatch, tmp_path):
    frontend_dir = tmp_path / "app"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text("<html><body>Fukae</body></html>", encoding="utf-8")
    monkeypatch.setattr(server, "frontend_dir", frontend_dir)
    client = TestClient(server.app)

    root_response = client.get("/")
    assert root_response.status_code == 200
    assert "Fukae" in root_response.text
    assert client.get("/upload/web").status_code == 404
    assert client.post("/upload/web").status_code == 404