import json
from pathlib import Path
from typing import Dict, List

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


@tool
def query_graph_agent(payload: str) -> str:
    """
    Execute SELECT queries against Fuseki using the query_graph MCP tool.
    Payload should include:
    - question: the original user request (required)
    - search_context: JSON from search_entities_agent (optional but recommended)
    """

    payload_dict = _parse_query_payload(payload)
    question = payload_dict.get("question", "").strip()
    if not question:
        return "Please provide a question to analyze."

    search_context = payload_dict.get("search_context")
    context_block = json.dumps(search_context, indent=2) if search_context is not None else "None provided."

    user_message = f"""
User question: {question}

Search context (from search_entities_agent):
{context_block}

Use this context to craft one or more SELECT statements. Always call query_graph with limit={QUERY_LIMIT} before answering.
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
