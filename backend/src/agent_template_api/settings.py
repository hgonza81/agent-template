from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    cors_allowed_origins: list[str]
    database_url: SecretStr
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    otel_exporter_otlp_endpoint: AnyHttpUrl | None = None

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
