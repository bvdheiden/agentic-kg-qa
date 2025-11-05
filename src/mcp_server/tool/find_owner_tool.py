"""Tool for finding the owning team of a specific entity."""

from typing import Optional
from pydantic import BaseModel, Field
from src.mcp_server.config import Config
from src.mcp_server.service.fuseki_query_service import FusekiQueryService


class OwnerInfo(BaseModel):
    """Owner information result."""
    entity_name: str
    owner_team_name: Optional[str] = Field(None, description="The name of the owning team.")
    owner_team_uri: Optional[str] = Field(None, description="The URI of the owning team.")


def _build_sparql_query(entity_name: str) -> str:
    """Helper to build the SPARQL query."""

    # NOTE: Using an f-string to inject the entity name into the FILTER.
    # This is generally safe for this data, but be aware of SPARQL injection
    # if entity names could contain special characters like quotes.
    entity_name_literal = f'"{entity_name}"'

    query = f"""
    PREFIX rdfs: <{Config.RDFS}>
    PREFIX voc: <{Config.VOC}>

    SELECT ?teamName ?team
    WHERE {{
      # Find the entity by its exact label
      ?entity rdfs:label {entity_name_literal} .

      {{
        # Path 1: Entity is directly owned by a team (e.g., a service)
        ?entity voc:ownedBy ?team .
      }}
      UNION
      {{
        # Path 2: Entity is contained in something that is owned
        # (e.g., an endpoint contained in a service)
        ?entity voc:containedIn ?service .
        ?service voc:ownedBy ?team .
      }}

      # Get the team's label
      ?team rdfs:label ?teamName .
    }}
    LIMIT 1
    """
    return query


def find_owner(entity_name: str) -> OwnerInfo:
    """
    Finds the owning team of a specific entity (like a service or endpoint)
    by its exact name (label).

    Args:
        entity_name: The exact name (rdfs:label) of the entity.

    Returns:
        OwnerInfo containing the entity name and optionally the owner team name and URI.
    """
    print(f"Running find_owner for entity: '{entity_name}'")

    fuseki_service = FusekiQueryService()
    sparql_query = _build_sparql_query(entity_name)
    query_results = fuseki_service.query_sparql(sparql_query)

    bindings = query_results.get("results", {}).get("bindings", [])

    if bindings:
        first_result = bindings[0]
        team_name = first_result.get("teamName", {}).get("value")
        team_uri = first_result.get("team", {}).get("value")
        return OwnerInfo(
            entity_name=entity_name,
            owner_team_name=team_name,
            owner_team_uri=team_uri
        )
    else:
        # No owner found
        return OwnerInfo(entity_name=entity_name)
