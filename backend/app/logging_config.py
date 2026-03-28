"""
Centralized structured logging configuration for Flowytics.

Provides:
  - JSON-formatted log output for production (machine-parseable)
  - Human-readable colored output for development
  - Request correlation IDs via contextvars
  - Consistent field extraction (tenant_id, service, etc.)

Usage:
  Called once at app startup via `setup_logging()`.
  All modules continue to use `logging.getLogger(__name__)` — no changes needed.
  Structured context is passed via `extra={}` or the correlation ID middleware.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from backend.app.config import get_settings

# ── Correlation ID context ──────────────────────────────────────
# Set per-request by the middleware, available to all loggers in that async context.
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


class JSONFormatter(logging.Formatter):
    """
    Produces one JSON object per log line. Machine-parseable, compatible with
    ELK, Datadog, CloudWatch, and any log aggregator.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get("-"),
        }

        # Pull structured fields from `extra` if provided
        for key in ("tenant_id", "org_id", "service", "event", "provider",
                     "sync_status", "model", "channel", "duration_ms",
                     "snapshots_created", "error_type"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include stack info if present
        if record.stack_info:
            log_entry["stack_info"] = record.stack_info

        return json.dumps(log_entry, default=str)


class DevFormatter(logging.Formatter):
    """
    Human-readable colored formatter for local development.
    Shows timestamp, level, logger name, correlation ID, and message.
    """

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[1;31m",  # Bold Red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        cid = correlation_id_var.get("-")
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S")

        # Collect extra structured fields for inline display
        extras = []
        for key in ("tenant_id", "org_id", "service", "event", "provider",
                     "duration_ms", "error_type"):
            value = getattr(record, key, None)
            if value is not None:
                extras.append(f"{key}={value}")
        extra_str = f" [{', '.join(extras)}]" if extras else ""

        base = f"{color}{ts} {record.levelname:<8}{self.RESET} [{cid[:8]}] {record.name}: {record.getMessage()}{extra_str}"

        if record.exc_info and record.exc_info[0] is not None:
            base += "\n" + self.formatException(record.exc_info)

        return base


def setup_logging(*, force_json: bool = False) -> None:
    """
    Configure the root logger for the entire application.

    Args:
        force_json: If True, always use JSON formatter (for CI/testing).
                    Otherwise, auto-detects: JSON if LOG_FORMAT=json env var or
                    non-TTY stdout, else dev-friendly colored output.
    """
    settings = get_settings()
    log_level_str = getattr(settings, "LOG_LEVEL", "INFO").upper()
    log_format = getattr(settings, "LOG_FORMAT", "auto").lower()

    level = getattr(logging, log_level_str, logging.INFO)

    # Determine formatter
    use_json = force_json or log_format == "json" or (
        log_format == "auto" and not sys.stderr.isatty()
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter() if use_json else DevFormatter())

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Remove any existing handlers (prevents duplicate logs on reload)
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for noisy_logger in (
        "httpx", "httpcore", "urllib3", "asyncio",
        "sqlalchemy.engine", "apscheduler",
        "slack_bolt", "slack_sdk",
    ):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # Log that we're set up
    logging.getLogger("backend.app.logging_config").info(
        "Logging initialized",
        extra={"event": "logging_init", "service": "flowytics", "log_level": log_level_str, "format": "json" if use_json else "dev"},
    )
