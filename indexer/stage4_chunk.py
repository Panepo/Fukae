"""Stage 4 — Chunk: split text/picture elements into text_chunks."""

from indexer.chunk_utils import (
    _build_context_prefix,
    _build_rcts,
    _group_elements,
    _merge_short_text_chunks,
    _merge_warning_headers,
)


def chunk_text(
    elements: list,
    vision_map: dict,
    doc_stem: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list:
    """
    Convert text and picture elements into text_chunk dicts.

    Picture elements are replaced by the VLM synthesis text from vision_map.
    Table elements are skipped (handled by stage2_tables).

    Parameters
    ----------
    elements     : flat element list from stage1_parse
    vision_map   : {element_id: {synthesis, …}} from stage3_vision
    doc_stem     : document stem for context prefix
    chunk_size   : target chunk character size
    chunk_overlap: overlap between consecutive chunks

    Returns
    -------
    list of text chunk dicts (chunk_text_original, chunk_text_embedded, page, section)
    """
    splitter = _build_rcts(chunk_size, chunk_overlap)

    # Materialise picture elements as text, drop tables
    processed: list[dict] = []
    for el in elements:
        el_type = el.get("type")
        if el_type == "table":
            continue
        if el_type == "picture":
            eid = el.get("element_id", "")
            synthesis = (vision_map.get(eid) or {}).get("synthesis") or el.get("text", "")
            if synthesis:
                processed.append({
                    "type": "text",
                    "text": synthesis,
                    "page": el["page"],
                    "section": el["section"],
                })
        else:
            processed.append(el)

    text_chunks: list[dict] = []
    groups = _group_elements(processed)

    for group in groups:
        section = group["section"]
        group_els = group["elements"]
        if not group_els:
            continue

        full_text = "\n\n".join(
            el["text"] for el in group_els if el.get("text", "").strip()
        )
        if not full_text.strip():
            continue

        first_page = next((el["page"] for el in group_els if el.get("page")), 0)
        prefix = _build_context_prefix(section, doc_stem)
        raw_splits = splitter.split_text(full_text)

        raw_chunks = [
            {"text": s, "page": first_page, "section": section}
            for s in raw_splits
            if s.strip()
        ]
        raw_chunks = _merge_warning_headers(raw_chunks)
        raw_chunks = _merge_short_text_chunks(raw_chunks)

        for chunk in raw_chunks:
            text_chunks.append({
                "chunk_type": "text",
                "chunk_text_original": chunk["text"],
                "chunk_text_embedded": prefix + chunk["text"],
                "page": chunk["page"],
                "section": chunk["section"],
            })

    return text_chunks
