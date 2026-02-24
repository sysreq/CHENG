"""Geometry engine -- public API re-exports.

Usage::

    from backend.geometry import assemble_aircraft, generate_geometry_safe, compute_derived_values
"""

from __future__ import annotations

from backend.geometry.engine import (
    assemble_aircraft,
    compute_derived_values,
    generate_geometry_safe,
)

__all__ = [
    "assemble_aircraft",
    "compute_derived_values",
    "generate_geometry_safe",
]
