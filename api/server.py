from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import shutil
import asyncio
from api.models import UploadResponse, TaskStatusResponse, ChunkResponse
from api.tasks import task_manager
import os
from dotenv import load_dotenv

app = FastAPI(title="Document Indexer API")

# Create necessary directories
chunks_dir = Path("chunks")
chunks_dir.mkdir(exist_ok=True)

uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Bearer key authentication
load_dotenv()
BEARER_KEY = os.getenv("BEARER_KEY") or ""

def verify_bearer_key(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    key = auth_header.split(" ")[1]
    if key != BEARER_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

# Endpoints for HTTP API
@app.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...), _: bool = Depends(verify_bearer_key)):
    task_id = task_manager.create_task()

    # Save uploaded file temporarily
    file_path = uploads_dir / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Start processing in background
    asyncio.create_task(task_manager.process_document(task_id, file_path, chunks_dir))

    return UploadResponse(
        task_id=task_id,
        status="pending",
        message="File upload received and processing started"
    )

@app.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, _: bool = Depends(verify_bearer_key)):
    task_status = task_manager.get_task_status(task_id)

    return TaskStatusResponse(
        task_id=task_id,
        status=task_status["status"],
        progress=task_status.get("progress"),
        result=task_status.get("result"),
        error=task_status.get("error")
    )

@app.get("/chunks/{doc_stem}", response_model=ChunkResponse)
async def get_chunks(doc_stem: str, _: bool = Depends(verify_bearer_key)):
    # Find the chunks file
    chunks_file = chunks_dir / f"{doc_stem}_chunks.json"
    if not chunks_file.exists():
        raise HTTPException(status_code=404, detail=f"Chunks not found for document: {doc_stem}")

    import json
    with open(chunks_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    return ChunkResponse(
        doc_stem=data.get("doc_stem", doc_stem),
        model=data.get("model", ""),
        dimension=data.get("dimension", 0),
        chunks=data.get("chunks", [])
    )

@app.get("/download/chunks/{doc_stem}_chunks.json")
async def download_chunks(doc_stem: str, _: bool = Depends(verify_bearer_key)):
    # Find the chunks file
    chunks_file = chunks_dir / f"{doc_stem}_chunks.json"
    if not chunks_file.exists():
        raise HTTPException(status_code=404, detail=f"Chunks file not found for document: {doc_stem}")

    return FileResponse(
        path=chunks_file,
        filename=f"{doc_stem}_chunks.json",
        media_type="application/json"
    )

# Web UI endpoints
@app.get("/upload/web", response_class=HTMLResponse)
async def upload_web_page(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.post("/upload/web")
async def upload_web_file(file: UploadFile = File(...)):
    task_id = task_manager.create_task()

    # Save uploaded file temporarily
    file_path = uploads_dir / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Start processing in background
    asyncio.create_task(task_manager.process_document(task_id, file_path, chunks_dir))

    return JSONResponse(content={
        "task_id": task_id,
        "status": "pending",
        "message": "File upload received and processing started"
    })
