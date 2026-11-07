import logging.config
from typing import Any


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
            }
        },
    }
    logging.config.dictConfig(config)
