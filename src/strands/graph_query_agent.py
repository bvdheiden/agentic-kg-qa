import json
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.tools.mcp import MCPClient, MCPAgentTool

from src.strands.llm import ollama_model

SEARCH_LIMIT = 5
QUERY_LIMIT = 50

try:
    ONTOLOGY_TTL = (Path(__file__).resolve().parents[1] / "ontology.ttl").read_text(encoding="utf-8")
except FileNotFoundError:  # pragma: no cover
    ONTOLOGY_TTL = "Ontology file src/ontology.ttl is missing."

SYSTEM_PROMPT = f"""
You are a graph query analyst. Always ground answers in Fuseki query results.

Process:
1. Candidate entities from `search_entities` are supplied in the user message. Use them to understand relevant IRIs.
2. You MUST call `query_graph` (a SELECT-only SPARQL executor) at least once before answering.
3. When calling `query_graph`, provide a SELECT statement without PREFIX/BASE or LIMIT clauses (they are injected automatically) and pass `limit={QUERY_LIMIT}` unless the user requests a smaller slice.
4. Use ontology terms from this schema when crafting queries:
{ONTOLOGY_TTL}

Guidelines:
- Construct concise SELECT statements that directly answer the question.
- Prefer IRIs from the supplied candidate list or the `data:` namespace.
- Summaries must reference human-readable labels, not raw IRIs.
- If the question cannot be answered with the available context, ask for clarification instead of guessing.
"""


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
    """Create a bullet list summary of search hits for the LLM."""
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


def _filter_query_tools(tools: List[MCPAgentTool]) -> List[MCPAgentTool]:
    """Limit available MCP tools to query_graph only."""
    return [tool for tool in tools if tool.mcp_tool.name == "query_graph"]


@tool
def graph_query_agent(query: str) -> str:
    """
    Answer questions about the knowledge graph by first locating candidate entities with search_entities,
    then executing SELECT statements via query_graph.
    """

    formatted_query = query.strip()
    if not formatted_query:
        return "Please provide a non-empty question to analyze."

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
                return "No entities matched that question. Try rephrasing with more specific names."

            available_tools = kg_mcp_server.list_tools_sync()
            query_tools = _filter_query_tools(available_tools)
            if not query_tools:
                return "The query_graph tool is unavailable. Please ensure the MCP server is running."

            search_summary = _format_search_summary(search_hits)
            user_message = f"""
User question: {formatted_query}

Candidate entities from semantic search (highest score first):
{search_summary}

Use these IRIs to craft SELECT statements. Always call query_graph at least once with limit={QUERY_LIMIT} before answering.
"""

            qa_agent = Agent(
                model=ollama_model,
                system_prompt=SYSTEM_PROMPT,
                tools=query_tools,
            )
            response = str(qa_agent(user_message.strip()))

        if response:
            return response
        return "I couldn't synthesize an answer from the query results."

    except Exception as exc:
        return f"Sorry, I couldn't complete that analysis: {exc}"


if __name__ == "__main__":
    print(graph_query_agent("Which services does the Platform team own?"))
