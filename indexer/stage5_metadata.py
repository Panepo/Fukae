"""Stage 5 — Metadata: assign chunk_id, language, chunk_hash and unify all chunks."""

import logging
import sys
import json

from indexer.metadata_utils import _detect_language, _chunk_hash

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def generate_title_and_tags(text: str, llm=None, max_tokens: int = 100) -> dict:
    """
    Generate a title and tags for the given text using the LLM.

    Args:
        text (str): The text to generate title and tags for
        llm: LLM instance to use for generation
        max_tokens (int, optional): Maximum tokens to generate

    Returns:
        dict: A dictionary with 'title' and 'tags' keys
    """
    if not llm:
        return _extract_title_and_tags_from_text(text)

    system_prompt = """You are an AI assistant that generates concise titles and relevant tags for document chunks.
Return a JSON object with exactly two keys: "title" (a concise, descriptive title of 5-10 words) and "tags" (an array of 3-5 relevant keywords or phrases).
Only return the JSON object, nothing else. Do not include any explanations or markdown formatting."""

    prompt = f"""Generate a title and tags for the following text:

{text[:2000]}"""  # Limit text to avoid exceeding token limits

    messages = [
        {"type": "system", "content": system_prompt},
        {"type": "human", "content": prompt}
    ]

    try:
        response = llm.generate_response(messages=messages, max_tokens=max_tokens)

        # Try to parse the response as JSON
        # Extract JSON from response if it's wrapped in markdown code blocks
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        # Find the JSON object in the response
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            json_str = response[json_start:json_end]
            result = json.loads(json_str)
            title = result.get("title", "")
            tags = result.get("tags", [])
            if not isinstance(tags, list):
                tags = []
            if title and tags:
                return {"title": title, "tags": tags}
    except Exception:
        pass

    # Fallback: extract title and tags from text
    return _extract_title_and_tags_from_text(text)


def _extract_title_and_tags_from_text(text: str) -> dict:
    """
    Extract a title and tags from text using heuristic rules when LLM fails.
    """
    # Clean up text for image descriptions
    text = text.strip()

    # Extract title from first sentence or key phrases
    title = "Document Chunk"
    if text.startswith("This image features") or text.startswith("This image shows"):
        # Extract key elements from image description
        import re
        # Look for character descriptions
        chars_match = re.search(r'(?:characters?|character).*?(?:with|and|are|is)', text[:300], re.IGNORECASE)
        if chars_match:
            title = "Image Description: Anthropomorphic Characters"
        else:
            title = "Image Description"
    elif text.startswith("This document") or text.startswith("Document:"):
        title = "Document Content"
    elif len(text.split()) > 10:
        # Use first 5-8 words as title
        words = text.split()[:8]
        title = ' '.join(words) + '...'

    # Extract tags from key terms
    tags = []
    text_lower = text.lower()

    # Image-related tags
    if "image" in text_lower or "character" in text_lower or "illustration" in text_lower:
        tags.append("image")
        if "character" in text_lower or "anthropomorphic" in text_lower:
            tags.append("characters")
        if "snow" in text_lower or "winter" in text_lower:
            tags.append("winter")
        if "flower" in text_lower or "nature" in text_lower:
            tags.append("nature")

    # Document-related tags
    elif "document" in text_lower or "page" in text_lower:
        tags.append("document")
        tags.append("text")

    # Table-related tags
    elif "table" in text_lower or "row" in text_lower or "column" in text_lower:
        tags.append("table")
        tags.append("data")

    # Add common tags from key terms
    key_terms = ["promotional", "event", "countdown", "graphic", "illustration", "artwork"]
    for term in key_terms:
        if term in text_lower and term not in tags:
            tags.append(term)
            if len(tags) >= 5:
                break

    # Ensure we have at least some tags
    if not tags:
        tags = ["document", "content"]

    # Limit tags to 5
    tags = tags[:5]

    return {"title": title, "tags": tags}


def enrich_metadata(text_chunks: list, table_chunks: list, source: str, llm=None) -> list:
    """
    Add identifiers and linguistic metadata to every chunk, then return a
    unified list matching the reference.json schema.

    Text chunk schema fields:
        chunk_id, source, chunk_type, chunk_text_original, chunk_text_embedded,
        page_number, section_title, language, chunk_hash, chunk_title, chunk_tags

    Additional fields for table chunks:
        chunk_text_raw, ocr_difficulty, rows, cols, table_type, chunk_title, chunk_tags
    """
    log.info(f"Enriching metadata for {len(text_chunks)} text chunks and {len(table_chunks)} table chunks from source: {source}")
    result: list[dict] = []

    for idx, chunk in enumerate(text_chunks):
        original = chunk.get("chunk_text_original", chunk.get("chunk_text_embedded", ""))

        # Generate title and tags using LLM if available
        chunk_title = chunk.get("section", "")  # Default to section title
        chunk_tags = []
        if llm:
            try:
                title_tags = generate_title_and_tags(original, llm, max_tokens=100)
                chunk_title = title_tags.get("title", chunk_title)
                chunk_tags = title_tags.get("tags", [])
            except Exception:
                # Fallback to section title if LLM fails
                pass

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
            "chunk_title": chunk_title,
            "chunk_tags": chunk_tags,
        })

    offset = len(text_chunks)
    for idx, chunk in enumerate(table_chunks):
        raw = chunk.get("chunk_text_raw", chunk.get("chunk_text_embedded", ""))
        embedded = chunk.get("chunk_text_embedded", raw)

        # Generate title and tags using LLM if available
        chunk_title = chunk.get("section", f"Table {offset + idx}")  # Default to section title or table identifier
        chunk_tags = ["table", "data"]
        if llm:
            try:
                title_tags = generate_title_and_tags(raw, llm, max_tokens=100)
                chunk_title = title_tags.get("title", chunk_title)
                chunk_tags = title_tags.get("tags", ["table", "data"])
            except Exception:
                # Fallback to default values if LLM fails
                pass

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
            "chunk_title": chunk_title,
            "chunk_tags": chunk_tags,
        })

    log.info(f"Completed metadata enrichment. Total unified chunks: {len(result)}")
    return result
