# Extraction Knowledge Graph Toolkit

## Overview
Extraction is a local agent workspace for exploring a service ownership knowledge graph. It pairs a FastMCP server that wraps Apache Fuseki and Qdrant with a Strands-powered CLI agent, enabling natural language exploration of teams, services, and endpoints. Data is bootstrapped with `poetry run bootstrap_data`, embeddings are generated via a local Ollama deployment, and telemetry flows through Langfuse and OpenTelemetry exporters.

## Repository Layout
```
.
|-- src/
|   |-- bootstrap_data.py           # Seeds Fuseki and Qdrant with ontology data
|   |-- mcp_server/
|   |   |-- main.py                 # FastMCP entrypoint exposing graph tools
|   |   |-- config.py               # Central config for hosts, ports, namespaces
|   |   |-- service/                # Fuseki, Qdrant, embedding, validation helpers
|   |   \-- tool/                   # Tool definitions (search, ownership, reasoning)
|   \-- strands/
|       |-- main.py                 # Strands CLI entrypoint
|       |-- llm.py                  # Shared Ollama model configuration
|       \-- ownership_researcher.py # Agent tool bridging to the MCP server
|-- services/docker-compose.yaml    # Local Fuseki and Qdrant services
|-- experiments/extraction.ipynb    # Notebook for exploratory work
|-- .env.example                    # Template for Langfuse and related settings
|-- poetry.lock / pyproject.toml    # Poetry project definition
\-- langfuse/                       # Langfuse SDK (external dependency; leave untouched)
```

### Key Modules
- `src/mcp_server/config.py`: canonical host, port, and namespace configuration shared across services and tools.
- `src/mcp_server/tool/search_entities_tool.py`: vector search against Qdrant to locate IRIs for later graph queries.
- `src/mcp_server/tool/reason_graph_tool.py`: builds and validates SPARQL to inspect incoming and outgoing relationships.
- `src/mcp_server/tool/find_resource_owner_tool.py`: determines the owning team for a resource after validating ontology types.
- `src/mcp_server/tool/find_resources_owned_by_team_tool.py`: enumerates assets owned by a team, including indirect containment paths.
- `src/mcp_server/service/`: infrastructure clients for Fuseki, Qdrant, embedding generation, and ontology validation routines.
- `src/strands/main.py`: Strands CLI entrypoint wiring Langfuse telemetry and the ownership researcher tool.
- `src/strands/ownership_researcher.py`: wraps the MCP server tooling behind a Strands agent workflow.
- `src/bootstrap_data.py`: prepares the ontology RDF graph and embeddings, then loads Fuseki and Qdrant.

### Data Flow
1. `poetry run bootstrap_data` generates ontology triples, writes them to Fuseki, and syncs entity embeddings into Qdrant.
2. `poetry run strands` launches the Strands CLI agent, starts the FastMCP server automatically, and connects to it over stdio.
3. Agent tool calls orchestrate searches and graph reasoning to answer natural language questions.

## Prerequisites
- Python 3.10 and Poetry (`pip install poetry`)
- Docker and Docker Compose (for Fuseki and Qdrant)
- Ollama running locally with the `qwen3:14b` and `nomic-embed-text` models (`ollama pull qwen3:14b`, `ollama pull nomic-embed-text`)
- Langfuse account credentials (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`) for telemetry export

## Setup
1. Clone the repository and fetch submodules:
   ```bash
   git clone <repo-url>
   cd extraction
   git submodule update --init --recursive
   ```
2. Install dependencies with Poetry:
   ```bash
   poetry install
   ```
3. Copy the environment template and fill in required values (Langfuse keys, base URL):
   ```bash
   cp .env.example .env
   # edit .env and provide LANGFUSE_* values
   ```
4. Ensure the Ollama models are available:
   ```bash
   ollama pull qwen3:14b
   ollama pull nomic-embed-text
   ```

## Running the Stack

### 1. Start data services
```
docker compose -f services/docker-compose.yaml up -d
```
This spins up Apache Fuseki on port 3031 and Qdrant on port 6333. Use `docker compose -f services/docker-compose.yaml down` to stop them.

Start the supporting stacks shipped with the Langfuse and LibreChat submodules:
```
docker compose up -d
```
Run the command above once from `langfuse/` to bring up telemetry services and again from `librechat/` to launch the chat UI. Use `docker compose down` within each directory to stop the respective services.

### 2. Bootstrap the knowledge graph
```
poetry run bootstrap_data
```
The script recreates the Fuseki dataset, uploads ontology triples, builds embeddings, and upserts them into Qdrant. Re-run whenever you change ontology data.

### 3. Launch the Strands CLI agent
```
poetry run strands
```
The CLI loads Langfuse telemetry configuration from the environment, starts the FastMCP server automatically, and provides an interactive prompt. Type `exit` to quit.

## Development and Testing
- Run the automated test suite (additions should live under `tests/` mirroring `src/`):
  ```bash
  poetry run pytest -q
  ```
- Use `poetry shell` to enter a virtualenv for ad-hoc scripts.
- `experiments/extraction.ipynb` mirrors the agent workflow for exploratory analysis.

## Troubleshooting and Tips
- Confirm Docker services respond: `curl http://localhost:3031/$/datasets` for Fuseki and `curl http://localhost:6333/collections` for Qdrant.
- If embeddings fail, verify Ollama is running (`ollama serve`) and reachable at `http://localhost:11434`.
- Langfuse telemetry requires reachable `LANGFUSE_BASE_URL`; set `OTEL_EXPORTER_OTLP_HEADERS` only after generating credentials.
- The `langfuse/` directory is vendored; avoid modifying it to keep upstream updates simple.
- For verbose logs, tail `docker compose -f services/docker-compose.yaml logs -f fuseki qdrant`.
