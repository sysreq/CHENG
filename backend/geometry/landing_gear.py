"""Landing gear geometry builder.

Generates basic strut geometry for tricycle or taildragger configurations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import cadquery as cq

if TYPE_CHECKING:
    from backend.models import AircraftDesign


def build_landing_gear(design: AircraftDesign) -> dict[str, cq.Workplane]:
    """Build landing gear based on the selected configuration.

    Returns a dictionary of named gear components.
    """
    if not hasattr(design, "landing_gear_type") or design.landing_gear_type == "None":
        return {}

    gear_components = {}
    
    # Simple struts
    main_gear_pos = (design.fuselage_length * design.main_gear_position / 100.0) if hasattr(design, "main_gear_position") else 100
    main_height = design.main_gear_height if hasattr(design, "main_gear_height") else 40
    track = design.main_gear_track if hasattr(design, "main_gear_track") else 120
    
    # Left Main Gear
    left_strut = (
        cq.Workplane("XY")
        .transformed(offset=(main_gear_pos, track / 2.0, -main_height / 2.0))
        .box(5, 5, main_height)
    )
    gear_components["main_gear_left"] = left_strut
    
    # Right Main Gear
    right_strut = (
        cq.Workplane("XY")
        .transformed(offset=(main_gear_pos, -track / 2.0, -main_height / 2.0))
        .box(5, 5, main_height)
    )
    gear_components["main_gear_right"] = right_strut
    
    if design.landing_gear_type == "Tricycle":
        nose_gear_height = design.nose_gear_height if hasattr(design, "nose_gear_height") else 45
        nose_strut = (
            cq.Workplane("XY")
            .transformed(offset=(10, 0, -nose_gear_height / 2.0))
            .box(5, 5, nose_gear_height)
        )
        gear_components["nose_gear"] = nose_strut
    elif design.landing_gear_type == "Taildragger":
        tail_gear_pos = (design.fuselage_length * design.tail_gear_position / 100.0) if hasattr(design, "tail_gear_position") else 280
        tail_gear_height = 20
        tail_strut = (
            cq.Workplane("XY")
            .transformed(offset=(tail_gear_pos, 0, -tail_gear_height / 2.0))
            .box(5, 5, tail_gear_height)
        )
        gear_components["tail_gear"] = tail_strut
        
    return gear_components
