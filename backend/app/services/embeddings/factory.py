from app.services.embeddings.base import EmbeddingProvider
from app.services.embeddings.hash_embeddings import HashEmbeddingProvider


def get_embedding_provider() -> EmbeddingProvider:
    # API embeddings can be plugged in here later behind the same interface.
    return HashEmbeddingProvider()
