import pytest
from pydantic import ValidationError

from agent_template_api.settings import Settings


def test_rejects_non_origin_cors_values() -> None:
    with pytest.raises(ValidationError, match="Invalid CORS origin"):
        Settings(
            cors_allowed_origins=["not-an-origin"],
            database_url="postgresql+psycopg://user:pass@localhost/app",
            _env_file=None,
        )


def test_rejects_non_postgresql_database_urls() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL URL"):
        Settings(
            cors_allowed_origins=["http://127.0.0.1:5173"],
            database_url="sqlite:///local.db",
            _env_file=None,
        )


def test_rejects_malformed_database_urls() -> None:
    with pytest.raises(ValidationError, match="valid PostgreSQL URL"):
        Settings(
            cors_allowed_origins=["http://127.0.0.1:5173"],
            database_url="not a database url",
            _env_file=None,
        )


def test_requires_cors_origins_when_no_environment_file_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    with pytest.raises(ValidationError, match="cors_allowed_origins"):
        Settings(_env_file=None)
