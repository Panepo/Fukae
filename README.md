# Fukae - Document Indexing Service

A comprehensive document indexing service that processes, chunks, and embeds documents for RAG (Retrieval-Augmented Generation) applications.

## Features

- **Multi-format Document Support**: Processes PDF, DOCX, XLSX, PPTX, images (PNG, JPG, JPEG, GIF, BMP, TIFF, WEBP), HTML, and more
- **Six-Stage Processing Pipeline**:
  1. Document parsing with Docling
  2. Table extraction and processing
  3. Vision processing for images and complex layouts
  4. Document chunking with configurable size and overlap
  5. Metadata extraction and language detection
  6. Vector embedding generation
- **FastAPI REST API**: Upload documents, check processing status, and retrieve chunks
- **Bearer Token Authentication**: Secure API endpoints
- **Web UI**: User-friendly interface for document upload and management
- **Asynchronous Processing**: Background task processing for document analysis

## Project Structure

```
fukae/
├── api/                    # FastAPI server and endpoints
│   ├── models.py          # Pydantic models for API responses
│   ├── server.py          # FastAPI application and routes
│   └── tasks.py           # Background task manager
├── chunks/                # Processed document chunks (JSON format)
├── core/                  # Core processing components
│   ├── docling.py         # Document parsing with Docling
│   ├── embedding.py       # Vector embedding generation
│   ├── llm.py             # Language model inference
│   ├── reranker.py        # Result reranking
│   ├── router.py          # Request routing
│   └── vlm.py             # Vision language model inference
├── docs/                  # Documentation
├── indexer/               # Document indexing pipeline
│   ├── chunk_utils.py     # Chunking utilities
│   ├── config.py          # Configuration settings
│   ├── indexer.py         # Main indexer orchestrator
│   ├── metadata_utils.py  # Metadata extraction utilities
│   ├── stage1_parse.py    # Stage 1: Document parsing
│   ├── stage2_tables.py   # Stage 2: Table processing
│   ├── stage3_vision.py   # Stage 3: Vision processing
│   ├── stage4_chunk.py    # Stage 4: Document chunking
│   ├── stage5_metadata.py # Stage 5: Metadata extraction
│   ├── stage6_embed.py    # Stage 6: Embedding generation
│   ├── table_utils.py     # Table processing utilities
│   └── vision_utils.py    # Vision processing utilities
├── scripts/               # Utility scripts
├── static/                # Static assets (CSS, JS, images)
├── templates/             # HTML templates for web UI
├── tests/                 # Test suite
├── uploads/               # Temporary upload directory
├── main.py                # Application entry point
├── pyproject.toml         # Project configuration
├── requirements.txt       # Python dependencies
└── docker-compose.yml     # Docker compose configuration
```

## Prerequisites

- Python 3.13.3
- uv package manager
- Docker and Docker Compose (for containerized deployment)

## Installation

### Local Development

1. Install [uv](https://github.com/astral-sh/uv) package manager:
   ```bash
   # Follow installation instructions at https://github.com/astral-sh/uv
   ```

2. Install project dependencies:
   ```bash
   uv pip install -r requirements.txt
   ```

3. Set up environment variables:
   Create a `.env` file in the project root with the following variables:
   ```env
   BEARER_KEY=your_secure_api_key_here
   # Add other environment variables as needed for LLM, embedding, and VLM services
   ```

### Docker Deployment

Build and run the service using Docker Compose:

```bash
docker-compose up --build
```

## Usage

### Starting the Server

Run the FastAPI server:

```bash
python main.py
```

The server will start on `http://localhost:8000`.

### API Endpoints

#### Upload Document

```bash
curl -X POST "http://localhost:8000/upload" \
  -H "Authorization: Bearer your_secure_api_key_here" \
  -F "file=@document.pdf"
```

Response:
```json
{
  "task_id": "uuid-string",
  "status": "pending",
  "message": "File upload received and processing started"
}
```

#### Check Task Status

```bash
curl -X GET "http://localhost:8000/status/{task_id}" \
  -H "Authorization: Bearer your_secure_api_key_here"
```

Response:
```json
{
  "task_id": "uuid-string",
  "status": "completed",
  "progress": 100,
  "result": {
    "doc_stem": "document_name",
    "chunks_count": 42
  }
}
```

#### Retrieve Document Chunks

```bash
curl -X GET "http://localhost:8000/chunks/{doc_stem}" \
  -H "Authorization: Bearer your_secure_api_key_here"
```

#### Download Chunks File

```bash
curl -X GET "http://localhost:8000/download/chunks/{doc_stem}_chunks.json" \
  -H "Authorization: Bearer your_secure_api_key_here" \
  -o chunks.json
```

### Web UI

Access the web interface at:
- `http://localhost:8000/upload/web`

## Configuration

The indexer can be configured through the `indexer/config.py` file:

- `SERVER_TIMEOUT`: Timeout for server operations
- `CHUNK_SIZE`: Size of document chunks
- `CHUNK_OVERLAP`: Overlap between consecutive chunks
- `VLM_TEMPERATURE`: Temperature setting for Vision Language Models

## Testing

Run the test suite:

```bash
pytest tests/
```

## Supported Document Formats

- **Documents**: PDF, DOCX, DOC, ODT, RTF
- **Spreadsheets**: XLSX, XLS, CSV
- **Presentations**: PPTX, PPT
- **Web**: HTML, HTM, JSON
- **Images**: PNG, JPG, JPEG, GIF, BMP, TIFF, WEBP
