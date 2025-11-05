"""
MCP Server using fastmcp to expose tools for querying the ontology.

This server connects to the Fuseki and Qdrant databases populated by
the bootstrap.py script.

It exposes two tools:
1. search_entities: Performs semantic search for entities.
2. find_owner: Finds the owning team for a given resource.
"""

from fastmcp import FastMCP
from src.mcp_server.tool.search_entities_tool import search_entities
from src.mcp_server.tool.find_owner_tool import find_owner

# Create the MCP server
mcp = FastMCP("Ontology Knowledge Graph Server")

# Register tools
mcp.tool(search_entities)
mcp.tool(find_owner)


def main():
    """
    Main function to run the fastmcp server.
    """
    print("Starting MCP server...")
    print("Available tools:")
    print("- search_entities")
    print("- find_owner")

    # Run the server
    mcp.run()


if __name__ == "__main__":
    main()
