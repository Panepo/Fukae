import asyncio
import uuid
from pathlib import Path
from typing import Dict, Any
from api.models import TaskStatus, UploadRequest
from indexer.indexer import DocumentIndexer


class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.indexer = DocumentIndexer()

    def create_task(self) -> str:
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            "status": TaskStatus.PENDING,
            "progress": 0,
            "result": None,
            "error": None
        }
        return task_id

    def update_task_status(self, task_id: str, status: TaskStatus, progress: int = None, result: Any = None, error: str = None):
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = status
            if progress is not None:
                self.tasks[task_id]["progress"] = progress
            if result is not None:
                self.tasks[task_id]["result"] = result
            if error is not None:
                self.tasks[task_id]["error"] = error

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        return self.tasks.get(task_id, {"status": TaskStatus.FAILED, "error": "Task not found"})

    async def process_document(self, task_id: str, file_path: Path, output_dir: Path):
        try:
            self.update_task_status(task_id, TaskStatus.PROCESSING, progress=10)

            # Process the document using the indexer in a thread pool to avoid blocking the async event loop
            # stage6_embed.generate_embeddings already saves the file to output_dir
            result = await asyncio.to_thread(self.indexer.load, str(file_path))

            self.update_task_status(task_id, TaskStatus.PROCESSING, progress=50)

            # Update task status with the result info
            doc_stem = file_path.stem
            output_filename = f"{doc_stem}_chunks.json"
            output_path = output_dir / output_filename

            # Handle both dict (pipeline) and list (passthrough) return types
            chunks_count = 0
            if isinstance(result, dict):
                chunks_count = len(result.get("chunks", []))
            elif isinstance(result, list):
                chunks_count = len(result)

            self.update_task_status(task_id, TaskStatus.COMPLETED, progress=100, result={
                "doc_stem": doc_stem,
                "output_file": str(output_path),
                "chunks_count": chunks_count
            })

        except Exception as e:
            self.update_task_status(task_id, TaskStatus.FAILED, error=str(e))


# Global task manager instance
task_manager = TaskManager()
