import base64
import logging
import os

from dotenv import load_dotenv
from mcp import StdioServerParameters, stdio_client

from strands.telemetry import StrandsTelemetry
from src.strands.query_graph_agent import create_query_graph_agent
from src.strands.search_entities_agent import create_search_entities_agent
from src.strands.reporter_agent import create_reporter_agent
from strands.multiagent import GraphBuilder
from strands.tools.mcp import MCPClient
from src.strands.llm import ollama_model


load_dotenv()

LANGFUSE_PUBLIC_KEY = os.environ["LANGFUSE_PUBLIC_KEY"]
LANGFUSE_SECRET_KEY = os.environ["LANGFUSE_SECRET_KEY"]
LANGFUSE_BASE_URL = os.environ["LANGFUSE_BASE_URL"]
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{LANGFUSE_BASE_URL}/api/public/otel"
LANGFUSE_AUTH = base64.b64encode(f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}".encode()).decode()
os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {LANGFUSE_AUTH}"


telemetry = StrandsTelemetry()
telemetry.setup_otlp_exporter()
telemetry.setup_meter(enable_otlp_exporter=True)

# Enable debug logs for multiagent
logging.getLogger("strands.multiagent").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

# Create shared MCP client
kg_mcp_client = MCPClient(
    lambda: stdio_client(
        StdioServerParameters(
            command="python",
            args=["-m", "src.mcp_server.main"],
        )
    )
)


def create_graph_workflow(mcp_client: MCPClient):
    """Create the multi-agent graph workflow for knowledge graph QA."""
    # Create specialized agents
    search_agent = create_search_entities_agent(mcp_client)
    query_agent = create_query_graph_agent(mcp_client)
    reporter_agent = create_reporter_agent()

    # Build the graph
    builder = GraphBuilder()

    # Add nodes
    builder.add_node(search_agent, "entity_search")
    builder.add_node(query_agent, "graph_query")
    builder.add_node(reporter_agent, "report_writer")

    # Add edges (dependencies)
    builder.add_edge("entity_search", "graph_query")
    builder.add_edge("graph_query", "report_writer")

    # Set entry point
    builder.set_entry_point("entity_search")

    # Configure execution timeout (10 minutes)
    builder.set_execution_timeout(600)

    # Build and return the graph
    return builder.build()


def run_graph_workflow(question: str) -> str:
    """Execute the graph-based multi-agent workflow for the given question."""
    # Use the MCP client context manager
    with kg_mcp_client:
        # Create the graph workflow within the context
        graph_workflow = create_graph_workflow(kg_mcp_client)

        # Execute the workflow
        result = graph_workflow(question)

        # Return the final result from the report_writer agent
        if result.status.value == "completed":
            # Get the NodeResult from the last node (report_writer)
            node_result = result.results.get("report_writer")
            if node_result and hasattr(node_result, 'result'):
                # Extract the AgentResult
                agent_result = node_result.result
                if hasattr(agent_result, 'message') and 'content' in agent_result.message:
                    # Extract text from the message content
                    content = agent_result.message['content']
                    if isinstance(content, list) and len(content) > 0:
                        # Get the text from the first content block
                        if isinstance(content[0], dict) and 'text' in content[0]:
                            return content[0]['text']
                # Fallback: try to get text representation
                return str(agent_result.message.get('content', 'No result available'))
            return "No result available"
        else:
            error_msg = getattr(result, 'error', 'Unknown error')
            return f"I encountered an issue while processing your question: {error_msg}"


class WorkflowSupervisorAgent:
    """Lightweight callable wrapper to expose run_graph_workflow."""

    def __call__(self, question: str) -> str:
        return run_graph_workflow(question)


def create_supervisor_agent() -> WorkflowSupervisorAgent:
    """Preserve the historical supervisor factory for UI callers."""
    return WorkflowSupervisorAgent()


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

            response = run_graph_workflow(user_input)
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
