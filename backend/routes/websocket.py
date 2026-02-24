"""/ws/preview — WebSocket handler for interactive 3D preview.

Connection lifecycle (spec §6.2):
1. Client opens ws://host:8000/ws/preview
2. Client sends AircraftDesign JSON on each parameter change
3. Server cancels in-flight generation (last-write-wins), runs new one
4. Server sends binary mesh frame (0x01) or error frame (0x02)
5. On disconnect, cancel pending work and clean up
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


def _build_error_frame(error: str, detail: str = "", field: str = "") -> bytes:
    """Build a 0x02 error binary frame."""
    payload = {"error": error}
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
    """Handle a single WebSocket connection for real-time preview."""
    await ws.accept()
    logger.info("WebSocket client connected")

    # Cancel scope for in-flight generation (last-write-wins)
    cancel_scope: anyio.CancelScope | None = None

    # Generation counter: incremented on each new request.  After a thread
    # finishes, we compare its snapshot to the current counter — if it's
    # stale we discard the result instead of sending it (#90).
    generation_counter = 0

    try:
        while True:
            raw = await ws.receive_text()

            # Parse design params
            try:
                data = json.loads(raw)
                design = AircraftDesign(**data)
            except (json.JSONDecodeError, ValidationError) as exc:
                frame = _build_error_frame(
                    error="Invalid design parameters",
                    detail=str(exc),
                )
                await ws.send_bytes(frame)
                continue

            # Cancel any in-flight generation
            if cancel_scope is not None:
                cancel_scope.cancel()

            # Increment generation counter so in-flight threads know they're stale
            generation_counter += 1
            my_generation = generation_counter

            # Start new generation in a cancel scope
            cancel_scope = anyio.CancelScope()

            try:
                with cancel_scope:
                    # Compute derived values (pure math, fast)
                    derived_dict = compute_derived_values(design)
                    derived = DerivedValues(**derived_dict)

                    # Compute warnings (canonical module)
                    warnings_list = compute_warnings(design)

                    # Generate geometry in thread pool with limiter
                    try:
                        mesh_data, comp_ranges = await anyio.to_thread.run_sync(
                            lambda: _generate_mesh(design),
                            limiter=_cadquery_limiter,
                            abandon_on_cancel=True,
                        )
                    except Exception as gen_err:
                        logger.warning("Geometry generation failed: %s", gen_err)
                        frame = _build_error_frame(
                            error="Geometry generation failed",
                            detail=str(gen_err),
                        )
                        await ws.send_bytes(frame)
                        continue

                    # Discard stale results: if a newer request arrived while
                    # we were generating, skip sending this outdated frame.
                    if my_generation != generation_counter:
                        logger.debug("Generation %d superseded by %d, discarding", my_generation, generation_counter)
                        continue

                    # Build and send response
                    response = _build_mesh_response(
                        mesh_data.to_binary_frame(),
                        derived,
                        warnings_list,
                        component_ranges=comp_ranges,
                    )
                    await ws.send_bytes(response)

            except anyio.get_cancelled_exc_class():
                # Generation was superseded by a newer request — that's fine
                logger.debug("Generation cancelled (superseded)")
                continue

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("WebSocket error")
    finally:
        if cancel_scope is not None:
            cancel_scope.cancel()


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
