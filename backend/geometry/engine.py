"""Geometry engine -- assembly, derived values, and async generation entry point.

This module ties together all component builders and provides the primary
entry points used by the REST/WebSocket handlers.

- ``assemble_aircraft()`` -- combine fuselage, wings, and tail
- ``compute_derived_values()`` -- pure math, no CadQuery
- ``generate_geometry_safe()`` -- async with CapacityLimiter(4)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import cadquery as cq

from backend.models import AircraftDesign, DerivedValues, GenerationResult, ValidationWarning

# Lazy import of anyio -- only needed when running async code.
# This allows the module to be imported in environments without anyio.
try:
    import anyio
    _cadquery_limiter = anyio.CapacityLimiter(4)
except Exception:
    _cadquery_limiter = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Wing mount X positions (fraction of fuselage length)
# ---------------------------------------------------------------------------

_WING_X_FRACTION: dict[str, float] = {
    "Conventional": 0.30,
    "Pod": 0.25,
    "Blended-Wing-Body": 0.35,
}

# Wing mount Z offsets (fraction of fuselage height, which we estimate)
_WING_Z_FRACTION: dict[str, float] = {
    "High-Wing": 0.4,
    "Shoulder-Wing": 0.25,
    "Mid-Wing": 0.0,
    "Low-Wing": -0.4,
}


# ---------------------------------------------------------------------------
# Public API: Assembly
# ---------------------------------------------------------------------------


def assemble_aircraft(design: AircraftDesign) -> dict[str, cq.Workplane]:
    """Assemble all aircraft components into their final positions.

    Calls each component builder, then translates/rotates into the aircraft
    coordinate system: Origin at nose, +X aft, +Y starboard, +Z up.

    **Assembly steps:**
    1. Build fuselage (already at origin).
    2. Build wing halves, translate to wing mount position:
       - X: 25-35% of fuselage_length (varies by fuselage_preset)
       - Z: per wing_mount_type (High/Mid/Low/Shoulder)
    3. Build tail surfaces, translate to X = wing_position_x + tail_arm.
    4. Combine into a single dictionary.

    Returns:
        Dict with keys: "fuselage", "wing_left", "wing_right", plus tail keys
        (varies by tail_type -- see build_tail).  Total: 5 or 4 entries.

    Raises:
        ValueError: If any component builder raises.
        RuntimeError: If CadQuery boolean operations fail.
    """
    import cadquery as cq  # noqa: F811

    from backend.geometry.fuselage import build_fuselage
    from backend.geometry.wing import build_wing
    from backend.geometry.tail import build_tail

    components: dict[str, cq.Workplane] = {}

    # 1. Fuselage (already at origin, nose at X=0, tail at X=fuselage_length)
    components["fuselage"] = build_fuselage(design)

    # 2. Wing mount position
    wing_x_frac = _WING_X_FRACTION.get(design.fuselage_preset, 0.30)
    wing_x = design.fuselage_length * wing_x_frac

    # Estimate fuselage height for wing Z positioning
    fuselage_height = design.wing_chord * 0.35 * 1.1  # matches fuselage builder
    wing_z_frac = _WING_Z_FRACTION.get(design.wing_mount_type, 0.0)
    wing_z = fuselage_height * wing_z_frac

    # Build wings and translate to mount position
    wing_left = build_wing(design, side="left")
    wing_right = build_wing(design, side="right")

    try:
        components["wing_left"] = wing_left.translate((wing_x, 0, wing_z))
        components["wing_right"] = wing_right.translate((wing_x, 0, wing_z))
    except Exception:
        # If translate fails (shouldn't, but safe), use untranslated
        components["wing_left"] = wing_left
        components["wing_right"] = wing_right

    # 3. Tail surfaces: position at X = wing_x + tail_arm
    tail_x = wing_x + design.tail_arm
    tail_components = build_tail(design)

    for name, solid in tail_components.items():
        try:
            components[name] = solid.translate((tail_x, 0, 0))
        except Exception:
            components[name] = solid

    return components


# ---------------------------------------------------------------------------
# Public API: Derived Values (pure math -- no CadQuery)
# ---------------------------------------------------------------------------


def compute_derived_values(design: AircraftDesign) -> dict[str, float]:
    """Compute all 8 derived/read-only values from design parameters.

    Pure math -- no CadQuery, no geometry.  Safe to call frequently.

    **Formulas:**
    1. tip_chord_mm     = wing_chord * wing_tip_root_ratio
    2. wing_area_cm2         = 0.5 * (wing_chord + tip_chord) * wing_span / 100
    3. aspect_ratio          = wing_span^2 / wing_area_mm^2
    4. mean_aero_chord_mm    = (2/3) * wing_chord * (1 + l + l^2) / (1 + l)
                               where l = wing_tip_root_ratio
    5. taper_ratio           = tip_chord / wing_chord  (= wing_tip_root_ratio in MVP)
    6. estimated_cg_mm       = 0.25 * mean_aero_chord_mm
    7. min_feature_thickness_mm = 2 * nozzle_diameter
    8. wall_thickness_mm     = 1.6 (Conventional/Pod) or wing_skin_thickness (BWB)

    Args:
        design: Complete aircraft design parameters.

    Returns:
        Dict with keys matching the WebSocket JSON trailer "derived" object.
    """
    lambda_ = design.wing_tip_root_ratio

    tip_chord_mm = design.wing_chord * lambda_

    wing_area_mm2 = 0.5 * (design.wing_chord + tip_chord_mm) * design.wing_span
    wing_area_cm2 = wing_area_mm2 / 100.0

    aspect_ratio = (design.wing_span ** 2) / wing_area_mm2 if wing_area_mm2 > 0 else 0.0

    mean_aero_chord_mm = (
        (2.0 / 3.0)
        * design.wing_chord
        * (1.0 + lambda_ + lambda_ ** 2)
        / (1.0 + lambda_)
    ) if (1.0 + lambda_) > 0 else design.wing_chord

    taper_ratio = tip_chord_mm / design.wing_chord if design.wing_chord > 0 else 0.0

    estimated_cg_mm = 0.25 * mean_aero_chord_mm

    min_feature_thickness_mm = 2.0 * design.nozzle_diameter

    wall_thickness_map: dict[str, float] = {
        "Conventional": 1.6,
        "Pod": 1.6,
        "Blended-Wing-Body": design.wing_skin_thickness,
    }
    wall_thickness_mm = wall_thickness_map.get(design.fuselage_preset, 1.6)

    return {
        "tip_chord_mm": tip_chord_mm,
        "wing_area_cm2": wing_area_cm2,
        "aspect_ratio": aspect_ratio,
        "mean_aero_chord_mm": mean_aero_chord_mm,
        "taper_ratio": taper_ratio,
        "estimated_cg_mm": estimated_cg_mm,
        "min_feature_thickness_mm": min_feature_thickness_mm,
        "wall_thickness_mm": wall_thickness_mm,
    }


# ---------------------------------------------------------------------------
# Public API: Async Generation Entry Point
# ---------------------------------------------------------------------------


async def generate_geometry_safe(design: AircraftDesign) -> GenerationResult:
    """Generate aircraft geometry with concurrency control.

    Primary entry point for all geometry generation.  Wraps blocking CadQuery
    operations in a thread with CapacityLimiter.

    Pipeline: validate -> assemble_aircraft -> tessellate -> compute_derived
              -> compute_warnings -> pack result.

    Args:
        design: Validated AircraftDesign parameters.

    Returns:
        GenerationResult with derived values and warnings.
    """
    import anyio  # noqa: F811

    global _cadquery_limiter
    if _cadquery_limiter is None:
        _cadquery_limiter = anyio.CapacityLimiter(4)

    result = await anyio.to_thread.run_sync(
        lambda: _generate_geometry_blocking(design),
        limiter=_cadquery_limiter,
        abandon_on_cancel=True,
    )
    return result


def _generate_geometry_blocking(design: AircraftDesign) -> GenerationResult:
    """Synchronous geometry generation -- runs inside a worker thread.

    NOT public API.  Called only by generate_geometry_safe().
    """
    from backend.geometry.tessellate import tessellate_for_preview

    # 1. Compute derived values (pure math, fast)
    derived_dict = compute_derived_values(design)
    derived = DerivedValues(**derived_dict)

    # 2. Assemble aircraft geometry (CadQuery, slow)
    components = assemble_aircraft(design)

    # 3. Tessellate for preview (CadQuery, moderate)
    # Note: mesh data is used by the WebSocket handler, not returned in GenerationResult
    # The WebSocket handler calls tessellate_for_preview separately.

    # 4. Compute validation warnings
    warnings = _compute_warnings(design, derived_dict)

    return GenerationResult(
        derived=derived,
        warnings=warnings,
    )


def _compute_warnings(
    design: AircraftDesign,
    derived: dict[str, float],
) -> list[ValidationWarning]:
    """Compute structural and print validation warnings.

    Structural warnings (V01-V06):
    - V02: Aspect ratio out of range
    - V04: Tail volume coefficient too low
    - V05: Dihedral angle warning

    Print warnings (V16-V23):
    - V17: Thin wall warning
    - V20: Minimum feature size
    - V22: Joint tolerance tight
    - V23: Nozzle diameter vs detail mismatch
    """
    warnings: list[ValidationWarning] = []

    aspect_ratio = derived["aspect_ratio"]
    taper_ratio = derived["taper_ratio"]
    min_feature = derived["min_feature_thickness_mm"]
    wall_thickness = derived["wall_thickness_mm"]

    # V02: Aspect ratio range check
    if aspect_ratio > 12.0:
        warnings.append(ValidationWarning(
            id="V02",
            message=(
                f"Aspect ratio {aspect_ratio:.1f} is high (>12). "
                "The wing may be structurally weak. Consider reducing wingspan "
                "or increasing chord."
            ),
            fields=["wing_span", "wing_chord"],
        ))
    elif aspect_ratio < 3.0:
        warnings.append(ValidationWarning(
            id="V02",
            message=(
                f"Aspect ratio {aspect_ratio:.1f} is low (<3). "
                "The aircraft may have high induced drag. Consider increasing "
                "wingspan or reducing chord."
            ),
            fields=["wing_span", "wing_chord"],
        ))

    # V04: Tail volume coefficient check
    mac = derived["mean_aero_chord_mm"]
    wing_area = derived["wing_area_cm2"] * 100.0  # back to mm^2
    if wing_area > 0 and mac > 0:
        h_stab_area = design.h_stab_span * design.h_stab_chord
        v_h = (h_stab_area * design.tail_arm) / (wing_area * mac)
        if v_h < 0.3:
            warnings.append(ValidationWarning(
                id="V04",
                message=(
                    f"Horizontal tail volume coefficient ({v_h:.2f}) is low (<0.3). "
                    "The aircraft may be unstable in pitch. Consider increasing "
                    "h_stab span/chord or tail arm."
                ),
                fields=["h_stab_span", "h_stab_chord", "tail_arm"],
            ))

    # V05: Dihedral angle warning
    if design.wing_dihedral > 10:
        warnings.append(ValidationWarning(
            id="V05",
            message=(
                f"Wing dihedral ({design.wing_dihedral} deg) is high (>10). "
                "This may cause excessive dutch roll tendency."
            ),
            fields=["wing_dihedral"],
        ))
    elif design.wing_dihedral < -5:
        warnings.append(ValidationWarning(
            id="V05",
            message=(
                f"Wing dihedral ({design.wing_dihedral} deg) is negative (<-5). "
                "Anhedral requires careful stability analysis."
            ),
            fields=["wing_dihedral"],
        ))

    # V17: Thin wall warning
    if design.hollow_parts and wall_thickness < 1.0:
        warnings.append(ValidationWarning(
            id="V17",
            message=(
                f"Wall thickness ({wall_thickness:.1f} mm) is very thin (<1.0 mm). "
                "Parts may be fragile and difficult to print."
            ),
            fields=["wing_skin_thickness"],
        ))

    # V20: Minimum feature size vs nozzle
    if design.te_min_thickness < min_feature:
        warnings.append(ValidationWarning(
            id="V20",
            message=(
                f"Trailing edge thickness ({design.te_min_thickness:.1f} mm) is less "
                f"than minimum feature size ({min_feature:.1f} mm = 2 x nozzle). "
                "The trailing edge may not print correctly."
            ),
            fields=["te_min_thickness", "nozzle_diameter"],
        ))

    # V22: Joint tolerance check
    if design.joint_tolerance < 0.1:
        warnings.append(ValidationWarning(
            id="V22",
            message=(
                f"Joint tolerance ({design.joint_tolerance:.2f} mm) is tight (<0.1 mm). "
                "Sections may not fit together. Consider increasing tolerance."
            ),
            fields=["joint_tolerance"],
        ))

    # V23: Nozzle diameter vs detail level
    if design.nozzle_diameter > 0.6 and design.te_min_thickness < 1.5:
        warnings.append(ValidationWarning(
            id="V23",
            message=(
                f"Large nozzle ({design.nozzle_diameter:.1f} mm) with thin trailing edge "
                f"({design.te_min_thickness:.1f} mm). Fine details may not resolve."
            ),
            fields=["nozzle_diameter", "te_min_thickness"],
        ))

    return warnings
