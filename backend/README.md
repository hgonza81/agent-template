# Agent Template API

From the repository root, install the pinned Python runtime and start the API:

```bash
uv python install 3.13
cd backend
uv sync --frozen
uv run uvicorn agent_template_api.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive OpenAPI documentation is at `/docs`.