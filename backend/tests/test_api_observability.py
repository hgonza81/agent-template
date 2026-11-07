import json
import logging
from types import ModuleType
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from pytest import LogCaptureFixture, MonkeyPatch


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


def request_logs(caplog: LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.name == "agent_template_api.requests"
    ]


def test_request_id_is_returned_and_logs_exclude_sensitive_request_data(
    api_module: ModuleType,
    caplog: LogCaptureFixture,
) -> None:
    request_id = "7e8f2f28-6f9e-4e8d-b903-25cc171b753d"
    secret = "test-token-do-not-log"
    caplog.set_level(logging.INFO, logger="agent_template_api.requests")

    with TestClient(api_module.app) as client:
        response = client.get(
            f"/api/v1/health/live?access_token={secret}",
            headers={
                "Authorization": f"Bearer {secret}",
                "Origin": "http://127.0.0.1:5173",
                "X-Request-ID": request_id,
            },
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
    assert response.headers["Access-Control-Expose-Headers"] == "X-Request-ID"
    records = request_logs(caplog)
    assert len(records) == 1
    event = json.loads(records[0].getMessage())
    assert event["event"] == "api.request"
    assert event["request_id"] == request_id
    assert event["method"] == "GET"
    assert event["route"] == "/api/v1/health/live"
    assert event["status_code"] == 200
    assert "duration_ms" in event
    assert secret not in records[0].getMessage()
    assert "access_token" not in records[0].getMessage()
    assert "Authorization" not in records[0].getMessage()


def test_invalid_request_id_is_replaced_with_a_generated_id(
    api_module: ModuleType,
) -> None:
    with TestClient(api_module.app) as client:
        response = client.get(
            "/api/v1/health/live",
            headers={"X-Request-ID": "not-a-valid-id"},
        )

    generated_request_id = response.headers["X-Request-ID"]
    assert str(UUID(generated_request_id)) == generated_request_id


def test_internal_errors_return_safe_response_and_log_no_exception_details(
    api_module: ModuleType,
    caplog: LogCaptureFixture,
) -> None:
    secret = "postgresql://user:password@database"

    def raise_internal_error() -> None:
        raise RuntimeError(secret)

    api_module.app.add_api_route(
        "/test-internal-error",
        raise_internal_error,
        methods=["GET"],
    )
    caplog.set_level(logging.WARNING, logger="agent_template_api.requests")

    with TestClient(api_module.app, raise_server_exceptions=False) as client:
        response = client.get("/test-internal-error")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Internal server error",
        "request_id": response.headers["X-Request-ID"],
    }
    records = request_logs(caplog)
    assert len(records) == 1
    event = json.loads(records[0].getMessage())
    assert event["error_category"] == "internal_error"
    assert secret not in response.text
    assert secret not in records[0].getMessage()


def test_validation_errors_do_not_echo_submitted_values(
    api_module: ModuleType,
    caplog: LogCaptureFixture,
) -> None:
    class Payload(BaseModel):
        account_number: int

    def validate_payload(payload: Payload) -> dict[str, str]:
        return {"status": "ok"}

    api_module.app.add_api_route(
        "/test-validation",
        validate_payload,
        methods=["POST"],
    )
    secret = "sensitive-account-value"
    caplog.set_level(logging.INFO, logger="agent_template_api.requests")

    with TestClient(api_module.app) as client:
        response = client.post(
            "/test-validation",
            json={"account_number": secret},
        )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Invalid request",
        "request_id": response.headers["X-Request-ID"],
    }
    assert secret not in response.text
    records = request_logs(caplog)
    assert len(records) == 1
    assert secret not in records[0].getMessage()


def test_http_exception_details_are_not_returned_to_clients(
    api_module: ModuleType,
) -> None:
    secret = "private-configuration-value"

    def raise_not_found() -> None:
        raise HTTPException(
            status_code=404,
            detail=secret,
            headers={
                "WWW-Authenticate": secret,
                "X-Configuration": secret,
            },
        )

    api_module.app.add_api_route(
        "/test-http-error",
        raise_not_found,
        methods=["GET"],
    )

    with TestClient(api_module.app) as client:
        response = client.get("/test-http-error")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Not found",
        "request_id": response.headers["X-Request-ID"],
    }
    assert secret not in response.text
    assert "WWW-Authenticate" not in response.headers
    assert "X-Configuration" not in response.headers
