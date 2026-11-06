from importlib.metadata import version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_template_api.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="Agent Template API",
    version=version("agent-template-api"),
    description="API for the Agent Template application.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}
