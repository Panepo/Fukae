import os
import pytest
from core.embedding import EmbeddingInference


def test_embedding_initialization():
    """Test EmbeddingInference initialization with environment variables."""
    embedding = EmbeddingInference()
    assert embedding.model_name is not None or embedding.model_name == ""
    assert embedding.base_url is not None or embedding.base_url == ""
    assert embedding.api_key is not None or embedding.api_key == ""


def test_embed_query():
    """Test embedding a query text."""
    embedding = EmbeddingInference()

    # Skip test if environment variables are not set
    if not embedding.model_name or not embedding.base_url or not embedding.api_key:
        pytest.skip("Embedding environment variables not set")

    query = "What is the capital of France?"
    embedding_vector = embedding.embed_query(query)

    assert isinstance(embedding_vector, list)
    assert len(embedding_vector) > 0
    # Check if the embedding vector contains floats
    for value in embedding_vector:
        assert isinstance(value, float)


def test_embed_documents():
    """Test embedding a list of documents."""
    embedding = EmbeddingInference()

    # Skip test if environment variables are not set
    if not embedding.model_name or not embedding.base_url or not embedding.api_key:
        pytest.skip("Embedding environment variables not set")

    documents = [
        "The capital of France is Paris.",
        "Germany's capital is Berlin.",
        "The largest planet in our solar system is Jupiter."
    ]

    embedding_vectors = embedding.embed_documents(documents)

    assert isinstance(embedding_vectors, list)
    assert len(embedding_vectors) == len(documents)
    # Check if each embedding vector is a list of floats
    for vector in embedding_vectors:
        assert isinstance(vector, list)
        assert len(vector) > 0
        for value in vector:
            assert isinstance(value, float)
