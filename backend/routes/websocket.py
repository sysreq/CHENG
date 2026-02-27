"""/ws/preview — WebSocket handler for interactive 3D preview.

Connection lifecycle (spec §6.2):
1. Client opens ws://host:8000/ws/preview
2. Client sends AircraftDesign JSON on each parameter change
3. Server cancels in-flight generation (last-write-wins), runs new one
4. Server sends binary mesh frame (0x01) or error frame (0x02)
5. On disconnect, cancel pending work and clean up

Concurrency model:
- A task group runs two concurrent tasks: a reader and a generator.
- The reader receives messages from the WebSocket, validates them, cancels
  any in-flight generation scope, and posts designs to a memory channel.
- The generator picks up the latest design and runs CadQuery in a thread.
- A lock protects ws.send_bytes to prevent interleaved frames.
- `abandon_on_cancel` is NOT used — cancelled threads properly release
  the CapacityLimiter token when they finish.
"""

from __future__ import annotations

import json
import logging
import struct
from typing import Any

import anyio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from backend.geometry.engine import (
    _cadquery_limiter,
    _compute_wing_mount,
    assemble_aircraft,
    compute_derived_values,
)
from backend.models import AircraftDesign, DerivedValues, ValidationWarning
from backend.validation import compute_warnings

logger = logging.getLogger("cheng.ws")

router = APIRouter()

# Maximum accepted WebSocket message size (bytes).  Messages larger than
# this are rejected with an error frame to prevent memory exhaustion.
MAX_MESSAGE_SIZE = 64 * 1024  # 64 KB


def _build_error_frame(error: str, detail: str = "", field: str = "") -> bytes:
    """Build a 0x02 error binary frame."""
    payload: dict[str, str] = {"error": error}
    if detail:
        payload["detail"] = detail
    if field:
        payload["field"] = field
    json_bytes = json.dumps(payload).encode("utf-8")
    header = struct.pack("<I", 0x02)
    return header + json_bytes


def _build_mesh_response(
    mesh_binary: bytes,
    derived: DerivedValues,
    warnings: list[ValidationWarning],
    component_ranges: dict[str, list[int]] | None = None,
) -> bytes:
    """Append JSON trailer to mesh binary frame.

    Uses Pydantic alias_generator (by_alias=True) for snake_case -> camelCase
    conversion — see models.py CamelModel base class.
    """
    trailer_dict: dict[str, Any] = {
        "derived": derived.model_dump(by_alias=True),
        "validation": [w.model_dump(by_alias=True) for w in warnings],
    }
    if component_ranges is not None:
        trailer_dict["componentRanges"] = component_ranges
    trailer = json.dumps(trailer_dict).encode("utf-8")
    return mesh_binary + trailer


@router.websocket("/ws/preview")
async def preview_websocket(ws: WebSocket) -> None:
    """Handle a single WebSocket connection for real-time preview.

    Uses a task group with two concurrent tasks:
    - **reader**: receives WebSocket messages, validates them, cancels any
      in-flight generation scope, and sends parsed AircraftDesign objects
      into a memory channel.
    - **generator**: consumes designs from the channel and runs CadQuery
      in a thread pool.  Results (or errors) are sent back via the WebSocket.

    A shared lock protects all ws.send_bytes calls to prevent interleaved
    frames from the two tasks.
    """
    await ws.accept()
    logger.info("WebSocket client connected")

    # Memory channel — reader posts validated designs, generator consumes.
    send_ch, recv_ch = anyio.create_memory_object_stream[AircraftDesign](max_buffer_size=16)

    # Lock protecting ws.send_bytes — both tasks may send frames.
    ws_lock = anyio.Lock()

    # Shared cancel scope: reader cancels it when a new message arrives,
    # generator creates it before starting work.
    generation_scope: anyio.CancelScope | None = None

    async def _send_frame(frame: bytes) -> None:
        """Send a binary frame to the WebSocket, protected by lock."""
        async with ws_lock:
            await ws.send_bytes(frame)

    async def reader_task() -> None:
        """Read messages from the WebSocket and post validated designs."""
        nonlocal generation_scope
        try:
            while True:
                try:
                    raw = await ws.receive()
                except WebSocketDisconnect:
                    return

                # Low-level ws.receive() returns a disconnect dict instead of
                # raising WebSocketDisconnect — calling receive() again after
                # this would raise RuntimeError (#282).
                if raw.get("type") == "websocket.disconnect":
                    return

                # Handle both text and binary frames
                if "text" in raw:
                    text = raw["text"]
                    # Guard against None — ASGI can deliver {"type": "websocket.receive", "text": None, "bytes": ...}
                    if text is None:
                        # Fall through to bytes branch if present, otherwise skip
                        if raw.get("bytes") is None:
                            continue
                        raw_bytes = raw["bytes"]
                        if len(raw_bytes) > MAX_MESSAGE_SIZE:
                            frame = _build_error_frame(
                                error="Message too large",
                                detail=f"Maximum message size is {MAX_MESSAGE_SIZE} bytes",
                            )
                            await _send_frame(frame)
                            continue
                        try:
                            text = raw_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            logger.warning("Received non-UTF-8 binary frame, ignoring")
                            frame = _build_error_frame(
                                error="Invalid message format",
                                detail="Expected UTF-8 encoded JSON text",
                            )
                            await _send_frame(frame)
                            continue
                elif "bytes" in raw:
                    raw_bytes = raw["bytes"]
                    if raw_bytes is None:
                        continue
                    # Reject oversized messages (#182)
                    if len(raw_bytes) > MAX_MESSAGE_SIZE:
                        frame = _build_error_frame(
                            error="Message too large",
                            detail=f"Maximum message size is {MAX_MESSAGE_SIZE} bytes",
                        )
                        await _send_frame(frame)
                        continue
                    try:
                        text = raw_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        logger.warning("Received non-UTF-8 binary frame, ignoring")
                        frame = _build_error_frame(
                            error="Invalid message format",
                            detail="Expected UTF-8 encoded JSON text",
                        )
                        await _send_frame(frame)
                        continue
                else:
                    continue

                # Reject oversized text messages (#182, #255)
                # Use byte-length (not character count) to correctly reject
                # non-ASCII payloads that could exceed the memory limit.
                # Use errors="replace" to safely handle isolated surrogate
                # characters (e.g. \ud800) that would raise UnicodeEncodeError
                # with the default "strict" handler — those characters are rare
                # in valid JSON but a malicious client could send them (#255).
                if len(text.encode("utf-8", errors="replace")) > MAX_MESSAGE_SIZE:
                    frame = _build_error_frame(
                        error="Message too large",
                        detail=f"Maximum message size is {MAX_MESSAGE_SIZE} bytes",
                    )
                    await _send_frame(frame)
                    continue

                # Parse and validate
                try:
                    data = json.loads(text)
                except json.JSONDecodeError as exc:
                    logger.warning("Malformed JSON from WebSocket client: %s", exc)
                    frame = _build_error_frame(
                        error="Invalid JSON",
                        detail=str(exc),
                    )
                    await _send_frame(frame)
                    continue

                try:
                    design = AircraftDesign(**data)
                except ValidationError as exc:
                    logger.warning("Pydantic validation error: %s", exc)
                    # Build structured error with per-field details
                    errors = exc.errors()
                    detail_parts = []
                    for err in errors[:5]:  # limit to 5 errors
                        loc = ".".join(str(l) for l in err["loc"])
                        detail_parts.append(f"{loc}: {err['msg']}")
                    frame = _build_error_frame(
                        error="Validation error",
                        detail="; ".join(detail_parts),
                    )
                    await _send_frame(frame)
                    continue

                # Cancel any in-flight generation immediately — the reader
                # is the only task that can do this promptly since the
                # generator is blocked on run_sync (#188).
                if generation_scope is not None:
                    generation_scope.cancel()

                # Post design to channel (non-blocking send)
                try:
                    send_ch.send_nowait(design)
                except anyio.WouldBlock:
                    # Channel full — drain old entries and send newest
                    while True:
                        try:
                            recv_ch.receive_nowait()
                        except anyio.WouldBlock:
                            break
                    send_ch.send_nowait(design)
        finally:
            send_ch.close()

    async def generator_task() -> None:
        """Consume designs from channel and generate meshes."""
        nonlocal generation_scope

        async for design in recv_ch:
            # Drain channel to get the latest design (last-write-wins)
            latest = design
            while True:
                try:
                    latest = recv_ch.receive_nowait()
                except anyio.WouldBlock:
                    break

            generation_scope = anyio.CancelScope()
            with generation_scope:
                # Compute derived values (pure math, fast)
                derived_dict = compute_derived_values(latest)
                derived = DerivedValues(**derived_dict)

                # Compute warnings (canonical module)
                # Pass derived_dict so V36-V48 dynamic/mass-property warnings fire.
                warnings_list = compute_warnings(latest, derived_dict)

                # Generate geometry in thread pool with limiter.
                # abandon_on_cancel=False ensures the thread releases
                # the CapacityLimiter token when it finishes (#189).
                try:
                    mesh_data, comp_ranges = await anyio.to_thread.run_sync(
                        lambda: _generate_mesh(latest),
                        limiter=_cadquery_limiter,
                        abandon_on_cancel=False,
                    )
                except Exception as gen_err:
                    if generation_scope.cancel_called:
                        # Cancelled while generating — don't send error
                        continue
                    logger.warning("Geometry generation failed: %s", gen_err)
                    frame = _build_error_frame(
                        error="Geometry generation failed",
                        detail=str(gen_err),
                    )
                    try:
                        await _send_frame(frame)
                    except Exception:
                        return
                    continue

                # If scope was cancelled while thread ran, discard result
                if generation_scope.cancel_called:
                    continue

                # Build and send response
                response = _build_mesh_response(
                    mesh_data.to_binary_frame(),
                    derived,
                    warnings_list,
                    component_ranges=comp_ranges,
                )
                try:
                    await _send_frame(response)
                except Exception:
                    return

            # CancelScope context manager handles its own CancelledError —
            # no need to catch it externally.

    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(reader_task)
            tg.start_soon(generator_task)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("WebSocket error")


def _generate_mesh(design: AircraftDesign):
    """Synchronous geometry generation — runs in thread pool.

    Assembles aircraft, tessellates each component separately (faster and
    more robust than boolean union), and merges the mesh data.

    For multi-section wings (#241, #242), each panel is tessellated separately
    so that:
    - Per-panel face normals are consistent (no shading banding at junctions).
    - Per-panel face ranges are exposed as ``wing_left_0``, ``wing_left_1``, etc.
      so the frontend can highlight individual panels.

    Returns:
        Tuple of (MeshData, component_ranges) where component_ranges maps
        component name to [startFace, endFace].  Wing halves appear as
        ``wing_left`` / ``wing_right`` (combined range) plus per-panel sub-keys
        ``wing_left_0``, ``wing_left_1``, etc. when wing_sections > 1.
    """
    from backend.geometry.tessellate import tessellate_for_preview, MeshData
    from backend.geometry.wing import build_wing_panels

    import numpy as np

    # For the preview, we don't need hollow internal geometry.
    # Disabling hollow_parts vastly reduces the vertex count (e.g. 34K -> 1K)
    # and prevents the WebSocket connection from crashing.
    preview_design = design.model_copy(update={"hollow_parts": False})
    components = assemble_aircraft(preview_design)

    if not components:
        raise RuntimeError("No geometry produced")

    # Tessellate each component individually — avoids slow/fragile boolean union.
    # Use coarser tolerance (2.0mm) for fast preview.
    all_verts = []
    all_normals = []
    all_faces = []
    offset = 0
    face_offset = 0

    # Track per-component face ranges for frontend selection highlighting.
    component_ranges: dict[str, list[int]] = {}

    def _add_mesh(name: str, solid: "Any") -> bool:
        """Tessellate one solid and append to accumulators, recording face range.

        Returns True if any faces were added.
        """
        nonlocal offset, face_offset
        mesh = tessellate_for_preview(solid, tolerance=2.0)
        if mesh.vertex_count == 0:
            return False
        all_verts.append(mesh.vertices)
        all_normals.append(mesh.normals)
        all_faces.append(mesh.faces + offset)
        component_ranges[name] = [face_offset, face_offset + mesh.face_count]
        offset += mesh.vertex_count
        face_offset += mesh.face_count
        return True

    # Wing mount position — shared helper ensures consistency with assemble_aircraft
    wing_x, wing_z = _compute_wing_mount(preview_design)

    # For multi-section wings, replace the unioned solid with individual panels
    # so each panel gets its own face range and clean normals (#241, #242).
    # build_wing_panels returns panels in LOCAL wing coordinates (no fuselage offset),
    # so we apply the same (wing_x, 0, wing_z) translation that assemble_aircraft used.
    multi_section_wing_keys: set[str] = set()
    if preview_design.wing_sections > 1:
        for side_key in ("wing_left", "wing_right"):
            if side_key not in components:
                continue
            side = "left" if side_key == "wing_left" else "right"
            try:
                panels = build_wing_panels(preview_design, side=side)
            except Exception:
                # Fall back to the assembled (unioned) solid
                panels = [components[side_key]]
            multi_section_wing_keys.add(side_key)
            half_start_face = face_offset
            for panel_idx, panel_solid in enumerate(panels):
                try:
                    translated = panel_solid.translate((wing_x, 0, wing_z))
                except Exception:
                    translated = panel_solid
                panel_key = f"{side_key}_{panel_idx}"
                _add_mesh(panel_key, translated)
            # Combined range for the half-wing spans all panels tessellated above
            if face_offset > half_start_face:
                component_ranges[side_key] = [half_start_face, face_offset]
        # Combined 'wing' range for backward compatibility
        wing_start: int | None = None
        wing_end: int | None = None
        for side_key in ("wing_left", "wing_right"):
            if side_key in component_ranges:
                r = component_ranges[side_key]
                wing_start = r[0] if wing_start is None else min(wing_start, r[0])
                wing_end = r[1] if wing_end is None else max(wing_end, r[1])
        if wing_start is not None and wing_end is not None:
            component_ranges["wing"] = [wing_start, wing_end]

    for name, solid in components.items():
        # Skip wing halves already handled as per-panel above
        if name in multi_section_wing_keys:
            continue

        # Map component name to category for the combined range
        if "fuselage" in name:
            category = "fuselage"
        elif name in ("wing_left", "wing_right"):
            category = "wing"
        elif name.startswith("aileron") or name.startswith("elevon"):
            category = name  # control surfaces keep their own key
        elif name.startswith("elevator") or name.startswith("rudder") or name.startswith("ruddervator"):
            category = name  # control surfaces keep their own key
        elif name.startswith("gear_"):
            category = name  # gear components keep their own key
        elif "wing" in name:
            category = "wing"
        else:
            category = "tail"

        start_face = face_offset
        added = _add_mesh(name, solid)

        # Also maintain the combined category range for backward compatibility
        if added and category != name:
            if category in component_ranges:
                component_ranges[category][1] = face_offset
            else:
                component_ranges[category] = [start_face, face_offset]

    if not all_verts:
        raise RuntimeError("Tessellation produced no geometry")

    mesh_data = MeshData(
        vertices=np.concatenate(all_verts),
        normals=np.concatenate(all_normals),
        faces=np.concatenate(all_faces),
    )
    return mesh_data, component_ranges
