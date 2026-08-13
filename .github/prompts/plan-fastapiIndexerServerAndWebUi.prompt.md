## Plan: FastAPI Indexer Server and Web UI

**TL;DR:** Build a FastAPI HTTP server for the document indexer that allows other servers to send documents via HTTP calls, and create a simple webpage where users can manually upload files to generate embedded chunks.

**Steps**

### Phase 1: Setup and Dependencies
1. Add FastAPI, uvicorn, and HTML template dependencies to `requirements.txt`
   - `fastapi>=0.104.0`
   - `uvicorn[standard]>=0.24.0`
   - `python-multipart>=0.0.6` (for file uploads)
   - `jinja2>=3.1.2` (for HTML templates)

### Phase 2: FastAPI Server Implementation
2. Create `api/server.py` - FastAPI application with:
   - `/upload` endpoint (POST) for HTTP API calls to send documents
   - `/upload/web` endpoint (GET/POST) for the web UI page and file upload handling
   - `/status/{task_id}` endpoint (GET) to check processing status
   - `/chunks/{doc_stem}` endpoint (GET) to retrieve generated chunks

3. Create `api/models.py` - Pydantic models for:
   - Upload request/response models
   - Task status models

4. Create `api/tasks.py` - Background task manager for:
   - Document processing using `DocumentIndexer`
   - Task state tracking (pending, processing, completed, failed)

### Phase 3: Web UI Implementation
5. Create `templates/index.html` - Simple web page with:
   - File upload form supporting multiple file types (.pdf, .docx, .xlsx, .png, etc.)
   - Progress indicator for processing
   - Display area for generated chunks or download link

6. Create `static/style.css` - Basic styling for the web UI

### Phase 4: Integration and Testing
7. Update `scripts/run_indexer.py` or create `scripts/run_api_server.py` - Script to start the FastAPI server

8. Test the HTTP API endpoints and web UI functionality

**Relevant files**
- `d:\Github\Fukae\requirements.txt` — Add FastAPI, uvicorn, python-multipart, jinja2 dependencies
- `d:\Github\Fukae\indexer\indexer.py` — `DocumentIndexer.load()` method for document processing
- `d:\Github\Fukae\scripts\run_indexer.py` — Reference for how the indexer processes files and outputs JSON
- `d:\Github\Fukae\indexer\stage6_embed.py` — Reference for embedding generation and output format

**Verification**
1. Start the FastAPI server: `python scripts/run_api_server.py` or `uvicorn api.server:app --host 0.0.0.0 --port 8000`
2. Test HTTP API: `curl -X POST http://localhost:8000/upload -F "file=@test.pdf"`
3. Test web UI: Open `http://localhost:8000/upload/web` in browser, upload a file, verify chunks are generated
4. Verify output JSON files are created in the designated output directory with correct embedded chunks format

**Decisions**
- Use FastAPI with uvicorn for the HTTP server (modern, async, well-suited for this use case)
- Store processed documents and chunks in the `chunks/` directory
- Use background tasks for document processing to avoid blocking the HTTP server
- Support the same file extensions as the current indexer: `.pdf, .docx, .doc, .odt, .rtf, .html, .htm, .xlsx, .xls, .csv, .pptx, .ppt, .json, .png, .jpg, .jpeg, .gif, .bmp, .tiff, .webp, .md, .txt`
- Use bearer key authentication for the HTTP API with the key: "pat_me_sw_fukae"

**Further Considerations**
1. Should the server store processed chunks in memory or always write to disk? Recommendation: Write to disk and return file references/paths.
   Ans: write on disk, save to chunks folder
2. Should the web UI support batch uploads or only single file uploads? Recommendation: Support multiple file uploads with individual processing status.
   Ans: support multiple file uploads
3. How should authentication/authorization be handled for the HTTP API? Recommendation: Start without auth for simplicity, but add API key support as a future consideration.
   Ans: use bearer key "pat_me_sw_fukae"
