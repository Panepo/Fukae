from pydantic import BaseModel
from typing import List, Dict, Optional
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadRequest(BaseModel):
    file_name: str
    file_content: bytes


class UploadResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: Optional[int] = None
    result: Optional[Dict] = None
    error: Optional[str] = None


class ChunkResponse(BaseModel):
    doc_stem: str
    model: str
    dimension: int
    chunks: List[Dict]
