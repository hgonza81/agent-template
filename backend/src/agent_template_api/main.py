from importlib.metadata import version

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from agent_template_api.database import create_database_engine
from agent_template_api.settings import get_settings

settings = get_settings()
database_engine = create_database_engine(settings)

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


@app.get(
    "/api/v1/health/ready",
    responses={503: {"description": "A required dependency is unavailable"}},
)
def health_ready() -> dict[str, str]:
    try:
        with database_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail={"status": "unavailable"},
        ) from error

    return {"status": "ok"}
