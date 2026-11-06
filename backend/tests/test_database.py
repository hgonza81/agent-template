from agent_template_api.database import create_database_engine
from agent_template_api.settings import Settings


def test_database_engine_uses_configured_postgresql_url() -> None:
    settings = Settings(
        cors_allowed_origins=["http://127.0.0.1:5173"],
        database_url="postgresql+psycopg://agent_template:local-dev-only@127.0.0.1:5433/agent_template",
        _env_file=None,
    )

    engine = create_database_engine(settings)

    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.database == "agent_template"
    engine.dispose()
