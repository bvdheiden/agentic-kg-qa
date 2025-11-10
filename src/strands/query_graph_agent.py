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
- Base every answer on tool output, citing labels rather than IRIs when possible.
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


def _format_tool_result(result: Dict[str, Any]) -> str:
    """Extract structured content from an MCP tool response."""
    structured = result.get("structuredContent")
    if structured is not None:
        if isinstance(structured, (dict, list)):
            return json.dumps(structured, indent=2)
        return str(structured)

    for block in result.get("content", []):
        if "json" in block:
            return json.dumps(block["json"], indent=2)
        if "text" in block:
            return block["text"]
    return json.dumps(result, indent=2)


def _build_bounded_query_tool(client: MCPClient):
    """Create a tool that proxies query_graph while enforcing the max limit."""

    @tool(name="query_graph")
    def query_graph_bounded(sparql_query: str, limit: int | None = None) -> str:
        effective_limit = limit if isinstance(limit, int) and limit > 0 else QUERY_LIMIT
        bounded_limit = min(effective_limit, MAX_QUERY_LIMIT)
        result = client.call_tool_sync(
            tool_use_id=str(uuid4()),
            name="query_graph",
            arguments={"sparql_query": sparql_query, "limit": bounded_limit},
        )
        return _format_tool_result(result)

    query_graph_bounded.__doc__ = (
        "Execute SELECT queries against Fuseki. Defaults to "
        f"limit={QUERY_LIMIT} and caps at limit={MAX_QUERY_LIMIT}."
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
