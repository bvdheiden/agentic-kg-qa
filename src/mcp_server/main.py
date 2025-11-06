"""
MCP Server using fastmcp to expose tools for querying the ontology.

This server connects to the Fuseki and Qdrant databases populated by
the bootstrap.py script.

Tools and usage order:
1. search_entities(query): Perform semantic search. Use the returned `uri` as the entity IRI.
2. reason_graph(entity_iri): Explore incoming/outgoing relationships for the selected entity.
3. find_resource_owner(entity_iri): Given a resource IRI, find the owning team.
4. find_resources_owned_by_team(entity_iri): Given a team IRI, list owned resources.

Always run `search_entities` first to get the correct `entity_iri` for graph queries,
then call `find_resource_owner` with that value.
"""

from fastmcp import FastMCP
from src.mcp_server.tool.search_entities_tool import search_entities
from src.mcp_server.tool.find_resource_owner_tool import find_resource_owner
from src.mcp_server.tool.find_resources_owned_by_team_tool import find_resources_owned_by_team
from src.mcp_server.tool.reason_graph_tool import reason_graph

# Create the MCP server
mcp = FastMCP("Ontology Knowledge Graph Server")

# Register tools
mcp.tool(search_entities)
mcp.tool(reason_graph)
mcp.tool(find_resource_owner)
mcp.tool(find_resources_owned_by_team)


def main():
    """
    Main function to run the fastmcp server.
    """
    print("Starting MCP server...")
    print("Available tools (use in this order):")
    print("1) search_entities(query) -> results[0].uri")
    print("2) reason_graph(entity_iri=<result IRI>)")
    print("3) find_resource_owner(entity_iri=<resource IRI>)")
    print("4) find_resources_owned_by_team(entity_iri=<team IRI>)")

    # Run the server
    mcp.run()


if __name__ == "__main__":
    main()
