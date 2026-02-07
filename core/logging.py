# core/logging.py

import structlog
from structlog.processors import JSONRenderer, TimeStamper, add_log_level
from structlog.stdlib import add_logger_name


def configure_logging(log_level: str = "INFO"):
    """Configure structured logging for STRATEGOS."""
    structlog.configure(
        processors=[
            add_log_level,
            add_logger_name,
            TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    """Get a structured logger instance."""
    return structlog.get_logger(name)
