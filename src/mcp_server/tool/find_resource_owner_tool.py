"""Tool for finding the owning team of a specific resource entity.

Usage notes:
- Run `search_entities(query)` first to locate candidate entities and obtain their `uri`.
- Pass that URI as `entity_iri` to this tool to resolve ownership.
- This tool only accepts IRIs whose rdf:type is a subclass of `voc:Resource`.
  A quick type check is performed and a clear error is returned otherwise.
"""

from typing import Optional
from pydantic import BaseModel, Field
from src.mcp_server.config import Config
from src.mcp_server.service.fuseki_query_service import FusekiQueryService
from src.mcp_server.service.validation_service import assert_entity_is_subtype_of


class OwnerInfo(BaseModel):
    """Owner information result."""
    entity_iri: str
    owner_team_name: Optional[str] = Field(None, description="The name of the owning team.")
    owner_team_uri: Optional[str] = Field(None, description="The URI of the owning team.")


def _assert_entity_is_resource(fuseki: FusekiQueryService, entity_iri: str) -> None:
    """Validate entity is a Resource (or subclass) using shared validator."""
    assert_entity_is_subtype_of(
        fuseki=fuseki,
        entity_iri=entity_iri,
        superclass_iri=str(Config.VOC.Resource),
        superclass_label="voc:Resource",
    )


def _build_sparql_query(entity_iri: str) -> str:
    """Helper to build the SPARQL query using the exact entity IRI."""

    # Insert the IRI directly into the query; ensure callers pass a valid absolute IRI.
    query = f"""
    PREFIX rdfs: <{Config.RDFS}>
    PREFIX voc: <{Config.VOC}>

    SELECT ?teamName ?team
    WHERE {{
      BIND(<{entity_iri}> AS ?entity)

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


def find_resource_owner(entity_iri: str) -> OwnerInfo:
    """
    Finds the owning team of a specific resource (like a service or endpoint)
    by its exact IRI.

    Args:
        entity_iri: The exact IRI of the resource (from `search_entities.uri`).

    Returns:
        OwnerInfo containing the entity IRI and optionally the owner team name and URI.
    """
    print(f"Running find_resource_owner for entity IRI: '{entity_iri}'")

    fuseki_service = FusekiQueryService()
    # Validate the IRI refers to a Resource (or subclass)
    _assert_entity_is_resource(fuseki_service, entity_iri)
    sparql_query = _build_sparql_query(entity_iri)
    query_results = fuseki_service.query_sparql(sparql_query)

    bindings = query_results.get("results", {}).get("bindings", [])

    if bindings:
        first_result = bindings[0]
        team_name = first_result.get("teamName", {}).get("value")
        team_uri = first_result.get("team", {}).get("value")
        return OwnerInfo(
            entity_iri=entity_iri,
            owner_team_name=team_name,
            owner_team_uri=team_uri
        )
    else:
        # No owner found
        return OwnerInfo(entity_iri=entity_iri)
