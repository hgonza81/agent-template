import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from importlib.metadata import version
from time import perf_counter
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from agent_template_api.agent import (
    AgentError,
    AgentTimeoutError,
    ChatAgent,
    get_chat_agent,
)
from agent_template_api.auth import TokenIdentity, get_current_identity
from agent_template_api.chat_limits import (
    ClientDisconnectedError,
    ConcurrencyLimiter,
    RateLimiter,
    run_until_disconnect,
)
from agent_template_api.conversations import ensure_thread_id
from agent_template_api.database import create_database_engine
from agent_template_api.logging_config import configure_logging
from agent_template_api.settings import get_settings
from agent_template_api.subscriptions import delete_account, provision_subscription
from agent_template_api.telemetry import TelemetryRuntime, configure_telemetry

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("agent_template_api.requests")
database_engine = create_database_engine(settings)
chat_concurrency = ConcurrencyLimiter(settings.chat_max_concurrent_requests)
chat_rate_limiter = RateLimiter(settings.chat_rate_limit_per_minute)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    get_chat_agent()  # fail at startup if the configured provider is unusable
    try:
        yield
    finally:
        telemetry_runtime = getattr(application.state, "telemetry_runtime", None)
        if isinstance(telemetry_runtime, TelemetryRuntime):
            telemetry_runtime.shutdown()


class ErrorResponse(BaseModel):
    detail: str
    request_id: str


class SubscriptionResponse(BaseModel):
    id: UUID
    started_at: datetime
    email: str | None = None


class ChatMessageRequest(BaseModel):
    # Only the message is accepted; user, subscription, agent, and provider
    # thread identifiers are server-owned and rejected if supplied.
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=settings.chat_max_message_chars)


class ChatMessageResponse(BaseModel):
    reply: str


app = FastAPI(
    title="Agent Template API",
    version=version("agent-template-api"),
    description="API for the Agent Template application.",
    lifespan=lifespan,
)


def get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if request_id is None:
        supplied_request_id = request.headers.get("X-Request-ID", "")
        try:
            request_id = str(UUID(supplied_request_id))
        except ValueError:
            request_id = str(uuid4())
        request.state.request_id = request_id
    return request_id


def record_provider_error(request: Request, error: BaseException) -> None:
    """Keep only the provider failure's class name and HTTP status."""
    if not isinstance(error, AgentError):
        return
    request.state.provider_error = error
    span = trace.get_current_span()
    if error.provider_error_type is not None:
        span.set_attribute("provider.error_type", error.provider_error_type)
    if error.provider_status is not None:
        span.set_attribute("provider.status_code", error.provider_status)


@app.middleware("http")
async def log_request(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    request_id = get_request_id(request)
    trace.get_current_span().set_attribute("request.id", request_id)
    started_at = perf_counter()
    request.state.error_category = None
    request.state.provider_error = None

    try:
        response = await call_next(request)
    except Exception:
        request.state.error_category = "internal_error"
        response = JSONResponse(
            status_code=500,
            content=ErrorResponse(
                detail="Internal server error",
                request_id=request_id,
            ).model_dump(),
        )

    response.headers["X-Request-ID"] = request_id
    route = request.scope.get("route")
    event: dict[str, str | int | float] = {
        "event": "api.request",
        "request_id": request_id,
        "method": request.method,
        "route": getattr(route, "path", "unmatched"),
        "status_code": response.status_code,
        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
    }
    if response.status_code >= 400:
        event["error_category"] = request.state.error_category or "http_error"
    provider_error = request.state.provider_error
    if provider_error is not None:
        if provider_error.provider_error_type is not None:
            event["provider_error_type"] = provider_error.provider_error_type
        if provider_error.provider_status is not None:
            event["provider_status"] = provider_error.provider_status
    logger.log(
        logging.WARNING if response.status_code >= 500 else logging.INFO,
        json.dumps(event, separators=(",", ":"), sort_keys=True),
    )
    return response


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(
    request: Request,
    error: StarletteHTTPException,
) -> JSONResponse:
    request.state.error_category = "http_error"
    details = {
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not found",
        405: "Method not allowed",
        409: "Conflict",
        422: "Invalid request",
        429: "Too many requests",
        499: "Client closed request",
        503: "Service unavailable",
        504: "Gateway timeout",
    }
    safe_headers: dict[str, str] = {}
    if error.headers:
        allowed_methods = {
            "DELETE",
            "GET",
            "HEAD",
            "OPTIONS",
            "PATCH",
            "POST",
            "PUT",
        }
        allow = error.headers.get("Allow")
        if allow is not None and all(
            method.strip() in allowed_methods for method in allow.split(",")
        ):
            safe_headers["Allow"] = allow
        retry_after = error.headers.get("Retry-After")
        if retry_after is not None and retry_after.isdecimal():
            safe_headers["Retry-After"] = retry_after
    return JSONResponse(
        status_code=error.status_code,
        content=ErrorResponse(
            detail=details.get(error.status_code, "Request failed"),
            request_id=get_request_id(request),
        ).model_dump(),
        headers=safe_headers,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    request.state.error_category = "request_validation_error"
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            detail="Invalid request",
            request_id=get_request_id(request),
        ).model_dump(),
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    expose_headers=["X-Request-ID"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/api/v1/health/ready",
    responses={
        503: {
            "model": ErrorResponse,
            "description": "A required dependency is unavailable",
        }
    },
)
def health_ready() -> dict[str, str]:
    try:
        with database_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Service unavailable",
        ) from error

    return {"status": "ok"}


@app.get(
    "/api/v1/me/subscription",
    response_model=SubscriptionResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid token"},
        403: {"model": ErrorResponse, "description": "Token lacks the required scope"},
        503: {
            "model": ErrorResponse,
            "description": "Identity provider or database unavailable",
        },
    },
)
def get_my_subscription(
    identity: Annotated[TokenIdentity, Depends(get_current_identity)],
) -> SubscriptionResponse:
    try:
        subscription = provision_subscription(database_engine, identity)
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Service unavailable") from error
    return SubscriptionResponse(
        id=subscription.id,
        started_at=subscription.started_at,
        email=subscription.email_snapshot,
    )


@app.delete(
    "/api/v1/me",
    status_code=204,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid token"},
        403: {"model": ErrorResponse, "description": "Token lacks the required scope"},
        503: {"model": ErrorResponse, "description": "A dependency is unavailable"},
        504: {"model": ErrorResponse, "description": "The provider timed out"},
    },
)
async def delete_my_account(
    request: Request,
    identity: Annotated[TokenIdentity, Depends(get_current_identity)],
    agent: Annotated[ChatAgent, Depends(get_chat_agent)],
) -> Response:
    try:
        async with asyncio.timeout(settings.chat_timeout_seconds):
            await delete_account(database_engine, identity, agent.delete_thread)
    except (TimeoutError, AgentTimeoutError) as error:
        record_provider_error(request, error)
        raise HTTPException(status_code=504) from error
    except (SQLAlchemyError, AgentError) as error:
        record_provider_error(request, error)
        raise HTTPException(status_code=503) from error
    return Response(status_code=204)


@app.post(
    "/api/v1/chat/messages",
    response_model=ChatMessageResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid token"},
        403: {"model": ErrorResponse, "description": "Token lacks the required scope"},
        422: {"model": ErrorResponse, "description": "Invalid or oversized message"},
        429: {
            "model": ErrorResponse,
            "description": "Rate or concurrency limit reached; see Retry-After",
        },
        499: {"model": ErrorResponse, "description": "Client disconnected"},
        503: {"model": ErrorResponse, "description": "A dependency is unavailable"},
        504: {"model": ErrorResponse, "description": "The agent timed out"},
    },
)
async def send_chat_message(
    payload: ChatMessageRequest,
    request: Request,
    identity: Annotated[TokenIdentity, Depends(get_current_identity)],
    agent: Annotated[ChatAgent, Depends(get_chat_agent)],
) -> ChatMessageResponse:
    retry_after = chat_rate_limiter.check(f"{identity.issuer}\n{identity.subject}")
    if retry_after is not None:
        raise HTTPException(status_code=429, headers={"Retry-After": str(retry_after)})
    if not chat_concurrency.try_acquire():
        raise HTTPException(status_code=429, headers={"Retry-After": "1"})

    async def converse() -> str:
        subscription = await run_in_threadpool(
            provision_subscription, database_engine, identity
        )
        thread_id = await ensure_thread_id(
            database_engine, subscription.id, agent.create_thread
        )
        return await agent.send_message(thread_id, payload.message)

    try:
        async with asyncio.timeout(settings.chat_timeout_seconds):
            reply = await run_until_disconnect(request, converse())
    except (TimeoutError, AgentTimeoutError) as error:
        record_provider_error(request, error)
        raise HTTPException(status_code=504) from error
    except ClientDisconnectedError as error:
        raise HTTPException(status_code=499) from error
    except (SQLAlchemyError, AgentError) as error:
        record_provider_error(request, error)
        raise HTTPException(status_code=503) from error
    finally:
        chat_concurrency.release()
    return ChatMessageResponse(reply=reply)


app.state.telemetry_runtime = configure_telemetry(
    app,
    database_engine,
    (
        str(settings.otel_exporter_otlp_endpoint)
        if settings.otel_exporter_otlp_endpoint is not None
        else None
    ),
    (
        settings.applicationinsights_connection_string.get_secret_value()
        if settings.applicationinsights_connection_string is not None
        else None
    ),
)
