import logging.config
from typing import Any

# Provider and HTTP client libraries log request bodies (the prompt), headers,
# and URLs at DEBUG. Pin them to WARNING whatever the root level is.
_QUIET_LIBRARIES = ("openai", "httpx", "httpcore", "azure", "msal")


def configure_logging(log_level: str) -> None:
    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "format": "%(message)s",
            }
        },
        "handlers": {
            "request_stream": {
                "class": "logging.StreamHandler",
                "formatter": "structured",
                "stream": "ext://sys.stdout",
            }
        },
        "loggers": {
            "agent_template_api.requests": {
                "handlers": ["request_stream"],
                "level": log_level,
                "propagate": False,
            },
            **{name: {"level": "WARNING"} for name in _QUIET_LIBRARIES},
        },
    }
    logging.config.dictConfig(config)
