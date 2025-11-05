"""Validation helpers for ontology entity IRIs.

Provides reusable assertions to ensure an entity is typed as a subclass
of a required ontology class (e.g., voc:Resource or voc:Team).
"""

from typing import List
from src.mcp_server.config import Config
from src.mcp_server.service.fuseki_query_service import FusekiQueryService


def assert_entity_is_subtype_of(
    fuseki: FusekiQueryService,
    entity_iri: str,
    superclass_iri: str,
    superclass_label: str,
) -> None:
    """Assert that entity_iri has rdf:type (?t) with ?t rdfs:subClassOf* superclass.

    Raises ValueError with a clear, agent-friendly message if the check fails,
    including any discovered rdf:types for context.
    """
    ask_query = f"""
    PREFIX rdfs: <{Config.RDFS}>

    ASK WHERE {{
      BIND(<{entity_iri}> AS ?entity)
      ?entity a ?t .
      ?t rdfs:subClassOf* <{superclass_iri}> .
    }}
    """

    try:
        ask_result = fuseki.query_sparql(ask_query)
        is_valid = bool(ask_result.get("boolean", False))
    except Exception as e:
        raise ValueError(f"Failed to validate entity type for {entity_iri}: {e}")

    if not is_valid:
        types_query = f"""
        SELECT DISTINCT ?type WHERE {{
          BIND(<{entity_iri}> AS ?entity)
          OPTIONAL {{ ?entity a ?type }}
        }}
        """
        try:
            rows = fuseki.query_sparql(types_query).get("results", {}).get("bindings", [])
            found_types: List[str] = [row.get("type", {}).get("value", "") for row in rows]
        except Exception:
            found_types = []

        details = (
            f"Entity {entity_iri} is not typed as a subclass of {superclass_label}. "
            f"Found rdf:types: {found_types or 'none'}. "
            "Use search_entities to select a correct IRI and try again."
        )
        raise ValueError(details)

