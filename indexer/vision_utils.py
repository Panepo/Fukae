import re

# --- VLM prompt constants ---

VLM_CAPTION_PROMPT = (
    "Describe this image in one or two concise sentences. "
    "Focus on the main subject and key visible details."
)

VLM_STRUCTURED_SYSTEM_PROMPT = (
    "You are a technical document analyst. "
    "Analyze images from technical documents and provide structured, factual descriptions."
)

VLM_STRUCTURED_PROMPT = (
    "Analyze this image from a technical document. Provide:\n"
    "1. Type: [photo|diagram|chart|screenshot|table|text|other]\n"
    "2. Main subject or topic\n"
    "3. Key elements visible\n"
    "4. Any text or numeric values present\n"
    "5. Technical significance\n\n"
    "Be concise and factual."
)

VLM_SYNTHESIS_SYSTEM_PROMPT = (
    "You are a technical writer. "
    "Write clear, informative descriptions of images for document search indexing."
)

VLM_SYNTHESIS_PROMPT_TEMPLATE = (
    "Based on the analysis below, write one coherent paragraph describing the image "
    "for full-text search indexing.\n\n"
    "Caption: {caption}\n"
    "Structured analysis: {structured}\n\n"
    "Write a clear description that helps someone find this image when searching."
)

_CAPTION_PREAMBLES = [
    "the image shows",
    "this image shows",
    "the image depicts",
    "this image depicts",
    "the figure shows",
    "this figure shows",
    "the picture shows",
    "the diagram shows",
    "the chart shows",
    "the screenshot shows",
    "the image contains",
    "the image presents",
]

_VISION_TYPES = {"photo", "diagram", "chart", "screenshot", "table", "text", "other"}

_TYPE_RE = re.compile(
    r"(?:type\s*[:：]\s*)(" + "|".join(_VISION_TYPES) + r")",
    re.IGNORECASE,
)


def _classify_vision_caption(text: str) -> str:
    m = _TYPE_RE.search(text)
    return m.group(1).lower() if m else "other"


def _size_guard(text: str, max_tokens: int) -> str:
    """Truncate to ~max_tokens (4 chars ≈ 1 token), preserving word boundaries."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # back off to last space to avoid splitting a word
    last_space = truncated.rfind(" ")
    return truncated[:last_space] if last_space > 0 else truncated


def _is_ocr_echo(caption: str, ocr_text: str, threshold: float = 0.8) -> bool:
    """Return True if the caption is mostly repeating OCR text."""
    if not ocr_text or not caption:
        return False
    ocr_words = set(ocr_text.lower().split())
    cap_words = set(caption.lower().split())
    if not cap_words:
        return False
    return len(ocr_words & cap_words) / len(cap_words) >= threshold


def _dedup_ocr(caption: str, ocr_text: str) -> str:
    """Remove lines from caption that duplicate OCR text."""
    if not ocr_text:
        return caption
    ocr_lines = {ln.strip().lower() for ln in ocr_text.splitlines() if ln.strip()}
    kept = [ln for ln in caption.splitlines() if ln.strip().lower() not in ocr_lines]
    return "\n".join(kept).strip()


def _strip_preamble(text: str) -> str:
    """Remove common image-description preambles."""
    stripped = text.strip()
    lower = stripped.lower()
    for preamble in _CAPTION_PREAMBLES:
        if lower.startswith(preamble):
            rest = stripped[len(preamble):].lstrip(", ")
            return rest[:1].upper() + rest[1:] if rest else stripped
    return stripped
