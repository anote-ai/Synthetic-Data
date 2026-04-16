"""
Structured JSON logging configuration for the Synthetic Data API.
Sets up JSON-formatted log output suitable for log aggregation services.
"""
import os
import logging
import json
import traceback
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        for key in ("request_id", "user_email", "task_type", "duration_ms"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(level: str = None) -> None:
    """
    Configure JSON structured logging for the application.
    Call once at startup before creating any loggers.

    Args:
        level: Log level string (DEBUG/INFO/WARNING/ERROR).
               Defaults to LOG_LEVEL env var or INFO.
    """
    level = level or os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, level, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("urllib3", "requests", "httpx", "httpcore", "openai", "werkzeug"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info("Logging configured", extra={"level": level})
