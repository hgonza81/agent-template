from types import ModuleType
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError


@pytest.fixture
def api_module(monkeypatch: MonkeyPatch) -> ModuleType:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://127.0.0.1:5173"]')
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://agent_template:local-dev-only"
        "@127.0.0.1:5433/agent_template_test",
    )

    from agent_template_api import main

    return main


def test_liveness_returns_ok_without_external_dependencies(
    monkeypatch: MonkeyPatch,
    api_module: ModuleType,
) -> None:
    database_engine = Mock(spec=Engine)
    monkeypatch.setattr(api_module, "database_engine", database_engine)

    with TestClient(api_module.app) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    database_engine.connect.assert_not_called()


def test_readiness_returns_ok_when_database_is_available(
    api_module: ModuleType,
) -> None:
    with TestClient(api_module.app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_unavailable_when_database_is_unavailable(
    monkeypatch: MonkeyPatch,
    api_module: ModuleType,
) -> None:
    database_engine = Mock(spec=Engine)
    database_engine.connect.side_effect = OperationalError(
        "SELECT 1",
        {},
        RuntimeError("database unavailable"),
    )
    monkeypatch.setattr(api_module, "database_engine", database_engine)

    with TestClient(api_module.app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Service unavailable",
        "request_id": response.headers["X-Request-ID"],
    }
