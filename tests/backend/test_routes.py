"""Tests for FastAPI routes — health endpoint and design CRUD."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import AircraftDesign
from backend.routes.designs import set_storage
from backend.storage import LocalStorage


@pytest.fixture(autouse=True)
def _use_tmp_storage(tmp_path: Path):
    """Override the default storage with a temp directory for every test."""
    storage = LocalStorage(base_path=str(tmp_path))
    set_storage(storage)
    yield
    set_storage(None)  # type: ignore[arg-type]


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient for the FastAPI app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# Design CRUD
# ---------------------------------------------------------------------------


class TestDesignCRUD:
    def test_list_empty(self, client: TestClient) -> None:
        """GET /api/designs on empty storage returns empty list."""
        resp = client.get("/api/designs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_design(self, client: TestClient) -> None:
        """POST /api/designs should save and return an id."""
        design = AircraftDesign(name="My Plane")
        resp = client.post("/api/designs", json=design.model_dump())
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert len(data["id"]) > 0

    def test_create_design_assigns_uuid(self, client: TestClient) -> None:
        """POST with empty id should get a UUID assigned."""
        design = AircraftDesign(id="", name="Auto-ID Plane")
        resp = client.post("/api/designs", json=design.model_dump())
        assert resp.status_code == 201
        assert resp.json()["id"] != ""

    def test_create_design_with_id(self, client: TestClient) -> None:
        """POST with an explicit id should preserve it."""
        design = AircraftDesign(id="my-custom-id", name="Custom Plane")
        resp = client.post("/api/designs", json=design.model_dump())
        assert resp.status_code == 201
        assert resp.json()["id"] == "my-custom-id"

    def test_load_design(self, client: TestClient) -> None:
        """GET /api/designs/{id} should return the saved design."""
        design = AircraftDesign(id="load-test", name="Load Test", wing_span=1500)
        client.post("/api/designs", json=design.model_dump())

        resp = client.get("/api/designs/load-test")
        assert resp.status_code == 200
        loaded = resp.json()
        assert loaded["id"] == "load-test"
        assert loaded["name"] == "Load Test"
        assert loaded["wing_span"] == 1500

    def test_load_missing_design(self, client: TestClient) -> None:
        """GET /api/designs/{nonexistent} should return 404."""
        resp = client.get("/api/designs/nonexistent")
        assert resp.status_code == 404

    def test_delete_design(self, client: TestClient) -> None:
        """DELETE /api/designs/{id} should remove the design."""
        design = AircraftDesign(id="delete-me", name="Doomed")
        client.post("/api/designs", json=design.model_dump())

        resp = client.delete("/api/designs/delete-me")
        assert resp.status_code == 204

        # Verify it's gone
        resp = client.get("/api/designs/delete-me")
        assert resp.status_code == 404

    def test_delete_missing_design(self, client: TestClient) -> None:
        """DELETE /api/designs/{nonexistent} should return 404."""
        resp = client.delete("/api/designs/nonexistent")
        assert resp.status_code == 404

    def test_list_after_create(self, client: TestClient) -> None:
        """GET /api/designs should list saved designs."""
        for name in ["Plane A", "Plane B"]:
            d = AircraftDesign(id=name.lower().replace(" ", "-"), name=name)
            client.post("/api/designs", json=d.model_dump())

        resp = client.get("/api/designs")
        assert resp.status_code == 200
        summaries = resp.json()
        assert len(summaries) == 2
        names = {s["name"] for s in summaries}
        assert "Plane A" in names
        assert "Plane B" in names

    def test_upsert_semantics(self, client: TestClient) -> None:
        """POST with an existing id should overwrite the design."""
        design_v1 = AircraftDesign(id="upsert-id", name="Version 1", wing_span=800)
        client.post("/api/designs", json=design_v1.model_dump())

        design_v2 = AircraftDesign(id="upsert-id", name="Version 2", wing_span=1200)
        resp = client.post("/api/designs", json=design_v2.model_dump())
        assert resp.status_code == 201

        loaded = client.get("/api/designs/upsert-id").json()
        assert loaded["name"] == "Version 2"
        assert loaded["wing_span"] == 1200

    def test_design_round_trip_preserves_all_params(self, client: TestClient) -> None:
        """Save and load should preserve every parameter."""
        design = AircraftDesign(
            id="full-round-trip",
            name="Full Params",
            wing_span=1500,
            wing_chord=250,
            fuselage_preset="Pod",
            motor_config="Pusher",
            wing_mount_type="Low-Wing",
            tail_type="V-Tail",
            v_tail_dihedral=40,
            v_tail_span=300,
            print_bed_x=300,
            joint_tolerance=0.2,
        )
        client.post("/api/designs", json=design.model_dump())
        loaded = AircraftDesign(**client.get("/api/designs/full-round-trip").json())
        assert loaded == design
