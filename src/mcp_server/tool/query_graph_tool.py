"""Tool for validating and executing user-provided read-only SPARQL queries."""

from copy import deepcopy
import re
from typing import Any, Dict

from pydantic import BaseModel, Field
from rdflib.plugins.sparql.parser import parseQuery

from src.mcp_server.service.fuseki_query_service import FusekiQueryService

READ_OPERATIONS = ("select", "construct", "describe", "ask")
UPDATE_KEYWORDS = ("insert", "delete", "load", "clear", "create", "drop", "add", "move", "copy", "modify")
LIMIT_PATTERN = re.compile(r"\blimit\b", re.IGNORECASE)


class QueryGraphResult(BaseModel):
    """Result container for the query_graph tool."""

    sparql: str = Field(..., description="Validated SPARQL query that was executed (limit applied when needed).")
    limit: int = Field(..., description="Maximum number of bindings returned to the caller.")
    results: Dict[str, Any] = Field(
        default_factory=dict,
        description="SPARQL JSON result with bindings trimmed to the requested limit when applicable.",
    )


def _extract_first_keyword(query: str) -> str:
    """Return the first non-PREFIX/BASE keyword from the query for operation checks."""
    tokens = re.findall(r"[A-Za-z]+", query)
    for token in tokens:
        lowered = token.lower()
        if lowered in {"prefix", "base"}:
            continue
        return lowered
    return ""


def _ensure_read_only(query: str) -> None:
    """Validate the query is syntactically correct and read-only."""
    try:
        parseQuery(query)
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"SPARQL query is not valid: {exc}") from exc

    first_keyword = _extract_first_keyword(query)
    if first_keyword not in READ_OPERATIONS:
        raise ValueError("Only read-only SPARQL queries (SELECT, CONSTRUCT, DESCRIBE, ASK) are permitted.")

    lowered = query.lower()
    if any(re.search(rf"\\b{keyword}\\b", lowered) for keyword in UPDATE_KEYWORDS):
        raise ValueError("SPARQL update operations are not allowed.")


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
    bindings = trimmed.get("results", {}).get("bindings")
    if isinstance(bindings, list):
        trimmed["results"]["bindings"] = bindings[:limit]
    return trimmed


def query_graph(sparql_query: str, limit: int = 50) -> QueryGraphResult:
    """
    Execute a validated, read-only SPARQL query against Fuseki.

    Args:
        sparql_query: SPARQL statement to run. Only SELECT/CONSTRUCT/DESCRIBE/ASK queries are allowed.
        limit: Maximum number of result bindings to return (default: 50). Applied when LIMIT is absent.

    Returns:
        QueryGraphResult containing the executed query and the truncated Fuseki response.
    """
    if not sparql_query or not sparql_query.strip():
        raise ValueError("SPARQL query must be a non-empty string.")

    effective_limit = limit if isinstance(limit, int) and limit > 0 else 50
    cleaned_query = sparql_query.strip()

    print(f"Running query_graph with limit={effective_limit}")
    _ensure_read_only(cleaned_query)
    executable_query = _apply_limit_clause(cleaned_query, effective_limit)

    fuseki = FusekiQueryService()
    raw_results = fuseki.query_sparql(executable_query)
    trimmed_results = _trim_bindings(raw_results, effective_limit)

    return QueryGraphResult(
        sparql=executable_query.strip(),
        limit=effective_limit,
        results=trimmed_results,
    )
