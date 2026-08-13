"""DocumentIndexer — orchestrates all five indexer stages."""

import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.docling import DoclingInference
from core.llm import LLMInference
from core.vlm import VLMInference
from indexer.config import SERVER_TIMEOUT, CHUNK_SIZE, CHUNK_OVERLAP, VLM_TEMPERATURE
from indexer import stage1_parse, stage2_tables, stage3_vision, stage4_chunk, stage5_metadata
from indexer.chunk_utils import _build_rcts
from indexer.metadata_utils import _detect_language, _chunk_hash

_PASSTHROUGH_EXTENSIONS = {".md", ".txt"}
_PIPELINE_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".odt", ".rtf",
    ".html", ".htm", ".xlsx", ".xls", ".csv",
    ".pptx", ".ppt", ".json",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp",
}


class DocumentIndexer:
    """
    Load documents into indexable chunks.

    Usage
    -----
    indexer = DocumentIndexer()
    chunks = indexer.load("report.pdf")
    # or
    chunks = indexer.load_directory("docs/")
    """

    def __init__(self):
        self.docling = DoclingInference(timeout=SERVER_TIMEOUT)
        self.llm = LLMInference()
        self.vlm = VLMInference(temperature=VLM_TEMPERATURE)
        self.chunk_size = CHUNK_SIZE
        self.chunk_overlap = CHUNK_OVERLAP

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, path: str) -> list[dict]:
        """Return a list of chunk dicts for *path*."""
        path = str(path)
        suffix = Path(path).suffix.lower()
        if suffix in _PASSTHROUGH_EXTENSIONS:
            return self._load_passthrough(path)
        return self._load_pipeline(path)

    def load_directory(self, directory: str, recursive: bool = True) -> list[dict]:
        """Recursively load all supported documents under *directory*."""
        all_chunks: list[dict] = []
        base = Path(directory)
        pattern = "**/*" if recursive else "*"
        all_exts = _PASSTHROUGH_EXTENSIONS | _PIPELINE_EXTENSIONS
        for path in sorted(base.glob(pattern)):
            if path.is_file() and path.suffix.lower() in all_exts:
                all_chunks.extend(self.load(str(path)))
        return all_chunks

    # ------------------------------------------------------------------
    # Internal paths
    # ------------------------------------------------------------------

    def _load_passthrough(self, path: str) -> list[dict]:
        """Markdown/text: split with RCTS, no service calls."""
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        source = Path(path).name
        splitter = _build_rcts(self.chunk_size, self.chunk_overlap)
        chunks: list[dict] = []
        for idx, split in enumerate(splitter.split_text(text)):
            if not split.strip():
                continue
            chunks.append({
                "chunk_id": f"{source}_{idx:04d}",
                "source": source,
                "chunk_type": "text",
                "chunk_text_original": split,
                "chunk_text_embedded": split,
                "page_number": 0,
                "section_title": "",
                "language": _detect_language(split),
                "chunk_hash": _chunk_hash(split),
            })
        return chunks

    def _load_pipeline(self, path: str) -> list[dict]:
        """Full five-stage pipeline; stages 2 and 3 run in parallel."""
        source = Path(path).name
        doc_stem = Path(path).stem

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Stage 1
            elements, pic_info = stage1_parse.parse(path, tmp_dir, self.docling)

            # Stage 2 + 3 in parallel (both are read-only w.r.t. elements)
            with ThreadPoolExecutor(max_workers=2) as pool:
                tables_future = pool.submit(
                    stage2_tables.process_tables, elements, doc_stem, self.llm
                )
                vision_future = pool.submit(
                    stage3_vision.summarize_pictures, pic_info, self.vlm, self.llm
                )
                table_chunks = tables_future.result()
                vision_map = vision_future.result()

            # Stage 4
            text_chunks = stage4_chunk.chunk_text(
                elements, vision_map, doc_stem, self.chunk_size, self.chunk_overlap
            )

            # Stage 5
            return stage5_metadata.enrich_metadata(text_chunks, table_chunks, source)
