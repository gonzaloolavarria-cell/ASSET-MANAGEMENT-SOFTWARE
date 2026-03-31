"""Security tests — API endpoint protection and response safety.

Tests CORS configuration, authentication gaps on destructive endpoints,
error response sanitization, and route structure.
Uses FastAPI TestClient — no server startup needed.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app

pytestmark = pytest.mark.security

client = TestClient(app)


class TestCORSConfiguration:
    """Verify CORS is configured with explicit origins (not wildcard)."""

    def test_cors_no_wildcard(self):
        """CORS should use explicit allowed origins, not wildcard.

        Origins are loaded from the AMS_ALLOWED_ORIGINS env var via
        settings.ALLOWED_ORIGINS — defaults to localhost dev servers.
        """
        from api.main import create_app
        test_app = create_app()
        # Find the CORS middleware
        cors_middleware = None
        for m in test_app.user_middleware:
            if "CORSMiddleware" in str(m.cls):
                cors_middleware = m
                break
        assert cors_middleware is not None, "CORS middleware should be configured"
        origins = cors_middleware.kwargs.get("allow_origins", [])
        assert "*" not in origins, \
            "CORS should NOT use wildcard — should use explicit allowed origins"
        assert len(origins) > 0, "At least one allowed origin should be configured"


class TestDestructiveEndpointsAuth:
    """Verify destructive endpoints require X-Admin-Key authentication."""

    def test_admin_reset_requires_auth(self):
        """DELETE /admin/reset-database should require X-Admin-Key header."""
        routes = [r.path for r in app.routes]
        admin_reset = "/api/v1/admin/reset-database"
        assert admin_reset in routes, "admin reset route should exist"
        # Without the header, the endpoint should reject the request
        resp = client.delete(admin_reset)
        assert resp.status_code in (403, 422, 503), \
            "Admin reset should reject requests without X-Admin-Key header"

    def test_admin_seed_requires_auth(self):
        """POST /admin/seed-database should require X-Admin-Key header."""
        routes = [r.path for r in app.routes]
        admin_seed = "/api/v1/admin/seed-database"
        assert admin_seed in routes, "admin seed route should exist"
        # Without the header, the endpoint should reject the request
        resp = client.post(admin_seed)
        assert resp.status_code in (403, 422, 503), \
            "Admin seed should reject requests without X-Admin-Key header"

    def test_sap_approve_no_auth_guard(self):
        """SECURITY FINDING: SAP approval endpoint has no authentication."""
        routes = [r.path for r in app.routes]
        sap_routes = [r for r in routes if "approve" in r]
        assert len(sap_routes) > 0, "SAP approve route should exist"


class TestEndpointResponseSafety:
    """Verify endpoints don't leak sensitive information."""

    def test_health_no_sensitive_data(self):
        """Health endpoint should only return status."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"status": "ok"}
        # Should not contain any system details
        text = resp.text
        assert "ANTHROPIC" not in text
        assert "DATABASE" not in text

    def test_root_no_internal_paths(self):
        """Root endpoint should not expose filesystem paths."""
        resp = client.get("/")
        assert resp.status_code == 200
        text = resp.text
        assert "C:\\" not in text
        assert "/home/" not in text
        assert "/Users/" not in text

    def test_unknown_route_returns_404(self):
        """Non-existent route should return 404, not 500."""
        resp = client.get("/api/v1/nonexistent-endpoint-xyz")
        assert resp.status_code == 404

    def test_error_response_no_stack_trace(self):
        """Invalid request should not expose Python traceback."""
        resp = client.post(
            "/api/v1/sap/generate-upload",
            content="not-valid-json",
            headers={"Content-Type": "application/json"},
        )
        text = resp.text
        assert "Traceback" not in text
        assert "File \"" not in text


class TestRouteStructure:
    """Verify all routes follow the expected pattern."""

    def test_api_v1_prefix_on_all_routers(self):
        """All business routes should be under /api/v1."""
        excluded = {"/", "/health", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        # /field is a static file mount for the GAP-W03 field PWA — not a business API route
        business_routes = [r for r in routes if r not in excluded and not r.startswith("/field")]
        for route in business_routes:
            assert route.startswith("/api/v1"), \
                f"Route {route} is not under /api/v1 prefix"

    def test_post_without_json_returns_422(self):
        """POST with non-JSON body should return 422, not 500."""
        resp = client.post(
            "/api/v1/admin/feedback",
            content="plain text body",
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code == 422
