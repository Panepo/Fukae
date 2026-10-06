"""Stage 1 — Parse: convert a document into elements + pic_info using Docling."""

import os
import base64
import csv
import json
import logging
import mimetypes
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from core.mineru import MinerUError, MinerUResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# Optional heavy dependencies (graceful fallback when absent)
try:
    import pandas as pd
    _PANDAS_AVAILABLE = True
except ImportError:
    _PANDAS_AVAILABLE = False

try:
    from pptx import Presentation
    from pptx.util import Pt
    _PPTX_AVAILABLE = True
except ImportError:
    _PPTX_AVAILABLE = False

# Docling-parseable extensions handled via convert_file
_DOCLING_EXTENSIONS = {".pdf", ".docx", ".doc", ".odt", ".rtf", ".html", ".htm"}
# Extensions handled by local parsers
_EXCEL_EXTENSIONS = {".xlsx", ".xls"}
_CSV_EXTENSIONS = {".csv"}
_PPTX_EXTENSIONS = {".pptx", ".ppt"}
_JSON_EXTENSIONS = {".json"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

class ParserError(RuntimeError):
    """Raised when a document cannot be converted into usable elements."""


def parse(path: str, tmp_dir: str, docling, mineru=None) -> tuple[list[dict], list[dict]]:
    """
    Convert *path* into a flat list of elements and a list of pic_info dicts.

    Parameters
    ----------
    path     : local file path
    tmp_dir  : writable temporary directory for picture images
    docling  : DoclingInference instance (from core.docling)

    Returns
    -------
    elements : list of element dicts (type, text, page, section, …)
    pic_info : list of picture metadata dicts
    """
    log.info(f"Parsing document: {path}")
    suffix = Path(path).suffix.lower()

    if suffix == ".pdf":
        return _parse_pdf(path, tmp_dir, docling, mineru)
    if suffix in _DOCLING_EXTENSIONS:
        return _parse_via_docling(path, tmp_dir, docling)
    if suffix in _EXCEL_EXTENSIONS:
        return _parse_excel(path)
    if suffix in _CSV_EXTENSIONS:
        return _parse_csv(path)
    if suffix in _PPTX_EXTENSIONS:
        return _parse_pptx(path, tmp_dir)
    if suffix in _JSON_EXTENSIONS:
        return _parse_json(path)
    if suffix in _IMAGE_EXTENSIONS:
        return _parse_image(path, tmp_dir)
    # Fallback: treat as plain text
    return _parse_plaintext(path)


# ---------------------------------------------------------------------------
# Docling path
# ---------------------------------------------------------------------------

def _parse_pdf(path: str, tmp_dir: str, docling, mineru) -> tuple[list, list]:
    """Use Docling first, then the configured MinerU service for unusable PDFs."""
    try:
        elements, pic_info = _parse_via_docling(path, tmp_dir, docling)
        if elements:
            return elements, pic_info
        raise ParserError("Docling returned zero usable elements")
    except Exception as docling_error:
        if mineru is None or not mineru.enabled:
            raise ParserError(f"Docling PDF parsing failed: {docling_error}") from docling_error
        log.warning("Docling PDF parsing failed; trying MinerU fallback: %s", type(docling_error).__name__)
        try:
            result = mineru.parse_pdf(path)
            elements, pic_info = _parse_mineru_result(result, tmp_dir)
            if elements:
                return elements, pic_info
            raise ParserError("MinerU returned zero usable elements")
        except Exception as mineru_error:
            raise ParserError(
                f"PDF parsing failed with Docling ({type(docling_error).__name__}) and MinerU ({type(mineru_error).__name__})"
            ) from mineru_error

def _parse_via_docling(path: str, tmp_dir: str, docling) -> tuple[list, list]:
    log.info(f"Parsing via Docling: {path}")
    # Async + polling avoids docling-serve's sync-endpoint wait cap (DOCLING_SERVE_MAX_SYNC_WAIT, default 120s)
    result = docling.convert_file_with_polling(path, to_formats=["md", "json"])

    # Normalise the response envelope (docling-serve returns {"documents": [...]} or {"document": ...})
    if not isinstance(result, dict):
        raise ParserError("Docling returned a malformed response envelope")
    documents = result.get("documents", result.get("document"))
    if isinstance(documents, list):
        doc = documents[0] if documents else {}
    elif isinstance(documents, dict):
        doc = documents
    else:
        doc = result  # unexpected shape — try root directly

    json_content = doc.get("json_content") or doc.get("content", {})

    if json_content:
        return _parse_docling_json(json_content, tmp_dir)

    # Fallback: parse the markdown text when JSON is unavailable
    md_content = doc.get("md_content") or doc.get("text", "")
    return _parse_markdown_text(md_content), []


def _parse_mineru_result(result: MinerUResult, tmp_dir: str) -> tuple[list, list]:
    """Normalize MinerU structured pages into the existing Stage 1 contract."""
    if result.structured_content is not None:
        return _parse_mineru_structured_content(result.structured_content, result.zip_bytes, tmp_dir)
    if result.markdown is not None:
        return _parse_markdown_text(result.markdown), []
    raise ParserError("MinerU returned neither structured content nor markdown")


def _parse_mineru_structured_content(content: dict | list, zip_bytes: bytes | None, tmp_dir: str) -> tuple[list, list]:
    image_paths = _extract_mineru_images(zip_bytes, tmp_dir)
    elements: list[dict] = []
    pic_info: list[dict] = []
    current_section = ""

    for page_index, block in _iter_mineru_blocks(content):
        block_type = str(block.get("type", block.get("block_type", "text"))).lower()
        page = _mineru_page_number(block, page_index)
        text = _mineru_block_text(block)

        if block_type in {"title", "heading", "section_header", "header"}:
            current_section = text
            if text:
                elements.append({"type": "heading", "text": text, "page": page, "section": current_section})
        elif block_type in {"table", "table_body"}:
            table_data = _mineru_table_data(block)
            elements.append({"type": "table", "text": text, "page": page, "section": current_section,
                             "table_data": table_data, "rows": table_data["num_rows"], "cols": table_data["num_cols"]})
        elif block_type in {"image", "picture", "figure", "image_body"}:
            element_id = str(block.get("id", block.get("block_id", f"mineru_picture_{len(pic_info)}")))
            image_path = _mineru_image_path(block, image_paths)
            caption = str(block.get("caption", text))
            mime_type = mimetypes.guess_type(image_path or "")[0] or "image/png"
            pic_info.append({"element_id": element_id, "image_path": image_path, "page": page,
                             "section": current_section, "caption": caption, "mime_type": mime_type})
            elements.append({"type": "picture", "text": caption, "page": page, "section": current_section,
                             "element_id": element_id})
        elif block_type in {"list", "list_item", "list_body"}:
            if text:
                elements.append({"type": "list_item", "text": text, "page": page, "section": current_section})
        elif block_type in {"code", "code_block"}:
            if text:
                elements.append({"type": "code", "text": text, "page": page, "section": current_section})
        elif text:
            elements.append({"type": "text", "text": text, "page": page, "section": current_section})

    return elements, pic_info


def _iter_mineru_blocks(content: dict | list):
    pages = content.get("pages") if isinstance(content, dict) else content
    if not isinstance(pages, list) and isinstance(content, dict):
        pages = content.get("content") or content.get("blocks")
    if not isinstance(pages, list):
        raise ParserError("MinerU structured content has no page or block list")
    for page_index, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        blocks = page.get("blocks", page.get("content", []))
        if "type" in page and not isinstance(blocks, list):
            blocks = [page]
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if isinstance(block, dict):
                yield page_index, block


def _mineru_page_number(block: dict, page_index: int) -> int:
    value = block.get("page_no", block.get("page_number", page_index))
    try:
        return int(value) + 1
    except (TypeError, ValueError):
        return page_index + 1


def _mineru_block_text(block: dict) -> str:
    for key in ("text", "content", "markdown", "title"):
        value = block.get(key)
        if isinstance(value, str):
            return value.strip()
    return ""


def _mineru_table_data(block: dict) -> dict:
    data = block.get("table_data")
    if isinstance(data, dict) and {"num_rows", "num_cols", "table_cells"} <= set(data):
        return data
    rows = block.get("rows", block.get("table", []))
    if isinstance(rows, list) and all(isinstance(row, list) for row in rows):
        return _rows_to_table_data(rows)
    return {"num_rows": 0, "num_cols": 0, "table_cells": []}


def _extract_mineru_images(zip_bytes: bytes | None, tmp_dir: str) -> dict[str, str]:
    if not zip_bytes:
        return {}
    image_paths: dict[str, str] = {}
    try:
        with zipfile.ZipFile(__import__("io").BytesIO(zip_bytes)) as archive:
            for name in archive.namelist():
                mime_type = mimetypes.guess_type(name)[0]
                if name.endswith("/") or not (mime_type and mime_type.startswith("image/")):
                    continue
                safe_name = Path(name).name
                target = os.path.join(tmp_dir, f"mineru_{safe_name}")
                with open(target, "wb") as output:
                    output.write(archive.read(name))
                image_paths[name] = target
                image_paths[safe_name] = target
    except (OSError, zipfile.BadZipFile) as exc:
        raise ParserError("MinerU ZIP artifact is invalid") from exc
    return image_paths


def _mineru_image_path(block: dict, image_paths: dict[str, str]) -> str | None:
    for key in ("image_path", "img_path", "path"):
        value = block.get(key)
        if isinstance(value, str):
            return image_paths.get(value) or image_paths.get(Path(value).name)
    return None


def _parse_docling_json(doc_json: dict, tmp_dir: str) -> tuple[list, list]:
    """Parse a DoclingDocument JSON into elements + pic_info."""
    log.info("Parsing Docling JSON content")
    elements: list[dict] = []
    pic_info: list[dict] = []

    # Build ref → item map
    ref_map: dict[str, dict] = {}
    for key in ("texts", "tables", "pictures"):
        for item in doc_json.get(key, []):
            ref = item.get("self_ref", "")
            if ref:
                ref_map[ref] = item

    current_section = ""
    body_children = doc_json.get("body", {}).get("children", [])

    for child in body_children:
        ref = child.get("$ref", "")
        item = ref_map.get(ref)
        if item is None:
            continue

        label = item.get("label", "text")
        prov = item.get("prov") or [{}]
        page = prov[0].get("page_no", 0) if prov else 0
        text = item.get("text", "").strip()

        if label in ("section_header", "title", "page_header"):
            current_section = text
            elements.append({"type": "heading", "text": text, "page": page, "section": current_section})

        elif label == "table":
            table_data = item.get("data", {})
            elements.append({
                "type": "table",
                "text": "",
                "page": page,
                "section": current_section,
                "table_data": table_data,
                "rows": table_data.get("num_rows", 0),
                "cols": table_data.get("num_cols", 0),
            })

        elif label == "picture":
            element_id = item["self_ref"]
            caption = ""
            for ann in item.get("annotations", []):
                if ann.get("kind") == "caption":
                    caption = ann.get("text", "")
                    break
            img_path = _save_picture_from_json(item, tmp_dir, element_id)
            pic_info.append({
                "element_id": element_id,
                "image_path": img_path,
                "page": page,
                "section": current_section,
                "caption": caption,
                "mime_type": "image/png",
            })
            elements.append({
                "type": "picture",
                "text": caption,
                "page": page,
                "section": current_section,
                "element_id": element_id,
            })

        elif label in ("list_item",):
            elements.append({"type": "list_item", "text": text, "page": page, "section": current_section})

        elif label in ("code",):
            elements.append({"type": "code", "text": text, "page": page, "section": current_section})

        elif label in ("caption", "footnote", "page_footer"):
            # Append to the preceding element if sensible
            if elements and elements[-1]["type"] in ("text", "table", "picture"):
                elements[-1]["text"] = (elements[-1]["text"] + "\n" + text).strip()

        elif text:
            elements.append({"type": "text", "text": text, "page": page, "section": current_section})

    return elements, pic_info


def _save_picture_from_json(pic_item: dict, tmp_dir: str, element_id: str) -> str | None:
    """Decode and save an embedded picture; return the file path or None."""
    data = pic_item.get("data") or {}
    uri = data.get("uri", "")
    if not uri.startswith("data:"):
        return None
    try:
        header, b64data = uri.split(",", 1)
        mime = header.split(";")[0].split(":")[1]
        ext = mimetypes.guess_extension(mime) or ".png"
        safe_id = element_id.replace("/", "_").replace("#", "")
        out_path = os.path.join(tmp_dir, f"{safe_id}{ext}")
        with open(out_path, "wb") as fh:
            fh.write(base64.b64decode(b64data))
        return out_path
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Markdown fallback parser
# ---------------------------------------------------------------------------

def _parse_markdown_text(md: str) -> list[dict]:
    """Minimal markdown → elements without docling JSON."""
    import re
    elements: list[dict] = []
    current_section = ""
    for line in md.splitlines():
        stripped = line.rstrip()
        if re.match(r"^#{1,6}\s", stripped):
            current_section = stripped.lstrip("#").strip()
            elements.append({"type": "heading", "text": current_section, "page": 0, "section": current_section})
        elif stripped:
            elements.append({"type": "text", "text": stripped, "page": 0, "section": current_section})
    return elements


# ---------------------------------------------------------------------------
# Excel / CSV parsers
# ---------------------------------------------------------------------------

def _parse_excel(path: str) -> tuple[list, list]:
    if not _PANDAS_AVAILABLE:
        raise ImportError("pandas is required to parse Excel files")
    elements: list[dict] = []
    xf = pd.ExcelFile(path)
    for sheet_name in xf.sheet_names:
        df = xf.parse(sheet_name)
        table_data = _dataframe_to_table_data(df)
        elements.append({
            "type": "table",
            "text": "",
            "page": 0,
            "section": str(sheet_name),
            "table_data": table_data,
            "rows": table_data["num_rows"],
            "cols": table_data["num_cols"],
        })
    return elements, []


def _parse_csv(path: str) -> tuple[list, list]:
    rows: list[list[str]] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        for row in reader:
            rows.append(row)
    if not rows:
        return [], []
    num_rows = len(rows)
    num_cols = max(len(r) for r in rows)
    cells: list[dict] = []
    for r_idx, row in enumerate(rows):
        for c_idx, cell_text in enumerate(row):
            cells.append({
                "start_row_offset_idx": r_idx,
                "end_row_offset_idx": r_idx + 1,
                "start_col_offset_idx": c_idx,
                "end_col_offset_idx": c_idx + 1,
                "text": cell_text,
                "column_header": r_idx == 0,
                "row_header": False,
            })
    table_data = {"num_rows": num_rows, "num_cols": num_cols, "table_cells": cells}
    stem = Path(path).stem
    return [{"type": "table", "text": "", "page": 0, "section": stem,
              "table_data": table_data, "rows": num_rows, "cols": num_cols}], []


def _dataframe_to_table_data(df) -> dict:
    """Convert a pandas DataFrame to docling-style table_data."""
    rows = [list(df.columns)] + df.astype(str).values.tolist()
    num_rows = len(rows)
    num_cols = max(len(r) for r in rows) if rows else 0
    cells: list[dict] = []
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            cells.append({
                "start_row_offset_idx": r_idx,
                "end_row_offset_idx": r_idx + 1,
                "start_col_offset_idx": c_idx,
                "end_col_offset_idx": c_idx + 1,
                "text": str(val),
                "column_header": r_idx == 0,
                "row_header": False,
            })
    return {"num_rows": num_rows, "num_cols": num_cols, "table_cells": cells}


# ---------------------------------------------------------------------------
# PPTX parser
# ---------------------------------------------------------------------------

def _parse_pptx(path: str, tmp_dir: str) -> tuple[list, list]:
    if not _PPTX_AVAILABLE:
        raise ImportError("python-pptx is required to parse PPTX files")
    prs = Presentation(path)
    elements: list[dict] = []
    pic_info: list[dict] = []

    for slide_num, slide in enumerate(prs.slides, start=1):
        section = f"Slide {slide_num}"
        elements.append({"type": "heading", "text": section, "page": slide_num, "section": section})

        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        elements.append({"type": "text", "text": text, "page": slide_num, "section": section})
            if shape.has_table:
                tbl = shape.table
                rows_data = [[cell.text for cell in row.cells] for row in tbl.rows]
                table_data = _rows_to_table_data(rows_data)
                elements.append({
                    "type": "table",
                    "text": "",
                    "page": slide_num,
                    "section": section,
                    "table_data": table_data,
                    "rows": table_data["num_rows"],
                    "cols": table_data["num_cols"],
                })

    return elements, pic_info


def _rows_to_table_data(rows: list[list[str]]) -> dict:
    num_rows = len(rows)
    num_cols = max(len(r) for r in rows) if rows else 0
    cells: list[dict] = []
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            cells.append({
                "start_row_offset_idx": r_idx,
                "end_row_offset_idx": r_idx + 1,
                "start_col_offset_idx": c_idx,
                "end_col_offset_idx": c_idx + 1,
                "text": str(val),
                "column_header": r_idx == 0,
                "row_header": False,
            })
    return {"num_rows": num_rows, "num_cols": num_cols, "table_cells": cells}


# ---------------------------------------------------------------------------
# Image parser
# ---------------------------------------------------------------------------

def _parse_image(path: str, tmp_dir: str) -> tuple[list, list]:
    """Parse an image file into a picture element and pic_info."""
    # Determine mime type
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type is None:
        mime_type = "image/png"

    # Read image file
    with open(path, "rb") as fh:
        image_data = fh.read()

    # Save to tmp_dir
    safe_name = Path(path).name.replace(" ", "_").replace("/", "_").replace("#", "")
    out_path = os.path.join(tmp_dir, safe_name)
    with open(out_path, "wb") as fh:
        fh.write(image_data)

    # Create element and pic_info
    element_id = f"picture_{Path(path).stem}"

    pic_info = [{
        "element_id": element_id,
        "image_path": out_path,
        "page": 0,
        "section": "Image",
        "caption": "",
        "mime_type": mime_type,
    }]

    elements = [{
        "type": "picture",
        "text": "",
        "page": 0,
        "section": "Image",
        "element_id": element_id,
    }]

    return elements, pic_info


# ---------------------------------------------------------------------------
# JSON parser
# ---------------------------------------------------------------------------

def _parse_json(path: str) -> tuple[list, list]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    stem = Path(path).stem
    return [{"type": "text", "text": text, "page": 0, "section": stem}], []


# ---------------------------------------------------------------------------
# Plain text fallback
# ---------------------------------------------------------------------------

def _parse_plaintext(path: str) -> tuple[list, list]:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    stem = Path(path).stem
    return [{"type": "text", "text": text, "page": 0, "section": stem}], []
