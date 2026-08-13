import re
from langchain_text_splitters import RecursiveCharacterTextSplitter

_SHORT_CHUNK_MIN = 100  # chars; shorter chunks are merged into the previous one

_WARNING_HEADER_RE = re.compile(
    r"^\s*(warning|caution|note|important|tip|danger)\s*[:：]?\s*$",
    re.IGNORECASE,
)


def _build_context_prefix(section: str, doc_stem: str) -> str:
    parts = [f"Document: {doc_stem}"]
    if section:
        parts.append(f"Section: {section}")
    return "[" + " | ".join(parts) + "]\n"


def _build_rcts(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def _preliminary_type(text: str) -> str:
    s = text.strip()
    if s.startswith("#"):
        return "heading"
    if re.match(r"^[-*+]\s", s) or re.match(r"^\d+\.\s", s):
        return "list_item"
    if s.startswith("```") or (s.startswith("    ") and "\n" in s):
        return "code"
    return "text"


def _group_elements(elements: list) -> list:
    """Return [{section, elements}] grouped under the nearest preceding heading."""
    groups: list = []
    current_section = ""
    current_group: list = []

    for el in elements:
        if el.get("type") == "heading":
            if current_group:
                groups.append({"section": current_section, "elements": current_group})
            current_section = el["text"].lstrip("#").strip()
            current_group = []
        else:
            current_group.append(el)

    if current_group:
        groups.append({"section": current_section, "elements": current_group})

    return groups


def _merge_short_text_chunks(chunks: list, min_size: int = _SHORT_CHUNK_MIN) -> list:
    if not chunks:
        return chunks
    merged = [dict(chunks[0])]
    for chunk in chunks[1:]:
        if len(chunk["text"]) < min_size:
            merged[-1]["text"] = merged[-1]["text"].rstrip() + "\n\n" + chunk["text"]
        else:
            merged.append(dict(chunk))
    return merged


def _merge_warning_headers(chunks: list) -> list:
    """Prepend WARNING/CAUTION/NOTE standalone lines to the following chunk."""
    if not chunks:
        return chunks
    merged = []
    i = 0
    while i < len(chunks):
        if _WARNING_HEADER_RE.match(chunks[i]["text"]) and i + 1 < len(chunks):
            chunks[i + 1] = dict(chunks[i + 1])
            chunks[i + 1]["text"] = chunks[i]["text"].strip() + "\n" + chunks[i + 1]["text"]
            i += 1
        else:
            merged.append(chunks[i])
            i += 1
    return merged


def _simple_split(text: str, chunk_size: int, chunk_overlap: int) -> list:
    return _build_rcts(chunk_size, chunk_overlap).split_text(text)
