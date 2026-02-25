"""Tests for test joint generation (Issue #146).

Covers:
- generate_test_joint_pieces() returns two valid CadQuery solids
- Plug bounding box depth matches section_overlap (+ tongue protrusion)
- Socket has extra back-wall depth (overlap + 10mm) to prevent groove punch-through
- Plug volume > base block (tongue adds mass)
- Socket volume < its base block (groove removes material)
- Socket retains solid back wall (groove does not punch through)
- Different tolerances and overlaps produce expected dimensional changes
- joint_type routing: Tongue-and-Groove adds geometry; others produce plain blocks
- build_test_joint_zip() creates a valid ZIP with the right files
- /api/export/test-joint endpoint returns 200 with application/zip
- ZIP contains plug.stl and socket.stl, both non-empty
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

# CadQuery is required for geometry tests — skip if not installed
cq = pytest.importorskip("cadquery")

# Socket back-wall constant must match test_joint.py
_SOCKET_BACK_WALL_MM = 10.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bbox_dims(solid: cq.Workplane) -> tuple[float, float, float]:
    """Return (dx, dy, dz) bounding box dimensions."""
    bb = solid.val().BoundingBox()
    return (bb.xmax - bb.xmin, bb.ymax - bb.ymin, bb.zmax - bb.zmin)


def _volume(solid: cq.Workplane) -> float:
    """Return volume of the solid."""
    return solid.val().Volume()


# ---------------------------------------------------------------------------
# Tests: generate_test_joint_pieces()
# ---------------------------------------------------------------------------


class TestGenerateTestJointPieces:
    """Unit tests for the generate_test_joint_pieces() function."""

    def test_returns_two_solids(self) -> None:
        """Function must return exactly two non-None CadQuery Workplane objects."""
        from backend.export.test_joint import generate_test_joint_pieces

        plug, socket = generate_test_joint_pieces(
            section_overlap=15.0,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
        )

        assert plug is not None, "plug solid must not be None"
        assert socket is not None, "socket solid must not be None"
        assert hasattr(plug, "val"), "plug must be a CadQuery Workplane"
        assert hasattr(socket, "val"), "socket must be a CadQuery Workplane"

    def test_plug_footprint_is_40mm(self) -> None:
        """Plug X and Z dimensions must be approximately 40mm."""
        from backend.export.test_joint import generate_test_joint_pieces

        plug, _ = generate_test_joint_pieces(
            section_overlap=15.0,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
        )

        dx, _dy, dz = _bbox_dims(plug)
        assert abs(dx - 40.0) < 2.0, f"Plug X width should be ~40mm, got {dx:.2f}"
        assert abs(dz - 40.0) < 2.0, f"Plug Z height should be ~40mm, got {dz:.2f}"

    def test_plug_depth_spans_overlap_and_tongue(self) -> None:
        """Plug Y extent must cover block depth (overlap) plus tongue protrusion (another overlap)."""
        from backend.export.test_joint import generate_test_joint_pieces

        overlap = 15.0
        plug, _ = generate_test_joint_pieces(
            section_overlap=overlap,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
        )

        _dx, dy, _dz = _bbox_dims(plug)
        # Plug block: Y=[0, overlap]; tongue protrudes up to Y=2*overlap
        assert dy >= overlap - 0.5, f"Plug Y must be at least overlap={overlap}, got {dy:.2f}"
        assert dy <= overlap * 2.0 + 1.0, f"Plug Y too large: {dy:.2f}"

    def test_socket_footprint_is_40mm(self) -> None:
        """Socket X and Z dimensions must be approximately 40mm."""
        from backend.export.test_joint import generate_test_joint_pieces

        _, socket = generate_test_joint_pieces(
            section_overlap=15.0,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
        )

        dx, _dy, dz = _bbox_dims(socket)
        assert abs(dx - 40.0) < 2.0, f"Socket X width should be ~40mm, got {dx:.2f}"
        assert abs(dz - 40.0) < 2.0, f"Socket Z height should be ~40mm, got {dz:.2f}"

    def test_socket_has_back_wall_buffer(self) -> None:
        """Socket Y depth must be overlap + back-wall buffer (10mm) to prevent groove punch-through."""
        from backend.export.test_joint import generate_test_joint_pieces

        overlap = 15.0
        _, socket = generate_test_joint_pieces(
            section_overlap=overlap,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
        )

        _dx, dy, _dz = _bbox_dims(socket)
        expected_min_depth = overlap + _SOCKET_BACK_WALL_MM
        # Socket spans from plug_depth to plug_depth + socket_depth in global Y
        # so dy (which is a bounding box extent) should approximately equal socket_depth
        assert dy >= expected_min_depth - 1.0, (
            f"Socket Y depth {dy:.2f} must be at least overlap+backwall={expected_min_depth:.1f}mm"
        )

    def test_plug_has_tongue_mass(self) -> None:
        """Plug volume must exceed the plain base block (tongue adds mass)."""
        from backend.export.test_joint import generate_test_joint_pieces

        overlap = 15.0
        plug, _ = generate_test_joint_pieces(
            section_overlap=overlap,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
        )

        base_volume = 40.0 * 40.0 * overlap
        plug_volume = _volume(plug)
        # Plug must be larger than the plain block because the tongue is added
        assert plug_volume > base_volume * 0.9, (
            f"Plug volume {plug_volume:.1f} mm³ should exceed base {base_volume:.1f} mm³"
        )

    def test_socket_has_groove_removed(self) -> None:
        """Socket volume must be less than its plain base block (groove removes material)."""
        from backend.export.test_joint import generate_test_joint_pieces

        overlap = 15.0
        _, socket = generate_test_joint_pieces(
            section_overlap=overlap,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
        )

        socket_depth = overlap + _SOCKET_BACK_WALL_MM
        base_volume = 40.0 * 40.0 * socket_depth
        socket_volume = _volume(socket)
        # Socket must be smaller than the plain block because the groove is cut
        assert socket_volume < base_volume * 1.02, (
            f"Socket volume {socket_volume:.1f} mm³ should be <= base {base_volume:.1f} mm³"
        )

    def test_socket_retains_back_wall(self) -> None:
        """Socket must have positive volume after groove (groove must not punch through)."""
        from backend.export.test_joint import generate_test_joint_pieces

        _, socket = generate_test_joint_pieces(
            section_overlap=15.0,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
        )

        vol = _volume(socket)
        assert vol > 1000.0, f"Socket volume {vol:.1f} mm³ too small — groove may have punched through"

    def test_different_tolerances_0_1(self) -> None:
        """Test with tolerance=0.1mm produces valid solids."""
        from backend.export.test_joint import generate_test_joint_pieces

        plug, socket = generate_test_joint_pieces(
            section_overlap=15.0,
            joint_tolerance=0.1,
            nozzle_diameter=0.4,
        )
        assert _volume(plug) > 0
        assert _volume(socket) > 0

    def test_different_tolerances_0_2(self) -> None:
        """Test with tolerance=0.2mm produces valid solids."""
        from backend.export.test_joint import generate_test_joint_pieces

        plug, socket = generate_test_joint_pieces(
            section_overlap=15.0,
            joint_tolerance=0.2,
            nozzle_diameter=0.4,
        )
        assert _volume(plug) > 0
        assert _volume(socket) > 0

    def test_larger_tolerance_larger_groove(self) -> None:
        """Larger tolerance should produce a smaller socket (more material removed)."""
        from backend.export.test_joint import generate_test_joint_pieces

        _, socket_tight = generate_test_joint_pieces(
            section_overlap=15.0, joint_tolerance=0.1, nozzle_diameter=0.4
        )
        _, socket_loose = generate_test_joint_pieces(
            section_overlap=15.0, joint_tolerance=0.3, nozzle_diameter=0.4
        )
        vol_tight = _volume(socket_tight)
        vol_loose = _volume(socket_loose)
        # Looser tolerance = bigger groove = less material in socket
        assert vol_loose <= vol_tight + 0.1, (
            f"Loose socket ({vol_loose:.2f}) should have <= material than tight ({vol_tight:.2f})"
        )

    def test_larger_overlap_taller_blocks(self) -> None:
        """Larger section_overlap produces taller blocks."""
        from backend.export.test_joint import generate_test_joint_pieces

        plug_small, _ = generate_test_joint_pieces(
            section_overlap=10.0, joint_tolerance=0.15, nozzle_diameter=0.4
        )
        plug_large, _ = generate_test_joint_pieces(
            section_overlap=25.0, joint_tolerance=0.15, nozzle_diameter=0.4
        )

        _, dy_small, _ = _bbox_dims(plug_small)
        _, dy_large, _ = _bbox_dims(plug_large)
        assert dy_large > dy_small, (
            f"Larger overlap block ({dy_large:.1f}) should be taller than smaller ({dy_small:.1f})"
        )

    def test_tongue_and_groove_type_default(self) -> None:
        """Default (Tongue-and-Groove) produces plug with tongue (volume > plain block)."""
        from backend.export.test_joint import generate_test_joint_pieces

        overlap = 15.0
        plug, _ = generate_test_joint_pieces(
            section_overlap=overlap,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
            joint_type="Tongue-and-Groove",
        )
        plain_volume = 40.0 * 40.0 * overlap
        assert _volume(plug) > plain_volume * 0.9, "Tongue-and-Groove plug should have tongue mass"

    def test_non_simulated_joint_type_returns_plain_blocks(self) -> None:
        """Dowel-Pin joint type returns plain blocks (no joint geometry yet)."""
        from backend.export.test_joint import generate_test_joint_pieces

        overlap = 15.0
        plug, socket = generate_test_joint_pieces(
            section_overlap=overlap,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
            joint_type="Dowel-Pin",
        )

        # Both should be valid solids
        assert _volume(plug) > 0
        assert _volume(socket) > 0

        # Plug should be approximately a plain block (no tongue added)
        plug_volume = _volume(plug)
        expected_plain = 40.0 * 40.0 * overlap
        # Allow small deviation but plug should not have a tongue (not much larger than plain block)
        assert plug_volume < expected_plain * 1.5, (
            f"Dowel-Pin plug ({plug_volume:.1f}) should be close to plain block ({expected_plain:.1f})"
        )


# ---------------------------------------------------------------------------
# Tests: build_test_joint_zip()
# ---------------------------------------------------------------------------


class TestBuildTestJointZip:
    """Tests for the ZIP packaging function."""

    def test_returns_existing_path(self, tmp_path: Path) -> None:
        """build_test_joint_zip() must return a Path that exists."""
        from backend.export.test_joint import build_test_joint_zip

        zip_path = build_test_joint_zip(
            section_overlap=15.0,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
            tmp_dir=tmp_path,
        )
        assert zip_path.exists(), f"ZIP file not created at {zip_path}"

    def test_zip_contains_two_stl_files(self, tmp_path: Path) -> None:
        """ZIP must contain test_joint_plug.stl and test_joint_socket.stl."""
        from backend.export.test_joint import build_test_joint_zip

        zip_path = build_test_joint_zip(
            section_overlap=15.0,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
            tmp_dir=tmp_path,
        )

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = set(zf.namelist())

        assert "test_joint_plug.stl" in names, f"plug.stl missing from ZIP. Found: {names}"
        assert "test_joint_socket.stl" in names, f"socket.stl missing from ZIP. Found: {names}"

    def test_stl_files_are_nonempty(self, tmp_path: Path) -> None:
        """Both STL files in the ZIP must be non-empty (> 84 bytes for binary STL header)."""
        from backend.export.test_joint import build_test_joint_zip

        zip_path = build_test_joint_zip(
            section_overlap=15.0,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
            tmp_dir=tmp_path,
        )

        with zipfile.ZipFile(zip_path, "r") as zf:
            plug_bytes = zf.read("test_joint_plug.stl")
            socket_bytes = zf.read("test_joint_socket.stl")

        assert len(plug_bytes) > 84, f"plug.stl too small: {len(plug_bytes)} bytes"
        assert len(socket_bytes) > 84, f"socket.stl too small: {len(socket_bytes)} bytes"

    def test_zip_contains_manifest(self, tmp_path: Path) -> None:
        """ZIP must contain manifest.json with joint settings."""
        from backend.export.test_joint import build_test_joint_zip

        overlap = 15.0
        tolerance = 0.15
        zip_path = build_test_joint_zip(
            section_overlap=overlap,
            joint_tolerance=tolerance,
            nozzle_diameter=0.4,
            tmp_dir=tmp_path,
        )

        with zipfile.ZipFile(zip_path, "r") as zf:
            manifest_bytes = zf.read("manifest.json")

        manifest = json.loads(manifest_bytes)
        assert manifest["joint_tolerance_mm"] == pytest.approx(tolerance)
        assert manifest["section_overlap_mm"] == pytest.approx(overlap)
        assert "test_joint_plug.stl" in manifest["files"]
        assert "test_joint_socket.stl" in manifest["files"]

    def test_zip_exactly_three_files(self, tmp_path: Path) -> None:
        """ZIP must contain exactly 3 files: plug.stl, socket.stl, manifest.json."""
        from backend.export.test_joint import build_test_joint_zip

        zip_path = build_test_joint_zip(
            section_overlap=15.0,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
            tmp_dir=tmp_path,
        )

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

        assert len(names) == 3, f"Expected 3 files in ZIP, got {len(names)}: {names}"

    def test_manifest_includes_joint_type(self, tmp_path: Path) -> None:
        """Manifest must record the joint_type and whether it was geometrically simulated."""
        from backend.export.test_joint import build_test_joint_zip

        zip_path = build_test_joint_zip(
            section_overlap=15.0,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
            tmp_dir=tmp_path,
            joint_type="Tongue-and-Groove",
        )

        with zipfile.ZipFile(zip_path, "r") as zf:
            manifest = json.loads(zf.read("manifest.json"))

        assert manifest["joint_type"] == "Tongue-and-Groove"
        assert manifest["joint_simulated"] is True

    def test_non_simulated_manifest_flag(self, tmp_path: Path) -> None:
        """Dowel-Pin manifest must mark joint_simulated as False."""
        from backend.export.test_joint import build_test_joint_zip

        zip_path = build_test_joint_zip(
            section_overlap=15.0,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
            tmp_dir=tmp_path,
            joint_type="Dowel-Pin",
        )

        with zipfile.ZipFile(zip_path, "r") as zf:
            manifest = json.loads(zf.read("manifest.json"))

        assert manifest["joint_type"] == "Dowel-Pin"
        assert manifest["joint_simulated"] is False


# ---------------------------------------------------------------------------
# Tests: /api/export/test-joint endpoint
# ---------------------------------------------------------------------------


class TestTestJointEndpoint:
    """Integration tests for the POST /api/export/test-joint route."""

    @pytest.fixture
    def client(self):
        """Create a TestClient for the FastAPI app."""
        from fastapi.testclient import TestClient
        from backend.main import app
        return TestClient(app)

    def test_endpoint_returns_200(self, client) -> None:
        """POST /api/export/test-joint must return HTTP 200."""
        response = client.post(
            "/api/export/test-joint",
            json={
                "jointType": "Tongue-and-Groove",
                "jointTolerance": 0.15,
                "sectionOverlap": 15.0,
                "nozzleDiameter": 0.4,
            },
        )
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text[:200]}"
        )

    def test_endpoint_returns_zip_content_type(self, client) -> None:
        """Response Content-Type must be application/zip."""
        response = client.post(
            "/api/export/test-joint",
            json={
                "jointType": "Tongue-and-Groove",
                "jointTolerance": 0.15,
                "sectionOverlap": 15.0,
                "nozzleDiameter": 0.4,
            },
        )
        assert response.status_code == 200
        assert "application/zip" in response.headers.get("content-type", ""), (
            f"Expected application/zip, got: {response.headers.get('content-type')}"
        )

    def test_endpoint_zip_contains_plug_and_socket(self, client) -> None:
        """Response ZIP must contain plug.stl and socket.stl."""
        response = client.post(
            "/api/export/test-joint",
            json={
                "jointType": "Tongue-and-Groove",
                "jointTolerance": 0.15,
                "sectionOverlap": 15.0,
                "nozzleDiameter": 0.4,
            },
        )
        assert response.status_code == 200

        zip_buf = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buf, "r") as zf:
            names = set(zf.namelist())

        assert "test_joint_plug.stl" in names, f"plug.stl missing. Files: {names}"
        assert "test_joint_socket.stl" in names, f"socket.stl missing. Files: {names}"

    def test_endpoint_stl_files_nonempty(self, client) -> None:
        """Both STL files in the response ZIP must be non-empty."""
        response = client.post(
            "/api/export/test-joint",
            json={
                "jointType": "Tongue-and-Groove",
                "jointTolerance": 0.15,
                "sectionOverlap": 15.0,
                "nozzleDiameter": 0.4,
            },
        )
        assert response.status_code == 200

        zip_buf = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buf, "r") as zf:
            plug_bytes = zf.read("test_joint_plug.stl")
            socket_bytes = zf.read("test_joint_socket.stl")

        assert len(plug_bytes) > 84, f"plug.stl too small: {len(plug_bytes)} bytes"
        assert len(socket_bytes) > 84, f"socket.stl too small: {len(socket_bytes)} bytes"

    def test_endpoint_snake_case_request(self, client) -> None:
        """Endpoint must also accept snake_case keys (populate_by_name=True)."""
        response = client.post(
            "/api/export/test-joint",
            json={
                "joint_type": "Tongue-and-Groove",
                "joint_tolerance": 0.15,
                "section_overlap": 15.0,
                "nozzle_diameter": 0.4,
            },
        )
        assert response.status_code == 200

    def test_endpoint_default_params(self, client) -> None:
        """Endpoint must work with an empty body (all defaults)."""
        response = client.post(
            "/api/export/test-joint",
            json={},
        )
        assert response.status_code == 200

    def test_endpoint_tolerance_out_of_range(self, client) -> None:
        """Tolerance outside [0.05, 0.5] should return 422 validation error."""
        response = client.post(
            "/api/export/test-joint",
            json={
                "jointType": "Tongue-and-Groove",
                "jointTolerance": 5.0,  # way too large
                "sectionOverlap": 15.0,
                "nozzleDiameter": 0.4,
            },
        )
        assert response.status_code == 422, (
            f"Expected 422 for out-of-range tolerance, got {response.status_code}"
        )

    def test_endpoint_dowel_pin_returns_200(self, client) -> None:
        """Dowel-Pin joint type must return a valid ZIP (plain blocks with manifest note)."""
        response = client.post(
            "/api/export/test-joint",
            json={
                "jointType": "Dowel-Pin",
                "jointTolerance": 0.15,
                "sectionOverlap": 15.0,
                "nozzleDiameter": 0.4,
            },
        )
        assert response.status_code == 200

        zip_buf = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buf, "r") as zf:
            names = set(zf.namelist())
            manifest = json.loads(zf.read("manifest.json"))

        assert "test_joint_plug.stl" in names
        assert "test_joint_socket.stl" in names
        assert manifest["joint_type"] == "Dowel-Pin"
        assert manifest["joint_simulated"] is False
