from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.tools.mcp import MCPClient


@tool
def knowledge_graph_researcher(query: str) -> str:
    """
    Process and respond to queries about the knowledge graph (teams, services, endpoints).

    Args:
        query: The user's question about entities in the knowledge graph

    Returns:
        A helpful response addressing the user query
    """

    formatted_query = f"Analyze and respond to this question using the knowledge graph: {query}"
    response = str()

    try:
        # Connect to the local MCP server
        kg_mcp_server = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="python",
                    args=["-m", "src.mcp_server.main"]
                )
            )
        )

        with kg_mcp_server:
            tools = kg_mcp_server.list_tools_sync()

            # Create the QA agent with access to knowledge graph tools
            qa_agent = Agent(
                system_prompt="""You are a knowledge graph expert specialized in answering
                questions about teams, services, and endpoints in the organization.

                You have access to two tools:
                1. search_entities: Use this to find entities by semantic search
                2. find_owner: Use this to find which team owns a specific entity

                For each question:
                1. Determine what information you need to answer the question
                2. Use the appropriate tool(s) to query the knowledge graph
                3. Extract relevant information from the results
                4. Synthesize a clear, comprehensive answer

                Always be specific about which entities you found and their relationships.
                If you can't find information, clearly state that.
                """,
                tools=tools,
            )
            response = str(qa_agent(formatted_query))
            print("\n\n")

        if len(response) > 0:
            return response

        return "I apologize, but I couldn't properly analyze your question. Could you please rephrase or provide more context?"

    except Exception as e:
        return f"Error processing your query: {str(e)}"


if __name__ == "__main__":
    knowledge_graph_researcher("What services are owned by the Platform team?")
