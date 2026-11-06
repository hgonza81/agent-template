# Agent Template API

From the repository root, install the pinned Python runtime and start the API:

```bash
uv python install 3.13
cd backend
cp .env.example .env
uv sync --frozen
uv run uvicorn agent_template_api.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive OpenAPI documentation is at `/docs`. 

## OpenAPI contract

FastAPI defines the API contract. Export the current schema after changing backend
routes or models:

```bash
uv run python -m agent_template_api.export_openapi
```

This updates the checked-in `../openapi/openapi.json` contract.

## Quality checks

Run these commands from `backend/` after `uv sync --frozen`:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
uv export --locked --format requirements.txt --no-emit-project \
  --output-file "${TMPDIR:-/tmp}/agent-template-backend-requirements.txt"
uv run pip-audit --strict --require-hashes \
  --requirement "${TMPDIR:-/tmp}/agent-template-backend-requirements.txt"
```