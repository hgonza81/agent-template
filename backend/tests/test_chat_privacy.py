"""Chat content, model output, tokens and personal data never reach logs or telemetry.

Drives the real app with the real `OpenAIFoundryClient` and `FoundryChatAgent`
over an in-process fake provider transport (no network, no cost), covering the
success path and provider failure paths whose exceptions or bodies could echo
the prompt or the reply.
"""

import json
import logging
from collections.abc import Callable, Iterator
from types import ModuleType
from uuid import uuid4

import httpx
import pytest
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import CredentialUnavailableError
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from pytest import MonkeyPatch
from sqlalchemy import delete
from sqlalchemy.orm import Session
from test_telemetry import InMemoryMetricExporter

from agent_template_api.agent import get_chat_agent
from agent_template_api.auth import TokenIdentity, get_current_identity
from agent_template_api.foundry_agent import FoundryChatAgent
from agent_template_api.foundry_client import OpenAIFoundryClient
from agent_template_api.logging_config import configure_logging
from agent_template_api.models import Subscription
from agent_template_api.telemetry import (
    PrivacyFilteringMetricExporter,
    PrivacyFilteringSpanExporter,
    _route_templates,
    instrument_application,
)

ISSUER = "https://issuer.example.test/tenant/v2.0"
PROMPT = "prompt-text-unique-7f3a"
REPLY = "model-output-unique-91bc"
PROVIDER_TOKEN = "provider-bearer-token-unique-55d2"
USER_TOKEN = "user-bearer-token-unique-c0de"
EMAIL = "private.person-unique@example.test"
SUBJECT = f"privacy-{uuid4()}"
SENSITIVE = (PROMPT, REPLY, PROVIDER_TOKEN, USER_TOKEN, EMAIL, SUBJECT)

Handler = Callable[[httpx.Request], httpx.Response]


class FakeCredential:
    def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        return AccessToken(PROVIDER_TOKEN, 4_000_000_000)


def provider_handler(responses_status: int, *, raise_error: bool = False) -> Handler:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/conversations"):
            return httpx.Response(200, json={"id": "conv_1", "object": "conversation"})
        if raise_error:
            raise httpx.ReadTimeout(f"timed out for {PROMPT} {REPLY}", request=request)
        if responses_status != 200:
            # Provider error bodies may echo the prompt, the output and the token.
            return httpx.Response(
                responses_status,
                json={
                    "error": {
                        "message": f"bad input {PROMPT} / {REPLY} / {PROVIDER_TOKEN}",
                        "code": "boom",
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "resp_1",
                "object": "response",
                "created_at": 1,
                "model": "m",
                "status": "completed",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "msg_1",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {"type": "output_text", "text": REPLY, "annotations": []}
                        ],
                    }
                ],
            },
        )

    return handle


def make_agent(handler: Handler) -> FoundryChatAgent:
    client = OpenAIFoundryClient(
        endpoint="https://foundry.example.test/api/projects/p",
        credential=FakeCredential(),  # type: ignore[arg-type]
    )
    inner: AsyncOpenAI = client._client  # noqa: SLF001
    client._client = inner.with_options(  # noqa: SLF001
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    return FoundryChatAgent(client, agent_id="deployment-1")


class Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        text = record.getMessage()
        extras = " ".join(f"{k}={v}" for k, v in record.__dict__.items())
        exc = ""
        if record.exc_info:
            exc = repr(record.exc_info[1]) + str(record.exc_text)
        self.lines.append(f"{record.name} {text} {extras} {exc}")


@pytest.fixture
def api_module(monkeypatch: MonkeyPatch) -> Iterator[ModuleType]:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://127.0.0.1:5173"]')
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://agent_template:local-dev-only"
        "@127.0.0.1:5433/agent_template_test",
    )
    from alembic import command
    from alembic.config import Config

    from agent_template_api import main

    command.upgrade(Config("alembic.ini"), "head")
    main.app.dependency_overrides[get_current_identity] = lambda: TokenIdentity(
        issuer=ISSUER, subject=SUBJECT, scopes=frozenset({"chat.use"})
    )
    yield main
    main.app.dependency_overrides.clear()
    with Session(main.database_engine) as session, session.begin():
        session.execute(
            delete(Subscription).where(Subscription.identity_subject == SUBJECT)
        )


@pytest.mark.parametrize(
    ("handler", "status"),
    [
        (provider_handler(200), 200),
        (provider_handler(400), 503),
        (provider_handler(401), 503),
        (provider_handler(404), 503),
        (provider_handler(429), 503),
        (provider_handler(500), 503),
        (provider_handler(200, raise_error=True), 503),
    ],
    ids=["success", "400", "401", "404", "429", "500", "transport-timeout"],
)
def test_chat_content_never_reaches_logs_traces_metrics_or_errors(
    api_module: ModuleType, handler: Handler, status: int
) -> None:
    api_module.app.dependency_overrides[get_chat_agent] = lambda: make_agent(handler)

    configure_logging("INFO")
    capture = Capture()
    root = logging.getLogger()
    previous_level = root.level
    root.setLevel(logging.DEBUG)
    root.addHandler(capture)
    requests_logger = logging.getLogger("agent_template_api.requests")
    requests_logger.addHandler(capture)

    resource = Resource.create({"service.name": "test-api"})
    span_exporter = InMemorySpanExporter()
    routes = _route_templates(api_module.app)
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        SimpleSpanProcessor(PrivacyFilteringSpanExporter(span_exporter, routes))
    )
    metric_exporter = InMemoryMetricExporter()
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(
                PrivacyFilteringMetricExporter(metric_exporter, routes),
                export_interval_millis=600000,
            )
        ],
    )
    instrumentor = instrument_application(
        api_module.app, api_module.database_engine, tracer_provider, meter_provider
    )
    try:
        with TestClient(api_module.app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/chat/messages",
                json={"message": PROMPT},
                headers={
                    "Authorization": f"Bearer {USER_TOKEN}",
                    "X-Email": EMAIL,
                },
            )
            invalid = client.post(
                "/api/v1/chat/messages",
                json={"message": PROMPT, "thread_id": REPLY},
                headers={"Authorization": f"Bearer {USER_TOKEN}"},
            )
        assert response.status_code == status
        assert invalid.status_code == 422

        assert meter_provider.force_flush()
        spans = span_exporter.get_finished_spans()
        assert spans
        telemetry = "\n".join(span.to_json() for span in spans)
        telemetry += "".join(data.to_json() for data in metric_exporter.metrics)
        events = [event for span in spans for event in span.events]
        assert events == []
        assert capture.lines
        outputs = {
            "logs": "\n".join(capture.lines),
            "telemetry": telemetry,
            "responses": (response.text if status != 200 else "")
            + invalid.text
            + str(response.headers),
        }
        for name, text in outputs.items():
            for value in SENSITIVE:
                assert value not in text, f"{value} leaked into {name}"
        if status == 200:
            assert response.json() == {"reply": REPLY}
        else:
            assert response.json()["detail"] == "Service unavailable"
    finally:
        instrumentor.uninstrument()
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.uninstrument_app(api_module.app)
        meter_provider.shutdown()
        tracer_provider.shutdown()
        root.removeHandler(capture)
        requests_logger.removeHandler(capture)
        root.setLevel(previous_level)


class FailingCredential:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        raise self.error


@pytest.mark.parametrize(
    ("status", "credential_error", "error_type", "provider_status"),
    [
        (400, None, "BadRequestError", 400),
        (401, None, "AuthenticationError", 401),
        (403, None, "PermissionDeniedError", 403),
        (404, None, "FoundryThreadNotFoundError", 404),
        (429, None, "RateLimitError", 429),
        (500, None, "InternalServerError", 500),
        (
            200,
            ClientAuthenticationError(f"denied {PROMPT} {PROVIDER_TOKEN}"),
            "ClientAuthenticationError",
            None,
        ),
        (
            200,
            CredentialUnavailableError(f"no identity {REPLY} {PROVIDER_TOKEN}"),
            "CredentialUnavailableError",
            None,
        ),
    ],
)
def test_provider_failures_log_only_error_class_and_status(
    api_module: ModuleType,
    status: int,
    credential_error: Exception | None,
    error_type: str,
    provider_status: int | None,
) -> None:
    agent = make_agent(provider_handler(status))
    if credential_error is not None:
        # Credential errors surface while the SDK acquires the bearer token.
        failing = OpenAIFoundryClient(
            endpoint="https://foundry.example.test/api/projects/p",
            credential=FailingCredential(credential_error),  # type: ignore[arg-type]
        )
        failing._client = failing._client.with_options(  # noqa: SLF001
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(provider_handler(200))
            )
        )
        agent = FoundryChatAgent(failing, agent_id="deployment-1")
    api_module.app.dependency_overrides[get_chat_agent] = lambda: agent

    configure_logging("INFO")
    capture = Capture()
    requests_logger = logging.getLogger("agent_template_api.requests")
    requests_logger.addHandler(capture)
    try:
        with TestClient(api_module.app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/chat/messages",
                json={"message": PROMPT},
                headers={"Authorization": f"Bearer {USER_TOKEN}"},
            )
    finally:
        requests_logger.removeHandler(capture)

    assert response.status_code == 503
    assert set(response.json()) == {"detail", "request_id"}
    assert response.json()["detail"] == "Service unavailable"
    events = [
        json.loads(line[line.index("{") : line.index("}") + 1])
        for line in capture.lines
        if '"api.request"' in line
    ]
    event = events[-1]
    assert event["provider_error_type"] == error_type
    assert event.get("provider_status") == provider_status
    joined = "\n".join(capture.lines) + response.text
    for value in SENSITIVE:
        assert value not in joined
