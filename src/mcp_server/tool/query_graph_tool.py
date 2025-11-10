"""Tool for validating and executing user-provided SELECT SPARQL queries."""

from copy import deepcopy
from pathlib import Path
import re
from typing import Any, Dict

from pydantic import BaseModel, Field
from rdflib.namespace import RDF, RDFS, OWL
from rdflib.plugins.sparql.parser import parseQuery

from src.mcp_server.config import Config
from src.mcp_server.service.fuseki_query_service import FusekiQueryService

LIMIT_PATTERN = re.compile(r"\blimit\b", re.IGNORECASE)
PREFIX_LINE_PATTERN = re.compile(r"(?im)^\s*(?:prefix|base)\s+[^\n]+\n?")

ONTOLOGY_TTL_PATH = Path(__file__).resolve().parents[2] / "ontology.ttl"
try:
    ONTOLOGY_TTL_CONTENT = ONTOLOGY_TTL_PATH.read_text(encoding="utf-8").strip()
except FileNotFoundError:  # pragma: no cover - should not happen in normal runs
    ONTOLOGY_TTL_CONTENT = "Ontology file src/ontology.ttl is missing."

DEFAULT_PREFIXES = [
    ("voc", str(Config.VOC)),
    ("data", str(Config.DATA)),
    ("rdf", str(RDF)),
    ("rdfs", str(RDFS)),
    ("owl", str(OWL)),
]
PREFIX_BLOCK = "\n".join(f"PREFIX {prefix}: <{iri}>" for prefix, iri in DEFAULT_PREFIXES)

QUERY_GRAPH_DESCRIPTION = f"""
Execute SELECT queries against the ontology without worrying about prefixes.

Ontology schema (loaded from src/ontology.ttl):
{ONTOLOGY_TTL_CONTENT}

Usage notes:
- Provide only SELECT statements. Skip PREFIX/BASE declarations and any global LIMIT; the tool strips namespaces and injects defaults.
- The tool prepends the following prefix block to every query before validation and execution:
{PREFIX_BLOCK}
- Because prefixes are injected automatically, you can reference classes/properties like `voc:Resource` or `data:team-alpha`
  without redefining namespace bindings.
- Queries are validated with rdflib to ensure they are read-only (SELECT) and syntactically correct.
- A LIMIT derived from the `limit` argument is appended automatically when missing, and bindings are truncated accordingly.
"""


class QueryGraphResult(BaseModel):
    """Result container for the query_graph tool."""

    sparql: str = Field(..., description="Validated SELECT SPARQL query that was executed (limit applied when needed).")
    limit: int = Field(..., description="Maximum number of bindings returned to the caller.")
    results: Dict[str, Any] = Field(
        default_factory=dict,
        description="SPARQL JSON result with bindings trimmed to the requested limit when applicable.",
    )


def _ensure_select_query(query: str) -> None:
    """Validate the query is syntactically correct and that it is a SELECT query."""
    try:
        parsed = parseQuery(query)
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"SPARQL query is not valid: {exc}") from exc

    if len(parsed) < 2:
        raise ValueError("Unable to determine SPARQL query type.")

    query_node = parsed[1]
    query_name = getattr(query_node, "name", None)
    if query_name != "SelectQuery":
        raise ValueError("Only SELECT SPARQL queries are permitted.")


def _strip_explicit_prefixes(query: str) -> str:
    """Remove any PREFIX or BASE declarations supplied by the caller."""
    return PREFIX_LINE_PATTERN.sub("", query).lstrip()


def _prepend_default_prefixes(query: str) -> str:
    """Prepend the default namespace bindings to the query."""
    return f"{PREFIX_BLOCK}\n{query.lstrip()}"


def _apply_limit_clause(query: str, limit: int) -> str:
    """Append a LIMIT clause if the caller provided a positive limit and none exists."""
    if limit > 0 and not LIMIT_PATTERN.search(query):
        sanitized = query.rstrip().rstrip(";")
        return f"{sanitized}\nLIMIT {limit}"
    return query


def _trim_bindings(results: Dict[str, Any], limit: int) -> Dict[str, Any]:
    """Return a copy of the Fuseki response with bindings trimmed to the requested limit."""
    if limit <= 0:
        return results

    trimmed = deepcopy(results)
    results_section = trimmed.get("results")
    if isinstance(results_section, dict):
        bindings = results_section.get("bindings")
        if isinstance(bindings, list):
            results_section["bindings"] = bindings[:limit]
    return trimmed


def query_graph(sparql_query: str, limit: int = 50) -> QueryGraphResult:
    if not sparql_query or not sparql_query.strip():
        raise ValueError("SPARQL query must be a non-empty string.")

    effective_limit = limit if isinstance(limit, int) and limit > 0 else 50
    cleaned_query = sparql_query.strip()
    query_body = _strip_explicit_prefixes(cleaned_query)
    query_with_prefixes = _prepend_default_prefixes(query_body)

    print(f"Running query_graph with limit={effective_limit}")
    _ensure_select_query(query_with_prefixes)
    executable_query = _apply_limit_clause(query_with_prefixes, effective_limit)

    fuseki = FusekiQueryService()
    raw_results = fuseki.query_sparql(executable_query)
    trimmed_results = _trim_bindings(raw_results, effective_limit)

    return QueryGraphResult(
        sparql=executable_query.strip(),
        limit=effective_limit,
        results=trimmed_results,
    )


query_graph.__doc__ = QUERY_GRAPH_DESCRIPTION
