import hashlib

try:
    from langdetect import detect, LangDetectException
    _LANGDETECT_AVAILABLE = True
except ImportError:
    _LANGDETECT_AVAILABLE = False

_LANG_REMAP = {
    "zh-cn": "zh",
    "zh-tw": "zh",
}


def _detect_language(text: str) -> str:
    if not _LANGDETECT_AVAILABLE or not text.strip():
        return "unknown"
    try:
        raw = detect(text[:500])
        return _LANG_REMAP.get(raw, raw)
    except Exception:
        return "unknown"


def _chunk_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
