"""Stage 2 — Tables: classify table elements and convert them into table_chunks.

Algorithm ported from `.github/reference/02_table.py`:
  - ASCII box-drawing tables embedded in plain text elements are detected too.
  - Table type ('faq' | 'spec' | 'general') is classified from header
    keywords, question-mark ratio and average cell length.
  - FAQ tables are split into one chunk per Q/A row instead of narrated
    as a whole.
  - Non-FAQ tables are narrated via the LLM.
  - Every chunk gets an 'ocr_difficulty' tag (EASY/MEDIUM/HARD) based on
    row/column counts.
"""

import logging
import re
import sys
from typing import List, Optional, Tuple

from indexer.table_utils import _serialize_massive_table_chunks, _table_to_markdown

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

_NARRATE_SYSTEM = (
    "You are a technical document analyst. "
    "Describe tables clearly and concisely in plain prose."
)

_NARRATE_PROMPTS = {
    "spec": (
        "Describe the following specification/comparison table from document '{stem}' "
        "(section: '{section}'). Summarize the key attributes and differences:\n\n{table_md}"
    ),
    "general": (
        "Describe the following table from document '{stem}' "
        "(section: '{section}'). Write a clear, concise paragraph about what it shows:\n\n{table_md}"
    ),
}

_Q_HEADERS = {"q", "question", "questions", "問題"}
_A_HEADERS = {"a", "answer", "answers", "答案", "回答", "solution", "solutions", "description"}
_FAQ_HEADER_KW = ("question", "answer", "q&a", "faq", "| q |", "| a |")

_BOX_DRAWING_CHARS = "│║┌┐└┘├┤┬┴┼═╔╗╚╝╠╣╦╩╬─"
_BOX_DRAWING_HEAVY_RE = re.compile(r"[│║┌┐└┘├┤┬┴┼═╔╗╚╝╠╣╦╩╬─]{3,}")


# ---------------------------------------------------------------------------
# ASCII box-drawing detection
# ---------------------------------------------------------------------------

def _has_heavy_box_drawing(text: str) -> bool:
    """True if text has 3+ consecutive box-drawing chars OR box chars > 15% of content."""
    if _BOX_DRAWING_HEAVY_RE.search(text):
        return True
    box_chars = sum(1 for ch in text if ch in _BOX_DRAWING_CHARS)
    return len(text) > 0 and box_chars / len(text) > 0.15


# ---------------------------------------------------------------------------
# OCR difficulty estimation
# ---------------------------------------------------------------------------

def _estimate_dimensions(text: str) -> Tuple[int, int]:
    """Estimate (rows, cols) from a markdown/ASCII table text; (0, 0) if not parseable."""
    rows = 0
    max_cols = 0
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^[\|\+\-\+]+$", stripped.replace(" ", "")):
            continue
        if "|" in stripped:
            cells = [c for c in stripped.split("|") if c.strip()]
            if cells:
                rows += 1
                max_cols = max(max_cols, len(cells))
    return rows, max_cols


def _ocr_difficulty(rows: int, cols: int) -> str:
    """HARD: cols>=7 or rows>=16 | MEDIUM: cols>=4 or rows>=9 | EASY: otherwise."""
    if cols >= 7 or rows >= 16:
        return "HARD"
    if cols >= 4 or rows >= 9:
        return "MEDIUM"
    return "EASY"


# ---------------------------------------------------------------------------
# Table type classification and FAQ row parsing
# ---------------------------------------------------------------------------

def _classify_table_type(markdown_text: str, rows: int, cols: int) -> str:
    """Classify table as 'faq', 'spec', or 'general'."""
    content_lines = [
        l.strip() for l in markdown_text.splitlines()
        if "|" in l.strip()
        and not (re.match(r"^[|\-:+ ]+$", l.strip()) and "-" in l)
    ]
    if not content_lines:
        return "general"

    header = content_lines[0].lower()
    if any(kw in header for kw in _FAQ_HEADER_KW):
        return "faq"

    data_lines = content_lines[1:]
    if data_lines:
        q_ratio = sum(1 for l in data_lines if "?" in l) / len(data_lines)
        if q_ratio > 0.3:
            return "faq"

    if cols >= 3 and data_lines:
        all_cells: List[str] = []
        for l in data_lines:
            cells = [c.strip() for c in l.split("|") if c.strip()]
            all_cells.extend(cells[1:])  # skip first col (feature label)
        if all_cells:
            avg_len = sum(len(c) for c in all_cells) / len(all_cells)
            if avg_len < 30:
                return "spec"

    return "general"


def _parse_faq_rows(markdown_text: str) -> Tuple[List[str], List[List[str]]]:
    """Parse a markdown table into (headers, data_rows), handling multi-line cells."""
    headers: List[str] = []
    data_rows: List[List[str]] = []
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        is_row_start = stripped.startswith("|")
        if is_row_start and re.match(r"^[|\-:+ ]+$", stripped) and "-" in stripped:
            continue
        if is_row_start:
            cells = [c.strip() for c in stripped.split("|")]
            if cells and cells[0] == "":
                cells = cells[1:]
            if cells and cells[-1] == "":
                cells = cells[:-1]
            if not cells:
                continue
            if not headers:
                headers = cells
            else:
                while len(cells) < len(headers):
                    cells.append("")
                data_rows.append(cells[: len(headers)])
        else:
            if not data_rows:
                continue
            content = stripped.rstrip("| ").strip()
            if not content:
                continue
            row = data_rows[-1]
            for i in range(len(row) - 1, -1, -1):
                if row[i]:
                    row[i] = row[i] + "\n" + content
                    break
    return headers, data_rows


def _faq_row_to_text(headers: List[str], row: List[str]) -> str:
    """Format a FAQ table row as 'Q: ...\\nA: ...' natural language text."""
    q_idx: Optional[int] = None
    a_idx: Optional[int] = None
    for i, h in enumerate(headers):
        hl = h.lower().strip()
        if hl in _Q_HEADERS:
            q_idx = i
        elif hl in _A_HEADERS:
            a_idx = i
    if q_idx is None or a_idx is None:
        if len(headers) == 2:
            q_idx, a_idx = 0, 1
        elif len(headers) >= 3:
            q_idx, a_idx = 1, 2
        else:
            q_idx, a_idx = 0, 0
    q_text = row[q_idx].strip() if q_idx is not None and q_idx < len(row) else ""
    a_text = row[a_idx].strip() if a_idx is not None and a_idx < len(row) else ""
    if q_text and a_text:
        return f"Q: {q_text}\nA: {a_text}"
    return a_text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_tables(elements: list, doc_stem: str, llm) -> list:
    """
    Convert table elements (and ASCII box-drawing tables in text elements)
    into table_chunks.

    Massive strategy is always attempted first for docling table elements.
    Remaining tables/ASCII tables are classified as faq/spec/general; FAQ
    tables are split into one chunk per Q/A row, others are narrated via LLM.

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
    log.info(f"Processing tables for document: {doc_stem}")
    table_chunks: list[dict] = []

    for el in elements:
        el_type = el.get("type")
        is_table = el_type == "table"
        is_ascii_table = el_type in ("text", "paragraph") and _has_heavy_box_drawing(el.get("text", ""))

        if not (is_table or is_ascii_table):
            continue

        if is_table and not el.get("text"):
            el["text"] = _table_to_markdown(el)

        text = el.get("text", "")
        if not text.strip():
            continue

        if is_table:
            massive = _serialize_massive_table_chunks(el, doc_stem)
            if massive:
                for chunk in massive:
                    chunk.setdefault("ocr_difficulty", _ocr_difficulty(chunk.get("rows", 0), chunk.get("cols", 0)))
                log.info(f"Processed massive table for document: {doc_stem}")
                table_chunks.extend(massive)
                continue
            rows, cols = el.get("rows", 0), el.get("cols", 0)
        else:
            rows, cols = _estimate_dimensions(text)

        diff = _ocr_difficulty(rows, cols)
        table_type = _classify_table_type(text, rows, cols)

        if table_type == "faq":
            headers, data_rows = _parse_faq_rows(text)
            row_chunks = []
            for row in data_rows:
                row_text = _faq_row_to_text(headers, row)
                if not row_text.strip():
                    continue
                row_chunks.append({
                    "chunk_type": "table_faq",
                    "chunk_text_raw": row_text,
                    "chunk_text_embedded": row_text,
                    "rows": 1,
                    "cols": len(headers),
                    "table_type": "faq",
                    "page": el.get("page", 0),
                    "section": el.get("section", ""),
                    "ocr_difficulty": diff,
                })
            if row_chunks:
                log.info(f"Processed FAQ table ({len(row_chunks)} rows) for document: {doc_stem}")
                table_chunks.extend(row_chunks)
                continue
            # No parseable Q/A rows — fall through to general narration below
            table_type = "general"

        narration = _narrate_table(text, table_type, doc_stem, el.get("section", ""), llm)
        log.info(f"Processed table type '{table_type}' for document: {doc_stem}")

        table_chunks.append({
            "chunk_type": f"table_{table_type}",
            "chunk_text_raw": text,
            "chunk_text_embedded": narration,
            "rows": rows,
            "cols": cols,
            "table_type": table_type,
            "page": el.get("page", 0),
            "section": el.get("section", ""),
            "ocr_difficulty": diff,
        })

    return table_chunks


def _narrate_table(table_md: str, table_type: str, doc_stem: str, section: str, llm) -> str:
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
