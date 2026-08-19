# Indexer Data Flow Documentation

## Overview

The `DocumentIndexer` orchestrates a six-stage pipeline for converting documents into searchable, semantically enriched chunks. The pipeline supports multiple document types (PDF, DOCX, XLSX, PPTX, CSV, JSON, images, Markdown, and plain text) and applies specialized processing based on content type.

```mermaid
graph TD
    A[Input Document] --> B{File Extension}
    B -->|.md|.txt| C[Passthrough Processing]
    B -->|.pdf|.docx|.doc|.odt|.rtf|.html|.htm| D[Stage 1: Parse via Docling]
    B -->|.xlsx|.xls| E[Stage 1: Parse Excel]
    B -->|.csv| F[Stage 1: Parse CSV]
    B -->|.pptx|.ppt| G[Stage 1: Parse PPTX]
    B -->|.json| H[Stage 1: Parse JSON]
    B -->|.png|.jpg|.jpeg|.gif|.bmp|.tiff|.webp| I[Stage 1: Parse Image]

    C --> J[Return Chunks]
    D --> K[Stage 2: Tables Processing]
    E --> K
    F --> K
    G --> K
    H --> K
    I --> K

    K --> L[Stage 3: Vision Processing]
    L --> M[Stage 4: Chunking]
    M --> N[Stage 5: Metadata Enrichment]
    N --> O[Stage 6: Embedding Generation]
    O --> P[Output: chunks/{doc_stem}_chunks.json]
```

## File Extension Routing

### Passthrough Extensions
Files with extensions `.md` and `.txt` bypass the full pipeline and undergo simple RCTS-based text splitting:
- Read file content
- Split using RCTS (Recursive Character Text Splitter)
- Detect language and compute hash for each chunk
- Return chunk list directly

### Pipeline Extensions
All other supported document types go through the full 6-stage pipeline:
- **Documents**: `.pdf`, `.docx`, `.doc`, `.odt`, `.rtf`, `.html`, `.htm`
- **Spreadsheets**: `.xlsx`, `.xls`, `.csv`
- **Presentations**: `.pptx`, `.ppt`
- **Data**: `.json`
- **Images**: `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.tiff`, `.webp`

## Pipeline Stages

### Stage 1: Parse (`stage1_parse.py`)

**Purpose**: Convert document into a flat list of structured elements and picture metadata.

**Input**: Document file path, temporary directory, DoclingInference instance

**Output**:
- `elements`: List of element dictionaries with structure:
  ```python
  {
      "type": "text" | "heading" | "table" | "picture" | "list_item" | "code" | "caption" | "footnote" | "page_footer",
      "text": str,
      "page": int,
      "section": str,
      # Additional fields based on type:
      # - table: "table_data", "rows", "cols"
      # - picture: "element_id"
  }
  ```
- `pic_info`: List of picture metadata dictionaries:
  ```python
  {
      "element_id": str,
      "image_path": str,
      "page": int,
      "section": str,
      "caption": str,
      "mime_type": str
  }
  ```

**Processing by Document Type**:

1. **Docling-supported formats** (`.pdf`, `.docx`, `.doc`, `.odt`, `.rtf`, `.html`, `.htm`):
   - Use Docling inference service to convert to Markdown and JSON
   - Parse JSON content to extract elements and picture information
   - Extract sections, headings, text blocks, tables, and images
   - Save embedded images to temporary directory

2. **Excel files** (`.xlsx`, `.xls`):
   - Parse using pandas to extract tabular data
   - Convert each sheet to table elements

3. **CSV files** (`.csv`):
   - Parse using pandas
   - Convert to table elements

4. **PowerPoint files** (`.pptx`, `.ppt`):
   - Parse using python-pptx
   - Extract text, images, and structure elements

5. **JSON files** (`.json`):
   - Parse as JSON
   - Convert to text elements

6. **Image files** (`.png`, `.jpg`, etc.):
   - Extract image metadata
   - Create picture elements with image paths

7. **Fallback - Plain text**:
   - Read as plain text
   - Create text elements

---

### Stage 2: Tables Processing (`stage2_tables.py`)

**Purpose**: Convert table elements into narrated table chunks via LLM.

**Input**:
- `elements`: List of elements from Stage 1
- `doc_stem`: Document stem name for context
- `llm`: LLMInference instance

**Output**: List of table chunk dictionaries:
```python
{
    "chunk_type": "table_faq" | "table_spec" | "table_general",
    "chunk_text_raw": str,      # Markdown representation of table
    "chunk_text_embedded": str, # LLM narration of table content
    "rows": int,
    "cols": int,
    "table_type": str,
    "page": int,
    "section": str
}
```

**Processing Strategy**:

1. **Massive Table Strategy** (Attempted first):
   - For large tables that exceed normal narration limits
   - Serialize table in chunked format suitable for embedding
   - If table qualifies, skip LLM narration and use serialized chunks

2. **Table Type Detection**:
   - `faq`: Tables with question-answer patterns
   - `spec`: Specification or comparison tables
   - `general`: All other tables

3. **LLM Narration**:
   - Generate plain prose description based on table type
   - FAQ tables: List of concise Q&A pairs
   - Spec tables: Key attributes and differences summary
   - General tables: Clear, concise paragraph about content

---

### Stage 3: Vision Processing (`stage3_vision.py`)

**Purpose**: Three-pass VLM/LLM processing of pictures to generate comprehensive descriptions.

**Input**:
- `pic_info`: List of picture metadata from Stage 1
- `vlm`: VLMInference instance
- `llm`: LLMInference instance

**Output**: `vision_map` dictionary:
```python
{
    "element_id": {
        "caption": str,       # Short description (Pass 1)
        "structured": str,    # Typed analysis (Pass 2)
        "synthesis": str      # Coherent paragraph (Pass 3)
    }
}
```

**Three-Pass Processing**:

1. **Pass 1 - Caption Generation** (VLM, temperature=0.0):
   - Generate short, factual description of the image
   - Maximum tokens: `VLM_CAPTION_MAX_TOKENS`
   - Temperature: 0.0 for deterministic output

2. **Pass 2 - Structured Analysis** (VLM, temperature=VLM_TEMPERATURE):
   - Generate typed, structured analysis of image content
   - Maximum tokens: `VLM_MAX_TOKENS`
   - Includes image type, content analysis, key elements

3. **Pass 3 - Synthesis** (LLM):
   - Combine caption and structured analysis into coherent paragraph
   - Maximum tokens: `VLM_SYNTHESIS_MAX_TOKENS`
   - Produces final synthesis text used in chunking

**Fallback Handling**:
- If image path is missing, use docling caption
- If VLM/LLM generation fails, fall back to available text or caption

---

### Stage 4: Chunking (`stage4_chunk.py`)

**Purpose**: Split text and picture elements into text chunks with context preservation.

**Input**:
- `elements`: List of elements from Stage 1 (tables excluded)
- `vision_map`: Picture synthesis map from Stage 3
- `doc_stem`: Document stem name
- `chunk_size`: Target chunk character size
- `chunk_overlap`: Overlap between consecutive chunks

**Output**: List of text chunk dictionaries:
```python
{
    "chunk_type": "text",
    "chunk_text_original": str,   # Original text without context
    "chunk_text_embedded": str,   # Text with section context prefix
    "page": int,
    "section": str
}
```

**Processing Steps**:

1. **Element Processing**:
   - Skip table elements (handled in Stage 2)
   - Replace picture elements with VLM synthesis text
   - Preserve text, heading, list_item, code, caption, footnote elements

2. **Element Grouping**:
   - Group elements by section
   - Maintain document structure and hierarchy

3. **Text Splitting**:
   - Use RCTS (Recursive Character Text Splitter)
   - Apply chunk_size and chunk_overlap parameters
   - Merge warning headers and short text chunks

4. **Context Prefix Generation**:
   - Build context prefix with section and document stem
   - Apply to `chunk_text_embedded` for better retrieval context

---

### Stage 5: Metadata Enrichment (`stage5_metadata.py`)

**Purpose**: Add identifiers, linguistic metadata, and unified schema to all chunks.

**Input**:
- `text_chunks`: List of text chunks from Stage 4
- `table_chunks`: List of table chunks from Stage 2
- `source`: Source document name
- `llm`: LLMInference instance (optional, for title/tag generation)

**Output**: Unified list of enriched chunk dictionaries:

**Text Chunk Schema**:
```python
{
    "chunk_id": str,              # Format: "{source}_{index:04d}"
    "source": str,                # Source document name
    "chunk_type": str,            # "text"
    "chunk_text_original": str,   # Original text
    "chunk_text_embedded": str,   # Text with context prefix
    "page_number": int,           # Page number
    "section_title": str,         # Section title
    "language": str,              # Detected language code
    "chunk_hash": str,            # Hash of original text
    "chunk_title": str,           # Generated or extracted title
    "chunk_tags": list[str]       # Generated or extracted tags
}
```

**Table Chunk Schema**:
```python
{
    "chunk_id": str,              # Format: "{source}_{offset+index:04d}"
    "source": str,
    "chunk_type": str,            # "table_faq" | "table_spec" | "table_general"
    "chunk_text_raw": str,        # Raw markdown table
    "chunk_text_embedded": str,   # LLM narration
    "page_number": int,
    "section_title": str,
    "language": str,
    "chunk_hash": str,
    "chunk_title": str,
    "chunk_tags": list[str],
    "rows": int,
    "cols": int,
    "table_type": str
}
```

**Metadata Enrichment Steps**:

1. **Chunk Identification**:
   - Generate unique `chunk_id` for each chunk
   - Compute `chunk_hash` using text content

2. **Language Detection**:
   - Detect language of `chunk_text_original`
   - Store language code (e.g., "en", "ja", "zh")

3. **Title and Tag Generation** (if LLM available):
   - Use LLM to generate concise title (5-10 words)
   - Generate 3-5 relevant tags/keywords
   - Fallback to heuristic extraction if LLM fails:
     - Image descriptions: Extract character/nature tags
     - Documents: Extract document/content tags
     - Tables: Extract table/data tags

---

### Stage 6: Embedding Generation (`stage6_embed.py`)

**Purpose**: Generate L2-normalised embedding vectors for all chunks using the embedding model.

**Input**:
- `chunks`: List of enriched chunks from Stage 5
- `source`: Source document name
- `output_dir`: Directory to save output (typically `chunks/`)

**Output**: Dictionary with embedding results and JSON file saved to `chunks/{doc_stem}_chunks.json`:

```python
{
    "model": str,                 # Embedding model name (e.g., "bge-m3")
    "dimension": int,             # Embedding vector dimension
    "doc_stem": str,              # Document stem name
    "chunks": [                   # List of chunks with embeddings
        {
            # ... all fields from Stage 5 ...
            "embedding": [float]  # L2-normalised embedding vector
        }
    ]
}
```

**Processing Steps**:

1. **Initialize Embedding Model**:
   - Create `EmbeddingInference` instance
   - Determine model name and dimension

2. **Prepare Texts**:
   - Extract `chunk_text_embedded` (or `chunk_text_original` as fallback)
   - Prepare list of texts for batch embedding

3. **Generate Embeddings**:
   - Use `embed_documents` method to generate vectors
   - Apply L2 normalisation

4. **Attach Embeddings**:
   - Add `embedding` field to each chunk dictionary

5. **Save Output**:
   - Write JSON file to `chunks/{doc_stem}_chunks.json`
   - Include model metadata, dimension, and all enriched chunks

---

## Parallel Processing

Stages 2 and 3 run in parallel using `ThreadPoolExecutor`:

```python
with ThreadPoolExecutor(max_workers=2) as pool:
    tables_future = pool.submit(
        stage2_tables.process_tables, elements, doc_stem, self.llm
    )
    vision_future = pool.submit(
        stage3_vision.summarize_pictures, pic_info, self.vlm, self.llm
    )
    table_chunks = tables_future.result()
    vision_map = vision_future.result()
```

**Rationale**:
- Stage 2 processes table elements (read-only with respect to elements)
- Stage 3 processes picture metadata (read-only with respect to pic_info)
- Both stages are independent and can run concurrently

---

## Data Flow Summary

```
Input Document
    │
    ├─→ Passthrough (.md, .txt) ──→ RCTS Split ──→ Language Detection ──→ Hash ──→ Chunks
    │
    └─→ Pipeline (all others)
         │
         ├─→ Stage 1: Parse ──→ elements + pic_info
         │
         ├─→ Stage 2: Tables ──→ table_chunks (parallel)
         │
         ├─→ Stage 3: Vision ──→ vision_map (parallel)
         │
         ├─→ Stage 4: Chunk ──→ text_chunks (uses vision_map synthesis)
         │
         ├─→ Stage 5: Metadata ──→ enriched_chunks (text_chunks + table_chunks)
         │
         └─→ Stage 6: Embed ──→ chunks with embeddings ──→ JSON output
```

---

## Configuration Parameters

Key configuration parameters (from `indexer/config.py`):

- `SERVER_TIMEOUT`: Timeout for Docling and other service calls
- `CHUNK_SIZE`: Target character size for text chunks
- `CHUNK_OVERLAP`: Overlap between consecutive chunks
- `VLM_TEMPERATURE`: Temperature for VLM structured analysis
- `VLM_CAPTION_MAX_TOKENS`: Maximum tokens for VLM caption generation
- `VLM_MAX_TOKENS`: Maximum tokens for VLM structured analysis
- `VLM_SYNTHESIS_MAX_TOKENS`: Maximum tokens for LLM synthesis generation

---

## Error Handling and Fallbacks

1. **Docling JSON fallback**: If JSON content is unavailable, parse Markdown text
2. **Table massive strategy**: Always attempted first before LLM narration
3. **LLM narration fallback**: Return raw markdown if LLM generation fails
4. **Vision processing fallback**: Use docling caption if image path is missing or VLM fails
5. **Title/tag generation fallback**: Heuristic extraction if LLM fails
6. **Language detection fallback**: Default to "en" if detection fails

---

## Output Format

Final output is a JSON file saved to `chunks/{doc_stem}_chunks.json` with the following structure:

```json
{
  "model": "bge-m3",
  "dimension": 1024,
  "doc_stem": "report",
  "chunks": [
    {
      "chunk_id": "report_0000",
      "source": "report.pdf",
      "chunk_type": "text",
      "chunk_text_original": "...",
      "chunk_text_embedded": "...",
      "page_number": 1,
      "section_title": "Introduction",
      "language": "en",
      "chunk_hash": "...",
      "chunk_title": "...",
      "chunk_tags": [...],
      "embedding": [0.012, -0.034, ...]
    },
    ...
  ]
}
```
