"""Stage 6 — Embedding Generation: generate embedding vectors for all chunks."""

import json
import logging
import os
import sys
from pathlib import Path

from core.embedding import EmbeddingInference

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def generate_embeddings(chunks: list[dict], source: str, output_dir: Path) -> dict:
    """
    Generate L2-normalised embedding vectors for every chunk using the configured
    embedding model.

    Output schema:
    {
      "model":     "bge-m3",
      "dimension": <dimension>,
      "device":    "cpu",
      "doc_stem":  "<source_stem>",
      "chunks": [
        {
          ...all fields from stage5...,
          "embedding": [0.012, -0.034, ...]   // embedding vector
        }
      ]
    }
    """
    # Initialize embedding model
    embedding_inference = EmbeddingInference()
    model_name = embedding_inference.model_name or "bge-m3"

    # Extract document stem from source
    doc_stem = Path(source).stem

    # Prepare texts for embedding
    texts = [c.get("chunk_text_embedded", c.get("chunk_text_original", "")) for c in chunks]
    log.info(f"Embedding {len(texts)} chunks using model: {model_name}...")

    # Generate embeddings
    embeddings_list = embedding_inference.embed_documents(texts)

    # Attach embeddings to chunks
    for chunk, emb in zip(chunks, embeddings_list):
        chunk["embedding"] = emb

    # Build output structure
    out = {
        "model": model_name,
        "dimension": len(embeddings_list[0]) if embeddings_list else 0,
        "doc_stem": doc_stem,
        "chunks": chunks,
    }

    # Write output file
    out_file = output_dir / f"{doc_stem}_chunks.json"
    out_file.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(
        f"Written: {out_file}  "
        f"({len(out['chunks'])} chunks, dim={out['dimension']}, model={out['model']})"
    )

    return out
