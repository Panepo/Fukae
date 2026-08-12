import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

# Load environment variables
load_dotenv()


class EmbeddingInference:
    def __init__(self):
        """Initialize the embedding inference class with embedding model configuration."""
        self.model_name = os.getenv("EMBEDDING_MODEL", "")
        self.base_url = os.getenv("EMBEDDING_BASE_URL", "")
        self.api_key = os.getenv("EMBEDDING_API_KEY", "")

        # Initialize the OpenAIEmbeddings client
        self.embeddings = OpenAIEmbeddings(
            model=self.model_name,
            openai_api_base=self.base_url,
            openai_api_key=self.api_key
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of documents.

        Args:
            texts (list[str]): List of text documents to embed

        Returns:
            list[list[float]]: List of embedding vectors
        """
        return self.embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        """
        Embed a query text.

        Args:
            text (str): Query text to embed

        Returns:
            list[float]: Embedding vector for the query
        """
        return self.embeddings.embed_query(text)
