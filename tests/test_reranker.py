import pytest
from langchain_core.documents import Document
from core.reranker import RerankingInference


def test_reranker_initialization():
    reranker = RerankingInference()
    assert reranker.model_name is not None or reranker.model_name == ""
    assert reranker.base_url is not None or reranker.base_url == ""
    assert reranker.api_key is not None or reranker.api_key == ""


def test_reranker_initialization_with_top_n():
    reranker = RerankingInference(top_n=3)
    assert reranker.top_n == 3


def test_rerank_returns_scored_results():
    reranker = RerankingInference()

    if not reranker.model_name or not reranker.base_url or not reranker.api_key:
        pytest.skip("Reranking environment variables not set")

    query = "What is the capital of France?"
    documents = [
        "The capital of France is Paris.",
        "Jupiter is the largest planet in the solar system.",
        "Paris is known for the Eiffel Tower.",
    ]

    results = reranker.rerank(query, documents)

    assert isinstance(results, list)
    assert len(results) == len(documents)
    for item in results:
        assert "index" in item
        assert "relevance_score" in item
        assert isinstance(item["relevance_score"], float)


def test_rerank_top_n():
    reranker = RerankingInference()

    if not reranker.model_name or not reranker.base_url or not reranker.api_key:
        pytest.skip("Reranking environment variables not set")

    query = "What is the capital of France?"
    documents = [
        "The capital of France is Paris.",
        "Jupiter is the largest planet in the solar system.",
        "Paris is known for the Eiffel Tower.",
        "Berlin is the capital of Germany.",
    ]

    results = reranker.rerank(query, documents, top_n=2)

    assert isinstance(results, list)
    assert len(results) == 2


def test_compress_documents_returns_documents():
    reranker = RerankingInference()

    if not reranker.model_name or not reranker.base_url or not reranker.api_key:
        pytest.skip("Reranking environment variables not set")

    query = "What is the capital of France?"
    docs = [
        Document(page_content="The capital of France is Paris.", metadata={"source": "geo"}),
        Document(page_content="Jupiter is the largest planet.", metadata={"source": "astro"}),
        Document(page_content="Paris is known for the Eiffel Tower.", metadata={"source": "travel"}),
    ]

    compressed = reranker.compress_documents(docs, query)

    assert isinstance(compressed, list)
    assert len(compressed) == len(docs)
    for doc in compressed:
        assert isinstance(doc, Document)
        assert "relevance_score" in doc.metadata
        assert isinstance(doc.metadata["relevance_score"], float)


def test_compress_documents_sorted_by_score():
    reranker = RerankingInference()

    if not reranker.model_name or not reranker.base_url or not reranker.api_key:
        pytest.skip("Reranking environment variables not set")

    query = "What is the capital of France?"
    docs = [
        Document(page_content="Jupiter is the largest planet."),
        Document(page_content="The capital of France is Paris."),
    ]

    compressed = reranker.compress_documents(docs, query)

    scores = [doc.metadata["relevance_score"] for doc in compressed]
    assert scores == sorted(scores, reverse=True)
    # The France document should rank higher
    assert "Paris" in compressed[0].page_content or "France" in compressed[0].page_content


def test_compress_documents_preserves_metadata():
    reranker = RerankingInference()

    if not reranker.model_name or not reranker.base_url or not reranker.api_key:
        pytest.skip("Reranking environment variables not set")

    query = "capital city"
    docs = [
        Document(page_content="Paris is in France.", metadata={"id": 1, "source": "wiki"}),
        Document(page_content="Berlin is in Germany.", metadata={"id": 2, "source": "wiki"}),
    ]

    compressed = reranker.compress_documents(docs, query)

    for doc in compressed:
        assert "id" in doc.metadata
        assert "source" in doc.metadata
        assert "relevance_score" in doc.metadata
