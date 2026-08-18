#!/usr/bin/env python3
"""Script to start the FastAPI Document Indexer server."""

import uvicorn
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

if __name__ == "__main__":
    print("Starting Document Indexer FastAPI server...")
    print("Server available at: http://localhost:8000")
    print("Web UI available at: http://localhost:8000/upload/web")
    print("Press CTRL+C to stop the server.")

    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
