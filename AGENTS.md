# Repository Guidelines

## Project Structure & Module Organization
- Source code lives under `src/`.
  - `src/mcp_server/`: MCP server entry (`main.py`), config, tools, and services.
  - `src/strands/`: CLI entry (`main.py`) and research helpers.
  - `src/bootstrap_data.py`: one-off bootstrap script.
- Data services are provisioned via `docker-compose.yaml` (Fuseki, Qdrant).
- Notebooks: `extraction.ipynb` at repo root.
- Tests (when added) belong in `tests/` mirroring `src/` paths.

## Build, Test, and Development Commands
- Install deps: `poetry install`
- Run MCP server: `poetry run mcp_server`
- Run Strands CLI: `poetry run strands`
- Bootstrap data: `poetry run bootstrap_data`
- Start services: `docker compose up -d`
- Run tests: `poetry run pytest -q`

## Coding Style & Naming Conventions
- Python 3.10, PEP 8, 4-space indentation.
- Use type hints for public functions and return types.
- Naming: packages/modules `snake_case`; classes `PascalCase`; functions/vars `snake_case`.
- Keep functions small and document with a one-line docstring summary.

## Testing Guidelines
- Framework: `pytest`.
- Place tests in `tests/` with filenames `test_*.py`; mirror `src/` structure.
- Prefer unit tests with mocks for external services (Qdrant, Fuseki).
- Run locally with `poetry run pytest` before opening a PR.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- Write imperative, concise subjects (<= 72 chars); add context in body when useful.
- PRs should include: clear description, linked issues, test instructions, and logs/screenshots when relevant.

## Security & Configuration Tips
- `docker-compose.yaml` exposes Fuseki (3030) and Qdrant (6333). Override defaults via env vars; do not commit secrets.
- For local runs, export environment variables or use your shell/session; prefer configuration over hardcoded values.

## Agent-Specific Notes
- Entrypoints are declared in `pyproject.toml` under `[tool.poetry.scripts]` (`mcp_server`, `strands`, `bootstrap_data`).
- Keep changes minimal and focused; follow the directory layout above.
- If you add new commands, update this document and `pyproject.toml` scripts.
- Keep `README.md` in sync with changes whenever new capabilities, setup steps, or usage patterns are introduced. Update it alongside any relevant modifications when possible.
- Treat the `langfuse/` directory as an external dependency; do not modify or inspect its contents.
