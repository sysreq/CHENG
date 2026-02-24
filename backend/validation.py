"""Validation rules — compute non-blocking warnings for a design.

MVP implements:
  - 6 structural / geometric warnings  (V01-V06)
  - 7 print / export warnings          (V16-V23)

All warnings are level="warn" and never block export.
"""

from __future__ import annotations

import math

from backend.models import AircraftDesign, ValidationWarning


def _mac(design: AircraftDesign) -> float:
    """Mean Aerodynamic Chord (mm)."""
    lam = design.wing_tip_root_ratio
    if (1 + lam) == 0:
        return design.wing_chord
    return (2.0 / 3.0) * design.wing_chord * (1 + lam + lam**2) / (1 + lam)


def _wing_area_mm2(design: AircraftDesign) -> float:
    """Wing area in mm^2 (trapezoidal approximation)."""
    tip_chord = design.wing_chord * design.wing_tip_root_ratio
    return 0.5 * (design.wing_chord + tip_chord) * design.wing_span


def _aspect_ratio(design: AircraftDesign) -> float:
    """Geometric aspect ratio."""
    area = _wing_area_mm2(design)
    if area <= 0:
        return 0.0
    return design.wing_span**2 / area


# ---------------------------------------------------------------------------
# Structural / geometric warnings  (V01 - V06)
# ---------------------------------------------------------------------------


def _check_v01(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V01: wingspan > 2000 mm  (very large aircraft)."""
    if design.wing_span > 2000:
        out.append(
            ValidationWarning(
                id="V01",
                message="Wingspan exceeds 2000 mm — consider structural reinforcement",
                fields=["wing_span"],
            )
        )


def _check_v02(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V02: wing loading too high.

    Rough heuristic from spec: wing_span * wing_chord * 0.5 * density_factor > threshold.
    We estimate total airframe shell weight (wing + fuselage) in PLA, then divide
    by wing area.  Typical RC model wing loading is 20-60 g/dm^2.
    Above ~65 g/dm^2 is aggressive for a 3D-printed model.
    """
    area_cm2 = _wing_area_mm2(design) / 100.0
    if area_cm2 <= 0:
        return
    area_dm2 = area_cm2 / 100.0  # convert cm^2 to dm^2

    # Rough total airframe weight estimate in grams:
    # Wing shell (both halves): span * avg_chord * thickness * 2_surfaces * PLA_density
    # PLA density = 1.24 g/cm^3 = 0.00124 g/mm^3
    # Structure factor 2.0 accounts for fuselage, tail, internal ribs, motor/electronics
    tip_chord = design.wing_chord * design.wing_tip_root_ratio
    avg_chord = (design.wing_chord + tip_chord) / 2.0
    wing_shell_volume_mm3 = design.wing_span * avg_chord * design.wing_skin_thickness * 2
    total_volume_mm3 = wing_shell_volume_mm3 * 2.0  # structure factor
    estimated_weight_g = total_volume_mm3 * 0.00124

    wing_loading_g_dm2 = estimated_weight_g / area_dm2 if area_dm2 > 0 else 0
    if wing_loading_g_dm2 > 80:
        out.append(
            ValidationWarning(
                id="V02",
                message="Estimated wing loading is high — consider increasing wing area or reducing weight",
                fields=["wing_span", "wing_chord", "wing_skin_thickness"],
            )
        )


def _check_v03(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V03: tail arm > fuselage length  (physically unrealistic)."""
    if design.tail_arm > design.fuselage_length:
        out.append(
            ValidationWarning(
                id="V03",
                message="Tail arm exceeds fuselage length — tail extends past the body",
                fields=["tail_arm", "fuselage_length"],
            )
        )


def _check_v04(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V04: tail volume coefficient too low.

    Horizontal tail volume coefficient:
        V_h = (S_h * l_t) / (S_w * MAC)
    Typical range is 0.3-0.6.  Below 0.3 is unstable.
    """
    mac = _mac(design)
    wing_area = _wing_area_mm2(design)
    if mac <= 0 or wing_area <= 0:
        return

    # Use h-stab or v-tail depending on tail type
    if design.tail_type == "V-Tail":
        # Projected horizontal area of V-tail
        h_stab_area = (
            design.v_tail_span
            * design.v_tail_chord
            * math.cos(math.radians(design.v_tail_dihedral))
        )
    else:
        h_stab_area = design.h_stab_span * design.h_stab_chord

    v_h = (h_stab_area * design.tail_arm) / (wing_area * mac)
    if v_h < 0.3:
        out.append(
            ValidationWarning(
                id="V04",
                message="Tail volume coefficient too low — may lack pitch stability",
                fields=["tail_arm", "h_stab_span", "h_stab_chord"],
            )
        )


def _check_v05(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V05: control surface / tip chord too small.

    Tip chord below 30 mm is extremely fragile and un-printable with FDM.
    """
    tip_chord = design.wing_chord * design.wing_tip_root_ratio
    if tip_chord < 30:
        out.append(
            ValidationWarning(
                id="V05",
                message="Extremely small tip chord — fragile and difficult to print",
                fields=["wing_chord", "wing_tip_root_ratio"],
            )
        )


def _check_v06(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V06: aspect ratio extreme (< 4 or > 12)."""
    ar = _aspect_ratio(design)
    if ar < 4:
        out.append(
            ValidationWarning(
                id="V06",
                message=f"Low aspect ratio ({ar:.1f}) — may have poor glide performance",
                fields=["wing_span", "wing_chord"],
            )
        )
    elif ar > 12:
        out.append(
            ValidationWarning(
                id="V06",
                message=f"High aspect ratio ({ar:.1f}) — structural flex risk without a spar",
                fields=["wing_span", "wing_chord"],
            )
        )


# ---------------------------------------------------------------------------
# 3D-printing warnings  (V16 - V23)
# ---------------------------------------------------------------------------


def _check_v16(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V16: wall thickness < 1.2 mm (wing skin)."""
    if design.wing_skin_thickness < 1.2:
        out.append(
            ValidationWarning(
                id="V16",
                message="Wing skin thickness below 1.2 mm — may be too fragile for FDM",
                fields=["wing_skin_thickness"],
            )
        )


def _check_v17(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V17: section would exceed print bed.

    If any major dimension exceeds the print bed AND auto-section is
    disabled, warn.
    """
    half_span = design.wing_span / 2.0
    bed_max = max(design.print_bed_x, design.print_bed_y)

    if not design.auto_section and (half_span > bed_max or design.fuselage_length > bed_max):
        out.append(
            ValidationWarning(
                id="V17",
                message="Parts exceed print bed size — enable auto-sectioning or reduce dimensions",
                fields=[
                    "wing_span",
                    "fuselage_length",
                    "print_bed_x",
                    "print_bed_y",
                    "auto_section",
                ],
            )
        )


def _check_v18(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V18: overhang angle concern (high dihedral + thin skin)."""
    if abs(design.wing_dihedral) > 8 and design.wing_skin_thickness < 1.5:
        out.append(
            ValidationWarning(
                id="V18",
                message="High dihedral with thin skin — steep overhangs may need supports",
                fields=["wing_dihedral", "wing_skin_thickness"],
            )
        )


def _check_v20(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V20: estimated part count > 20."""
    if not design.auto_section:
        return  # Can't estimate parts when sectioning is off

    bed_max = max(design.print_bed_x, design.print_bed_y) - 20  # 20mm joint margin
    if bed_max <= 0:
        return

    half_span = design.wing_span / 2.0
    wing_sections_per_half = max(1, math.ceil(half_span / bed_max))
    wing_parts = wing_sections_per_half * 2  # left + right

    fuselage_sections = max(1, math.ceil(design.fuselage_length / bed_max))

    # Tail parts (rough estimate: 2-3 surfaces)
    tail_parts = 3

    total = wing_parts + fuselage_sections + tail_parts
    if total > 20:
        out.append(
            ValidationWarning(
                id="V20",
                message=(
                    f"Estimated {total} parts — complex assembly, "
                    "consider larger print bed or smaller aircraft"
                ),
                fields=["wing_span", "print_bed_x", "print_bed_y"],
            )
        )


def _check_v21(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V21: estimated print time > 48h.

    Rough heuristic based on total material volume.
    """
    # Rough volume estimate: wing shell + fuselage shell (mm^3)
    tip_chord = design.wing_chord * design.wing_tip_root_ratio
    avg_chord = (design.wing_chord + tip_chord) / 2.0
    # Wing volume as thin shell (both halves)
    wing_volume = design.wing_span * avg_chord * 0.1 * design.wing_skin_thickness * 2
    # Fuselage as a rough cylinder shell
    fuse_radius = design.wing_chord * 0.3  # rough
    fuse_volume = math.pi * 2 * fuse_radius * design.fuselage_length * design.wing_skin_thickness
    total_volume_mm3 = wing_volume + fuse_volume

    # Typical FDM rate: ~15 mm^3/s for 0.4mm nozzle, 0.2mm layer, 60mm/s
    print_rate_mm3_per_s = 15.0
    estimated_hours = total_volume_mm3 / (print_rate_mm3_per_s * 3600)

    if estimated_hours > 48:
        out.append(
            ValidationWarning(
                id="V21",
                message=(
                    f"Estimated print time ~{estimated_hours:.0f}h "
                    "— consider simplifying or scaling down"
                ),
                fields=["wing_span", "wing_chord", "fuselage_length"],
            )
        )


def _check_v22(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V22: joint tolerance too tight (< 0.1 mm)."""
    if design.joint_tolerance < 0.1:
        out.append(
            ValidationWarning(
                id="V22",
                message="Joint tolerance below 0.1 mm — parts may not fit together",
                fields=["joint_tolerance"],
            )
        )


def _check_v23(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V23: trailing edge min thickness < 2 * nozzle_diameter."""
    min_te = 2.0 * design.nozzle_diameter
    if design.te_min_thickness < min_te:
        out.append(
            ValidationWarning(
                id="V23",
                message=(
                    f"TE min thickness ({design.te_min_thickness} mm) is below "
                    f"2x nozzle diameter ({min_te} mm) — may not print cleanly"
                ),
                fields=["te_min_thickness", "nozzle_diameter"],
            )
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_warnings(design: AircraftDesign) -> list[ValidationWarning]:
    """Compute all non-blocking validation warnings for a design.

    Returns a list of ValidationWarning objects.  Each warning has a unique
    ID (V01-V06 for structural, V16-V23 for print), a human-readable message,
    and the list of affected parameter field names.
    """
    warnings: list[ValidationWarning] = []

    # Structural / geometric
    _check_v01(design, warnings)
    _check_v02(design, warnings)
    _check_v03(design, warnings)
    _check_v04(design, warnings)
    _check_v05(design, warnings)
    _check_v06(design, warnings)

    # 3D printing
    _check_v16(design, warnings)
    _check_v17(design, warnings)
    _check_v18(design, warnings)
    _check_v20(design, warnings)
    _check_v21(design, warnings)
    _check_v22(design, warnings)
    _check_v23(design, warnings)

    return warnings
