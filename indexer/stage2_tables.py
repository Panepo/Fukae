"""Stage 2 — Tables: convert table elements into table_chunks via LLM narration."""

from indexer.table_utils import (
    _serialize_massive_table_chunks,
    _table_to_markdown,
    _detect_table_type,
)

_NARRATE_SYSTEM = (
    "You are a technical document analyst. "
    "Describe tables clearly and concisely in plain prose."
)

_NARRATE_PROMPTS = {
    "faq": (
        "Summarize the following FAQ table from document '{stem}' "
        "(section: '{section}') as a list of concise Q&A pairs:\n\n{table_md}"
    ),
    "spec": (
        "Describe the following specification/comparison table from document '{stem}' "
        "(section: '{section}'). Summarize the key attributes and differences:\n\n{table_md}"
    ),
    "general": (
        "Describe the following table from document '{stem}' "
        "(section: '{section}'). Write a clear, concise paragraph about what it shows:\n\n{table_md}"
    ),
}


def process_tables(elements: list, doc_stem: str, llm) -> list:
    """
    Convert table elements into table_chunks.

    Massive strategy is always attempted first.  Non-qualifying tables fall
    through to FAQ / spec / general narration via LLM.

    Parameters
    ----------
    elements : flat element list produced by stage1_parse
    doc_stem : document stem name (for context in prompts)
    llm      : LLMInference instance

    Returns
    -------
    list of table chunk dicts (without chunk_id / language / chunk_hash —
    those are added in stage5_metadata)
    """
    table_chunks: list[dict] = []

    for el in elements:
        if el.get("type") != "table":
            continue

        # Ensure markdown text is populated on the element
        if not el.get("text"):
            el["text"] = _table_to_markdown(el)

        # --- Massive strategy (always first) ---
        massive = _serialize_massive_table_chunks(el, doc_stem)
        if massive:
            table_chunks.extend(massive)
            continue

        # --- Determine type and narrate ---
        table_type = _detect_table_type(el)
        narration = _narrate_table(el, table_type, doc_stem, llm)

        table_chunks.append({
            "chunk_type": f"table_{table_type}",
            "chunk_text_raw": el["text"],
            "chunk_text_embedded": narration,
            "rows": el.get("rows", 0),
            "cols": el.get("cols", 0),
            "table_type": table_type,
            "page": el.get("page", 0),
            "section": el.get("section", ""),
        })

    return table_chunks


def _narrate_table(table: dict, table_type: str, doc_stem: str, llm) -> str:
    table_md = table.get("text", "")
    section = table.get("section", "")
    prompt = _NARRATE_PROMPTS.get(table_type, _NARRATE_PROMPTS["general"]).format(
        stem=doc_stem, section=section, table_md=table_md
    )
    try:
        return llm.generate_response(
            messages=[{"type": "human", "content": prompt}],
            system_prompt=_NARRATE_SYSTEM,
        )
    except Exception:
        # Fallback to raw markdown when LLM is unavailable
        return table_md
