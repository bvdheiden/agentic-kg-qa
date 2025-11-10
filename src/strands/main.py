import base64
import json
import os
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

from strands.telemetry import StrandsTelemetry
from src.strands.query_graph_agent import query_graph_agent
from src.strands.search_entity_agent import search_entity_agent
from strands import Agent
from src.strands.llm import ollama_model
from strands_tools import workflow


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

WORKFLOW_SUPERVISOR_PROMPT = """
You orchestrate the Knowledge Graph QA workflow. For every user question you:
1. Trigger the semantic search stage (search_entity_agent) to gather candidate IRIs.
2. Pass the collected context into the querying stage (query_graph_agent) to execute SPARQL.
3. Report the final synthesized answer grounded in Fuseki results.
Always keep the workflow deterministic and document each stage with the workflow tool.
"""

GRAPH_QA_WORKFLOW_TASKS = [
    {
        "task_id": "entity_search",
        "description": "Map the user question to ontology IRIs via semantic search.",
        "system_prompt": """
You are the Entity Discovery agent. Call `search_entity_agent` with the original user
question and capture the JSON response so downstream agents can use it.
""".strip(),
        "priority": 5,
    },
    {
        "task_id": "graph_query",
        "description": "Use Fuseki query_graph to answer the validated question.",
        "dependencies": ["entity_search"],
        "system_prompt": """
You are the Graph Query agent. Combine the user question with the JSON output returned
by `search_entity_agent` and call `query_graph_agent` to obtain the final answer.
""".strip(),
        "priority": 4,
    },
]


def create_workflow_agent() -> Agent:
    """Create the workflow supervisor agent with the workflow tool."""
    return Agent(
        model=ollama_model,
        system_prompt=WORKFLOW_SUPERVISOR_PROMPT,
        tools=[workflow],
    )


workflow_agent = create_workflow_agent()


def _parse_search_output(raw_output: str) -> dict[str, Any]:
    """Convert the search_entity_agent output into a dict for downstream tasks."""
    try:
        parsed = json.loads(raw_output)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {"search_summary": raw_output}


def run_graph_workflow(question: str) -> str:
    """Execute the deterministic search -> query workflow for the given question."""
    workflow_id = f"graph_qa_{uuid4().hex[:8]}"

    workflow_agent.tool.workflow(
        action="create",
        workflow_id=workflow_id,
        tasks=GRAPH_QA_WORKFLOW_TASKS,
    )
    workflow_agent.tool.workflow(
        action="start",
        workflow_id=workflow_id,
        input=question,
    )

    search_metadata = _parse_search_output(search_entity_agent(question))
    candidate_entities = search_metadata.get("candidate_entities", [])
    search_summary = search_metadata.get("search_summary")

    query_payload = json.dumps(
        {
            "question": question,
            "candidate_entities": candidate_entities,
            "search_summary": search_summary,
        }
    )
    response = query_graph_agent(query_payload)

    try:
        workflow_agent.tool.workflow(action="status", workflow_id=workflow_id)
    except Exception:
        # Swallow workflow status errors so the CLI can continue responding.
        pass

    return response


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
