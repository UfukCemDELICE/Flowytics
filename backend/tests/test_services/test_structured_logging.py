"""
Tests for the structured logging system.

Covers:
  - JSONFormatter produces valid JSON with required fields
  - DevFormatter produces human-readable output
  - Extra structured fields are captured
  - Correlation ID is included from ContextVar
  - CorrelationIDMiddleware injects and returns correlation IDs
  - setup_logging configures the root logger
"""

import json
import logging
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app.logging_config import (
    JSONFormatter,
    DevFormatter,
    correlation_id_var,
    setup_logging,
)
from backend.app.main import app


# ── JSONFormatter ───────────────────────────────────────────────

class TestJSONFormatter:
    def _make_record(self, msg="test message", level=logging.INFO, **extra):
        logger = logging.getLogger("test.structured")
        record = logger.makeRecord(
            name="test.structured",
            level=level,
            fn="test_file.py",
            lno=42,
            msg=msg,
            args=(),
            exc_info=None,
        )
        for k, v in extra.items():
            setattr(record, k, v)
        return record

    def test_produces_valid_json(self):
        formatter = JSONFormatter()
        record = self._make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_required_fields_present(self):
        formatter = JSONFormatter()
        record = self._make_record("hello world")
        parsed = json.loads(formatter.format(record))
        assert parsed["message"] == "hello world"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.structured"
        assert "timestamp" in parsed
        assert "correlation_id" in parsed

    def test_extra_fields_captured(self):
        formatter = JSONFormatter()
        record = self._make_record(
            "sync failed",
            tenant_id="t-123",
            provider="quickbooks",
            error_type="token_expired",
        )
        parsed = json.loads(formatter.format(record))
        assert parsed["tenant_id"] == "t-123"
        assert parsed["provider"] == "quickbooks"
        assert parsed["error_type"] == "token_expired"

    def test_extra_fields_absent_when_not_provided(self):
        formatter = JSONFormatter()
        record = self._make_record("simple message")
        parsed = json.loads(formatter.format(record))
        assert "tenant_id" not in parsed
        assert "provider" not in parsed

    def test_correlation_id_from_contextvar(self):
        formatter = JSONFormatter()
        token = correlation_id_var.set("req-abc-123")
        try:
            record = self._make_record("with correlation")
            parsed = json.loads(formatter.format(record))
            assert parsed["correlation_id"] == "req-abc-123"
        finally:
            correlation_id_var.reset(token)

    def test_exception_info_included(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            record = self._make_record("error occurred")
            record.exc_info = sys.exc_info()
            parsed = json.loads(formatter.format(record))
            assert "exception" in parsed
            assert "ValueError" in parsed["exception"]

    def test_duration_ms_captured(self):
        formatter = JSONFormatter()
        record = self._make_record("request completed", duration_ms=42.5)
        parsed = json.loads(formatter.format(record))
        assert parsed["duration_ms"] == 42.5


# ── DevFormatter ────────────────────────────────────────────────

class TestDevFormatter:
    def test_produces_human_readable(self):
        formatter = DevFormatter()
        logger = logging.getLogger("test.dev")
        record = logger.makeRecord(
            name="test.dev", level=logging.WARNING, fn="f.py", lno=1,
            msg="something happened", args=(), exc_info=None,
        )
        output = formatter.format(record)
        assert "WARNING" in output
        assert "test.dev" in output
        assert "something happened" in output

    def test_extra_fields_in_brackets(self):
        formatter = DevFormatter()
        logger = logging.getLogger("test.dev")
        record = logger.makeRecord(
            name="test.dev", level=logging.INFO, fn="f.py", lno=1,
            msg="sync done", args=(), exc_info=None,
        )
        setattr(record, "tenant_id", "t-456")
        setattr(record, "provider", "quickbooks")
        output = formatter.format(record)
        assert "tenant_id=t-456" in output
        assert "provider=quickbooks" in output


# ── Correlation ID Middleware ───────────────────────────────────

class TestCorrelationIDMiddleware:
    def test_generates_correlation_id(self):
        """Response should include X-Correlation-ID header."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        cid = response.headers.get("X-Correlation-ID")
        assert cid is not None
        assert len(cid) == 36  # UUID4 format

    def test_forwards_existing_correlation_id(self):
        """If request has X-Correlation-ID, it should be forwarded."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/v1/health",
            headers={"X-Correlation-ID": "my-trace-id-123"},
        )
        assert response.headers.get("X-Correlation-ID") == "my-trace-id-123"


# ── setup_logging ───────────────────────────────────────────────

class TestSetupLogging:
    def test_configures_root_logger(self):
        """setup_logging should add a handler to the root logger."""
        setup_logging(force_json=True)
        root = logging.getLogger()
        assert len(root.handlers) >= 1
        # Formatter should be JSONFormatter
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_dev_mode(self):
        """With LOG_FORMAT=dev, should use DevFormatter."""
        with patch("backend.app.logging_config.get_settings") as mock:
            mock_settings = MagicMock()
            mock_settings.LOG_LEVEL = "DEBUG"
            mock_settings.LOG_FORMAT = "dev"
            mock.return_value = mock_settings
            setup_logging()
            root = logging.getLogger()
            assert isinstance(root.handlers[0].formatter, DevFormatter)

    def test_noisy_loggers_quieted(self):
        """Third-party loggers should be set to WARNING or above."""
        setup_logging()
        assert logging.getLogger("httpx").level >= logging.WARNING
        assert logging.getLogger("sqlalchemy.engine").level >= logging.WARNING
        assert logging.getLogger("apscheduler").level >= logging.WARNING


# ── Integration: structured log output from real services ───────

def test_structured_log_from_sync_module():
    """Verify that a logger in the sync module outputs structured JSON."""
    setup_logging(force_json=True)
    logger = logging.getLogger("backend.app.services.sync")

    # Capture output
    handler = logging.getLogger().handlers[0]
    formatter = handler.formatter

    record = logger.makeRecord(
        name="backend.app.services.sync",
        level=logging.ERROR,
        fn="sync.py",
        lno=88,
        msg="QBO token expired during sync",
        args=(),
        exc_info=None,
    )
    setattr(record, "tenant_id", "tenant-xyz")
    setattr(record, "error_type", "token_expired")
    setattr(record, "provider", "quickbooks")

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["message"] == "QBO token expired during sync"
    assert parsed["tenant_id"] == "tenant-xyz"
    assert parsed["error_type"] == "token_expired"
    assert parsed["provider"] == "quickbooks"
    assert parsed["logger"] == "backend.app.services.sync"
