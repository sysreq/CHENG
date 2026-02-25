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

                # Handle both text and binary frames
                if "text" in raw:
                    text = raw["text"]
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

                # Reject oversized text messages (#182)
                if len(text) > MAX_MESSAGE_SIZE:
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
                warnings_list = compute_warnings(latest)

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

    Returns:
        Tuple of (MeshData, component_ranges) where component_ranges maps
        component category ('fuselage', 'wing', 'tail') to [startFace, endFace].
    """
    from backend.geometry.tessellate import tessellate_for_preview, MeshData

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
    # Keys are component categories: 'fuselage', 'wing', 'tail'.
    component_ranges: dict[str, list[int]] = {}

    for name, solid in components.items():
        mesh = tessellate_for_preview(solid, tolerance=2.0)
        if mesh.vertex_count == 0:
            continue
        all_verts.append(mesh.vertices)
        all_normals.append(mesh.normals)
        all_faces.append(mesh.faces + offset)

        # Map component name to category
        if "fuselage" in name:
            category = "fuselage"
        elif "wing" in name:
            category = "wing"
        else:
            category = "tail"

        start_face = face_offset
        end_face = face_offset + mesh.face_count
        if category in component_ranges:
            # Extend existing range (e.g. wing_left + wing_right)
            component_ranges[category][1] = end_face
        else:
            component_ranges[category] = [start_face, end_face]

        offset += mesh.vertex_count
        face_offset += mesh.face_count

    if not all_verts:
        raise RuntimeError("Tessellation produced no geometry")

    mesh_data = MeshData(
        vertices=np.concatenate(all_verts),
        normals=np.concatenate(all_normals),
        faces=np.concatenate(all_faces),
    )
    return mesh_data, component_ranges
