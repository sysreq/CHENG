"""Tests for the WebSocket preview handler.

Covers concurrency, message validation, size limits, and error handling.
"""

from __future__ import annotations

import json

import pytest

from backend.routes.websocket import (
    _build_error_frame,
    _build_mesh_response,
    MAX_MESSAGE_SIZE,
)


class TestBuildErrorFrame:
    """Tests for the _build_error_frame helper."""

    def test_basic_error(self) -> None:
        frame = _build_error_frame("test error")
        # First 4 bytes are the header (0x02 as little-endian uint32)
        assert frame[:4] == b"\x02\x00\x00\x00"
        payload = json.loads(frame[4:])
        assert payload["error"] == "test error"
        assert "detail" not in payload
        assert "field" not in payload

    def test_error_with_detail(self) -> None:
        frame = _build_error_frame("test error", detail="some detail")
        payload = json.loads(frame[4:])
        assert payload["error"] == "test error"
        assert payload["detail"] == "some detail"

    def test_error_with_field(self) -> None:
        frame = _build_error_frame("test error", field="wing_span")
        payload = json.loads(frame[4:])
        assert payload["field"] == "wing_span"


class TestMaxMessageSize:
    """Tests that MAX_MESSAGE_SIZE is properly defined."""

    def test_max_message_size_is_64kb(self) -> None:
        assert MAX_MESSAGE_SIZE == 64 * 1024


class TestAbandonOnCancelRemoved:
    """Verify that abandon_on_cancel=True is NOT used in websocket.py (#189).

    When abandon_on_cancel=True, cancelled threads keep running and hold
    CapacityLimiter tokens, leading to token exhaustion under load.
    """

    def test_no_abandon_on_cancel_true_in_source(self) -> None:
        """The websocket module must not use abandon_on_cancel=True."""
        import inspect
        from backend.routes import websocket

        source = inspect.getsource(websocket)
        assert "abandon_on_cancel=True" not in source
        # Verify it explicitly uses False
        assert "abandon_on_cancel=False" in source
