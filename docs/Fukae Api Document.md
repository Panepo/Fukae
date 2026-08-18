# Document Indexer API Documentation

This document provides an overview of the Document Indexer API endpoints, request/response formats, and authentication details.

## Authentication

All API endpoints (except the web UI endpoints) require Bearer token authentication. The authentication header should be provided as:

```
Authorization: Bearer <YOUR_BEARER_KEY>
```

If the authentication header is missing or the key is invalid, the API will return a `401 Unauthorized` error.

---

## API Endpoints

### 1. Upload Document for Processing

**Endpoint:** `POST /upload`

Uploads a document file for processing and indexing.

**Headers:**
```
Authorization: Bearer <YOUR_BEARER_KEY>
Content-Type: multipart/form-data
```

**Form Data:**
- `file` (file, required): The document file to upload and process.

**Response:** `UploadResponse`

**Example Response:**
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426655440000",
  "status": "pending",
  "message": "File upload received and processing started"
}
```

**Status Codes:**
- `200 OK`: Upload successful, processing started.
- `401 Unauthorized`: Missing or invalid authentication.
- `422 Unprocessable Entity`: Invalid file upload format.

---

### 2. Get Task Status

**Endpoint:** `GET /status/{task_id}`

Retrieves the current status and results of a document processing task.

**Headers:**
```
Authorization: Bearer <YOUR_BEARER_KEY>
```

**Path Parameters:**
- `task_id` (string, required): The ID of the task to check.

**Response:** `TaskStatusResponse`

**Example Response (Pending/Processing):**
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426655440000",
  "status": "processing",
  "progress": 50,
  "result": null,
  "error": null
}
```

**Example Response (Completed):**
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426655440000",
  "status": "completed",
  "progress": 100,
  "result": {
    "doc_stem": "document_name",
    "chunks_file": "document_name_chunks.json"
  },
  "error": null
}
```

**Example Response (Failed):**
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426655440000",
  "status": "failed",
  "progress": null,
  "result": null,
  "error": "Error message describing the failure"
}
```

**Status Codes:**
- `200 OK`: Status retrieved successfully.
- `401 Unauthorized`: Missing or invalid authentication.

---

### 3. Get Document Chunks

**Endpoint:** `GET /chunks/{doc_stem}`

Retrieves the processed chunks and embedding metadata for a specific document.

**Headers:**
```
Authorization: Bearer <YOUR_BEARER_KEY>
```

**Path Parameters:**
- `doc_stem` (string, required): The stem (filename without extension) of the document.

**Response:** `ChunkResponse`

**Example Response:**
```json
{
  "model": "bge-m3",
  "dimension": 1024,
  "doc_stem": "IMG_8196",
  "chunks": [
    {
      "chunk_id": "IMG_8196.jpeg_0000",
      "source": "IMG_8196.jpeg",
      "chunk_type": "text",
      "chunk_text_original": "This image features two cute, anthropomorphic characters with large eyes and leaf-like ears standing together against a snowy background with falling snowflakes. The character on the left is green and decorated with pink flowers, while the character on the right",
      "chunk_text_embedded": "[Document: IMG_8196]\nThis image features two cute, anthropomorphic characters with large eyes and leaf-like ears standing together against a snowy background with falling snowflakes. The character on the left is green and decorated with pink flowers, while the character on the right",
      "page_number": 0,
      "section_title": "",
      "language": "unknown",
      "chunk_hash": "2a6e520eedcb7665",
      "chunk_title": "Image Description: Anthropomorphic Characters",
      "chunk_tags": [
        "image",
        "characters",
        "winter",
        "nature"
      ],
      "embedding": [
        0.018299506977200508,
        0.007519653532654047,
        -0.012132196687161922,
        ...
      ]
    }
  ]
}
```

**Status Codes:**
- `200 OK`: Chunks retrieved successfully.
- `401 Unauthorized`: Missing or invalid authentication.
- `404 Not Found`: Chunks not found for the provided document stem.

---

### 4. Download Document Chunks File

**Endpoint:** `GET /download/chunks/{doc_stem}_chunks.json`

Downloads the JSON file containing the processed chunks and embedding metadata for a specific document.

**Headers:**
```
Authorization: Bearer <YOUR_BEARER_KEY>
```

**Path Parameters:**
- `doc_stem` (string, required): The stem (filename without extension) of the document.

**Response:**
- File download of type `application/json`.

**Status Codes:**
- `200 OK`: File download initiated.
- `401 Unauthorized`: Missing or invalid authentication.
- `404 Not Found`: Chunks file not found for the provided document stem.

---

## Web UI Endpoints

These endpoints are used for the web-based user interface and do not require Bearer token authentication.

### 5. Upload Web UI Page

**Endpoint:** `GET /upload/web`

Returns the HTML page for the document upload web interface.

**Response:** `HTMLResponse`

---

### 6. Upload Web UI File

**Endpoint:** `POST /upload/web`

Uploads a document file via the web interface for processing and indexing.

**Headers:**
```
Content-Type: multipart/form-data
```

**Form Data:**
- `file` (file, required): The document file to upload and process.

**Response:** `JSONResponse`

**Example Response:**
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426655440000",
  "status": "pending",
  "message": "File upload received and processing started"
}
```

**Status Codes:**
- `200 OK`: Upload successful, processing started.
- `422 Unprocessable Entity`: Invalid file upload format.

---

## Data Models

### TaskStatus Enum

Represents the status of a processing task.

- `pending`: Task is queued for processing.
- `processing`: Task is currently being processed.
- `completed`: Task has completed successfully.
- `failed`: Task has failed due to an error.

### UploadResponse

Response model for file upload endpoints.

- `task_id` (string): The unique identifier for the processing task.
- `status` (TaskStatus): The current status of the task.
- `message` (string): A message describing the upload result.

### TaskStatusResponse

Response model for task status checks.

- `task_id` (string): The unique identifier for the processing task.
- `status` (TaskStatus): The current status of the task.
- `progress` (integer, optional): The progress of the task (0-100).
- `result` (dictionary, optional): The result data if the task is completed.
- `error` (string, optional): The error message if the task failed.

### ChunkResponse

Response model for document chunks retrieval.

- `model` (string): The embedding model used for generating chunks (e.g., `bge-m3`).
- `dimension` (integer): The dimension of the embeddings generated (e.g., `1024`).
- `doc_stem` (string): The stem (filename without extension) of the document.
- `chunks` (list of dictionaries): The list of processed chunks, each containing detailed chunk metadata and embedding data.

### Chunk

Represents a single processed chunk within a document.

- `chunk_id` (string): The unique identifier for the chunk (e.g., `IMG_8196.jpeg_0000`).
- `source` (string): The source file name of the chunk.
- `chunk_type` (string): The type of the chunk (e.g., `text`, `image`, `table`).
- `chunk_text_original` (string): The original text of the chunk.
- `chunk_text_embedded` (string): The text used for embedding, possibly with document context prepended.
- `page_number` (integer): The page number where the chunk was found (0-indexed).
- `section_title` (string): The section title if available.
- `language` (string): The detected language of the chunk (e.g., `unknown`, `en`, `ja`).
- `chunk_hash` (string): A hash of the chunk text for deduplication or verification.
- `chunk_title` (string): A generated title or description for the chunk.
- `chunk_tags` (list of strings): Tags associated with the chunk for categorization (e.g., `image`, `characters`, `winter`, `nature`).
- `embedding` (list of numbers): The vector embedding of the chunk text, generated by the specified model.

---

## Indexed Document (Chunks JSON) Format

When a document is indexed by this server, it is processed and split into chunks with metadata and embeddings. The indexed document is stored as a JSON file (e.g., `IMG_8196_chunks.json`) with the following structure:

```json
{
  "model": "bge-m3",
  "dimension": 1024,
  "doc_stem": "IMG_8196",
  "chunks": [
    {
      "chunk_id": "IMG_8196.jpeg_0000",
      "source": "IMG_8196.jpeg",
      "chunk_type": "text",
      "chunk_text_original": "This image features two cute, anthropomorphic characters...",
      "chunk_text_embedded": "[Document: IMG_8196]\nThis image features two cute, anthropomorphic characters...",
      "page_number": 0,
      "section_title": "",
      "language": "unknown",
      "chunk_hash": "2a6e520eedcb7665",
      "chunk_title": "Image Description: Anthropomorphic Characters",
      "chunk_tags": [
        "image",
        "characters",
        "winter",
        "nature"
      ],
      "embedding": [
        0.018299506977200508,
        0.007519653532654047,
        ...
      ]
    }
  ]
}
```

### Top-Level Fields

- `model` (string): The embedding model used for generating the embeddings (e.g., `bge-m3`).
- `dimension` (integer): The dimension of the embeddings generated (e.g., `1024`).
- `doc_stem` (string): The stem (filename without extension) of the document.
- `chunks` (list of dictionaries): The list of processed chunks, each containing detailed chunk metadata and embedding data as described in the [Chunk](#chunk) model.
