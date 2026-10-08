from fastapi.testclient import TestClient
import json

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


def test_delete_managed_file_requires_auth_and_stays_in_managed_directory(monkeypatch, tmp_path):
    uploads_dir = tmp_path / "uploads"
    chunks_dir = tmp_path / "chunks"
    uploads_dir.mkdir()
    chunks_dir.mkdir()
    (uploads_dir / "document.pdf").write_text("content", encoding="utf-8")
    monkeypatch.setattr(server, "BEARER_KEY", "test-key")
    monkeypatch.setattr(server, "uploads_dir", uploads_dir)
    monkeypatch.setattr(server, "chunks_dir", chunks_dir)
    client = TestClient(server.app)

    assert client.delete("/files/uploads/document.pdf").status_code == 401

    response = client.delete(
        "/files/uploads/document.pdf",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    assert response.json() == {"deleted": "document.pdf"}
    assert not (uploads_dir / "document.pdf").exists()

    traversal_response = client.delete(
        "/files/uploads/..%2Foutside.txt",
        headers={"Authorization": "Bearer test-key"},
    )
    assert traversal_response.status_code == 404


def test_process_document_bypasses_indexing_for_generated_chunk_json(monkeypatch, tmp_path):
    chunk_export = {
        "model": "test-embedding-model",
        "dimension": 2,
        "doc_stem": "already-indexed",
        "chunks": [{
            "chunk_id": "source.pdf_0000",
            "source": "source.pdf",
            "chunk_type": "text",
            "chunk_text_original": "Original text",
            "chunk_text_embedded": "Embedded text",
            "embedding": [0.1, -0.2],
        }],
    }
    uploaded_file = tmp_path / "uploaded_chunks.json"
    output_dir = tmp_path / "chunks"
    output_dir.mkdir()
    uploaded_file.write_text(json.dumps(chunk_export), encoding="utf-8")

    task_manager = server.task_manager.__class__()
    monkeypatch.setattr(task_manager.indexer, "load", lambda _: (_ for _ in ()).throw(AssertionError("Indexer was called")))
    task_id = task_manager.create_task()

    import asyncio
    asyncio.run(task_manager.process_document(task_id, uploaded_file, output_dir))

    status = task_manager.get_task_status(task_id)
    assert status["status"] == "completed"
    assert status["result"]["doc_stem"] == "already-indexed"
    assert status["result"]["chunks_count"] == 1
    assert json.loads((output_dir / "already-indexed_chunks.json").read_text(encoding="utf-8")) == chunk_export
