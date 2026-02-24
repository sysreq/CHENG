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
    _compute_warnings,
)
from backend.models import AircraftDesign, DerivedValues

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
    derived: dict[str, float],
    warnings: list[dict[str, Any]],
) -> bytes:
    """Append JSON trailer to mesh binary frame."""
    trailer = json.dumps({
        "derived": derived,
        "validation": warnings,
    }).encode("utf-8")
    return mesh_binary + trailer


@router.websocket("/ws/preview")
async def preview_websocket(ws: WebSocket) -> None:
    """Handle a single WebSocket connection for real-time preview."""
    await ws.accept()
    logger.info("WebSocket client connected")

    # Cancel scope for in-flight generation (last-write-wins)
    cancel_scope: anyio.CancelScope | None = None

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

            # Start new generation in a cancel scope
            cancel_scope = anyio.CancelScope()

            try:
                with cancel_scope:
                    # Compute derived values (pure math, fast)
                    derived_dict = compute_derived_values(design)

                    # Compute warnings
                    warnings_list = _compute_warnings(design, derived_dict)
                    warnings_dicts = [w.model_dump() for w in warnings_list]

                    # Generate geometry in thread pool with limiter
                    try:
                        mesh_data = await anyio.to_thread.run_sync(
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

                    # Build and send response
                    response = _build_mesh_response(
                        mesh_data.to_binary_frame(),
                        derived_dict,
                        warnings_dicts,
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

    Assembles aircraft, tessellates the union for preview.
    """
    from backend.geometry.tessellate import tessellate_for_preview

    components = assemble_aircraft(design)

    # Union all components into a single solid for preview tessellation
    import cadquery as cq

    solids = list(components.values())
    if not solids:
        raise RuntimeError("No geometry produced")

    combined = solids[0]
    for s in solids[1:]:
        try:
            combined = combined.union(s)
        except Exception:
            # If boolean union fails, just use the first solid
            pass

    return tessellate_for_preview(combined)
