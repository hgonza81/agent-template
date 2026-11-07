from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ExponentialHistogram,
    ExponentialHistogramDataPoint,
    Gauge,
    Histogram,
    HistogramDataPoint,
    MetricExporter,
    MetricExportResult,
    MetricsData,
    NumberDataPoint,
    PeriodicExportingMetricReader,
    Sum,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import Status
from opentelemetry.util.types import Attributes, AttributeValue

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.engine import Engine


def _route_templates(app: FastAPI) -> frozenset[str]:
    route_templates: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            route_templates.add(path)
    return frozenset(route_templates)


_SAFE_SPAN_ATTRIBUTES = frozenset(
    {
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
)
_SAFE_DATABASE_OPERATIONS = frozenset(
    {
        "ALTER",
        "BEGIN",
        "COMMIT",
        "CREATE",
        "DELETE",
        "DROP",
        "INSERT",
        "ROLLBACK",
        "SELECT",
        "UPDATE",
    }
)
_SAFE_METRIC_ATTRIBUTES = frozenset(
    {
        "db.name",
        "db.operation",
        "db.operation.name",
        "db.system",
        "http.method",
        "http.request.method",
        "http.route",
        "http.scheme",
        "http.status_code",
        "http.response.status_code",
        "network.protocol.version",
        "url.scheme",
    }
)


def _safe_attribute_value(key: str, value: AttributeValue) -> AttributeValue | None:
    if key in {"db.operation", "db.operation.name"}:
        if not isinstance(value, str):
            return None
        operation_parts = value.split(maxsplit=1)
        if not operation_parts:
            return None
        operation = operation_parts[0].upper()
        return operation if operation in _SAFE_DATABASE_OPERATIONS else None
    return value


def _filter_attributes(
    attributes: Attributes,
    allowed_attributes: frozenset[str],
    allowed_route_templates: frozenset[str],
) -> dict[str, AttributeValue]:
    return {
        key: safe_value
        for key, value in (attributes or {}).items()
        if key in allowed_attributes
        and (
            key != "http.route"
            or (isinstance(value, str) and value in allowed_route_templates)
        )
        and (safe_value := _safe_attribute_value(key, value)) is not None
    }


class PrivacyFilteringSpanExporter(SpanExporter):
    def __init__(
        self,
        exporter: SpanExporter,
        allowed_route_templates: frozenset[str] = frozenset(),
    ) -> None:
        self._exporter = exporter
        self._allowed_route_templates = allowed_route_templates

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        sanitized_spans = [
            ReadableSpan(
                name=_safe_span_name(span, self._allowed_route_templates),
                context=span.context,
                parent=span.parent,
                resource=span.resource,
                attributes=_filter_attributes(
                    span.attributes,
                    _SAFE_SPAN_ATTRIBUTES,
                    self._allowed_route_templates,
                ),
                kind=span.kind,
                status=Status(span.status.status_code),
                start_time=span.start_time,
                end_time=span.end_time,
                instrumentation_scope=span.instrumentation_scope,
            )
            for span in spans
        ]
        return self._exporter.export(sanitized_spans)

    def shutdown(self) -> None:
        self._exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._exporter.force_flush(timeout_millis)


class PrivacyFilteringMetricExporter(MetricExporter):
    def __init__(
        self,
        exporter: MetricExporter,
        allowed_route_templates: frozenset[str] = frozenset(),
    ) -> None:
        super().__init__(
            preferred_temporality=exporter._preferred_temporality,
            preferred_aggregation=exporter._preferred_aggregation,
        )
        self._exporter = exporter
        self._allowed_route_templates = allowed_route_templates

    def export(
        self,
        metrics_data: MetricsData,
        timeout_millis: float = 10000,
        **kwargs: object,
    ) -> MetricExportResult:
        return self._exporter.export(
            _sanitize_metrics_data(
                metrics_data,
                self._allowed_route_templates,
            ),
            timeout_millis=timeout_millis,
            **kwargs,
        )

    def shutdown(self, timeout_millis: float = 30000, **kwargs: object) -> None:
        self._exporter.shutdown(timeout_millis=timeout_millis, **kwargs)

    def force_flush(self, timeout_millis: float = 10000) -> bool:
        return self._exporter.force_flush(timeout_millis)


def _sanitize_metrics_data(
    metrics_data: MetricsData,
    allowed_route_templates: frozenset[str],
) -> MetricsData:
    return replace(
        metrics_data,
        resource_metrics=tuple(
            replace(
                resource_metrics,
                scope_metrics=tuple(
                    replace(
                        scope_metrics,
                        metrics=tuple(
                            replace(
                                metric,
                                data=_sanitize_metric_aggregation(
                                    metric.data,
                                    allowed_route_templates,
                                ),
                            )
                            for metric in scope_metrics.metrics
                        ),
                    )
                    for scope_metrics in resource_metrics.scope_metrics
                ),
            )
            for resource_metrics in metrics_data.resource_metrics
        ),
    )


def _sanitize_metric_attributes(
    attributes: Attributes,
    allowed_route_templates: frozenset[str],
) -> dict[str, AttributeValue]:
    return _filter_attributes(
        attributes,
        _SAFE_METRIC_ATTRIBUTES,
        allowed_route_templates,
    )


def _sanitize_number_point(
    point: NumberDataPoint,
    allowed_route_templates: frozenset[str],
) -> NumberDataPoint:
    return replace(
        point,
        attributes=_sanitize_metric_attributes(
            point.attributes,
            allowed_route_templates,
        ),
        exemplars=(),
    )


def _sanitize_histogram_point(
    point: HistogramDataPoint,
    allowed_route_templates: frozenset[str],
) -> HistogramDataPoint:
    return replace(
        point,
        attributes=_sanitize_metric_attributes(
            point.attributes,
            allowed_route_templates,
        ),
        exemplars=(),
    )


def _sanitize_exponential_histogram_point(
    point: ExponentialHistogramDataPoint,
    allowed_route_templates: frozenset[str],
) -> ExponentialHistogramDataPoint:
    return replace(
        point,
        attributes=_sanitize_metric_attributes(
            point.attributes,
            allowed_route_templates,
        ),
        exemplars=(),
    )


def _sanitize_metric_aggregation(
    data: Sum | Gauge | Histogram | ExponentialHistogram,
    allowed_route_templates: frozenset[str],
) -> Sum | Gauge | Histogram | ExponentialHistogram:
    if isinstance(data, (Sum, Gauge)):
        return replace(
            data,
            data_points=tuple(
                _sanitize_number_point(point, allowed_route_templates)
                for point in data.data_points
            ),
        )
    if isinstance(data, Histogram):
        return replace(
            data,
            data_points=tuple(
                _sanitize_histogram_point(point, allowed_route_templates)
                for point in data.data_points
            ),
        )
    return replace(
        data,
        data_points=tuple(
            _sanitize_exponential_histogram_point(point, allowed_route_templates)
            for point in data.data_points
        ),
    )


def _safe_span_name(
    span: ReadableSpan,
    allowed_route_templates: frozenset[str],
) -> str:
    attributes = span.attributes or {}
    route = attributes.get("http.route")
    if isinstance(route, str) and route in allowed_route_templates:
        method = attributes.get(
            "http.request.method",
            attributes.get("http.method", "request"),
        )
        if not isinstance(method, str):
            method = "request"
        return f"{method} {route}"
    if "db.system" in attributes or "db.system.name" in attributes:
        return "database operation"
    return "application operation"


@dataclass(slots=True)
class TelemetryRuntime:
    app: FastAPI
    sqlalchemy_instrumentor: SQLAlchemyInstrumentor
    tracer_provider: TracerProvider
    meter_provider: MeterProvider

    def shutdown(self) -> None:
        FastAPIInstrumentor.uninstrument_app(self.app)
        self.sqlalchemy_instrumentor.uninstrument()
        self.meter_provider.shutdown()
        self.tracer_provider.shutdown()


def instrument_application(
    app: FastAPI,
    engine: Engine,
    tracer_provider: TracerProvider,
    meter_provider: MeterProvider,
) -> SQLAlchemyInstrumentor:
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        http_capture_headers_server_request=[],
        http_capture_headers_server_response=[],
    )
    sqlalchemy_instrumentor = SQLAlchemyInstrumentor()
    sqlalchemy_instrumentor.instrument(
        engine=engine,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        enable_commenter=False,
        enable_attribute_commenter=False,
    )
    return sqlalchemy_instrumentor


def configure_telemetry(
    app: FastAPI,
    engine: Engine,
    endpoint: str | None,
) -> TelemetryRuntime | None:
    if endpoint is None:
        return None

    normalized_endpoint = endpoint.rstrip("/")
    allowed_route_templates = _route_templates(app)
    resource = Resource.create({"service.name": "agent-template-api"})
    tracer_provider = TracerProvider(resource=resource)
    span_exporter = PrivacyFilteringSpanExporter(
        OTLPSpanExporter(endpoint=f"{normalized_endpoint}/v1/traces"),
        allowed_route_templates,
    )
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    metric_reader = PeriodicExportingMetricReader(
        PrivacyFilteringMetricExporter(
            OTLPMetricExporter(endpoint=f"{normalized_endpoint}/v1/metrics"),
            allowed_route_templates,
        )
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    )
    sqlalchemy_instrumentor = instrument_application(
        app,
        engine,
        tracer_provider,
        meter_provider,
    )
    return TelemetryRuntime(
        app=app,
        sqlalchemy_instrumentor=sqlalchemy_instrumentor,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )
