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
    from backend.geometry.control_surfaces import (
        cut_aileron,
        cut_elevator,
        cut_rudder,
        cut_ruddervators,
        cut_elevons,
    )

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
    wing_left_raw = build_wing(design, side="left")
    wing_right_raw = build_wing(design, side="right")

    # Apply control surface cuts BEFORE translation (in local wing frame)
    is_flying_wing = design.fuselage_preset == "Blended-Wing-Body"
    if is_flying_wing and design.elevon_enable:
        wing_left_raw, elevon_left = cut_elevons(wing_left_raw, design, side="left")
        wing_right_raw, elevon_right = cut_elevons(wing_right_raw, design, side="right")
    elif not is_flying_wing and design.aileron_enable:
        wing_left_raw, aileron_left = cut_aileron(wing_left_raw, design, side="left")
        wing_right_raw, aileron_right = cut_aileron(wing_right_raw, design, side="right")
    else:
        aileron_left = aileron_right = None
        elevon_left = elevon_right = None

    try:
        components["wing_left"] = wing_left_raw.translate((wing_x, 0, wing_z))
        components["wing_right"] = wing_right_raw.translate((wing_x, 0, wing_z))
    except Exception:
        # If translate fails (shouldn't, but safe), use untranslated
        components["wing_left"] = wing_left_raw
        components["wing_right"] = wing_right_raw

    # Translate control surfaces along with their parent wing
    if not is_flying_wing and design.aileron_enable:
        if aileron_left is not None:
            try:
                components["aileron_left"] = aileron_left.translate((wing_x, 0, wing_z))
            except Exception:
                components["aileron_left"] = aileron_left
        if aileron_right is not None:
            try:
                components["aileron_right"] = aileron_right.translate((wing_x, 0, wing_z))
            except Exception:
                components["aileron_right"] = aileron_right

    if is_flying_wing and design.elevon_enable:
        if elevon_left is not None:
            try:
                components["elevon_left"] = elevon_left.translate((wing_x, 0, wing_z))
            except Exception:
                components["elevon_left"] = elevon_left
        if elevon_right is not None:
            try:
                components["elevon_right"] = elevon_right.translate((wing_x, 0, wing_z))
            except Exception:
                components["elevon_right"] = elevon_right

    # Cut wing-root saddle pocket from fuselage for a flush mount.
    fuselage = _cut_wing_saddle(cq, fuselage, design, wing_x, wing_z)
    components["fuselage"] = fuselage

    # 3. Tail surfaces: position at X = wing_x + tail_arm
    tail_x = wing_x + design.tail_arm
    tail_components = build_tail(design)

    # Apply control surface cuts to tail components BEFORE translation
    if design.tail_type == "V-Tail" and design.ruddervator_enable:
        v_tail_left = tail_components.get("v_tail_left")
        v_tail_right = tail_components.get("v_tail_right")
        if v_tail_left is not None and v_tail_right is not None:
            v_tail_left, v_tail_right, ruddervator_left, ruddervator_right = cut_ruddervators(
                v_tail_left, v_tail_right, design
            )
            tail_components["v_tail_left"] = v_tail_left
            tail_components["v_tail_right"] = v_tail_right
        else:
            ruddervator_left = ruddervator_right = None
    else:
        ruddervator_left = ruddervator_right = None

    if design.tail_type not in ("V-Tail", "Cruciform") and design.elevator_enable:
        h_stab_left = tail_components.get("h_stab_left")
        h_stab_right = tail_components.get("h_stab_right")
        if h_stab_left is not None:
            tail_components["h_stab_left"], elevator_left = cut_elevator(
                h_stab_left, design, side="left"
            )
        else:
            elevator_left = None
        if h_stab_right is not None:
            tail_components["h_stab_right"], elevator_right = cut_elevator(
                h_stab_right, design, side="right"
            )
        else:
            elevator_right = None
    else:
        elevator_left = elevator_right = None

    if design.tail_type not in ("V-Tail",) and design.rudder_enable:
        v_stab = tail_components.get("v_stab")
        if v_stab is not None:
            tail_components["v_stab"], rudder = cut_rudder(v_stab, design)
        else:
            rudder = None
    else:
        rudder = None

    for name, solid in tail_components.items():
        try:
            components[name] = solid.translate((tail_x, 0, 0))
        except Exception:
            components[name] = solid

    # Add translated tail control surfaces
    if ruddervator_left is not None:
        try:
            components["ruddervator_left"] = ruddervator_left.translate((tail_x, 0, 0))
        except Exception:
            components["ruddervator_left"] = ruddervator_left
    if ruddervator_right is not None:
        try:
            components["ruddervator_right"] = ruddervator_right.translate((tail_x, 0, 0))
        except Exception:
            components["ruddervator_right"] = ruddervator_right

    if elevator_left is not None:
        try:
            components["elevator_left"] = elevator_left.translate((tail_x, 0, 0))
        except Exception:
            components["elevator_left"] = elevator_left
    if elevator_right is not None:
        try:
            components["elevator_right"] = elevator_right.translate((tail_x, 0, 0))
        except Exception:
            components["elevator_right"] = elevator_right

    if rudder is not None:
        try:
            components["rudder"] = rudder.translate((tail_x, 0, 0))
        except Exception:
            components["rudder"] = rudder

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

    **Weight estimation (v0.6):**
    9-12. weight_wing_g, weight_tail_g, weight_fuselage_g, weight_total_g

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

    min_feature_thickness_mm = 2.0 * design.nozzle_diameter

    # Wall thickness reports the user-controllable fuselage wall_thickness (F14).
    wall_thickness_mm = design.wall_thickness

    # Weight estimation (v0.6 #142)
    weights = _compute_weight_estimates(design)

    # Full CG calculator (v0.6 #139) — weighted average of all mass positions.
    # All X positions are measured from the aircraft nose (X=0).
    half_span = design.wing_span / 2.0
    sweep_rad = math.radians(design.wing_sweep)
    y_mac = (
        (half_span / 3.0) * (1.0 + 2.0 * lambda_) / (1.0 + lambda_)
    ) if (1.0 + lambda_) > 0 else 0.0

    estimated_cg_mm = _compute_cg(
        design, weights, mean_aero_chord_mm, y_mac, sweep_rad,
    )

    return {
        "tip_chord_mm": tip_chord_mm,
        "wing_area_cm2": wing_area_cm2,
        "aspect_ratio": aspect_ratio,
        "mean_aero_chord_mm": mean_aero_chord_mm,
        "taper_ratio": taper_ratio,
        "estimated_cg_mm": estimated_cg_mm,
        "min_feature_thickness_mm": min_feature_thickness_mm,
        "wall_thickness_mm": wall_thickness_mm,
        **weights,
    }


def _compute_weight_estimates(design: AircraftDesign) -> dict[str, float]:
    """Estimate printed part weights based on bounding volumes, infill, and density.

    Weight estimation approach for FDM-printed RC aircraft:

    1. **Bounding volume**: Approximate each component's solid volume from its
       parametric dimensions (trapezoidal planform for wings/tail, elliptical
       cross-section cylinder for fuselage).

    2. **Airfoil thickness ratio**: Wings and tail surfaces are not solid blocks;
       they have an airfoil cross-section. A typical airfoil occupies ~60-70% of
       its bounding box. We use 0.65 as the average fill factor.

    3. **Shell + infill model**: For hollow parts, the printed weight comes from:
       - Outer shell: skin_thickness perimeter walls (solid PLA)
       - Internal infill: fill the interior at print_infill percentage
       The effective material fraction is:
         f_eff = 1 - (1 - infill/100) * (1 - shell_fraction)
       where shell_fraction approximates what fraction of the cross-section
       is occupied by the solid skin walls.

    4. **Density**: Material density in g/cm^3 (PLA default: 1.24)

    All dimensions in mm; convert to cm^3 for density multiplication.

    Returns dict with weight_wing_g, weight_tail_g, weight_fuselage_g, weight_total_g.
    """
    density = design.material_density  # g/cm^3
    infill_frac = design.print_infill / 100.0
    skin_t = design.wing_skin_thickness  # mm
    wall_t = design.wall_thickness  # mm (fuselage)

    # --- Wing weight (both halves) ---
    # Planform area = 0.5 * (root_chord + tip_chord) * span (mm^2)
    tip_chord = design.wing_chord * design.wing_tip_root_ratio
    wing_planform_mm2 = 0.5 * (design.wing_chord + tip_chord) * design.wing_span

    # Average airfoil thickness ~ 12% of mean chord for typical airfoils
    mean_chord = 0.5 * (design.wing_chord + tip_chord)
    airfoil_thickness_fraction = 0.12
    avg_thickness_mm = mean_chord * airfoil_thickness_fraction

    # Bounding volume * airfoil fill factor (airfoil shape is ~65% of bounding box)
    airfoil_fill = 0.65
    wing_solid_vol_mm3 = wing_planform_mm2 * avg_thickness_mm * airfoil_fill

    # Effective material fraction for shell + infill
    # shell_frac: ratio of skin volume to total airfoil volume.
    # Top+bottom skins cover full planform at thickness skin_t each = 2*skin_t.
    # Divide by (avg_thickness * airfoil_fill) since the bounding volume already
    # has the fill factor applied, and the shell covers the full planform.
    wing_shell_frac = min(1.0, (2.0 * skin_t) / (avg_thickness_mm * airfoil_fill)) if avg_thickness_mm > 0 else 1.0
    wing_f_eff = 1.0 - (1.0 - infill_frac) * (1.0 - wing_shell_frac)
    wing_vol_cm3 = wing_solid_vol_mm3 * wing_f_eff / 1000.0  # mm^3 -> cm^3
    weight_wing_g = wing_vol_cm3 * density

    # --- Tail weight ---
    if design.tail_type == "V-Tail":
        # V-tail: two canted panels (rectangular planform approximation)
        tail_planform_mm2 = design.v_tail_chord * design.v_tail_span
        tail_mean_chord = design.v_tail_chord
    else:
        # Conventional/T-Tail/Cruciform: h_stab + v_stab
        h_stab_area = design.h_stab_chord * design.h_stab_span
        v_stab_area = design.v_stab_root_chord * design.v_stab_height
        tail_planform_mm2 = h_stab_area + v_stab_area
        total_span = design.h_stab_span + design.v_stab_height
        tail_mean_chord = (
            (design.h_stab_chord * design.h_stab_span
             + design.v_stab_root_chord * design.v_stab_height)
            / max(total_span, 1.0)
        )

    tail_thickness_mm = tail_mean_chord * airfoil_thickness_fraction
    tail_solid_vol_mm3 = tail_planform_mm2 * tail_thickness_mm * airfoil_fill

    tail_shell_frac = min(1.0, (2.0 * skin_t) / (tail_thickness_mm * airfoil_fill)) if tail_thickness_mm > 0 else 1.0
    tail_f_eff = 1.0 - (1.0 - infill_frac) * (1.0 - tail_shell_frac)
    tail_vol_cm3 = tail_solid_vol_mm3 * tail_f_eff / 1000.0
    weight_tail_g = tail_vol_cm3 * density

    # --- Fuselage weight ---
    # Approximate as elliptical cross-section tube along the length.
    # Cross-section dimensions must match fuselage builder (engine.py assembly).
    preset = design.fuselage_preset
    if preset == "Pod":
        max_width = design.wing_chord * 0.45
        max_height = max_width * 1.0
    elif preset == "Blended-Wing-Body":
        max_width = design.wing_chord * 0.6
        max_height = design.wing_chord * 0.15
    else:  # Conventional
        max_width = design.wing_chord * 0.35
        max_height = max_width * 1.1

    # Elliptical cross-section outer area = pi * (w/2) * (h/2)
    outer_area_mm2 = math.pi * (max_width / 2.0) * (max_height / 2.0)

    # Inner cross-section after subtracting wall thickness
    inner_w = max(0.0, max_width - 2.0 * wall_t)
    inner_h = max(0.0, max_height - 2.0 * wall_t)
    inner_area_mm2 = math.pi * (inner_w / 2.0) * (inner_h / 2.0)

    # Shell volume = (outer - inner) * length; interior gets infill.
    # Apply prismatic coefficient (0.6) to account for nose/tail taper —
    # real fuselages are not constant-section cylinders.
    prismatic_coeff = 0.6
    shell_vol_mm3 = (outer_area_mm2 - inner_area_mm2) * design.fuselage_length * prismatic_coeff
    interior_vol_mm3 = inner_area_mm2 * design.fuselage_length * infill_frac * prismatic_coeff
    fuselage_vol_cm3 = (shell_vol_mm3 + interior_vol_mm3) / 1000.0
    weight_fuselage_g = fuselage_vol_cm3 * density

    # Round components first, then sum for consistency
    w_wing = round(weight_wing_g, 1)
    w_tail = round(weight_tail_g, 1)
    w_fuse = round(weight_fuselage_g, 1)

    return {
        "weight_wing_g": w_wing,
        "weight_tail_g": w_tail,
        "weight_fuselage_g": w_fuse,
        "weight_total_g": round(w_wing + w_tail + w_fuse, 1),
    }


def _compute_cg(
    design: AircraftDesign,
    weights: dict[str, float],
    mac: float,
    y_mac: float,
    sweep_rad: float,
) -> float:
    """Compute CG as weighted average of all component X positions.

    All X positions are measured from the aircraft nose (X=0, +X aft).

    Component CG positions:
    - **Wing**: at wing_mount_x + LE_offset + 25% MAC.
      LE_offset = y_mac * tan(sweep) accounts for sweep.
    - **Tail**: at wing_mount_x + tail_arm + 50% tail chord.
    - **Fuselage**: at 50% fuselage_length (center of mass of tapered body).
    - **Motor**: at X=0 for tractor, X=fuselage_length for pusher.
    - **Battery**: at battery_position_frac * fuselage_length.

    Falls back to 25% MAC (aerodynamic center) if total weight is zero.
    """
    # Wing mount X position (same logic as assemble_aircraft)
    wing_x_frac = _WING_X_FRACTION.get(design.fuselage_preset, 0.30)
    wing_x = design.fuselage_length * wing_x_frac

    # Wing CG: wing mount + sweep offset + 25% MAC
    wing_le_offset = y_mac * math.tan(sweep_rad)
    wing_cg_x = wing_x + wing_le_offset + 0.25 * mac

    # Tail CG: wing mount + tail_arm + 50% of tail chord
    if design.tail_type == "V-Tail":
        tail_chord = design.v_tail_chord
    else:
        # Weighted average of h_stab and v_stab chords
        h_weight = design.h_stab_span
        v_weight = design.v_stab_height
        total = h_weight + v_weight
        tail_chord = (
            (design.h_stab_chord * h_weight + design.v_stab_root_chord * v_weight)
            / max(total, 1.0)
        )
    tail_cg_x = wing_x + design.tail_arm + 0.5 * tail_chord

    # Fuselage CG: center of mass (slightly forward of geometric center due
    # to nose taper being more gradual than tail cone)
    fuselage_cg_x = 0.45 * design.fuselage_length

    # Motor CG
    if design.motor_config == "Tractor":
        motor_cg_x = 0.0  # At nose
    else:  # Pusher
        motor_cg_x = design.fuselage_length

    # Battery CG: user-configurable position along fuselage
    battery_cg_x = design.battery_position_frac * design.fuselage_length

    # Weighted average
    w_wing = weights["weight_wing_g"]
    w_tail = weights["weight_tail_g"]
    w_fuse = weights["weight_fuselage_g"]
    w_motor = design.motor_weight_g
    w_battery = design.battery_weight_g

    total_weight = w_wing + w_tail + w_fuse + w_motor + w_battery

    if total_weight <= 0:
        # Fallback to aerodynamic center (25% MAC)
        return 0.25 * mac + y_mac * math.tan(sweep_rad)

    cg_x = (
        wing_cg_x * w_wing
        + tail_cg_x * w_tail
        + fuselage_cg_x * w_fuse
        + motor_cg_x * w_motor
        + battery_cg_x * w_battery
    ) / total_weight

    # Return CG relative to wing leading edge (same convention as before:
    # "distance aft of wing root LE").
    return cg_x - wing_x


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
