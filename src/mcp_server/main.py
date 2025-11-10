"""
MCP Server using fastmcp to expose tools for querying the ontology.

This server connects to the Fuseki and Qdrant databases populated by
the bootstrap.py script.

Tools and usage order:
1. search_entities(query): Perform semantic search. Use the returned `uri` as the entity IRI.
2. query_graph(sparql_query): Run SELECT SPARQL against the ontology. Prefixes and limits are automatically applied.
"""

from fastmcp import FastMCP
from src.mcp_server.tool.search_entities_tool import search_entities
from src.mcp_server.tool.query_graph_tool import query_graph

# Create the MCP server
mcp = FastMCP("Ontology Knowledge Graph Server")

# Register tools
mcp.tool(search_entities)
mcp.tool(query_graph)


def main():
    """
    Main function to run the fastmcp server.
    """
    print("Starting MCP server...")
    print("Available tools (use in this order):")
    print("1) search_entities(query) -> results[0].uri")
    print("2) query_graph(sparql_query=\"SELECT ...\", limit=50)")

    # Run the server
    mcp.run()


if __name__ == "__main__":
    main()
