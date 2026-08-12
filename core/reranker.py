import os
from typing import Optional, Sequence

import httpx
from dotenv import load_dotenv
from langchain_core.callbacks.manager import Callbacks
from langchain_core.documents import Document
from langchain_core.documents.compressor import BaseDocumentCompressor

load_dotenv()


class RerankingInference(BaseDocumentCompressor):
    model_name: str = ""
    base_url: str = ""
    api_key: str = ""
    top_n: Optional[int] = None

    def __init__(self, **kwargs):
        kwargs.setdefault("model_name", os.getenv("RERANKING_MODEL", ""))
        kwargs.setdefault("base_url", os.getenv("RERANKING_BASE_URL", ""))
        kwargs.setdefault("api_key", os.getenv("RERANKING_API_KEY", ""))
        super().__init__(**kwargs)

    def rerank(self, query: str, documents: list[str], top_n: Optional[int] = None) -> list[dict]:
        """Call the reranking endpoint and return scored results."""
        url = f"{self.base_url.rstrip('/')}/rerank"
        payload: dict = {"model": self.model_name, "query": query, "documents": documents}
        effective_top_n = top_n or self.top_n
        if effective_top_n is not None:
            payload["top_n"] = effective_top_n

        with httpx.Client() as client:
            response = client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()

        return response.json()["results"]

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        """Rerank documents by relevance to the query, returning them sorted by score."""
        doc_texts = [doc.page_content for doc in documents]
        results = self.rerank(query, doc_texts)
        reranked = sorted(results, key=lambda x: x["relevance_score"], reverse=True)

        return [
            Document(
                page_content=documents[r["index"]].page_content,
                metadata={**documents[r["index"]].metadata, "relevance_score": r["relevance_score"]},
            )
            for r in reranked
        ]
