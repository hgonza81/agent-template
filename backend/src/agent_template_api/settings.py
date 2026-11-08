from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    cors_allowed_origins: list[str]
    database_url: SecretStr
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    otel_exporter_otlp_endpoint: AnyHttpUrl | None = None
    # "fake" (default) is the deterministic local agent: no network, no cost.
    # "foundry" calls the real Azure AI Foundry deployment and must be enabled
    # explicitly; missing configuration then fails at startup (never the fake).
    agent_provider: Literal["fake", "foundry"] = "fake"
    foundry_project_endpoint: AnyHttpUrl | None = None
    foundry_deployment: str | None = None
    # Chat limits. Defaults follow the agreed targets: p95 <= 20 s and 5
    # concurrent chat requests; the timeout is a hard ceiling above the p95.
    chat_max_message_chars: int = Field(default=4000, ge=1, le=100_000)
    chat_timeout_seconds: float = Field(default=30, gt=0, le=300)
    chat_max_concurrent_requests: int = Field(default=5, ge=1, le=1000)
    chat_rate_limit_per_minute: int = Field(default=20, ge=1, le=10_000)
    # Entra External ID values are pending provisioning; auth stays disabled
    # (protected routes return 503) until all four are configured.
    oidc_issuer: str | None = None
    oidc_discovery_url: AnyHttpUrl | None = None
    oidc_audience: str | None = None
    oidc_required_scope: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, log_level: str) -> str:
        return log_level.upper()

    @field_validator("otel_exporter_otlp_endpoint")
    @classmethod
    def validate_otel_exporter_otlp_endpoint(
        cls,
        endpoint: AnyHttpUrl | None,
    ) -> AnyHttpUrl | None:
        if endpoint is None:
            return None
        parsed = urlsplit(str(endpoint))
        if (
            parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "OTEL_EXPORTER_OTLP_ENDPOINT must not contain credentials, "
                "a query, or a fragment"
            )
        return endpoint

    @field_validator(
        "oidc_issuer", "oidc_audience", "oidc_required_scope", mode="before"
    )
    @classmethod
    def blank_oidc_value_is_unset(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("oidc_discovery_url", mode="before")
    @classmethod
    def blank_oidc_discovery_url_is_unset(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("oidc_discovery_url")
    @classmethod
    def validate_oidc_discovery_url(cls, url: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if url is None:
            return None
        parsed = urlsplit(str(url))
        is_local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or (parsed.scheme != "https" and not is_local)
        ):
            raise ValueError(
                "OIDC_DISCOVERY_URL must use HTTPS (HTTP only for localhost) "
                "and contain no credentials, query, or fragment"
            )
        return url

    @field_validator("foundry_project_endpoint", "foundry_deployment", mode="before")
    @classmethod
    def blank_foundry_value_is_unset(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_foundry_configuration(self) -> "Settings":
        if self.agent_provider == "foundry":
            endpoint = self.foundry_project_endpoint
            if (
                endpoint is None
                or self.foundry_deployment is None
                or endpoint.scheme != "https"
                or endpoint.username is not None
                or endpoint.password is not None
                or endpoint.query
                or endpoint.fragment
            ):
                raise ValueError(
                    "AGENT_PROVIDER=foundry requires FOUNDRY_PROJECT_ENDPOINT (HTTPS, "
                    "no credentials) and FOUNDRY_DEPLOYMENT"
                )
        return self

    @model_validator(mode="after")
    def validate_oidc_is_all_or_nothing(self) -> "Settings":
        values = (
            self.oidc_issuer,
            self.oidc_discovery_url,
            self.oidc_audience,
            self.oidc_required_scope,
        )
        if any(v is not None for v in values) and any(v is None for v in values):
            raise ValueError(
                "OIDC_ISSUER, OIDC_DISCOVERY_URL, OIDC_AUDIENCE, and "
                "OIDC_REQUIRED_SCOPE must be set together or not at all"
            )
        return self

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, database_url: SecretStr) -> SecretStr:
        try:
            parsed = make_url(database_url.get_secret_value())
        except ArgumentError as error:
            raise ValueError("DATABASE_URL must be a valid PostgreSQL URL") from error
        if (
            parsed.drivername != "postgresql+psycopg"
            or parsed.host is None
            or parsed.database is None
        ):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL URL using the psycopg driver"
            )
        return database_url

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_allowed_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"Invalid CORS origin: {origin}")
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
