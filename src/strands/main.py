"""Knowledge Graph QA Agent

An agent specialized in answering questions about teams, services,
and endpoints using the ontology knowledge graph MCP server.

Example queries:
- Who owns the Payment Service?
- Find all endpoints in the User Service
- What services does the Platform team own?
"""

from src.strands.ownership_researcher import ownership_researcher
from strands import Agent
from src.strands.llm import ollama_model
from strands_tools import think


SUPERVISOR_AGENT_PROMPT = """
You are a Knowledge Graph QA Agent, designed to answer questions about the
organization's services, endpoints, and team ownership.

Your role is to:
1. Understand user queries about:
   - Teams and what they own
   - Services and their endpoints
   - Ownership relationships

2. Use the ownership_researcher tool to query the knowledge graph

3. Provide clear, accurate answers based on the knowledge graph data

Always confirm you understand the question before querying the knowledge graph.
"""


supervisor_agent = Agent(
    model=ollama_model,
    system_prompt=SUPERVISOR_AGENT_PROMPT,
    tools=[ownership_researcher, think],
)


def main() -> int:
    """CLI entrypoint for the Strands knowledge graph QA agent."""
    print("\nKnowledge Graph QA Agent\n")
    print("Ask questions about teams, services, and endpoints in your organization.\n")

    print("Try queries like:")
    print("- Who owns the Payment Service?")
    print("- Find services related to authentication")
    print("- What endpoints does the User Service have?")
    print("Type 'exit' to quit.")

    while True:
        try:
            user_input = input("\n> ")
            if user_input.strip().lower() == "exit":
                print("\nGoodbye!")
                return 0

            response = supervisor_agent(user_input)
            print("\nRESPONSE:\n")
            print(str(response))

        except KeyboardInterrupt:
            print("\nExecution interrupted. Exiting...")
            return 130
        except Exception as e:
            print(f"\nAn error occurred: {e}")
            print("Please try asking a different question.")


if __name__ == "__main__":
    raise SystemExit(main())
