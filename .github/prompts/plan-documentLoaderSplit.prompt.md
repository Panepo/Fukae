# Plan: Split DocumentLoader into `indexer/` Modules

Split the 1400-line reference into 12 focused files. All stage functions receive service clients (from `core/`) as parameters rather than doing HTTP inline. Massive table strategy becomes always-on (env flag removed). Five env vars only.

---

## Steps

### Phase 1 — Pure utility modules *(parallel, no dependencies)*

1. **`indexer/config.py`** — two sections of module-level constants:
   - *From env* (5 vars): `SERVER_TIMEOUT` (180), `CHUNK_SIZE` (1024), `CHUNK_OVERLAP` (128), `VLM_TEMPERATURE` (0.1), `VLM_MAX_TOKENS` (8192)
   - *Code-only* (not in `.env`): `VLM_CAPTION_MAX_TOKENS=80`, `VLM_SYNTHESIS_MAX_TOKENS=1200`, `MASSIVE_METRICS_PER_CHUNK=40`, `MASSIVE_COMPARISON_WINDOW=4`, `MASSIVE_COMPARISON_OVERLAP=1`, `MASSIVE_COMPARISON_MAX_METRICS=36`

2. **`indexer/metadata_utils.py`** — extract `_detect_language` (langdetect + remap) and `_chunk_hash` (sha256) from reference

3. **`indexer/vision_utils.py`** — all VLM prompt constants + pure helpers: `_classify_vision_caption`, `_size_guard`, `_is_ocr_echo`, `_dedup_ocr`, `_strip_preamble`

4. **`indexer/chunk_utils.py`** — pure chunking helpers: `_build_context_prefix`, `_build_rcts`, `_preliminary_type`, `_group_elements`, `_merge_short_text_chunks`, `_merge_warning_headers`, `_simple_split`

5. **`indexer/table_utils.py`** — all pure table helpers including `_serialize_massive_table_chunks` (reads defaults from `config`) and `_is_massive_table_model`

### Phase 2 — Minimal `core/` modifications *(parallel)*

6. **`core/docling.py`** — two changes:
   - add `timeout: float` to `__init__` defaulting to `SERVER_TIMEOUT` env var; pass to every `httpx.Client(timeout=self.timeout)`
   - add `convert_file(path, to_formats, **options)` method: opens file in binary mode, posts multipart to `/v1/convert/file`, returns `md_content` str or `json_content` dict based on format

7. **`core/llm.py`** and **`core/vlm.py`** — add `max_tokens: int = None` param to `generate_response()`; include in `.bind()` when set

### Phase 3 — Stage modules *(depends on Phase 1+2)*

8. **`indexer/stage1_parse.py`** — `parse(path, tmp_dir, docling: DoclingInference)` → `(elements, pic_info)`; uses `docling.convert_file()` (new multipart method) replacing all `requests.post`; includes excel/csv/pptx/json parsers and `_save_picture_from_json`

9. **`indexer/stage2_tables.py`** — `process_tables(elements, doc_stem, llm: LLMInference)` → `table_chunks`; **massive strategy always attempted first** (no env flag); `_serialize_massive_table_chunks` returns `[]` for non-qualifying tables → falls through to FAQ/spec/general path; narration calls `llm.generate_response()`

10. **`indexer/stage3_vision.py`** — `summarize_pictures(pic_info, vlm, llm)` → `vision_map`; Pass 1 (caption, `VLM_CAPTION_MAX_TOKENS`, temperature=0.0) + Pass 2 (structured, `VLM_MAX_TOKENS`, `VLM_TEMPERATURE`) + Pass 3 (synthesis, LLM, `VLM_SYNTHESIS_MAX_TOKENS`); all constants imported from `config`

11. **`indexer/stage4_chunk.py`** — `chunk_text(elements, vision_map, doc_stem, chunk_size, chunk_overlap)` → `text_chunks`

12. **`indexer/stage5_metadata.py`** — `enrich_metadata(text_chunks, table_chunks)` → unified list matching `reference.json` schema

### Phase 4 — Loader + exports *(depends on Phase 3)*

13. **`indexer/loader.py`** — `DocumentLoader.__init__` instantiates `DoclingInference`, `LLMInference`, `VLMInference` from `core/`; `load()` dispatches to `_load_passthrough` or `_load_pipeline`; in `_load_pipeline`, **Stage 2 and Stage 3 run in parallel** via `ThreadPoolExecutor(max_workers=2)` — both receive the same `elements` list from Stage 1, futures collected before Stage 4; `load_directory()` walks recursively

14. **`indexer/__init__.py`** — `from .loader import DocumentLoader`

---

## Relevant Files

- `core/docling.py` — add `timeout` param + `convert_file()` multipart method (step 6)
- `core/llm.py` — add `max_tokens` to `generate_response` (step 7)
- `core/vlm.py` — add `max_tokens` to `generate_response` (step 7)
- `core/__init__.py` — no changes needed
- `indexer/__init__.py` — create (step 14)
- `indexer/config.py` — create (step 1)
- `indexer/loader.py` — create (step 13)
- `indexer/stage1_parse.py` — create (step 8)
- `indexer/stage2_tables.py` — create (step 9)
- `indexer/stage3_vision.py` — create (step 10)
- `indexer/stage4_chunk.py` — create (step 11)
- `indexer/stage5_metadata.py` — create (step 12)
- `indexer/table_utils.py` — create (step 5)
- `indexer/chunk_utils.py` — create (step 4)
- `indexer/vision_utils.py` — create (step 3)
- `indexer/metadata_utils.py` — create (step 2)
- `.env` — already correct, no changes needed

---

## Verification

1. `DocumentLoader.load("some.pdf")` produces chunks with all fields from `reference.json` schema (`chunk_id`, `source`, `chunk_type`, `chunk_text_original`, `chunk_text_embedded`, `page_number`, `section_title`, `language`, `chunk_hash`; table extras: `chunk_text_raw`, `ocr_difficulty`, `rows`, `cols`, `table_type`)
2. `DocumentLoader.load("some.md")` returns passthrough text chunks (no service calls beyond docling)
3. `grep -r "ENABLE_MASSIVE_TABLE_STRATEGY" indexer/` → no results
4. Each stage module independently importable and testable with mock service clients

---

## Decisions

- `_is_massive_table_model` guard is **kept** inside `_serialize_massive_table_chunks` — "always on" removes the env flag, not the model structure check. Non-qualifying tables (< 3 entity cols, < 6 rows) fall through to FAQ/spec/general path
- `core/docling.py` gains `convert_file()` using multipart `/v1/convert/file`; stage1 uses this, not `convert_document()`
- Stage functions accept service instances as parameters (no module-level singletons) for testability
- Massive table defaults and VLM token caps live in `indexer/config.py` as Python constants — not in `.env`
- Stage 2 (tables) and Stage 3 (vision) run in parallel inside `_load_pipeline` via `ThreadPoolExecutor(max_workers=2)`

---

## Further Considerations

1. **`ThreadPoolExecutor` thread safety**: `LLMInference` and `VLMInference` use httpx under the hood (via langchain). Both are stateless per-call, so concurrent use from two threads is safe. If a future langchain version introduces a non-thread-safe transport, switch to `asyncio.gather` with async clients.
