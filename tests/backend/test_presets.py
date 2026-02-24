"""Tests for custom presets CRUD — GET/POST/DELETE /api/presets."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import AircraftDesign
from backend.routes.presets import set_storage
from backend.storage import LocalStorage


@pytest.fixture(autouse=True)
def _use_tmp_preset_storage(tmp_path: Path):
    """Override the default preset storage with a temp directory for every test."""
    storage = LocalStorage(base_path=str(tmp_path))
    set_storage(storage)
    yield
    set_storage(None)


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient for the FastAPI app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# List presets
# ---------------------------------------------------------------------------


class TestListPresets:
    def test_list_empty(self, client: TestClient) -> None:
        """GET /api/presets on empty storage returns empty list."""
        resp = client.get("/api/presets")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_save(self, client: TestClient) -> None:
        """After saving a preset, list should include it."""
        design = AircraftDesign(name="My Plane").model_dump()
        client.post("/api/presets", json={"name": "Trainer V2", "design": design})

        resp = client.get("/api/presets")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["name"] == "Trainer V2"
        assert "id" in items[0]
        assert "createdAt" in items[0]

    def test_list_multiple_sorted(self, client: TestClient) -> None:
        """Multiple presets returned, most recent first."""
        design = AircraftDesign().model_dump()
        client.post("/api/presets", json={"name": "First", "design": design})
        client.post("/api/presets", json={"name": "Second", "design": design})

        resp = client.get("/api/presets")
        items = resp.json()
        assert len(items) == 2
        # Most recent first (by file mtime)
        assert items[0]["name"] == "Second"
        assert items[1]["name"] == "First"


# ---------------------------------------------------------------------------
# Save presets
# ---------------------------------------------------------------------------


class TestSavePreset:
    def test_save_returns_id_and_name(self, client: TestClient) -> None:
        """POST /api/presets should return id and name."""
        design = AircraftDesign(name="Test Plane").model_dump()
        resp = client.post("/api/presets", json={"name": "My Preset", "design": design})
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["name"] == "My Preset"
        assert len(data["id"]) > 0

    def test_save_generates_unique_ids(self, client: TestClient) -> None:
        """Each save should generate a unique UUID."""
        design = AircraftDesign().model_dump()
        resp1 = client.post("/api/presets", json={"name": "P1", "design": design})
        resp2 = client.post("/api/presets", json={"name": "P2", "design": design})
        assert resp1.json()["id"] != resp2.json()["id"]

    def test_save_preserves_design_data(self, client: TestClient) -> None:
        """Saved preset should contain the full design parameters."""
        design = AircraftDesign(wing_span=1500, name="Big Plane").model_dump()
        resp = client.post("/api/presets", json={"name": "Big Preset", "design": design})
        preset_id = resp.json()["id"]

        # Load it back
        resp2 = client.get(f"/api/presets/{preset_id}")
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["wing_span"] == 1500
        assert data["preset_name"] == "Big Preset"


# ---------------------------------------------------------------------------
# Get single preset
# ---------------------------------------------------------------------------


class TestGetPreset:
    def test_get_existing(self, client: TestClient) -> None:
        """GET /api/presets/{id} returns full preset data."""
        design = AircraftDesign(wing_chord=250).model_dump()
        resp = client.post("/api/presets", json={"name": "Chord Test", "design": design})
        preset_id = resp.json()["id"]

        resp2 = client.get(f"/api/presets/{preset_id}")
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["wing_chord"] == 250
        assert data["name"] == "Chord Test"

    def test_get_nonexistent_returns_404(self, client: TestClient) -> None:
        """GET /api/presets/{id} with unknown id returns 404."""
        resp = client.get("/api/presets/nonexistent-id")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete presets
# ---------------------------------------------------------------------------


class TestDeletePreset:
    def test_delete_existing(self, client: TestClient) -> None:
        """DELETE /api/presets/{id} should remove the preset."""
        design = AircraftDesign().model_dump()
        resp = client.post("/api/presets", json={"name": "To Delete", "design": design})
        preset_id = resp.json()["id"]

        resp2 = client.delete(f"/api/presets/{preset_id}")
        assert resp2.status_code == 204

        # Verify it's gone
        resp3 = client.get(f"/api/presets/{preset_id}")
        assert resp3.status_code == 404

    def test_delete_nonexistent_returns_404(self, client: TestClient) -> None:
        """DELETE /api/presets/{id} with unknown id returns 404."""
        resp = client.delete("/api/presets/nonexistent-id")
        assert resp.status_code == 404

    def test_delete_removes_from_list(self, client: TestClient) -> None:
        """After deleting, preset should not appear in list."""
        design = AircraftDesign().model_dump()
        resp = client.post("/api/presets", json={"name": "Temp", "design": design})
        preset_id = resp.json()["id"]

        client.delete(f"/api/presets/{preset_id}")
        resp2 = client.get("/api/presets")
        assert len(resp2.json()) == 0


# ---------------------------------------------------------------------------
# CamelCase serialization
# ---------------------------------------------------------------------------


class TestPresetSerialization:
    def test_list_returns_camel_case(self, client: TestClient) -> None:
        """Preset list should use camelCase keys (createdAt, not created_at)."""
        design = AircraftDesign().model_dump()
        client.post("/api/presets", json={"name": "Camel Test", "design": design})

        resp = client.get("/api/presets")
        item = resp.json()[0]
        assert "createdAt" in item
        assert "created_at" not in item

    def test_save_accepts_snake_case(self, client: TestClient) -> None:
        """POST body with snake_case design fields should be accepted."""
        resp = client.post("/api/presets", json={
            "name": "Snake Test",
            "design": {
                "wing_span": 1200,
                "wing_chord": 200,
                "name": "Snake Plane",
            },
        })
        assert resp.status_code == 201

    def test_save_accepts_camel_case(self, client: TestClient) -> None:
        """POST body with camelCase design fields should also be accepted."""
        resp = client.post("/api/presets", json={
            "name": "Camel Test",
            "design": {
                "wingSpan": 1200,
                "wingChord": 200,
                "name": "Camel Plane",
            },
        })
        assert resp.status_code == 201
