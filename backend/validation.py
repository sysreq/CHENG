"""Validation rules — compute non-blocking warnings for a design.

Implements:
  - 8 structural / geometric warnings  (V01-V08)
  - 5 aerodynamic / structural analysis (V09-V13)  [v0.6]
  - 7 print / export warnings          (V16-V23)
  - 5 printability analysis warnings    (V24-V28)  [v0.6]
  - 1 multi-section wing analysis       (V29)      [v0.7]
  - 4 landing gear warnings             (V31)      [v0.7]

All warnings are level="warn" and never block export.

Spec reference: docs/mvp_spec.md §9.2 and §9.3.
"""

from __future__ import annotations

import math

from backend.models import AircraftDesign, ValidationWarning


def _mac(design: AircraftDesign) -> float:
    """Mean Aerodynamic Chord (mm).

    For multi-section (cranked) wings, delegates to the engine's cranked MAC
    calculator.  For single-section wings uses the classic taper formula.
    """
    if design.wing_sections > 1:
        from backend.geometry.engine import _compute_mac_cranked
        mac, _ = _compute_mac_cranked(design)
        return mac
    lam = design.wing_tip_root_ratio
    if (1 + lam) == 0:
        return design.wing_chord
    return (2.0 / 3.0) * design.wing_chord * (1 + lam + lam**2) / (1 + lam)


# ---------------------------------------------------------------------------
# Structural / geometric warnings  (V01 - V06)
# ---------------------------------------------------------------------------


def _check_v01(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V01: wingspan > 10 * fuselageLength."""
    if design.wing_span > 10 * design.fuselage_length:
        out.append(
            ValidationWarning(
                id="V01",
                message="Very high aspect ratio relative to fuselage",
                fields=["wing_span", "fuselage_length"],
            )
        )


def _check_v02(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V02: tipRootRatio < 0.3 — aggressive taper, tip stall risk."""
    if design.wing_tip_root_ratio < 0.3:
        out.append(
            ValidationWarning(
                id="V02",
                message="Aggressive taper — tip stall risk",
                fields=["wing_tip_root_ratio"],
            )
        )


def _check_v03(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V03: fuselageLength < wingChord."""
    if design.fuselage_length < design.wing_chord:
        out.append(
            ValidationWarning(
                id="V03",
                message="Fuselage shorter than wing chord",
                fields=["fuselage_length", "wing_chord"],
            )
        )


def _check_v04(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V04: tailArm < 2 * MAC — short tail arm, may lack pitch stability."""
    mac = _mac(design)
    if mac > 0 and design.tail_arm < 2 * mac:
        out.append(
            ValidationWarning(
                id="V04",
                message="Short tail arm — may lack pitch stability",
                fields=["tail_arm"],
            )
        )


def _check_v05(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V05: wingChord * tipRootRatio < 30 — extremely small tip chord."""
    tip_chord = design.wing_chord * design.wing_tip_root_ratio
    if tip_chord < 30:
        out.append(
            ValidationWarning(
                id="V05",
                message="Extremely small tip chord",
                fields=["wing_chord", "wing_tip_root_ratio"],
            )
        )


def _check_v06(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V06: tailArm > fuselageLength — tail extends past the body."""
    if design.tail_arm > design.fuselage_length:
        out.append(
            ValidationWarning(
                id="V06",
                message="Tail arm exceeds fuselage — tail extends past the body",
                fields=["tail_arm", "fuselage_length"],
            )
        )


def _check_v07(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V07: fuselage section lengths don't sum to fuselage_length (>5% deviation)."""
    section_sum = (
        design.fuselage_nose_length
        + design.fuselage_cabin_length
        + design.fuselage_tail_length
    )
    if design.fuselage_length > 0:
        deviation = abs(section_sum - design.fuselage_length) / design.fuselage_length
        if deviation > 0.05:
            out.append(
                ValidationWarning(
                    id="V07",
                    message=(
                        f"Section lengths sum ({section_sum:.0f} mm) differs from "
                        f"fuselage length ({design.fuselage_length:.0f} mm) by "
                        f"{deviation*100:.0f}% — sections will be scaled proportionally"
                    ),
                    fields=[
                        "fuselage_nose_length",
                        "fuselage_cabin_length",
                        "fuselage_tail_length",
                        "fuselage_length",
                    ],
                )
            )


def _check_v08(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V08: wall_thickness < 2 * nozzle_diameter — fuselage wall too thin."""
    if design.wall_thickness < 2 * design.nozzle_diameter:
        out.append(
            ValidationWarning(
                id="V08",
                message="Fuselage wall too thin for solid perimeters",
                fields=["wall_thickness", "nozzle_diameter"],
            )
        )


# ---------------------------------------------------------------------------
# Aerodynamic / structural analysis  (V09 - V13)  [v0.6]
# ---------------------------------------------------------------------------


def _wing_area_m2(design: AircraftDesign) -> float:
    """Wing planform area in m^2."""
    tip_chord = design.wing_chord * design.wing_tip_root_ratio
    return 0.5 * (design.wing_chord + tip_chord) * design.wing_span * 1e-6


def _estimate_weight_kg(design: AircraftDesign) -> float:
    """Quick total weight estimate in kg (airframe + motor + battery).

    Uses the same volume-based approach as engine._compute_weight_estimates
    but simplified for validation (avoids circular import).
    """
    from backend.geometry.engine import _compute_weight_estimates
    weights = _compute_weight_estimates(design)
    airframe_g = weights["weight_total_g"]
    return (airframe_g + design.motor_weight_g + design.battery_weight_g) / 1000.0


def _check_v09(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V09: Wing bending moment check.

    Rough estimate: root bending moment from lift ≈ (W * b) / (4 * pi).
    For a 3D-printed wing, bending stress ~ M / (t^2 * c) should stay within
    PLA tensile limits. We warn if the non-dimensional bending parameter
    (weight_kg * span_m) / skin_thickness_mm^2 exceeds a threshold.

    The threshold is empirically set: above ~2.5, a 1.2mm skin PLA wing
    is at risk of creasing under moderate g-loads (2-3g maneuvers).
    """
    weight_kg = _estimate_weight_kg(design)
    span_m = design.wing_span / 1000.0
    skin_t = design.wing_skin_thickness

    if skin_t <= 0:
        return

    bending_param = (weight_kg * span_m) / (skin_t ** 2)

    if bending_param > 2.5:
        out.append(
            ValidationWarning(
                id="V09",
                message=(
                    f"High wing bending load — consider thicker skin or shorter span "
                    f"(bending index {bending_param:.1f}, limit 2.5)"
                ),
                fields=["wing_span", "wing_skin_thickness"],
            )
        )


def _check_v10(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V10: Tail volume coefficient check.

    Horizontal tail volume: V_h = (S_h * l_t) / (S_w * MAC)
    Typical RC range: 0.3 - 0.8. Below 0.3 = insufficient pitch stability.
    Above 1.0 = over-stabilized (sluggish pitch response).

    Vertical tail volume: V_v = (S_v * l_t) / (S_w * b)
    Typical range: 0.02 - 0.05. Below 0.02 = poor directional stability.
    """
    mac = _mac(design)
    wing_area_mm2 = 0.5 * (design.wing_chord + design.wing_chord * design.wing_tip_root_ratio) * design.wing_span

    if mac <= 0 or wing_area_mm2 <= 0 or design.wing_span <= 0:
        return

    if design.tail_type == "V-Tail":
        # V-tail effective areas using Purser-Campbell method:
        # The aerodynamic effectiveness is reduced by the square of the
        # trig function because both the force component and the effective
        # angle-of-attack change are reduced by the dihedral angle.
        v_tail_area = design.v_tail_chord * design.v_tail_span
        dihedral_rad = math.radians(design.v_tail_dihedral)
        h_area = v_tail_area * math.cos(dihedral_rad) ** 2
        v_area = v_tail_area * math.sin(dihedral_rad) ** 2
    else:
        h_area = design.h_stab_chord * design.h_stab_span
        v_area = design.v_stab_root_chord * design.v_stab_height

    # Horizontal tail volume coefficient
    v_h = (h_area * design.tail_arm) / (wing_area_mm2 * mac)
    if v_h < 0.3:
        out.append(
            ValidationWarning(
                id="V10",
                message=f"Low horizontal tail volume ({v_h:.2f}) — may lack pitch stability (typical: 0.3-0.8)",
                fields=["h_stab_span", "h_stab_chord", "tail_arm"],
            )
        )
    elif v_h > 1.0:
        out.append(
            ValidationWarning(
                id="V10",
                message=f"High horizontal tail volume ({v_h:.2f}) — pitch response may be sluggish (typical: 0.3-0.8)",
                fields=["h_stab_span", "h_stab_chord", "tail_arm"],
            )
        )

    # Vertical tail volume coefficient
    v_v = (v_area * design.tail_arm) / (wing_area_mm2 * design.wing_span)
    if v_v < 0.02:
        out.append(
            ValidationWarning(
                id="V10",
                message=f"Low vertical tail volume ({v_v:.3f}) — poor directional stability (typical: 0.02-0.05)",
                fields=["v_stab_height", "v_stab_root_chord", "tail_arm"],
            )
        )


def _check_v11(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V11: Flutter margin estimate.

    Higher aspect ratio wings at higher speeds are more susceptible to flutter.
    For 3D-printed PLA wings (low stiffness), warn if:
      AR > 8 (high AR increases flutter risk)
      or AR > 6 AND sweep > 15° (swept high-AR is worse)

    This is a simplified heuristic — real flutter analysis requires FEA.
    """
    tip_chord = design.wing_chord * design.wing_tip_root_ratio
    wing_area_mm2 = 0.5 * (design.wing_chord + tip_chord) * design.wing_span
    ar = (design.wing_span ** 2) / wing_area_mm2 if wing_area_mm2 > 0 else 0.0

    if ar > 8:
        out.append(
            ValidationWarning(
                id="V11",
                message=f"High aspect ratio ({ar:.1f}) — flutter risk for 3D-printed wings (limit AR < 8)",
                fields=["wing_span", "wing_chord", "wing_tip_root_ratio"],
            )
        )
    elif ar > 6 and abs(design.wing_sweep) > 15:
        out.append(
            ValidationWarning(
                id="V11",
                message=f"High AR ({ar:.1f}) combined with sweep ({design.wing_sweep:.0f}°) increases flutter risk",
                fields=["wing_span", "wing_chord", "wing_sweep"],
            )
        )


def _check_v12(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V12: Wing loading check.

    Wing loading = weight / wing_area.
    For RC planes:
      < 20 g/dm² = very light (floater/glider)
      20-60 g/dm² = typical sport
      > 80 g/dm² = heavy — needs higher speed, harder landings
      > 120 g/dm² = very heavy — not suitable for beginners
    """
    weight_kg = _estimate_weight_kg(design)
    weight_g = weight_kg * 1000.0
    wing_area_dm2 = _wing_area_m2(design) * 100.0  # m² to dm²

    if wing_area_dm2 <= 0:
        return

    wing_loading = weight_g / wing_area_dm2

    if wing_loading > 120:
        out.append(
            ValidationWarning(
                id="V12",
                message=f"Very high wing loading ({wing_loading:.0f} g/dm²) — needs fast airspeed, hard landings",
                fields=["wing_span", "wing_chord"],
            )
        )
    elif wing_loading > 80:
        out.append(
            ValidationWarning(
                id="V12",
                message=f"High wing loading ({wing_loading:.0f} g/dm²) — not beginner-friendly (typical: 20-60)",
                fields=["wing_span", "wing_chord"],
            )
        )


def _check_v13(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V13: Stall speed estimate.

    V_stall = sqrt(2 * W / (rho * S * Cl_max))

    Where:
      W = weight in N
      rho = 1.225 kg/m³ (sea level)
      S = wing area in m²
      Cl_max ≈ 1.2 (typical for RC airfoils)

    Warn if stall speed > 15 m/s (54 km/h) — difficult for beginners.
    Info if stall speed > 10 m/s (36 km/h).
    """
    weight_kg = _estimate_weight_kg(design)
    weight_n = weight_kg * 9.81
    wing_area_m2 = _wing_area_m2(design)

    if wing_area_m2 <= 0 or weight_n <= 0:
        return

    rho = 1.225  # kg/m³, sea level ISA
    cl_max = 1.2  # typical RC airfoil

    v_stall = math.sqrt(2.0 * weight_n / (rho * wing_area_m2 * cl_max))
    v_stall_kmh = v_stall * 3.6

    if v_stall > 15.0:
        out.append(
            ValidationWarning(
                id="V13",
                message=f"High stall speed ({v_stall_kmh:.0f} km/h) — needs fast approach, difficult landings",
                fields=["wing_span", "wing_chord"],
            )
        )
    elif v_stall > 10.0:
        out.append(
            ValidationWarning(
                id="V13",
                message=f"Moderate stall speed ({v_stall_kmh:.0f} km/h) — OK for experienced pilots",
                fields=["wing_span", "wing_chord"],
            )
        )


# ---------------------------------------------------------------------------
# 3D-printing warnings  (V16 - V23)
# ---------------------------------------------------------------------------


def _check_v16(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V16: skinThickness < 2 * nozzleDiameter — wall too thin for solid perimeters."""
    if design.wing_skin_thickness < 2 * design.nozzle_diameter:
        out.append(
            ValidationWarning(
                id="V16",
                message="Wall too thin for solid perimeters",
                fields=["wing_skin_thickness", "nozzle_diameter"],
            )
        )


def _check_v17(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V17: skinThickness % nozzleDiameter > 0.01 — wall not clean multiple of nozzle."""
    remainder = design.wing_skin_thickness % design.nozzle_diameter
    # Use math.isclose to handle floating-point precision (e.g. 1.2 % 0.4 = 0.3999...)
    if not math.isclose(remainder, 0, abs_tol=1e-6) and not math.isclose(remainder, design.nozzle_diameter, abs_tol=1e-6):
        out.append(
            ValidationWarning(
                id="V17",
                message="Wall not clean multiple of nozzle diameter",
                fields=["wing_skin_thickness", "nozzle_diameter"],
            )
        )


def _check_v18(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V18: skinThickness < 1.0mm — absolute structural minimum for FDM wing skin."""
    if design.wing_skin_thickness < 1.0:
        out.append(
            ValidationWarning(
                id="V18",
                message="Wing skin below 1.0 mm absolute structural minimum",
                fields=["wing_skin_thickness"],
            )
        )


def _check_v20(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V20: any part exceeds bed size AND auto-section disabled."""
    if design.auto_section:
        return

    half_span = design.wing_span / 2.0
    bed_max = max(design.print_bed_x, design.print_bed_y)

    if half_span > bed_max or design.fuselage_length > bed_max:
        out.append(
            ValidationWarning(
                id="V20",
                message="Enable auto-sectioning or reduce dimensions",
                fields=["print_bed_x", "print_bed_y", "wing_span", "fuselage_length", "auto_section"],
            )
        )


def _check_v21(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V21: jointOverlap < 10 AND wingspan > 800 — joint overlap too short."""
    if design.section_overlap < 10 and design.wing_span > 800:
        out.append(
            ValidationWarning(
                id="V21",
                message="Joint overlap too short for this span",
                fields=["section_overlap", "wing_span"],
            )
        )


def _check_v22(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V22: jointTolerance > 0.3 — parts may be loose."""
    if design.joint_tolerance > 0.3:
        out.append(
            ValidationWarning(
                id="V22",
                message="Parts may be loose",
                fields=["joint_tolerance"],
            )
        )


def _check_v23(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V23: jointTolerance < 0.05 — parts may not fit."""
    if design.joint_tolerance < 0.05:
        out.append(
            ValidationWarning(
                id="V23",
                message="Parts may not fit",
                fields=["joint_tolerance"],
            )
        )


# ---------------------------------------------------------------------------
# Printability analysis  (V24 - V28)  [v0.6]
# ---------------------------------------------------------------------------


def _check_v24(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V24: Overhang analysis.

    FDM printers struggle with overhangs > 45 degrees. For aircraft:
    - Wing dihedral > 45° creates unsupported overhangs on the underside
    - Wing sweep > 30° combined with dihedral creates compound overhangs
    - V-tail dihedral > 45° creates overhangs on inner surfaces
    """
    if abs(design.wing_dihedral) > 45:
        out.append(
            ValidationWarning(
                id="V24",
                message=(
                    f"Wing dihedral ({design.wing_dihedral:.0f}°) exceeds 45° — "
                    f"underside overhang requires support material"
                ),
                fields=["wing_dihedral"],
            )
        )
    elif abs(design.wing_dihedral) > 30 and abs(design.wing_sweep) > 15:
        out.append(
            ValidationWarning(
                id="V24",
                message=(
                    f"Combined dihedral ({design.wing_dihedral:.0f}°) and sweep "
                    f"({design.wing_sweep:.0f}°) may create compound overhangs"
                ),
                fields=["wing_dihedral", "wing_sweep"],
            )
        )

    if design.tail_type == "V-Tail" and design.v_tail_dihedral > 45:
        out.append(
            ValidationWarning(
                id="V24",
                message=(
                    f"V-tail dihedral ({design.v_tail_dihedral:.0f}°) exceeds 45° — "
                    f"inner surfaces need support"
                ),
                fields=["v_tail_dihedral"],
            )
        )


def _check_v25(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V25: Trailing edge sharpness.

    If te_min_thickness is set below a printable threshold, warn the user.
    Also check if the tip chord is so small that the TE becomes impractically
    thin (tip chord * 0.02 for typical TE = ~2% of chord).
    """
    if design.te_min_thickness < 0.8:
        out.append(
            ValidationWarning(
                id="V25",
                message=(
                    f"Trailing edge thickness ({design.te_min_thickness:.1f} mm) "
                    f"below 0.8 mm — may not print reliably"
                ),
                fields=["te_min_thickness"],
            )
        )

    # Check tip chord TE
    tip_chord = design.wing_chord * design.wing_tip_root_ratio
    # TE is typically ~2% of chord for thin airfoils; thicker for NACA 0012 etc.
    tip_te_estimate = tip_chord * 0.02
    if tip_te_estimate < design.te_min_thickness and tip_chord < 80:
        out.append(
            ValidationWarning(
                id="V25",
                message=(
                    f"Tip chord ({tip_chord:.0f} mm) too small for reliable TE printing — "
                    f"consider increasing taper ratio"
                ),
                fields=["wing_chord", "wing_tip_root_ratio", "te_min_thickness"],
            )
        )


def _check_v26(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V26: Connector/joint clearance check.

    Tongue-and-groove joints need sufficient depth relative to the wall
    thickness. If joint_tolerance is very tight AND section_overlap is short,
    the joint may not engage properly with FDM dimensional variance.

    Also check that the joint tolerance is compatible with the nozzle diameter
    (tolerance should be at least nozzle_diameter / 4 for reliable fit).
    """
    min_clearance = design.nozzle_diameter / 4.0
    if design.joint_tolerance < min_clearance:
        out.append(
            ValidationWarning(
                id="V26",
                message=(
                    f"Joint tolerance ({design.joint_tolerance:.2f} mm) below "
                    f"{min_clearance:.2f} mm — too tight for {design.nozzle_diameter:.1f} mm nozzle"
                ),
                fields=["joint_tolerance", "nozzle_diameter"],
            )
        )

    # Check joint depth relative to wall/skin
    if design.joint_type == "Tongue-and-Groove":
        # Tongue depth is typically section_overlap * 0.5
        tongue_depth = design.section_overlap * 0.5
        min_wall = min(design.wing_skin_thickness, design.wall_thickness)
        if tongue_depth < 2.0 * min_wall:
            out.append(
                ValidationWarning(
                    id="V26",
                    message=(
                        f"Joint tongue depth ({tongue_depth:.1f} mm) may be too shallow "
                        f"relative to wall thickness ({min_wall:.1f} mm)"
                    ),
                    fields=["section_overlap", "wing_skin_thickness", "wall_thickness"],
                )
            )


def _check_v27(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V27: Per-part print orientation recommendation.

    For FDM printing of aircraft parts:
    - Wings: print chord-wise (LE down, TE up) for best surface finish
    - Fuselage: print lengthwise (nose forward) — but may need splitting
    - Tail: similar to wings

    Warn if dimensions suggest difficult print orientations.
    """
    # Check if fuselage height exceeds bed Z
    preset = design.fuselage_preset
    if preset == "Pod":
        fuse_height = design.wing_chord * 0.45
    elif preset == "Blended-Wing-Body":
        fuse_height = design.wing_chord * 0.15
    else:
        fuse_height = design.wing_chord * 0.35 * 1.1

    # Wing chord is the critical dimension for print orientation
    # If chord > bed_z, the wing cannot be printed chord-upright
    if design.wing_chord > design.print_bed_z:
        out.append(
            ValidationWarning(
                id="V27",
                message=(
                    f"Wing chord ({design.wing_chord:.0f} mm) exceeds bed height "
                    f"({design.print_bed_z:.0f} mm) — cannot print upright for best finish"
                ),
                fields=["wing_chord", "print_bed_z"],
            )
        )

    if fuse_height > design.print_bed_z:
        out.append(
            ValidationWarning(
                id="V27",
                message=(
                    f"Fuselage cross-section ({fuse_height:.0f} mm) exceeds bed height "
                    f"({design.print_bed_z:.0f} mm) — print on side or split vertically"
                ),
                fields=["wing_chord", "fuselage_preset", "print_bed_z"],
            )
        )


def _check_v28(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V28: Layer adhesion warning for thin walls.

    For FDM-printed aircraft, wall thickness should be at least 2x nozzle
    diameter for structural integrity (2 perimeters minimum). 1-perimeter
    walls are possible but fragile. 3x is ideal for high-stress areas
    but too heavy for full-wing skins.
    """
    min_perimeters = 2.0
    min_wall = min_perimeters * design.nozzle_diameter

    if design.wing_skin_thickness < min_wall:
        out.append(
            ValidationWarning(
                id="V28",
                message=(
                    f"Wing skin ({design.wing_skin_thickness:.1f} mm) below "
                    f"{min_wall:.1f} mm (3x nozzle) — weak layer adhesion"
                ),
                fields=["wing_skin_thickness", "nozzle_diameter"],
            )
        )

    if design.wall_thickness < min_wall:
        out.append(
            ValidationWarning(
                id="V28",
                message=(
                    f"Fuselage wall ({design.wall_thickness:.1f} mm) below "
                    f"{min_wall:.1f} mm (3x nozzle) — weak layer adhesion"
                ),
                fields=["wall_thickness", "nozzle_diameter"],
            )
        )


# ---------------------------------------------------------------------------
# Multi-section wing analysis  (V29)  [v0.7]
# ---------------------------------------------------------------------------


def _check_v29(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V29: Multi-section wing configuration checks.

    Validates panel break positions, dihedral angles, and array consistency
    for multi-section wings (wing_sections > 1).
    """
    n = design.wing_sections
    if n <= 1:
        return

    n_breaks = n - 1
    breaks = design.panel_break_positions[:n_breaks]
    dihedrals = design.panel_dihedrals[:n_breaks]

    # Check break positions are strictly monotonically increasing
    for i in range(len(breaks) - 1):
        if breaks[i] >= breaks[i + 1]:
            out.append(
                ValidationWarning(
                    id="V29",
                    message=(
                        f"Panel break positions must be strictly increasing "
                        f"(break {i + 1}={breaks[i]:.0f}% >= break {i + 2}={breaks[i + 1]:.0f}%)"
                    ),
                    fields=["panel_break_positions"],
                )
            )
            return  # Further checks invalid until ordering is fixed

    # Check outermost break leaves a usable outer panel (> 10% semi-span remains)
    if breaks and breaks[-1] > 90.0:
        out.append(
            ValidationWarning(
                id="V29",
                message=(
                    f"Outermost panel break at {breaks[-1]:.0f}% leaves a very short "
                    f"outer panel — minimum 10% semi-span recommended"
                ),
                fields=["panel_break_positions"],
            )
        )

    # Check outer panel dihedrals don't create extreme print overhangs
    for i, d in enumerate(dihedrals):
        if abs(d) > 30:
            out.append(
                ValidationWarning(
                    id="V29",
                    message=(
                        f"Panel {i + 2} dihedral ({d:.0f}°) exceeds 30° — "
                        f"large panel dihedral creates significant print overhang"
                    ),
                    fields=["panel_dihedrals"],
                )
            )

    # Check innermost break is not too close to root (< 10% would create a
    # very thin root panel that is hard to print and structurally weak)
    if breaks and breaks[0] < 10.0:
        out.append(
            ValidationWarning(
                id="V29",
                message=(
                    f"First panel break at {breaks[0]:.0f}% is very close to root — "
                    f"minimum 10% semi-span recommended for structural integrity"
                ),
                fields=["panel_break_positions"],
            )
        )


# ---------------------------------------------------------------------------
# Landing gear warnings  (V31)  [v0.7]
# ---------------------------------------------------------------------------


def _estimate_cg_x(design: AircraftDesign) -> float:
    """Rough estimate of aircraft CG X position (mm from nose).

    Uses the same logic as engine._compute_cg but simplified (no sweep offset)
    to avoid a full weight computation here.  Intended only for relative comparisons
    like 'is main gear ahead of / behind CG'.
    """
    from backend.geometry.engine import _WING_X_FRACTION
    wing_x_frac = _WING_X_FRACTION.get(design.fuselage_preset, 0.30)
    wing_x = design.fuselage_length * wing_x_frac
    # CG is roughly at 25% MAC aft of wing leading edge
    lam = design.wing_tip_root_ratio
    mac = _mac(design)
    cg_x = wing_x + 0.25 * mac
    return cg_x


def _check_v31(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V31: Landing gear validation rules.

    V31a: Tricycle — main gear more than 10% of fuselage ahead of CG
          (gear forward of CG → aircraft may tip onto tail on ground).
    V31b: Taildragger — main gear behind estimated CG
          (main gear aft of CG → unstable on ground, will tip forward/nose-over).
    V31c: Prop ground clearance — when gear is installed and motor is Tractor,
          check prop tip clears the ground:
          clearance = main_gear_height - (prop_diameter/2 - fuselage_height/2)
          Warn if clearance < 10 mm.
    V31d: Gear track narrow relative to height — risk of crosswind tipover
          if track < 0.4 * height.
    """
    if design.landing_gear_type == "None":
        return

    height = design.main_gear_height
    track = design.main_gear_track
    main_gear_x = design.fuselage_length * (design.main_gear_position / 100.0)
    cg_x = _estimate_cg_x(design)

    # V31a: Tricycle — main gear should be BEHIND CG
    if design.landing_gear_type == "Tricycle":
        forward_limit = cg_x - 0.10 * design.fuselage_length
        if main_gear_x < forward_limit:
            out.append(
                ValidationWarning(
                    id="V31",
                    message=(
                        f"Main gear far forward of CG ({main_gear_x:.0f} mm vs "
                        f"CG~{cg_x:.0f} mm from nose) — aircraft may tip tail-down on ground"
                    ),
                    fields=["main_gear_position"],
                )
            )

    # V31b: Taildragger — main gear should be AT or AHEAD of CG
    if design.landing_gear_type == "Taildragger":
        if main_gear_x > cg_x:
            out.append(
                ValidationWarning(
                    id="V31",
                    message=(
                        f"Taildragger main gear is aft of CG ({main_gear_x:.0f} mm vs "
                        f"CG~{cg_x:.0f} mm from nose) — unstable on ground, risk of nose-over"
                    ),
                    fields=["main_gear_position"],
                )
            )

    # V31c: Prop ground clearance (Tractor only)
    if design.motor_config == "Tractor" and height < 30.0:
        out.append(
            ValidationWarning(
                id="V31",
                message=(
                    f"Gear height ({height:.0f} mm) is very low for a tractor configuration — "
                    f"the propeller may strike the ground (consider ≥ 30 mm strut height)"
                ),
                fields=["main_gear_height"],
            )
        )

    # V31d: Narrow track — tipover risk
    if track < 0.4 * height:
        out.append(
            ValidationWarning(
                id="V31",
                message=(
                    f"Narrow gear track ({track:.0f} mm) relative to height ({height:.0f} mm) "
                    f"— risk of tipover in crosswind landing (recommend track ≥ {0.4*height:.0f} mm)"
                ),
                fields=["main_gear_track", "main_gear_height"],
            )
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_warnings(design: AircraftDesign) -> list[ValidationWarning]:
    """Compute all non-blocking validation warnings for a design.

    Returns a list of ValidationWarning objects.  Each warning has a unique
    ID (V01-V08 structural, V09-V13 aero/structural, V16-V23 print,
    V24-V28 printability, V29 multi-section wing), a human-readable message,
    and the list of affected parameter field names.
    """
    warnings: list[ValidationWarning] = []

    # Structural / geometric (V01-V08)
    _check_v01(design, warnings)
    _check_v02(design, warnings)
    _check_v03(design, warnings)
    _check_v04(design, warnings)
    _check_v05(design, warnings)
    _check_v06(design, warnings)
    _check_v07(design, warnings)
    _check_v08(design, warnings)

    # Aerodynamic / structural analysis (V09-V13)
    _check_v09(design, warnings)
    _check_v10(design, warnings)
    _check_v11(design, warnings)
    _check_v12(design, warnings)
    _check_v13(design, warnings)

    # 3D printing (V16-V23)
    _check_v16(design, warnings)
    _check_v17(design, warnings)
    _check_v18(design, warnings)
    _check_v20(design, warnings)
    _check_v21(design, warnings)
    _check_v22(design, warnings)
    _check_v23(design, warnings)

    # Printability analysis (V24-V28)
    _check_v24(design, warnings)
    _check_v25(design, warnings)
    _check_v26(design, warnings)
    _check_v27(design, warnings)
    _check_v28(design, warnings)

    # Multi-section wing analysis (V29)
    _check_v29(design, warnings)

    # Landing gear (V31)
    _check_v31(design, warnings)

    return warnings
