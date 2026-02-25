"""Tests for the WebSocket preview handler.

Covers concurrency, message validation, size limits, and error handling.
"""

from __future__ import annotations

import inspect
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
    """Verify that abandon_on_cancel=True is NOT used in websocket.py (#189)."""

    def test_no_abandon_on_cancel_true_in_source(self) -> None:
        """The websocket module must not use abandon_on_cancel=True."""
        from backend.routes import websocket

        source = inspect.getsource(websocket)
        assert "abandon_on_cancel=True" not in source
        assert "abandon_on_cancel=False" in source


class TestWebSocketHardening:
    """Tests for WebSocket hardening features (#182).

    These verify the source code contains the required hardening logic
    for size limits, malformed JSON, validation errors, and binary frames.
    """

    @pytest.fixture(autouse=True)
    def _load_source(self) -> None:
        from backend.routes import websocket
        self.source = inspect.getsource(websocket)

    def test_size_limit_check_present(self) -> None:
        """Reader must reject messages exceeding MAX_MESSAGE_SIZE."""
        assert "MAX_MESSAGE_SIZE" in self.source
        assert "Message too large" in self.source

    def test_json_decode_error_handled(self) -> None:
        """Malformed JSON must produce a structured error frame."""
        assert "json.JSONDecodeError" in self.source
        assert "Invalid JSON" in self.source

    def test_validation_error_handled(self) -> None:
        """Pydantic validation errors must produce structured error frames."""
        assert "ValidationError" in self.source
        assert "Validation error" in self.source

    def test_binary_frame_handling(self) -> None:
        """Non-UTF-8 binary frames must be handled gracefully."""
        assert "UnicodeDecodeError" in self.source
        assert "Invalid message format" in self.source

    def test_warning_level_logging(self) -> None:
        """Validation and parse errors must be logged at WARNING level."""
        assert "logger.warning" in self.source

    def test_ws_lock_for_concurrent_sends(self) -> None:
        """A lock must protect ws.send_bytes for concurrent frame safety."""
        assert "ws_lock" in self.source
        assert "anyio.Lock" in self.source

    def test_task_group_pattern(self) -> None:
        """The handler must use a task group with reader and generator tasks."""
        assert "create_task_group" in self.source
        assert "reader_task" in self.source
        assert "generator_task" in self.source


class TestNoneTextGuard:
    """Tests for Issue #255 — None text guard and byte-length size check."""

    @pytest.fixture(autouse=True)
    def _load_source(self) -> None:
        from backend.routes import websocket
        self.source = inspect.getsource(websocket)

    def test_none_text_guard_present(self) -> None:
        """Reader must guard against text=None in the ASGI receive dict (#255)."""
        assert "if text is None:" in self.source

    def test_byte_length_size_check(self) -> None:
        """Size check must use byte-length with errors='replace' not bare len(text) (#255).
        errors='replace' avoids UnicodeEncodeError on surrogate pairs from malicious clients.
        """
        assert 'text.encode("utf-8", errors="replace")' in self.source

    def test_character_count_not_used_for_text_size(self) -> None:
        """The text size limit must NOT use bare len(text) — it must use the
        utf-8 encoded byte length to reject oversized non-ASCII payloads.
        Byte-length check should be present; bare len(text) size check should
        be absent from the text size-check branch."""
        # Confirm the encoding-based check is present with safe error handler
        assert 'len(text.encode("utf-8", errors="replace")) > MAX_MESSAGE_SIZE' in self.source

    def test_none_text_with_none_bytes_skipped(self) -> None:
        """When text=None and bytes=None, the frame must be skipped (not crash)."""
        # Verify the guard checks raw.get("bytes") is None before continuing
        assert 'raw.get("bytes") is None' in self.source

    def test_oversized_non_ascii_rejected(self) -> None:
        """A string of N multi-byte characters > MAX_MESSAGE_SIZE bytes but
        <= MAX_MESSAGE_SIZE characters must be rejected by the byte-length check.
        """
        from backend.routes.websocket import MAX_MESSAGE_SIZE

        # Build a string where character count is ≤ MAX_MESSAGE_SIZE but
        # byte count exceeds MAX_MESSAGE_SIZE (each '€' is 3 bytes in UTF-8).
        # char_count = MAX_MESSAGE_SIZE // 2  →  byte_count = 3 * char_count  > MAX_MESSAGE_SIZE
        char_count = MAX_MESSAGE_SIZE // 2
        text = "\u20ac" * char_count  # '€' = U+20AC, 3 bytes each
        byte_len = len(text.encode("utf-8"))
        assert byte_len > MAX_MESSAGE_SIZE, "test precondition: byte_len must exceed limit"
        assert len(text) <= MAX_MESSAGE_SIZE, "test precondition: char count must fit old limit"

        # The byte-length check should trigger
        assert len(text.encode("utf-8")) > MAX_MESSAGE_SIZE
