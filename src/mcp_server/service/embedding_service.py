"""Service for generating embeddings."""

from typing import List
from litellm import embedding
from src.mcp_server.config import Config


class EmbeddingService:
    """Service for generating embeddings (mirrored from bootstrap.py)."""

    @staticmethod
    def generate(text: str) -> List[float]:
        """Generate embedding vector for text."""
        try:
            response = embedding(
                model=Config.EMBEDDING_MODEL,
                input=[text],
                api_base=Config.EMBEDDING_API_BASE
            )
            return response.data[0]['embedding']
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise
