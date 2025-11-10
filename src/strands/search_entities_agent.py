from typing import List

from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.tools.mcp import MCPClient, MCPAgentTool

from src.strands.llm import ollama_model

SYSTEM_PROMPT = """
You are the Entity Discovery agent for our ontology knowledge graph.

Responsibilities:
- Read the user's question and identify up to 5 concrete entity mentions (teams, services, endpoints, etc.).
- For each mention, call the `search_entities` tool to retrieve candidate IRIs.
- Use your reasoning to choose the single best matching entity per mention based on the tool output.
- Produce a final JSON object with this structure:
  {
    "question": "...",
    "entities": [
      {
        "mention": "<entity phrase from the question>",
        "result": {"label": "...", "uri": "...", "type": "...", "score": ...}
      }
    ]
  }
- If a mention has no viable match, set its "result" to null.
- If no entities are found overall, return {"question": "...", "entities": []}.

Always prefer direct tool results over your own assumptions.
"""


def _filter_search_tools(tools: List[MCPAgentTool]) -> List[MCPAgentTool]:
    """Return only the search_entities MCP tool."""
    return [tool for tool in tools if tool.mcp_tool.name == "search_entities"]


@tool
def search_entities_agent(query: str) -> str:
    """LLM-powered wrapper around the search_entities MCP tool."""

    formatted_query = query.strip()
    if not formatted_query:
        return "Please provide a non-empty query."

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
            search_tools = _filter_search_tools(available_tools)
            if not search_tools:
                return "The search_entities tool is unavailable. Please ensure the MCP server is running."

            entity_agent = Agent(
                model=ollama_model,
                system_prompt=SYSTEM_PROMPT,
                tools=search_tools,
            )

            user_message = f"""
User question: {formatted_query}

Identify relevant entity mentions and call `search_entities` for each one.
Return the JSON schema described in your instructions.
"""
            response = str(entity_agent(user_message.strip()))

        if response:
            return response
        return "Entity discovery did not return any results."

    except Exception as exc:
        return f"search_entities_agent failed: {exc}"


if __name__ == "__main__":
    print(search_entities_agent("Which services does the Platform team own?"))
