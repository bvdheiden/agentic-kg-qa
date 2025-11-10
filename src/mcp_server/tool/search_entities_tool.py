"""Tool for performing semantic vector search for entities.

Use this tool first to find candidate entities. The returned `uri` value of a
result is the entity IRI that should feed into follow-up SPARQL queries using
`query_graph`.
"""

from typing import List
from pydantic import BaseModel, Field
from src.mcp_server.service.embedding_service import EmbeddingService
from src.mcp_server.service.qdrant_query_service import QdrantQueryService


class SearchResultItem(BaseModel):
    """Single search result item."""
    label: str
    uri: str
    type: str
    score: float


class SearchResults(BaseModel):
    """Search results container."""
    results: List[SearchResultItem] = Field(..., description="A list of search results.")


def search_entities(query: str, limit: int = 5) -> SearchResults:
    """
    Performs a semantic vector search for entities (teams, services, endpoints)
    in the knowledge base.

    Args:
        query: The natural language search query.
        limit: Maximum number of results to return (default: 5).

    Returns:
        SearchResults containing matching entities with their labels, URIs, types, and relevance scores.
    """
    print(f"Running search_entities with query: '{query}'")

    embedding_service = EmbeddingService()
    qdrant_service = QdrantQueryService()

    # 1. Generate embedding for the query
    query_vector = embedding_service.generate(query)

    # 2. Search Qdrant
    search_results = qdrant_service.search(query_vector, limit)

    # 3. Format results
    formatted_results = []
    for point in search_results:
        formatted_results.append(
            SearchResultItem(
                label=point.payload.get("label", "N/A"),
                uri=point.payload.get("uri", "N/A"),
                type=point.payload.get("type", "N/A"),
                score=point.score
            )
        )

    return SearchResults(results=formatted_results)
