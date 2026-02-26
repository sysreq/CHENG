"""Tests for GET /api/info -- deployment mode endpoint.

Issue #152 (Mode badge), #149 (CHENG_MODE toggle)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient for the FastAPI app."""
    return TestClient(app)


class TestInfoEndpoint:
    """Tests for /api/info endpoint."""

    def test_returns_local_by_default(self, client: TestClient, monkeypatch) -> None:
        """Endpoint returns mode=local when CHENG_MODE is not set."""
        monkeypatch.delenv("CHENG_MODE", raising=False)
        resp = client.get("/api/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "local"
        assert "version" in data

    def test_returns_local_when_env_is_local(self, client: TestClient, monkeypatch) -> None:
        """Endpoint returns mode=local when CHENG_MODE=local."""
        monkeypatch.setenv("CHENG_MODE", "local")
        resp = client.get("/api/info")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "local"

    def test_returns_cloud_when_env_is_cloud(self, client: TestClient, monkeypatch) -> None:
        """Endpoint returns mode=cloud when CHENG_MODE=cloud."""
        monkeypatch.setenv("CHENG_MODE", "cloud")
        resp = client.get("/api/info")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "cloud"

    def test_case_insensitive_env(self, client: TestClient, monkeypatch) -> None:
        """CHENG_MODE is normalized to lowercase."""
        monkeypatch.setenv("CHENG_MODE", "CLOUD")
        resp = client.get("/api/info")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "cloud"

    def test_invalid_mode_falls_back_to_local(self, client: TestClient, monkeypatch) -> None:
        """Unknown CHENG_MODE value falls back to local."""
        monkeypatch.setenv("CHENG_MODE", "staging")
        resp = client.get("/api/info")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "local"

    def test_whitespace_in_env_is_stripped(self, client: TestClient, monkeypatch) -> None:
        """Leading/trailing whitespace in CHENG_MODE is stripped."""
        monkeypatch.setenv("CHENG_MODE", "  cloud  ")
        resp = client.get("/api/info")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "cloud"

    def test_version_field_matches_app_version(self, client: TestClient, monkeypatch) -> None:
        """Version field matches the FastAPI app version from main.py."""
        monkeypatch.delenv("CHENG_MODE", raising=False)
        resp = client.get("/api/info")
        data = resp.json()
        assert "version" in data
        assert isinstance(data["version"], str)
        assert data["version"] == app.version
