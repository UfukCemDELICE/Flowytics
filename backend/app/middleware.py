"""
FastAPI middleware that assigns a unique correlation ID to every request.

The correlation ID is:
  - Generated fresh (UUID4) if `X-Correlation-ID` header is absent
  - Forwarded if the header is present (for tracing across upstream services)
  - Stored in a ContextVar so all loggers in the request context include it
  - Returned in the response `X-Correlation-ID` header
"""

import uuid
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.app.logging_config import correlation_id_var

logger = logging.getLogger(__name__)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Injects correlation IDs and logs request lifecycle events."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract or generate correlation ID
        cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        token = correlation_id_var.set(cid)

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
            logger.error(
                f"{request.method} {request.url.path} failed after {duration_ms}ms",
                extra={"event": "request_error", "duration_ms": duration_ms},
                exc_info=True,
            )
            raise
        finally:
            correlation_id_var.reset(token)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 1)

        # Response header for downstream tracing
        response.headers["X-Correlation-ID"] = cid

        # Skip noisy health checks from access logs
        if request.url.path not in ("/api/v1/health", "/docs", "/openapi.json", "/"):
            logger.info(
                f"{request.method} {request.url.path} → {response.status_code} ({duration_ms}ms)",
                extra={
                    "event": "request_completed",
                    "duration_ms": duration_ms,
                },
            )
            with open("response_debug.log", "a") as f:
                f.write(f"MIDDLEWARE: {request.method} {request.url.path} -> {response.status_code}\n")

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects standard security response headers (OWASP best practices).
    Applied as the outermost middleware so headers are present on every response.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Control referrer information leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Disable unnecessary browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # API responses should not be cached by default
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        return response
