import json
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.tools.mcp import MCPClient, MCPAgentTool

from src.strands.llm import ollama_model

QUERY_LIMIT = 50
MAX_QUERY_LIMIT = 200
REQUIRED_RESULT_FIELDS = {"uri", "label"}
XSD_INTEGER_TYPES = {
    iri.lower()
    for iri in (
        "http://www.w3.org/2001/XMLSchema#integer",
        "http://www.w3.org/2001/XMLSchema#int",
        "http://www.w3.org/2001/XMLSchema#long",
        "http://www.w3.org/2001/XMLSchema#short",
        "http://www.w3.org/2001/XMLSchema#nonNegativeInteger",
        "http://www.w3.org/2001/XMLSchema#nonPositiveInteger",
    )
}
XSD_FLOAT_TYPES = {
    iri.lower()
    for iri in (
        "http://www.w3.org/2001/XMLSchema#decimal",
        "http://www.w3.org/2001/XMLSchema#double",
        "http://www.w3.org/2001/XMLSchema#float",
    )
}
XSD_BOOLEAN_TYPE = "http://www.w3.org/2001/XMLSchema#boolean".lower()

try:
    ONTOLOGY_TTL = (Path(__file__).resolve().parents[1] / "ontology.ttl").read_text(encoding="utf-8")
except FileNotFoundError:  # pragma: no cover
    ONTOLOGY_TTL = "Ontology file src/ontology.ttl is missing."

SYSTEM_PROMPT = f"""
You are the Graph Query agent.

Instructions:
- Always call the `query_graph` tool at least once before responding.
- Write SELECT statements without PREFIX/BASE/LIMIT clauses; the tool injects them automatically.
- Default to limit={QUERY_LIMIT} unless the user needs a different slice, but never exceed limit={MAX_QUERY_LIMIT}.
- Entity-centric queries MUST bind the primary resource to ?uri and fetch ?label via `?uri rdfs:label ?label`.
- Never return unlabeled entities; update the query so that each row provides both uri and label.
- Base every answer on tool output, citing labels rather than IRIs when possible.
- Respond with JSON that includes the executed `sparql`, the applied `limit`, and a `results` array.
- The `results` array must be a list of plain objects mirroring your SELECT variables; every object includes `uri` and `label`, with more keys when additional variables are projected.
- If the provided context is insufficient, ask for clarification instead of guessing.

Schema snapshot for reference:
{ONTOLOGY_TTL}
"""


def _filter_query_tools(tools: List[MCPAgentTool]) -> List[MCPAgentTool]:
    """Limit available MCP tools to query_graph only."""
    return [tool for tool in tools if tool.mcp_tool.name == "query_graph"]


def _parse_query_payload(raw_input: str) -> Dict[str, object]:
    """Normalize user payloads into a dict containing question and search metadata."""
    if not raw_input.strip():
        return {}

    try:
        payload = json.loads(raw_input)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    return {"question": raw_input.strip()}


def _load_json_data(payload: Any) -> Any:
    """Convert JSON text blocks into Python data structures when possible."""
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload
    return payload


def _extract_structured_payload(result: Dict[str, Any]) -> Dict[str, Any] | None:
    """Extract the QueryGraphResult payload from the MCP response."""
    if isinstance(result, dict) and {"sparql", "results"}.issubset(result.keys()):
        return result

    structured = result.get("structuredContent")
    if structured is not None:
        data = _load_json_data(structured)
        if isinstance(data, list) and len(data) == 1:
            data = data[0]
        if isinstance(data, dict):
            return data

    for block in result.get("content", []):
        if not isinstance(block, dict):
            continue
        if "json" in block:
            return block["json"]
        if "text" in block:
            data = _load_json_data(block["text"])
            if isinstance(data, dict):
                return data
    return None


def _coerce_binding_value(binding_cell: Dict[str, Any]) -> Any:
    """Attempt to coerce SPARQL binding values into native Python types."""
    value = binding_cell.get("value")
    if value is None:
        return None

    datatype = binding_cell.get("datatype")
    if not isinstance(datatype, str):
        return value

    normalized = datatype.lower()
    if normalized in XSD_INTEGER_TYPES:
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
    if normalized in XSD_FLOAT_TYPES:
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    if normalized == XSD_BOOLEAN_TYPE:
        return value.lower() == "true"
    return value


def _bindings_to_objects(raw_results: Any) -> List[Dict[str, Any]]:
    """Convert SPARQL JSON bindings into a list of flat dictionaries."""
    if not isinstance(raw_results, dict):
        return []

    results_section = raw_results.get("results")
    if isinstance(results_section, dict):
        bindings = results_section.get("bindings", [])
    else:
        bindings = raw_results.get("bindings", [])

    if not isinstance(bindings, list):
        return []

    formatted: List[Dict[str, Any]] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        row: Dict[str, Any] = {}
        for variable, cell in binding.items():
            if isinstance(cell, dict):
                row[variable] = _coerce_binding_value(cell)
            else:
                row[variable] = cell

        if not row:
            continue

        missing = REQUIRED_RESULT_FIELDS - row.keys()
        if missing:
            raise ValueError(
                "Each query result must include both 'uri' and 'label'. "
                "Update your SELECT clause to project ?uri and ?label via rdfs:label."
            )
        formatted.append(row)
    return formatted


def _format_tool_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract structured content from an MCP tool response."""
    payload = _extract_structured_payload(result) or {}
    formatted_results = _bindings_to_objects(payload.get("results", {}))
    return {
        "sparql": payload.get("sparql"),
        "limit": payload.get("limit"),
        "results": formatted_results,
    }


def _build_bounded_query_tool(client: MCPClient):
    """Create a tool that proxies query_graph while enforcing the max limit."""

    @tool(name="query_graph")
    def query_graph_bounded(sparql_query: str, limit: int | None = None) -> Dict[str, Any]:
        effective_limit = limit if isinstance(limit, int) and limit > 0 else QUERY_LIMIT
        bounded_limit = min(effective_limit, MAX_QUERY_LIMIT)
        raw_result = client.call_tool_sync(
            tool_use_id=str(uuid4()),
            name="query_graph",
            arguments={"sparql_query": sparql_query, "limit": bounded_limit},
        )
        return _format_tool_result(raw_result)

    query_graph_bounded.__doc__ = (
        "Execute SELECT queries against Fuseki. Defaults to "
        f"limit={QUERY_LIMIT} and caps at limit={MAX_QUERY_LIMIT}. "
        "Returns {'sparql': str, 'limit': int, 'results': [{...}]} where each result object always "
        "includes `uri` and `label`."
    )
    return query_graph_bounded


def create_query_graph_agent(mcp_client: MCPClient = None) -> Agent:
    """Create and return the query graph agent with MCP tools."""
    if mcp_client is None:
        mcp_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="python",
                    args=["-m", "src.mcp_server.main"],
                )
            )
        )

    # Get MCP tools from the client
    available_tools = mcp_client.list_tools_sync()
    query_tools = _filter_query_tools(available_tools)

    return Agent(
        name="query_graph",
        model=ollama_model,
        system_prompt=SYSTEM_PROMPT,
        tools=query_tools if query_tools else [],
    )


if __name__ == "__main__":
    print(
        query_graph_agent(
            json.dumps(
                {
                    "question": "Which services does the Platform team own?",
                    "search_context": {
                        "entities": [
                            {
                                "mention": "Platform team",
                                "results": [
                                    {
                                        "label": "Platform Team",
                                        "uri": "data:team/platform",
                                        "type": "Team",
                                        "score": 0.92,
                                    }
                                ],
                            }
                        ]
                    },
                }
            )
        )
    )
