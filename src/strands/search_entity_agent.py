import json
from typing import Any, Dict, List
from uuid import uuid4

from mcp import StdioServerParameters, stdio_client
from strands import tool
from strands.tools.mcp import MCPClient

SEARCH_LIMIT = 5


def _call_mcp_tool(client: MCPClient, name: str, arguments: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Invoke an MCP tool synchronously and surface structured JSON payloads."""
    result = client.call_tool_sync(
        tool_use_id=str(uuid4()),
        name=name,
        arguments=arguments or {},
    )
    if result.get("status") != "success":
        raise RuntimeError(f"{name} failed: {result}")
    return result


def _extract_json_payload(result: Dict[str, Any]) -> Any:
    """Return structured JSON from an MCP tool result."""
    structured = result.get("structuredContent")
    if structured is not None:
        return structured

    for block in result.get("content", []):
        if "json" in block:
            return block["json"]
        if "text" in block:
            try:
                return json.loads(block["text"])
            except json.JSONDecodeError:
                continue
    return None


def _format_search_summary(results: List[Dict[str, Any]]) -> str:
    """Create a bullet list summary of search hits for follow-up agents."""
    if not results:
        return "No semantic matches were found."

    lines = []
    for idx, item in enumerate(results[:SEARCH_LIMIT], start=1):
        label = item.get("label", "Unknown")
        entity_type = item.get("type", "Unknown")
        uri = item.get("uri", "Unknown")
        score = item.get("score")
        score_str = f"{float(score):.3f}" if isinstance(score, (int, float)) else "n/a"
        lines.append(f"{idx}. {label} ({entity_type}) -> {uri} [score={score_str}]")
    return "\n".join(lines)


@tool
def search_entity_agent(query: str) -> str:
    """
    Locate candidate entities in the ontology knowledge graph via semantic search.
    Returns structured JSON containing the user question, raw hits, and a summary.
    """

    formatted_query = query.strip()
    if not formatted_query:
        return json.dumps({"error": "Please provide a non-empty query."})

    try:
        kg_mcp_server = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="python",
                    args=["-m", "src.mcp_server.main"],
                )
            )
        )

        with kg_mcp_server:
            search_result = _call_mcp_tool(
                kg_mcp_server,
                "search_entities",
                {"query": formatted_query, "limit": SEARCH_LIMIT},
            )
            search_payload = _extract_json_payload(search_result) or {}
            search_hits = search_payload.get("results", []) if isinstance(search_payload, dict) else []

            if not search_hits:
                return json.dumps(
                    {
                        "question": formatted_query,
                        "candidate_entities": [],
                        "search_summary": "No entities matched that question. Try rephrasing with more specific names.",
                    },
                    indent=2,
                )

            payload = {
                "question": formatted_query,
                "candidate_entities": search_hits[:SEARCH_LIMIT],
                "search_summary": _format_search_summary(search_hits),
            }
            return json.dumps(payload, indent=2)

    except Exception as exc:
        return json.dumps(
            {"question": formatted_query, "error": f"search_entity_agent failed: {exc}"},
            indent=2,
        )


if __name__ == "__main__":
    print(search_entity_agent("Which services does the Platform team own?"))
