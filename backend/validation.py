"""Validation rules — compute non-blocking warnings for a design.

MVP implements:
  - 6 structural / geometric warnings  (V01-V06)
  - 7 print / export warnings          (V16-V23)

All warnings are level="warn" and never block export.

Spec reference: docs/mvp_spec.md §9.2 and §9.3.
"""

from __future__ import annotations

from backend.models import AircraftDesign, ValidationWarning


def _mac(design: AircraftDesign) -> float:
    """Mean Aerodynamic Chord (mm)."""
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
    # Account for floating-point: remainder near nozzle_diameter means ~0
    if remainder > design.nozzle_diameter - 0.01:
        remainder = 0.0
    if remainder > 0.01:
        out.append(
            ValidationWarning(
                id="V17",
                message="Wall not clean multiple of nozzle diameter",
                fields=["wing_skin_thickness", "nozzle_diameter"],
            )
        )


def _check_v18(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V18: skinThickness < 2 * nozzleDiameter — wing skin too thin for reliable FDM."""
    if design.wing_skin_thickness < 2 * design.nozzle_diameter:
        out.append(
            ValidationWarning(
                id="V18",
                message="Wing skin too thin for reliable FDM",
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
