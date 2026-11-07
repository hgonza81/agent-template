import logging

from agent_template_api.logging_config import configure_logging


def test_configure_logging_sets_level_formatter_handler_and_propagation() -> None:
    logger = logging.getLogger("agent_template_api.requests")

    try:
        configure_logging("DEBUG")

        assert logger.level == logging.DEBUG
        assert logger.propagate is False
        assert len(logger.handlers) == 1
        assert logger.handlers[0].formatter is not None
        assert logger.handlers[0].formatter._fmt == "%(message)s"
    finally:
        configure_logging("INFO")
