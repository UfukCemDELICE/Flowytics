"""
Security audit tests — validates that all security hardening measures are active.

Tests:
  - Security response headers are present on all API responses
  - CORS is locked down to configured origins (not wildcard)
  - Error responses don't leak internal details (stack traces, file paths)
  - Auth-protected endpoints reject unauthenticated requests
  - Encryption infrastructure (Fernet) works correctly
"""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import get_session


# ── Shared fixtures ─────────────────────────────────────────────

@pytest.fixture
def client():
    """TestClient with no auth overrides — tests real middleware."""
    return TestClient(app, raise_server_exceptions=False)


# ── Security Headers ────────────────────────────────────────────

class TestSecurityHeaders:
    def test_health_has_security_headers(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "camera=()" in resp.headers["Permissions-Policy"]

    def test_api_has_cache_control(self, client):
        resp = client.get("/api/v1/health")
        assert "no-store" in resp.headers.get("Cache-Control", "")

    def test_correlation_id_header(self, client):
        resp = client.get("/api/v1/health")
        assert "X-Correlation-ID" in resp.headers


# ── Auth Enforcement ────────────────────────────────────────────

class TestAuthEnforcement:
    def test_me_requires_auth(self, client):
        resp = client.get("/api/v1/me")
        assert resp.status_code == 401

    def test_qbo_auth_requires_auth(self, client):
        resp = client.get("/api/v1/quickbooks/auth")
        assert resp.status_code == 401

    def test_qbo_sync_requires_auth(self, client):
        resp = client.post("/api/v1/quickbooks/sync")
        assert resp.status_code == 401

    def test_qbo_disconnect_requires_auth(self, client):
        resp = client.delete("/api/v1/quickbooks/disconnect")
        assert resp.status_code == 401

    def test_stripe_checkout_requires_auth(self, client):
        resp = client.post("/api/v1/stripe/create-checkout-session", json={
            "tier": "pro_monthly", "success_url": "http://x", "cancel_url": "http://y"
        })
        assert resp.status_code == 401

    def test_slack_install_requires_auth(self, client):
        resp = client.get("/api/v1/slack/install")
        assert resp.status_code == 401

    def test_slack_disconnect_requires_auth(self, client):
        resp = client.delete("/api/v1/slack/disconnect")
        assert resp.status_code == 401

    def test_trigger_report_requires_auth(self, client):
        resp = client.post("/api/v1/slack/trigger_monthly_report?tenant_id=abc")
        assert resp.status_code == 401


# ── Error Response Safety ───────────────────────────────────────

class TestErrorResponseSafety:
    def test_stripe_webhook_invalid_sig_no_leak(self, client):
        """Invalid Stripe webhook should not leak internal exception details."""
        mock_session = MagicMock()

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            resp = client.post(
                "/api/v1/stripe/webhook",
                content=b"fake payload",
                headers={"stripe-signature": "invalid", "Content-Type": "application/json"},
            )
            body = resp.json()
            detail = str(body.get("detail", ""))
            # Should NOT contain Python tracebacks, file paths, or module names
            assert "Traceback" not in detail
            assert ".py" not in detail
            assert "File " not in detail
        finally:
            app.dependency_overrides.clear()

    def test_qbo_callback_invalid_state_no_leak(self, client):
        """Invalid OAuth state should not reveal JWT internals."""
        mock_session = MagicMock()

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            resp = client.get("/api/v1/quickbooks/callback?code=x&realmId=y&state=invalid_jwt")
            body = resp.json()
            detail = body.get("detail", {})
            message = detail.get("message", "") if isinstance(detail, dict) else str(detail)
            # Should give generic message, not internal JWT exception text
            assert "invalid or expired" in message.lower() or "invalid" in message.lower()
            assert "decode" not in message.lower()
        finally:
            app.dependency_overrides.clear()


# ── CORS Policy ─────────────────────────────────────────────────

class TestCORSPolicy:
    def test_allowed_origin_gets_headers(self, client):
        resp = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should have CORS headers for allowed origin
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_disallowed_origin_blocked(self, client):
        resp = client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://evil-site.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should NOT have CORS headers for unknown origin
        assert resp.headers.get("access-control-allow-origin") != "https://evil-site.com"


# ── Encryption Infrastructure ───────────────────────────────────

class TestEncryptionInfrastructure:
    def test_fernet_roundtrip(self):
        """Verify Fernet can encrypt and decrypt data correctly."""
        from backend.app.integrations.quickbooks import get_fernet
        import json

        fernet = get_fernet()
        original = {"access_token": "test_token_123", "refresh_token": "refresh_456"}
        encrypted = fernet.encrypt(json.dumps(original).encode())
        decrypted = json.loads(fernet.decrypt(encrypted).decode())
        assert decrypted == original

    def test_fernet_key_stability(self):
        """Two calls to get_fernet() should produce the same key (no rotation mid-session)."""
        from backend.app.integrations.quickbooks import get_fernet

        f1 = get_fernet()
        f2 = get_fernet()
        test_data = b"stability_check"
        token = f1.encrypt(test_data)
        assert f2.decrypt(token) == test_data


# ── Middleware Configuration ────────────────────────────────────

class TestMiddlewareConfig:
    def test_security_headers_middleware_exists(self):
        from backend.app.middleware import SecurityHeadersMiddleware
        assert SecurityHeadersMiddleware is not None

    def test_correlation_id_middleware_exists(self):
        from backend.app.middleware import CorrelationIDMiddleware
        assert CorrelationIDMiddleware is not None
