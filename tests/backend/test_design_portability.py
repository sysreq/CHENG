"""Tests for design import/export portability endpoints (Issue #156).

Covers:
  POST /api/designs/import  — Upload a .cheng JSON file
  GET  /api/designs/{id}/download — Download a design as a .cheng JSON file
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import AircraftDesign
from backend.routes.designs import set_storage
from backend.storage import LocalStorage, MemoryStorage


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
# POST /api/designs/import
# ---------------------------------------------------------------------------


class TestImportDesign:
    def test_import_valid_design(self, client: TestClient) -> None:
        """Import a valid .cheng file; should save and return a new id."""
        design = AircraftDesign(name="Imported Plane", wing_span=1400)
        json_bytes = json.dumps(design.model_dump()).encode("utf-8")

        resp = client.post(
            "/api/designs/import",
            files={"file": ("my_plane.cheng", io.BytesIO(json_bytes), "application/json")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert len(data["id"]) > 0

    def test_import_assigns_new_uuid(self, client: TestClient) -> None:
        """Imported design should receive a fresh UUID even if original had one."""
        design = AircraftDesign(id="original-id", name="Portable Plane")
        json_bytes = json.dumps(design.model_dump()).encode("utf-8")

        resp = client.post(
            "/api/designs/import",
            files={"file": ("plane.cheng", io.BytesIO(json_bytes), "application/json")},
        )
        assert resp.status_code == 201
        new_id = resp.json()["id"]
        # Must not reuse the original id
        assert new_id != "original-id"

    def test_import_is_loadable(self, client: TestClient) -> None:
        """After import, the design should be retrievable via GET /api/designs/{id}."""
        design = AircraftDesign(name="Round-Trip Import", wing_span=950)
        json_bytes = json.dumps(design.model_dump()).encode("utf-8")

        import_resp = client.post(
            "/api/designs/import",
            files={"file": ("plane.cheng", io.BytesIO(json_bytes), "application/json")},
        )
        new_id = import_resp.json()["id"]

        load_resp = client.get(f"/api/designs/{new_id}")
        assert load_resp.status_code == 200
        loaded = load_resp.json()
        assert loaded["name"] == "Round-Trip Import"
        assert loaded["wingSpan"] == 950

    def test_import_appears_in_list(self, client: TestClient) -> None:
        """Imported design should appear in GET /api/designs list."""
        design = AircraftDesign(name="Listed After Import", wing_span=800)
        json_bytes = json.dumps(design.model_dump()).encode("utf-8")

        client.post(
            "/api/designs/import",
            files={"file": ("plane.cheng", io.BytesIO(json_bytes), "application/json")},
        )

        list_resp = client.get("/api/designs")
        assert list_resp.status_code == 200
        names = [d["name"] for d in list_resp.json()]
        assert "Listed After Import" in names

    def test_import_invalid_json(self, client: TestClient) -> None:
        """Uploading non-JSON content should return 400."""
        resp = client.post(
            "/api/designs/import",
            files={"file": ("bad.cheng", io.BytesIO(b"this is not json"), "application/json")},
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["detail"]

    def test_import_wrong_schema(self, client: TestClient) -> None:
        """Uploading JSON that doesn't match AircraftDesign schema should return 400."""
        bad_data = {"wing_span": "not-a-number", "fuselage_preset": "invalid-preset"}
        resp = client.post(
            "/api/designs/import",
            files={
                "file": (
                    "bad.cheng",
                    io.BytesIO(json.dumps(bad_data).encode("utf-8")),
                    "application/json",
                )
            },
        )
        assert resp.status_code == 400
        assert "Invalid design file" in resp.json()["detail"]

    def test_import_file_too_large(self, client: TestClient) -> None:
        """Uploading a file larger than 1 MB should return 400."""
        big_bytes = b"x" * (1024 * 1024 + 2)
        resp = client.post(
            "/api/designs/import",
            files={"file": ("huge.cheng", io.BytesIO(big_bytes), "application/json")},
        )
        assert resp.status_code == 400
        assert "too large" in resp.json()["detail"]

    def test_import_memory_storage_at_capacity(self, tmp_path: Path, client: TestClient) -> None:
        """Import to a full MemoryStorage should return 507."""
        mem = MemoryStorage(max_designs=1)
        # Pre-fill the storage
        mem.save_design("existing", AircraftDesign(name="Existing").model_dump())
        set_storage(mem)

        design = AircraftDesign(name="Overflow")
        json_bytes = json.dumps(design.model_dump()).encode("utf-8")

        resp = client.post(
            "/api/designs/import",
            files={"file": ("plane.cheng", io.BytesIO(json_bytes), "application/json")},
        )
        assert resp.status_code == 507

    def test_import_preserves_all_params(self, client: TestClient) -> None:
        """Importing preserves all design parameters."""
        design = AircraftDesign(
            name="Full Params",
            wing_span=1600,
            wing_chord=220,
            fuselage_preset="Pod",
            motor_config="Pusher",
            tail_type="V-Tail",
            v_tail_dihedral=35,
            print_bed_x=300,
        )
        json_bytes = json.dumps(design.model_dump()).encode("utf-8")

        resp = client.post(
            "/api/designs/import",
            files={"file": ("full.cheng", io.BytesIO(json_bytes), "application/json")},
        )
        new_id = resp.json()["id"]

        loaded = AircraftDesign(**client.get(f"/api/designs/{new_id}").json())
        assert loaded.name == "Full Params"
        assert loaded.wing_span == 1600
        assert loaded.wing_chord == 220
        assert loaded.fuselage_preset == "Pod"
        assert loaded.motor_config == "Pusher"
        assert loaded.tail_type == "V-Tail"
        assert loaded.v_tail_dihedral == 35
        assert loaded.print_bed_x == 300


# ---------------------------------------------------------------------------
# GET /api/designs/{id}/download
# ---------------------------------------------------------------------------


class TestDownloadDesign:
    def test_download_existing_design(self, client: TestClient) -> None:
        """Download should return JSON with attachment header."""
        design = AircraftDesign(id="dl-test", name="My Trainer", wing_span=1200)
        client.post("/api/designs", json=design.model_dump())

        resp = client.get("/api/designs/dl-test/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert ".cheng" in cd

    def test_download_filename_derived_from_name(self, client: TestClient) -> None:
        """Filename in Content-Disposition should match the design name."""
        design = AircraftDesign(id="fn-test", name="My Trainer", wing_span=1000)
        client.post("/api/designs", json=design.model_dump())

        resp = client.get("/api/designs/fn-test/download")
        cd = resp.headers.get("content-disposition", "")
        assert "My_Trainer.cheng" in cd

    def test_download_filename_sanitized(self, client: TestClient) -> None:
        """Special characters in the design name should be replaced with underscores."""
        design = AircraftDesign(id="san-test", name="My Plane / v2.0!")
        client.post("/api/designs", json=design.model_dump())

        resp = client.get("/api/designs/san-test/download")
        cd = resp.headers.get("content-disposition", "")
        # Slashes, dots, exclamation marks should be replaced
        assert "My_Plane" in cd
        assert "/" not in cd.split("filename=")[-1]
        assert ".cheng" in cd

    def test_download_content_is_valid_json(self, client: TestClient) -> None:
        """Downloaded content should be valid JSON."""
        design = AircraftDesign(id="json-test", name="JSON Plane", wing_span=1100)
        client.post("/api/designs", json=design.model_dump())

        resp = client.get("/api/designs/json-test/download")
        # Must parse without error
        data = json.loads(resp.content)
        assert data["name"] == "JSON Plane"
        assert data["wing_span"] == 1100

    def test_download_content_round_trips(self, client: TestClient) -> None:
        """Downloaded JSON should be re-importable (round-trip)."""
        design = AircraftDesign(id="rt-test", name="Round Trip", wing_span=1350)
        client.post("/api/designs", json=design.model_dump())

        # Download
        dl_resp = client.get("/api/designs/rt-test/download")
        assert dl_resp.status_code == 200

        # Re-import
        import_resp = client.post(
            "/api/designs/import",
            files={"file": ("round_trip.cheng", io.BytesIO(dl_resp.content), "application/json")},
        )
        assert import_resp.status_code == 201
        new_id = import_resp.json()["id"]

        # Verify the re-imported design matches
        loaded = AircraftDesign(**client.get(f"/api/designs/{new_id}").json())
        assert loaded.name == "Round Trip"
        assert loaded.wing_span == 1350

    def test_download_nonexistent_design(self, client: TestClient) -> None:
        """Download of missing design should return 404."""
        resp = client.get("/api/designs/does-not-exist/download")
        assert resp.status_code == 404
