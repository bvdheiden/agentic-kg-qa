"""Service for querying the Qdrant vector database."""

from typing import List
from qdrant_client import QdrantClient
from qdrant_client.models import ScoredPoint
from src.mcp_server.config import Config


class QdrantQueryService:
    """Service for querying the Qdrant vector database."""

    def __init__(self):
        self.client = QdrantClient(host=Config.QDRANT_HOST, port=Config.QDRANT_PORT)
        self.collection_name = Config.COLLECTION_NAME

    def search(self, vector: List[float], limit: int) -> List[ScoredPoint]:
        """Perform a vector search."""
        try:
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=limit,
                with_payload=True
            )
            return search_result
        except Exception as e:
            print(f"Error searching Qdrant: {e}")
            raise
