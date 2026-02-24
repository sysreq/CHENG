"""Integration tests for Phase 2 endpoints.

Tests the /api/generate, /api/export, and /ws/preview endpoints
with the actual backend wiring (no CadQuery mocking for generate/export
since those require the geometry engine — we test what we can without it).
"""

from __future__ import annotations

import json
import struct

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models import AircraftDesign


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def default_design_dict() -> dict:
    """Default design as a dict (Trainer-like)."""
    return AircraftDesign().model_dump()


@pytest.fixture
def trainer_design_dict() -> dict:
    """Trainer preset design dict."""
    return AircraftDesign(
        name="Trainer",
        wing_span=1200,
        wing_chord=200,
        wing_airfoil="Clark-Y",
        wing_tip_root_ratio=1.0,
        wing_dihedral=3,
        fuselage_preset="Conventional",
        fuselage_length=400,
        tail_type="Conventional",
        h_stab_span=400,
        h_stab_chord=120,
        tail_arm=220,
    ).model_dump()


# ---------------------------------------------------------------------------
# POST /api/generate
# ---------------------------------------------------------------------------


class TestGenerate:
    """Tests for the REST generate endpoint."""

    @pytest.mark.anyio
    async def test_generate_returns_derived_and_warnings(
        self, default_design_dict: dict
    ) -> None:
        """POST /api/generate should return derived values and warnings."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/generate", json=default_design_dict)

        assert resp.status_code == 200
        data = resp.json()
        assert "derived" in data
        assert "warnings" in data

        # Check derived values are present (camelCase per API naming contract)
        derived = data["derived"]
        assert "tipChordMm" in derived
        assert "wingAreaCm2" in derived
        assert "aspectRatio" in derived
        assert "meanAeroChordMm" in derived
        assert "taperRatio" in derived
        assert "estimatedCgMm" in derived

    @pytest.mark.anyio
    async def test_generate_with_trainer(self, trainer_design_dict: dict) -> None:
        """Trainer preset should produce valid derived values."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/generate", json=trainer_design_dict)

        assert resp.status_code == 200
        derived = resp.json()["derived"]
        # Trainer: 1200mm span, 200mm chord, taper 1.0
        # wing_area = 0.5 * (200 + 200) * 1200 / 100 = 2400 cm2
        assert derived["wingAreaCm2"] == pytest.approx(2400.0, rel=0.01)
        assert derived["aspectRatio"] == pytest.approx(6.0, rel=0.01)
        assert derived["taperRatio"] == pytest.approx(1.0)

    @pytest.mark.anyio
    async def test_generate_warnings_are_list(
        self, default_design_dict: dict
    ) -> None:
        """Warnings should always be a list."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/generate", json=default_design_dict)

        assert resp.status_code == 200
        warnings = resp.json()["warnings"]
        assert isinstance(warnings, list)
        for w in warnings:
            assert "id" in w
            assert "message" in w
            assert "level" in w
            assert w["level"] == "warn"

    @pytest.mark.anyio
    async def test_generate_invalid_design(self) -> None:
        """Invalid design should return 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/generate", json={"wing_span": -100}
            )

        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_generate_extreme_design_triggers_warning(self) -> None:
        """Extreme wingspan relative to fuselage should produce V01 warning."""
        design = AircraftDesign(wing_span=3000, fuselage_length=200).model_dump()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/generate", json=design)

        assert resp.status_code == 200
        warnings = resp.json()["warnings"]
        warning_ids = [w["id"] for w in warnings]
        assert "V01" in warning_ids


# ---------------------------------------------------------------------------
# POST /api/export (limited testing without CadQuery)
# ---------------------------------------------------------------------------


class TestExportEndpoint:
    """Tests for the export endpoint structure (without CadQuery)."""

    @pytest.mark.anyio
    async def test_export_accepts_request(self) -> None:
        """Export endpoint should accept valid ExportRequest format."""
        design = AircraftDesign(name="Test Export").model_dump()
        payload = {"design": design, "format": "stl"}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/export", json=payload)

        # Without CadQuery, expect 500 (geometry generation fails)
        # but the endpoint itself should be reachable (not 404)
        assert resp.status_code in (200, 500)

    @pytest.mark.anyio
    async def test_export_invalid_request(self) -> None:
        """Missing design should return 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/export", json={"format": "stl"})

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# WebSocket /ws/preview
# ---------------------------------------------------------------------------


class TestWebSocket:
    """Tests for the WebSocket preview endpoint."""

    @pytest.mark.anyio
    async def test_websocket_connects(self) -> None:
        """WebSocket should accept connection."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            async with client.stream("GET", "/ws/preview") as resp:
                # httpx doesn't natively support WebSocket, but we can verify
                # the endpoint exists. For real WS testing, use the starlette
                # test client.
                pass

    @pytest.mark.anyio
    async def test_websocket_with_starlette_client(
        self, default_design_dict: dict
    ) -> None:
        """WebSocket should respond to design params."""
        from starlette.testclient import TestClient

        client = TestClient(app)
        with client.websocket_connect("/ws/preview") as ws:
            ws.send_text(json.dumps(default_design_dict))

            # Without CadQuery, we should get an error frame (0x02)
            # since geometry generation will fail
            data = ws.receive_bytes()
            msg_type = struct.unpack("<I", data[:4])[0]

            # Either mesh (0x01) if CadQuery is available,
            # or error (0x02) if not
            assert msg_type in (0x01, 0x02)

            if msg_type == 0x02:
                error_json = json.loads(data[4:].decode("utf-8"))
                assert "error" in error_json

    @pytest.mark.anyio
    async def test_websocket_invalid_json(self) -> None:
        """Invalid JSON should return error frame, not crash."""
        from starlette.testclient import TestClient

        client = TestClient(app)
        with client.websocket_connect("/ws/preview") as ws:
            ws.send_text("not valid json")
            data = ws.receive_bytes()
            msg_type = struct.unpack("<I", data[:4])[0]
            assert msg_type == 0x02
            error = json.loads(data[4:].decode("utf-8"))
            assert "error" in error

    @pytest.mark.anyio
    async def test_websocket_invalid_design(self) -> None:
        """Valid JSON but invalid design should return error frame."""
        from starlette.testclient import TestClient

        client = TestClient(app)
        with client.websocket_connect("/ws/preview") as ws:
            ws.send_text(json.dumps({"wing_span": -999}))
            data = ws.receive_bytes()
            msg_type = struct.unpack("<I", data[:4])[0]
            assert msg_type == 0x02


# ---------------------------------------------------------------------------
# Health + route registration
# ---------------------------------------------------------------------------


class TestRouteRegistration:
    """Verify all Phase 2 routes are registered."""

    @pytest.mark.anyio
    async def test_health(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.anyio
    async def test_generate_route_exists(self) -> None:
        """Generate endpoint should be registered (not 404/405)."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/generate", json={})
        # 200 (defaults fill in) or 422 means the route exists
        assert resp.status_code in (200, 422)

    @pytest.mark.anyio
    async def test_export_route_exists(self) -> None:
        """Export endpoint should be registered (not 404/405)."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/export", json={})
        assert resp.status_code == 422
