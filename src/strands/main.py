"""
# 🔍 Knowledge Graph QA Agent

A agent specialized in answering questions about teams, services, and endpoints
using the ontology knowledge graph MCP server.

## What This Example Shows

This example demonstrates:
- Creating a QA-oriented agent
- Using a local MCP server to query a knowledge graph
- Semantic search for entities
- Finding ownership relationships

Basic query examples:
```
Who owns the Payment Service?
Find all endpoints in the User Service
What services does the Platform team own?
```
"""

from src.strands.knowledge_graph_researcher import knowledge_graph_researcher
from strands import Agent
from strands_tools import think

# Supervisor agent prompt
SUPERVISOR_AGENT_PROMPT = """
You are a Knowledge Graph QA Agent, designed to answer questions about the
organization's services, endpoints, and team ownership.

Your role is to:
1. Understand user queries about:
   - Teams and what they own
   - Services and their endpoints
   - Ownership relationships

2. Use the knowledge_graph_researcher tool to query the knowledge graph

3. Provide clear, accurate answers based on the knowledge graph data

Always confirm you understand the question before querying the knowledge graph.
"""

supervisor_agent = Agent(
    system_prompt=SUPERVISOR_AGENT_PROMPT,
    tools=[knowledge_graph_researcher, think],
)


# Example usage
if __name__ == "__main__":
    print("\n🔍 Knowledge Graph QA Agent\n")
    print("Ask questions about teams, services, and endpoints in your organization.\n\n")

    print("You can try following queries:")
    print("- Who owns the Payment Service?")
    print("- Find services related to authentication")
    print("- What endpoints does the User Service have?")
    print("Type 'exit' to quit.")

    # Interactive loop
    while True:
        try:
            user_input = input("\n> ")
            if user_input.lower() == "exit":
                print("\nGoodbye! 👋")
                break

            response = supervisor_agent(user_input)

            # Extract and print the response
            content = str(response)
            print(content)

        except KeyboardInterrupt:
            print("\n\nExecution interrupted. Exiting...")
            break
        except Exception as e:
            print(f"\nAn error occurred: {str(e)}")
            print("Please try asking a different question.")
