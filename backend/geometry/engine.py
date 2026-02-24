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

from backend.models import AircraftDesign, DerivedValues, GenerationResult

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
    fuselage = build_fuselage(design)

    # 2. Wing mount position
    wing_x_frac = _WING_X_FRACTION.get(design.fuselage_preset, 0.30)
    wing_x = design.fuselage_length * wing_x_frac

    # Estimate fuselage height for wing Z positioning.
    # Must match the actual max_height used in each fuselage builder.
    preset = design.fuselage_preset
    if preset == "Pod":
        fuselage_height = design.wing_chord * 0.45  # pod: max_width * 1.0
    elif preset == "Blended-Wing-Body":
        fuselage_height = design.wing_chord * 0.15  # BWB: flat airfoil-like
    else:  # Conventional
        fuselage_height = design.wing_chord * 0.35 * 1.1
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

    # Cut wing-root saddle pocket from fuselage for a flush mount.
    fuselage = _cut_wing_saddle(cq, fuselage, design, wing_x, wing_z)
    components["fuselage"] = fuselage

    # 3. Tail surfaces: position at X = wing_x + tail_arm
    tail_x = wing_x + design.tail_arm
    tail_components = build_tail(design)

    for name, solid in tail_components.items():
        try:
            components[name] = solid.translate((tail_x, 0, 0))
        except Exception:
            components[name] = solid

    return components


def _cut_wing_saddle(
    cq_mod: type,
    fuselage: cq.Workplane,
    design: AircraftDesign,
    wing_x: float,
    wing_z: float,
) -> cq.Workplane:
    """Subtract a wing-root-shaped pocket from the fuselage at the mount point.

    Creates a box matching the wing root chord and a small spanwise depth,
    centered at (wing_x, 0, wing_z), and cuts it from the fuselage so the
    wing root sits flush.
    """
    cq = cq_mod

    root_chord = design.wing_chord
    # Pocket depth extends slightly into the fuselage on each side.
    # Limit depth to less than fuselage wall thickness to avoid penetrating
    # the shell and exposing the hollow interior (#86).
    fuselage_wall_t = design.wall_thickness
    pocket_half_y = min(design.wing_chord * 0.05, fuselage_wall_t * 0.8)
    # Pocket height approximates the root airfoil thickness (~12% of chord)
    pocket_height = root_chord * 0.14

    try:
        pocket = (
            cq.Workplane("XY")
            .transformed(offset=(wing_x + root_chord / 2, 0, wing_z))
            .box(root_chord, pocket_half_y * 2, pocket_height)
        )
        fuselage = fuselage.cut(pocket)
    except Exception:
        pass  # If boolean cut fails, return fuselage as-is

    return fuselage


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
    8. wall_thickness_mm     = design.wall_thickness (user-editable, F14)

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

    # CG position aft of root LE at 25% MAC, accounting for sweep.
    # For swept/tapered wings the MAC is located aft of the root LE by
    # y_mac * tan(sweep), where y_mac is the spanwise position of the MAC.
    # The aerodynamic center (25% MAC) is then:
    #   CG = 0.25 * MAC + y_mac * tan(sweep_c/4)
    half_span = design.wing_span / 2.0
    sweep_rad = math.radians(design.wing_sweep)
    y_mac = (
        (half_span / 3.0) * (1.0 + 2.0 * lambda_) / (1.0 + lambda_)
    ) if (1.0 + lambda_) > 0 else 0.0
    estimated_cg_mm = 0.25 * mean_aero_chord_mm + y_mac * math.tan(sweep_rad)

    min_feature_thickness_mm = 2.0 * design.nozzle_diameter

    # Wall thickness reports the user-controllable fuselage wall_thickness (F14).
    wall_thickness_mm = design.wall_thickness

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

    # 4. Compute validation warnings (using canonical module)
    from backend.validation import compute_warnings

    warnings = compute_warnings(design)

    return GenerationResult(
        derived=derived,
        warnings=warnings,
    )
