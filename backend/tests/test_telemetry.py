from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    MetricExportResult,
    MetricsData,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import Status, StatusCode
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from agent_template_api.telemetry import (
    PrivacyFilteringMetricExporter,
    PrivacyFilteringSpanExporter,
    configure_telemetry,
    instrument_application,
)


class InMemoryMetricExporter(MetricExporter):
    def __init__(self) -> None:
        super().__init__()
        self.metrics: list[MetricsData] = []

    def export(
        self,
        metrics_data: MetricsData,
        timeout_millis: float = 10000,
        **kwargs: object,
    ) -> MetricExportResult:
        self.metrics.append(metrics_data)
        return MetricExportResult.SUCCESS

    def shutdown(self, timeout_millis: float = 30000, **kwargs: object) -> None:
        return None

    def force_flush(self, timeout_millis: float = 10000) -> bool:
        return True


@pytest.fixture
def sqlite_engine() -> Iterator[Engine]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        yield engine
    finally:
        engine.dispose()


def test_telemetry_is_disabled_without_an_otlp_endpoint(
    sqlite_engine: Engine,
) -> None:
    app = FastAPI()

    assert configure_telemetry(app, sqlite_engine, None) is None


def test_instrumentation_exports_privacy_safe_traces_and_http_metrics(
    sqlite_engine: Engine,
) -> None:
    app = FastAPI()
    query_secret = "private-query-value"

    @app.post("/records/{record_id}")
    def post_record(record_id: str, payload: dict[str, str]) -> dict[str, str]:
        with sqlite_engine.connect() as connection:
            connection.execute(text(f"SELECT '{query_secret}'"))
        return {"record_id": record_id}

    resource = Resource.create({"service.name": "test-api"})
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        SimpleSpanProcessor(
            PrivacyFilteringSpanExporter(
                span_exporter,
                frozenset({"/records/{record_id}"}),
            )
        )
    )
    metric_exporter = InMemoryMetricExporter()
    metric_reader = PeriodicExportingMetricReader(
        PrivacyFilteringMetricExporter(
            metric_exporter,
            frozenset({"/records/{record_id}"}),
        ),
        export_interval_millis=600000,
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    )
    sqlalchemy_instrumentor = instrument_application(
        app,
        sqlite_engine,
        tracer_provider,
        meter_provider,
    )
    path_secret = "private-path-value"
    query_parameter_secret = "private-url-query-value"
    bearer_token = "telemetry-bearer-token-unique"
    api_key = "telemetry-api-key-unique"
    cookie = "telemetry-cookie-unique"
    password = "telemetry-password-unique"
    email = "telemetry-email-unique@example.test"
    phone_number = "+1-202-555-0191"
    identity_subject = "telemetry-identity-subject-unique"
    sensitive_values = (
        query_secret,
        path_secret,
        query_parameter_secret,
        bearer_token,
        api_key,
        cookie,
        password,
        email,
        phone_number,
        identity_subject,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/records/{path_secret}?access_token={query_parameter_secret}",
                headers={
                    "Authorization": f"Bearer {bearer_token}",
                    "X-API-Key": api_key,
                    "Cookie": f"session={cookie}",
                },
                json={
                    "password": password,
                    "email": email,
                    "phone_number": phone_number,
                    "identity_subject": identity_subject,
                },
            )

        assert response.status_code == 200
        assert response.json() == {"record_id": path_secret}

        spans = span_exporter.get_finished_spans()
        assert len(spans) >= 2
        exported = "\n".join(span.to_json() for span in spans)
        assert all(value not in exported for value in sensitive_values)
        assert "Authorization" not in exported
        assert "X-API-Key" not in exported
        assert "Cookie" not in exported
        assert "db.statement" not in exported
        assert "exception" not in exported.lower()
        assert any(
            (span.attributes or {}).get("http.route") == "/records/{record_id}"
            for span in spans
        )
        assert any(span.name == "database operation" for span in spans)
        database_spans = [
            span for span in spans if "db.system" in (span.attributes or {})
        ]
        assert database_spans
        assert all(
            (span.attributes or {}).get("db.operation") in {None, "SELECT"}
            for span in database_spans
        )
        assert all(
            (span.attributes or {}).keys()
            <= {
                "db.name",
                "db.namespace",
                "db.operation",
                "db.operation.name",
                "db.system",
                "db.system.name",
                "error.type",
                "http.request.method",
                "http.response.status_code",
                "http.route",
                "http.scheme",
                "http.status_code",
                "http.method",
                "url.scheme",
                "request.id",
            }
            for span in spans
        )

        assert meter_provider.force_flush()
        assert metric_exporter.metrics
        metrics_data = metric_exporter.metrics[-1]
        metric_names = {
            metric.name
            for resource_metrics in metrics_data.resource_metrics
            for scope_metrics in resource_metrics.scope_metrics
            for metric in scope_metrics.metrics
        }
        assert "http.server.duration" in metric_names
        serialized_metrics = metrics_data.to_json()
        assert all(value not in serialized_metrics for value in sensitive_values)
        assert "Authorization" not in serialized_metrics
        assert "X-API-Key" not in serialized_metrics
        assert "Cookie" not in serialized_metrics
    finally:
        FastAPIInstrumentor.uninstrument_app(app)
        sqlalchemy_instrumentor.uninstrument()
        meter_provider.shutdown()
        tracer_provider.shutdown()


def test_privacy_filtering_exporter_removes_exception_details() -> None:
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(
        SimpleSpanProcessor(
            PrivacyFilteringSpanExporter(
                span_exporter,
                frozenset({"/safe/{route}"}),
            )
        )
    )

    with tracer_provider.get_tracer(__name__).start_as_current_span(
        "untrusted span name"
    ) as span:
        span.set_attribute("url.full", "https://example.test/?token=secret")
        span.set_attribute("db.statement", "SELECT 'private-value'")
        span.set_attribute("http.route", "/safe/{route}")
        span.set_attribute("http.request.method", "GET")
        span.set_status(
            Status(StatusCode.ERROR, description="private exception detail")
        )
        span.add_event(
            "exception",
            {
                "exception.message": "private exception detail",
                "exception.stacktrace": "private stack trace",
            },
        )

    with tracer_provider.get_tracer(__name__).start_as_current_span(
        "untrusted route"
    ) as span:
        span.set_attribute("http.route", "/private-path-value")
        span.set_attribute("http.method", "GET")

    try:
        spans = span_exporter.get_finished_spans()
        exported = "\n".join(span.to_json() for span in spans)
        assert "private" not in exported
        assert "token=secret" not in exported
        assert "http.route" in (spans[0].attributes or {})
        assert spans[0].name == "GET /safe/{route}"
        assert "http.route" not in (spans[1].attributes or {})
        assert spans[1].name == "application operation"
    finally:
        tracer_provider.shutdown()


_CONNECTION_STRING = (
    "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
    "IngestionEndpoint=https://ingest.invalid/"
)


def test_azure_monitor_export_is_privacy_filtered_and_needs_no_network(
    sqlite_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spans = InMemorySpanExporter()
    metrics = InMemoryMetricExporter()
    received: dict[str, object] = {}

    def fake_trace_exporter(**kwargs: object) -> InMemorySpanExporter:
        received["trace"] = kwargs
        return spans

    def fake_metric_exporter(**kwargs: object) -> InMemoryMetricExporter:
        received["metric"] = kwargs
        return metrics

    monkeypatch.setattr(
        "agent_template_api.telemetry.AzureMonitorTraceExporter", fake_trace_exporter
    )
    monkeypatch.setattr(
        "agent_template_api.telemetry.AzureMonitorMetricExporter",
        fake_metric_exporter,
    )
    app = FastAPI()

    @app.post("/records/{record_id}")
    def post_record(record_id: str, payload: dict[str, str]) -> dict[str, str]:
        with sqlite_engine.connect() as connection:
            connection.execute(text("SELECT 'private-sql-value'"))
        return {"record_id": record_id}

    runtime = configure_telemetry(app, sqlite_engine, None, _CONNECTION_STRING)
    assert runtime is not None
    try:
        response = TestClient(app).post(
            "/records/private-path-value?q=private-query-value",
            json={"message": "private-chat-content"},
            headers={"Authorization": "Bearer private-token"},
        )
        assert response.status_code == 200
        runtime.tracer_provider.force_flush()
        runtime.meter_provider.force_flush()
    finally:
        runtime.shutdown()

    for name, kwargs in received.items():
        expected: dict[str, object] = {
            "connection_string": _CONNECTION_STRING,
            "disable_offline_storage": True,
        }
        if name == "trace":
            expected["tracer_provider"] = runtime.tracer_provider
        assert kwargs == expected
    exported_spans = "\n".join(span.to_json() for span in spans.get_finished_spans())
    assert exported_spans
    exported_metrics = "\n".join(
        data.to_json() for batch in metrics.metrics for data in [batch]
    )
    assert exported_metrics
    for text_out in (exported_spans, exported_metrics):
        assert "private" not in text_out
    assert "POST /records/{record_id}" in exported_spans


def test_azure_monitor_exporters_are_built_alongside_otlp(
    sqlite_engine: Engine,
) -> None:
    runtime = configure_telemetry(
        FastAPI(), sqlite_engine, "http://127.0.0.1:4318", _CONNECTION_STRING
    )
    assert runtime is not None
    try:
        processors = runtime.tracer_provider._active_span_processor._span_processors
        assert len(processors) == 2
    finally:
        runtime.shutdown()


def test_azure_monitor_trace_exporter_finds_the_resource_without_errors(
    sqlite_engine: Engine,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: the exporter used the global ProxyTracerProvider (no resource)."""
    from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

    monkeypatch.setattr(AzureMonitorTraceExporter, "_transmit", lambda *_a: None)
    monkeypatch.setattr(
        AzureMonitorTraceExporter, "_handle_transmit_from_storage", lambda *_a: None
    )
    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {}

    runtime = configure_telemetry(app, sqlite_engine, None, _CONNECTION_STRING)
    assert runtime is not None
    try:
        with caplog.at_level("ERROR"):
            with TestClient(app) as client:
                assert client.get("/ping").status_code == 200
            runtime.tracer_provider.force_flush()
    finally:
        runtime.shutdown()
    assert "Failed to derive Resource" not in caplog.text
    assert "ProxyTracerProvider" not in caplog.text
