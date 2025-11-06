"""Tool for generating and executing a SPARQL query that explores an entity's graph neighborhood.

Given an `entity_iri`, this tool builds a SPARQL query that collects incoming and outgoing
relationships connected to the entity. It validates that the generated query is syntactically
correct using `rdflib` before executing the query against Fuseki.
"""

from typing import List, Optional, Literal

from pydantic import BaseModel, Field
from rdflib.plugins.sparql.parser import parseQuery

from src.mcp_server.config import Config
from src.mcp_server.service.fuseki_query_service import FusekiQueryService


class ReasonGraphEdge(BaseModel):
    """Single incoming or outgoing edge discovered from the starting entity."""

    direction: Literal["incoming", "outgoing"] = Field(
        ..., description="Whether the relationship is incoming to or outgoing from the entity."
    )
    predicate: str = Field(..., description="Predicate IRI connecting the entity and the related resource.")
    predicate_label: Optional[str] = Field(
        None, description="Human-readable label for the predicate, when available."
    )
    related: str = Field(..., description="IRI of the related entity discovered across the predicate.")
    related_label: Optional[str] = Field(
        None, description="Human-readable label for the related entity, when available."
    )


class ReasonGraphResult(BaseModel):
    """Result container for the reason_graph tool."""

    entity_iri: str = Field(..., description="The starting entity IRI supplied to the tool.")
    sparql: str = Field(..., description="The validated SPARQL query that was executed.")
    edges: List[ReasonGraphEdge] = Field(
        default_factory=list,
        description="Relationships connected to the entity, grouped by direction.",
    )


def _build_reason_graph_query(entity_iri: str, limit: int) -> str:
    """Compose the SPARQL query used to explore the entity's neighborhood."""
    limit_clause = f"LIMIT {int(limit)}" if limit and limit > 0 else ""

    query = f"""
    PREFIX rdfs: <{Config.RDFS}>

    SELECT DISTINCT ?direction ?predicate ?predicateLabel ?related ?relatedLabel
    WHERE {{
      BIND(<{entity_iri}> AS ?entity)

      {{
        BIND("outgoing" AS ?direction)
        ?entity ?predicate ?related .
        FILTER(isIRI(?related))
      }}
      UNION
      {{
        BIND("incoming" AS ?direction)
        ?related ?predicate ?entity .
        FILTER(isIRI(?related))
      }}

      OPTIONAL {{ ?predicate rdfs:label ?predicateLabel }}
      OPTIONAL {{ ?related rdfs:label ?relatedLabel }}
    }}
    ORDER BY ?direction ?predicate ?related
    {limit_clause}
    """
    return query


def _validate_sparql_syntax(query: str) -> None:
    """Ensure the generated SPARQL query parses successfully."""
    try:
        parseQuery(query)
    except Exception as exc:  # pragma: no cover - rdflib raises various subclasses
        raise ValueError(f"Generated SPARQL query is not valid: {exc}") from exc


def reason_graph(entity_iri: str, limit: int = 50) -> ReasonGraphResult:
    """
    Explore the knowledge graph around a starting entity by fetching connected relationships.

    Args:
        entity_iri: The starting entity IRI.
        limit: Maximum number of relationships to return (default: 50).

    Returns:
        A ReasonGraphResult containing the validated SPARQL query and discovered edges.
    """
    print(f"Running reason_graph for entity IRI: '{entity_iri}' with limit={limit}")

    sparql_query = _build_reason_graph_query(entity_iri=entity_iri, limit=limit)
    _validate_sparql_syntax(sparql_query)

    fuseki = FusekiQueryService()
    results = fuseki.query_sparql(sparql_query)
    bindings = results.get("results", {}).get("bindings", [])

    edges: List[ReasonGraphEdge] = []
    for row in bindings:
        direction = row.get("direction", {}).get("value")
        predicate = row.get("predicate", {}).get("value")
        related = row.get("related", {}).get("value")

        if not direction or not predicate or not related:
            continue

        edges.append(
            ReasonGraphEdge(
                direction=direction,
                predicate=predicate,
                predicate_label=row.get("predicateLabel", {}).get("value"),
                related=related,
                related_label=row.get("relatedLabel", {}).get("value"),
            )
        )

    return ReasonGraphResult(
        entity_iri=entity_iri,
        sparql=sparql_query.strip(),
        edges=edges,
    )

