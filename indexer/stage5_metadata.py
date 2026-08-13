"""Stage 5 — Metadata: assign chunk_id, language, chunk_hash and unify all chunks."""

from indexer.metadata_utils import _detect_language, _chunk_hash


def enrich_metadata(text_chunks: list, table_chunks: list, source: str) -> list:
    """
    Add identifiers and linguistic metadata to every chunk, then return a
    unified list matching the reference.json schema.

    Text chunk schema fields:
        chunk_id, source, chunk_type, chunk_text_original, chunk_text_embedded,
        page_number, section_title, language, chunk_hash

    Additional fields for table chunks:
        chunk_text_raw, ocr_difficulty, rows, cols, table_type
    """
    result: list[dict] = []

    for idx, chunk in enumerate(text_chunks):
        original = chunk.get("chunk_text_original", chunk.get("chunk_text_embedded", ""))
        result.append({
            "chunk_id": f"{source}_{idx:04d}",
            "source": source,
            "chunk_type": chunk.get("chunk_type", "text"),
            "chunk_text_original": original,
            "chunk_text_embedded": chunk.get("chunk_text_embedded", original),
            "page_number": chunk.get("page", 0),
            "section_title": chunk.get("section", ""),
            "language": _detect_language(original),
            "chunk_hash": _chunk_hash(original),
        })

    offset = len(text_chunks)
    for idx, chunk in enumerate(table_chunks):
        raw = chunk.get("chunk_text_raw", chunk.get("chunk_text_embedded", ""))
        embedded = chunk.get("chunk_text_embedded", raw)
        result.append({
            "chunk_id": f"{source}_{offset + idx:04d}",
            "source": source,
            "chunk_type": chunk.get("chunk_type", "table"),
            "chunk_text_original": raw,
            "chunk_text_embedded": embedded,
            "chunk_text_raw": raw,
            "page_number": chunk.get("page", 0),
            "section_title": chunk.get("section", ""),
            "language": _detect_language(raw),
            "chunk_hash": _chunk_hash(raw),
            "rows": chunk.get("rows", 0),
            "cols": chunk.get("cols", 0),
            "table_type": chunk.get("table_type", "general"),
            "ocr_difficulty": chunk.get("ocr_difficulty", "low"),
        })

    return result
