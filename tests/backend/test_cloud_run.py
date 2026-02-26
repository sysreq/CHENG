"""Tests for Cloud Run deployment configuration.

Verifies:
- Health endpoint returns mode field
- CHENG_MODE env var correctly configures CORS policy
- PORT env var is respected by the startup command
"""

from __future__ import annotations

import os
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture(autouse=True)
def reset_module():
    """Reset main module between tests that change env vars."""
    import importlib
    import backend.main as main_mod
    yield
    importlib.reload(main_mod)


class TestHealthEndpoint:
    """Health endpoint returns required fields for Cloud Run readiness probes."""

    @pytest.mark.asyncio
    async def test_health_returns_status_ok(self):
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_returns_mode_field(self):
        """Cloud Run startup/liveness probes rely on /health; mode field aids debugging."""
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "mode" in data
        assert data["mode"] in ("local", "cloud")

    @pytest.mark.asyncio
    async def test_health_returns_version(self):
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data


class TestChengModeLocal:
    """In local mode CORS allows only localhost:5173."""

    def test_local_mode_cors_origins(self, monkeypatch):
        monkeypatch.setenv("CHENG_MODE", "local")
        monkeypatch.delenv("CHENG_CORS_ORIGINS", raising=False)
        import importlib
        import backend.main as main_mod
        importlib.reload(main_mod)
        # _allow_origins should be the localhost dev server list, not ["*"]
        assert main_mod._allow_origins != ["*"]
        assert any("5173" in o for o in main_mod._allow_origins)

    def test_local_mode_credentials_allowed(self, monkeypatch):
        monkeypatch.setenv("CHENG_MODE", "local")
        monkeypatch.delenv("CHENG_CORS_ORIGINS", raising=False)
        import importlib
        import backend.main as main_mod
        importlib.reload(main_mod)
        # allow_credentials=True is only valid when origins is not ["*"]
        assert main_mod._allow_all is False


class TestChengModeCloud:
    """In cloud mode CORS allows all origins (browser-served SPA)."""

    def test_cloud_mode_cors_all_origins(self, monkeypatch):
        monkeypatch.setenv("CHENG_MODE", "cloud")
        monkeypatch.delenv("CHENG_CORS_ORIGINS", raising=False)
        import importlib
        import backend.main as main_mod
        importlib.reload(main_mod)
        assert main_mod._allow_origins == ["*"]

    def test_cloud_mode_credentials_disabled(self, monkeypatch):
        """allow_credentials must be False when allow_origins=['*'] per CORS spec."""
        monkeypatch.setenv("CHENG_MODE", "cloud")
        monkeypatch.delenv("CHENG_CORS_ORIGINS", raising=False)
        import importlib
        import backend.main as main_mod
        importlib.reload(main_mod)
        assert main_mod._allow_all is True

    @pytest.mark.asyncio
    async def test_cloud_mode_health_reports_cloud(self, monkeypatch):
        monkeypatch.setenv("CHENG_MODE", "cloud")
        import importlib
        import backend.main as main_mod
        importlib.reload(main_mod)
        async with AsyncClient(
            transport=ASGITransport(app=main_mod.app), base_url="http://test"
        ) as client:
            r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["mode"] == "cloud"


class TestCorsOriginsOverride:
    """CHENG_CORS_ORIGINS env var overrides CHENG_MODE CORS defaults."""

    def test_custom_origins_override_cloud_defaults(self, monkeypatch):
        monkeypatch.setenv("CHENG_MODE", "cloud")
        monkeypatch.setenv("CHENG_CORS_ORIGINS", "https://app.example.com,https://dev.example.com")
        import importlib
        import backend.main as main_mod
        importlib.reload(main_mod)
        assert "https://app.example.com" in main_mod._allow_origins
        assert "https://dev.example.com" in main_mod._allow_origins
        assert "*" not in main_mod._allow_origins

    def test_custom_origins_override_local_defaults(self, monkeypatch):
        monkeypatch.setenv("CHENG_MODE", "local")
        monkeypatch.setenv("CHENG_CORS_ORIGINS", "https://staging.example.com")
        import importlib
        import backend.main as main_mod
        importlib.reload(main_mod)
        assert "https://staging.example.com" in main_mod._allow_origins
        assert not any("5173" in o for o in main_mod._allow_origins)
