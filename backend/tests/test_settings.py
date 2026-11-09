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


def test_log_level_defaults_to_info() -> None:
    settings = Settings(
        cors_allowed_origins=["http://127.0.0.1:5173"],
        database_url="postgresql+psycopg://agent_template:local-dev-only@localhost/app",
        _env_file=None,
    )

    assert settings.log_level == "INFO"


def test_log_level_is_read_from_environment_and_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = Settings(
        cors_allowed_origins=["http://127.0.0.1:5173"],
        database_url="postgresql+psycopg://agent_template:local-dev-only@localhost/app",
        _env_file=None,
    )

    assert settings.log_level == "DEBUG"


def test_rejects_unsupported_log_level() -> None:
    with pytest.raises(ValidationError, match="log_level"):
        Settings(
            cors_allowed_origins=["http://127.0.0.1:5173"],
            database_url=(
                "postgresql+psycopg://agent_template:local-dev-only@localhost/app"
            ),
            log_level="TRACE",
            _env_file=None,
        )


def test_accepts_otlp_endpoint_without_enabling_it_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    settings = Settings(
        cors_allowed_origins=["http://127.0.0.1:5173"],
        database_url="postgresql+psycopg://agent_template:local-dev-only@localhost/app",
        _env_file=None,
    )

    assert settings.otel_exporter_otlp_endpoint is None


def test_accepts_valid_otlp_endpoint() -> None:
    settings = Settings(
        cors_allowed_origins=["http://127.0.0.1:5173"],
        database_url="postgresql+psycopg://agent_template:local-dev-only@localhost/app",
        otel_exporter_otlp_endpoint="http://127.0.0.1:4318",
        _env_file=None,
    )

    assert str(settings.otel_exporter_otlp_endpoint) == "http://127.0.0.1:4318/"


def test_rejects_otlp_endpoint_with_credentials() -> None:
    with pytest.raises(ValidationError, match="must not contain credentials"):
        Settings(
            cors_allowed_origins=["http://127.0.0.1:5173"],
            database_url=(
                "postgresql+psycopg://agent_template:local-dev-only@localhost/app"
            ),
            otel_exporter_otlp_endpoint="http://user:password@localhost:4318",
            _env_file=None,
        )


def test_requires_cors_origins_when_no_environment_file_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    with pytest.raises(ValidationError, match="cors_allowed_origins"):
        Settings(_env_file=None)


def test_oidc_settings_must_be_set_together() -> None:
    with pytest.raises(ValidationError, match="set together"):
        Settings(
            cors_allowed_origins=["http://127.0.0.1:5173"],
            database_url="postgresql+psycopg://user:pass@localhost/app",
            oidc_issuer="https://issuer.example.test",
            _env_file=None,
        )


def test_oidc_discovery_url_requires_https_outside_localhost() -> None:
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(
            cors_allowed_origins=["http://127.0.0.1:5173"],
            database_url="postgresql+psycopg://user:pass@localhost/app",
            oidc_issuer="http://issuer.example.test",
            oidc_discovery_url="http://issuer.example.test/.well-known/x",
            oidc_audience="api://x",
            oidc_required_scope="chat.use",
            _env_file=None,
        )


def test_blank_oidc_values_mean_unconfigured() -> None:
    settings = Settings(
        cors_allowed_origins=["http://127.0.0.1:5173"],
        database_url="postgresql+psycopg://user:pass@localhost/app",
        oidc_issuer="",
        oidc_discovery_url="",
        oidc_audience="",
        oidc_required_scope="",
        _env_file=None,
    )
    assert settings.oidc_issuer is None
    assert settings.oidc_discovery_url is None


def _base(
    provider: str = "fake", endpoint: str | None = None, deployment: str | None = None
) -> Settings:
    return Settings(
        cors_allowed_origins=["http://127.0.0.1:5173"],
        database_url="postgresql+psycopg://u:p@127.0.0.1:5433/db",
        agent_provider=provider,
        foundry_project_endpoint=endpoint,
        foundry_deployment=deployment,
        _env_file=None,
    )


def test_agent_provider_defaults_to_fake() -> None:
    assert _base().agent_provider == "fake"


def test_foundry_provider_without_configuration_fails_at_startup() -> None:
    with pytest.raises(ValidationError):
        _base("foundry")
    with pytest.raises(ValidationError):
        _base("foundry", "https://x.example/")
    with pytest.raises(ValidationError):
        _base("foundry", "http://x.example/", "chat")


def test_foundry_provider_with_configuration_is_accepted() -> None:
    assert _base("foundry", "https://x.example/", "chat").foundry_deployment == "chat"


def test_application_insights_connection_string_is_secret_and_blank_is_unset() -> None:
    database_url = "postgresql+psycopg://agent_template:local-dev-only@localhost/app"
    blank = Settings(
        cors_allowed_origins=["http://127.0.0.1:5173"],
        database_url=database_url,
        applicationinsights_connection_string=" ",
        _env_file=None,
    )
    assert blank.applicationinsights_connection_string is None
    settings = Settings(
        cors_allowed_origins=["http://127.0.0.1:5173"],
        database_url=database_url,
        applicationinsights_connection_string="InstrumentationKey=abc",
        _env_file=None,
    )
    assert "abc" not in repr(settings)
    assert settings.applicationinsights_connection_string is not None
    assert (
        settings.applicationinsights_connection_string.get_secret_value()
        == "InstrumentationKey=abc"
    )
