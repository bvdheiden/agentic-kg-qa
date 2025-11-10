import json
from pathlib import Path
from typing import Any, Dict, List

from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.tools.mcp import MCPClient, MCPAgentTool

from src.strands.llm import ollama_model

QUERY_LIMIT = 50

try:
    ONTOLOGY_TTL = (Path(__file__).resolve().parents[1] / "ontology.ttl").read_text(encoding="utf-8")
except FileNotFoundError:  # pragma: no cover
    ONTOLOGY_TTL = "Ontology file src/ontology.ttl is missing."

SYSTEM_PROMPT = f"""
You are a graph query analyst. Always ground answers in Fuseki query results.

Process:
1. Candidate entities from `search_entity_agent` are supplied in the user message. Use them to understand relevant IRIs.
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


def _filter_query_tools(tools: List[MCPAgentTool]) -> List[MCPAgentTool]:
    """Limit available MCP tools to query_graph only."""
    return [tool for tool in tools if tool.mcp_tool.name == "query_graph"]


def _summarize_candidates(candidates: List[Dict[str, Any]]) -> str:
    """Render a text summary of candidate entities for the LLM."""
    if not candidates:
        return "No candidate entities were provided. Call search_entity_agent first."

    lines = []
    for idx, item in enumerate(candidates, start=1):
        label = item.get("label", "Unknown")
        entity_type = item.get("type", "Unknown")
        uri = item.get("uri", "Unknown")
        score = item.get("score")
        score_str = f"{float(score):.3f}" if isinstance(score, (int, float)) else "n/a"
        lines.append(f"{idx}. {label} ({entity_type}) -> {uri} [score={score_str}]")
    return "\n".join(lines)


def _parse_query_payload(raw_input: str) -> Dict[str, Any]:
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


@tool
def query_graph_agent(payload: str) -> str:
    """
    Use Fuseki SELECT queries to answer a question. Expects JSON containing:
    - question: original user query
    - candidate_entities: search_entity_agent hits (optional but recommended)
    - search_summary: human-readable summary of entities
    """

    payload_dict = _parse_query_payload(payload)
    question = payload_dict.get("question", "").strip()
    if not question:
        return "Please provide a question to analyze."

    candidates = payload_dict.get("candidate_entities") or []
    search_summary = payload_dict.get("search_summary") or _summarize_candidates(candidates)

    user_message = f"""
User question: {question}

Candidate entities from semantic search (highest score first):
{search_summary}

Candidate entity JSON (first {len(candidates)} results):
{json.dumps(candidates, indent=2) if candidates else "[]"}

Use these IRIs to craft SELECT statements. Always call query_graph at least once with limit={QUERY_LIMIT} before answering.
"""

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
            available_tools = kg_mcp_server.list_tools_sync()
            query_tools = _filter_query_tools(available_tools)
            if not query_tools:
                return "The query_graph tool is unavailable. Please ensure the MCP server is running."

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
    print(
        query_graph_agent(
            json.dumps(
                {
                    "question": "Which services does the Platform team own?",
                    "candidate_entities": [],
                    "search_summary": "Platform team (Team) -> data:team/platform",
                }
            )
        )
    )
