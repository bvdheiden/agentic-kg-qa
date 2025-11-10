from typing import List

from mcp import StdioServerParameters, stdio_client
from strands import Agent
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


def create_search_entities_agent(mcp_client: MCPClient = None) -> Agent:
    """Create and return the entity search agent with MCP tools."""
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
    search_tools = _filter_search_tools(available_tools)

    return Agent(
        name="search_entities",
        model=ollama_model,
        system_prompt=SYSTEM_PROMPT,
        tools=search_tools if search_tools else [],
    )


if __name__ == "__main__":
    print(search_entities_agent("Which services does the Platform team own?"))
