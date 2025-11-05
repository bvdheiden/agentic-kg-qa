"""Tool for listing resources owned by a given team.

Validates that the input IRI is typed as a subclass of `voc:Team`, then returns
resources owned by that team, including indirect ownership via containment.
"""

from typing import List
from pydantic import BaseModel, Field
from src.mcp_server.config import Config
from src.mcp_server.service.fuseki_query_service import FusekiQueryService
from src.mcp_server.service.validation_service import assert_entity_is_subtype_of


class OwnedResourceItem(BaseModel):
    label: str
    uri: str
    type: str


class OwnedResources(BaseModel):
    results: List[OwnedResourceItem] = Field(..., description="Resources owned by the team.")


def _build_team_owned_resources_query(team_iri: str, limit: int | None) -> str:
    limit_clause = f"LIMIT {int(limit)}" if limit and limit > 0 else ""
    query = f"""
    PREFIX rdfs: <{Config.RDFS}>
    PREFIX voc: <{Config.VOC}>

    SELECT DISTINCT ?resource ?label ?type
    WHERE {{
      BIND(<{team_iri}> AS ?team)

      {{
        # Direct ownership
        ?resource voc:ownedBy ?team .
      }}
      UNION
      {{
        # Indirect ownership via containment chain
        ?top voc:ownedBy ?team .
        ?resource voc:containedIn* ?top .
      }}

      ?resource a ?type ;
               rdfs:label ?label .
    }}
    {limit_clause}
    """
    return query


def find_resources_owned_by_team(entity_iri: str, limit: int = 50) -> OwnedResources:
    """
    Find resources (direct or via containment) owned by a team IRI.

    Args:
        entity_iri: IRI of the team (from search_entities.uri)
        limit: Maximum number of resources to return (default 50)

    Returns:
        OwnedResources with items containing label, uri, and type.
    """
    print(f"Running find_resources_owned_by_team for team IRI: '{entity_iri}'")

    fuseki = FusekiQueryService()

    # Validate that entity_iri is a Team (or subclass)
    assert_entity_is_subtype_of(
        fuseki=fuseki,
        entity_iri=entity_iri,
        superclass_iri=str(Config.VOC.Team),
        superclass_label="voc:Team",
    )

    sparql = _build_team_owned_resources_query(entity_iri, limit)
    data = fuseki.query_sparql(sparql)
    bindings = data.get("results", {}).get("bindings", [])

    items: List[OwnedResourceItem] = []
    for row in bindings:
        items.append(
            OwnedResourceItem(
                label=row.get("label", {}).get("value", ""),
                uri=row.get("resource", {}).get("value", ""),
                type=row.get("type", {}).get("value", ""),
            )
        )

    return OwnedResources(results=items)

