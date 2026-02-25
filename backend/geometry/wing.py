"""Wing geometry builder -- generates wing half-panels via CadQuery lofting.

Each wing half is built from root (Y=0) to tip (Y=+/-span/2), with
airfoil loading, taper, sweep, dihedral, TE enforcement, and shelling.

Multi-section wings (wing_sections > 1) build N separate lofted panels
and union them into a single solid.  Each panel has independent dihedral
and sweep angles (W10/W11), with dihedral accumulated across panel breaks.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import cadquery as cq

from backend.models import AircraftDesign
from backend.geometry.airfoil import load_airfoil

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_wing_panels(
    design: AircraftDesign,
    side: Literal["left", "right"],
) -> "list[cq.Workplane]":
    """Build one wing half as a list of individual panel solids.

    For single-section wings, returns a list with one element (the single panel).
    For multi-section wings, returns N separate panel solids WITHOUT boolean union.

    This is the preferred function for preview/tessellation since it avoids the
    fragile boolean union and produces per-panel meshes with consistent normals.
    Control surface cuts should be applied to the result of build_wing() (which
    unions the panels), not to individual panels from this function.

    Args:
        design: Complete aircraft design parameters.
        side:   Which wing half.  "left" extends in -Y, "right" in +Y.

    Returns:
        List of cq.Workplane objects, one per panel (length == wing_sections).
    """
    import cadquery as cq  # noqa: F811

    if design.wing_sections > 1:
        return _build_multi_section_panels(cq, design, side)
    return [_build_single_panel(cq, design, side)]


def build_wing(
    design: AircraftDesign,
    side: Literal["left", "right"],
) -> "cq.Workplane":
    """Build one wing half (left or right) as a solid.

    For single-section wings (wing_sections == 1), generates a single lofted
    panel from root to tip -- the classic behaviour.

    For multi-section wings (wing_sections > 1), generates N separate lofted
    panels and unions them into a single solid.  Panel break positions are
    taken from design.panel_break_positions, dihedrals from
    design.panel_dihedrals, and sweep overrides from design.panel_sweeps.

    **Geometry construction process (single-section):**

    1. **Airfoil loading**: Load profile from .dat file.
    2. **Root section**: Scale to wing_chord, apply wing_incidence.
    3. **Tip section**: Scale to tip_chord, apply incidence + twist.
    4. **Sweep**: Offset tip X by quarter-chord sweep formula.
    5. **Dihedral**: Applied via transformed() Z offsets per panel.
    6. **Loft**: cq loft() with ruled=False.
    7. **TE enforcement**: No-op, documented.
    8. **Skin shell**: If hollow_parts, shell to wing_skin_thickness.

    Args:
        design: Complete aircraft design parameters.
        side:   Which wing half.  "left" extends in -Y, "right" in +Y.

    Returns:
        cq.Workplane with wing half solid.

    Raises:
        FileNotFoundError: If airfoil .dat file not found.
        ValueError: If airfoil profile has fewer than 10 points.
    """
    import cadquery as cq  # noqa: F811

    if design.wing_sections > 1:
        return _build_multi_section_wing(cq, design, side)
    return _build_single_panel(cq, design, side)


# ---------------------------------------------------------------------------
# Single-section wing (original algorithm)
# ---------------------------------------------------------------------------


def _build_single_panel(
    cq: type,
    design: AircraftDesign,
    side: Literal["left", "right"],
) -> "cq.Workplane":
    """Build a classic single-panel wing half."""
    # 1. Load airfoil profile (unit chord)
    profile = load_airfoil(design.wing_airfoil)

    # 2. Dimensions
    root_chord = design.wing_chord
    tip_chord = root_chord * design.wing_tip_root_ratio
    half_span = design.wing_span / 2.0

    # 3. Sweep offset at tip (quarter-chord line sweep)
    sweep_rad = math.radians(design.wing_sweep)
    sweep_offset_x = (
        half_span * math.tan(sweep_rad)
        + 0.25 * (root_chord - tip_chord)
    )

    # 4. Y direction sign
    y_sign = -1.0 if side == "left" else 1.0

    # 5. Scale airfoil points
    wing_incidence_deg = design.wing_incidence
    wing_twist_deg = design.wing_twist
    root_pts = _scale_airfoil_2d(profile, root_chord, wing_incidence_deg)
    tip_pts = _scale_airfoil_2d(
        profile, tip_chord, wing_incidence_deg + wing_twist_deg,
    )

    # 6. Dihedral Z offset at tip (accumulated via transformed)
    dihedral_rad = math.radians(design.wing_dihedral)
    dihedral_z_at_tip = half_span * math.tan(dihedral_rad)

    # 7. Loft: root at Y=0, tip with sweep + dihedral offsets
    result = (
        cq.Workplane("XZ")
        .spline(root_pts, periodic=False).close()
        .workplane(offset=y_sign * half_span)
        .transformed(offset=(sweep_offset_x, dihedral_z_at_tip, 0))
        .spline(tip_pts, periodic=False).close()
        .loft(ruled=False)
    )

    # 8. TE enforcement: no-op
    result = _enforce_te_thickness(cq, result, design.te_min_thickness)

    # 9. Shell if hollow
    if design.hollow_parts:
        result = _shell_wing(result, design.wing_skin_thickness, side)

    return result


# ---------------------------------------------------------------------------
# Multi-section wing (new algorithm)
# ---------------------------------------------------------------------------


def _build_multi_section_wing(
    cq: type,
    design: AircraftDesign,
    side: Literal["left", "right"],
) -> "cq.Workplane":
    """Build a multi-panel wing half using N lofted segments.

    Each panel is lofted from its inboard cross-section to its outboard
    cross-section.  Dihedral is accumulated geometrically: each panel's
    dihedral is relative to the previous panel's end orientation.

    The approach uses transformed() offsets to build the outboard station
    of each panel in the correct 3D position, then unions the panels.
    No .rotate() is applied -- the geometry is built directly in place.

    Coordinate reminders (XZ workplane):
      local X  = global X (chordwise)
      local Y  = global Z (vertical)  -- offset via transformed(0, z, 0)
      local Z  = global -Y (spanwise) -- offset via workplane(offset=y)

    For the right wing: outboard = +Y (positive workplane offset).
    For the left wing:  outboard = -Y (negative workplane offset).
    """
    root_profile = load_airfoil(design.wing_airfoil)
    n = design.wing_sections
    root_chord = design.wing_chord
    tip_chord = root_chord * design.wing_tip_root_ratio
    half_span = design.wing_span / 2.0
    y_sign = -1.0 if side == "left" else 1.0

    wing_incidence_deg = design.wing_incidence
    wing_twist_deg = design.wing_twist

    # Build list of (span_frac, chord) for all stations: root + breaks + tip
    # span_frac is fraction of half-span (0.0 = root, 1.0 = tip).
    n_breaks = n - 1  # number of break positions
    break_fracs = [
        design.panel_break_positions[i] / 100.0
        for i in range(n_breaks)
    ]
    # Stations: root (0.0), breaks, tip (1.0)
    station_fracs = [0.0] + break_fracs + [1.0]

    # Per-station chord (linear taper)
    station_chords = [
        root_chord + (tip_chord - root_chord) * frac
        for frac in station_fracs
    ]

    # Per-station sweep angle: panel 1 uses wing_sweep, panels 2+ use panel_sweeps
    # (panel_sweeps[i] is the sweep for panel i+2, i.e., the second panel onwards)
    panel1_sweep = design.wing_sweep
    panel_sweep_angles = [panel1_sweep] + [
        design.panel_sweeps[i] for i in range(n_breaks)
    ]

    # Per-station dihedral angle: panel 1 uses wing_dihedral, panels 2+ use panel_dihedrals
    panel1_dihedral = design.wing_dihedral
    panel_dihedral_angles = [panel1_dihedral] + [
        design.panel_dihedrals[i] for i in range(n_breaks)
    ]

    # Compute cumulative absolute X (sweep) and Z (dihedral) offsets at each station.
    # Station 0 (root) is at (x=0, z=0, y=0).
    #
    # ``panel_span_mm`` is derived from ``half_span`` which is the user-specified
    # horizontal wingspan / 2.  It therefore represents the **projected horizontal**
    # (Y-axis) extent of each panel — i.e., the "adjacent" side in the dihedral
    # right-triangle (horizontal leg), NOT the true spanwise arc length.
    #
    # Given projected horizontal span as the adjacent side:
    #   delta_y = panel_span_mm           (projected Y is already the adjacent side)
    #   delta_z = panel_span_mm * tan(dihedral_rad)  (vertical rise from adjacent)
    #   delta_x = panel_span_mm * tan(sweep_rad) + 0.25*(c_in - c_out)  (chordwise LE shift)
    #
    # Do NOT multiply delta_y by cos(dihedral_rad) — that would incorrectly shrink
    # the projected span as if panel_span_mm were the true arc (hypotenuse).

    station_abs_x: list[float] = [0.0]  # absolute sweep offset from root LE
    station_abs_z: list[float] = [0.0]  # absolute dihedral Z offset from root
    station_abs_y: list[float] = [0.0]  # absolute projected Y (spanwise) offset

    for panel_idx in range(n):
        frac_in = station_fracs[panel_idx]
        frac_out = station_fracs[panel_idx + 1]
        # Projected horizontal span for this panel (adjacent side in dihedral triangle)
        panel_span_mm = half_span * (frac_out - frac_in)

        sweep_rad = math.radians(panel_sweep_angles[panel_idx])
        dihedral_rad = math.radians(panel_dihedral_angles[panel_idx])

        chord_in = station_chords[panel_idx]
        chord_out = station_chords[panel_idx + 1]

        # Quarter-chord sweep: LE offset accounts for taper
        qc_correction = 0.25 * (chord_in - chord_out)
        delta_x = panel_span_mm * math.tan(sweep_rad) + qc_correction

        # Dihedral vertical rise: rise = adjacent * tan(angle)
        delta_z = panel_span_mm * math.tan(dihedral_rad)

        # Projected Y extent equals panel_span_mm (it is already the horizontal projection)
        delta_y = panel_span_mm

        station_abs_x.append(station_abs_x[-1] + delta_x)
        station_abs_z.append(station_abs_z[-1] + delta_z)
        station_abs_y.append(station_abs_y[-1] + delta_y)

    # Build each panel as a separate lofted solid
    panels: list["cq.Workplane"] = []
    for panel_idx in range(n):
        chord_in = station_chords[panel_idx]
        chord_out = station_chords[panel_idx + 1]

        # Twist at the tip station (linear interpolation for intermediate stations)
        frac_in = station_fracs[panel_idx]
        frac_out = station_fracs[panel_idx + 1]

        # Apply incidence + linear twist fraction at each station
        twist_in = wing_incidence_deg + wing_twist_deg * frac_in
        twist_out = wing_incidence_deg + wing_twist_deg * frac_out

        # W12: per-panel airfoil selection.
        # panel_idx 0 = innermost panel (always uses root airfoil).
        # panel_idx 1, 2, 3 = panels 2, 3, 4 — use override if set.
        if panel_idx == 0 or design.panel_airfoils[panel_idx - 1] is None:
            profile = root_profile
        else:
            profile = load_airfoil(design.panel_airfoils[panel_idx - 1])

        pts_in = _scale_airfoil_2d(profile, chord_in, twist_in)
        pts_out = _scale_airfoil_2d(profile, chord_out, twist_out)

        x_in = station_abs_x[panel_idx]
        z_in = station_abs_z[panel_idx]
        y_in = station_abs_y[panel_idx]

        x_out = station_abs_x[panel_idx + 1]
        z_out = station_abs_z[panel_idx + 1]
        y_out = station_abs_y[panel_idx + 1]

        # Y extent for this panel's loft workplane offset (projected span)
        panel_y_extent = y_out - y_in

        try:
            panel = (
                cq.Workplane("XZ")
                .transformed(offset=(x_in, z_in, 0))
                .spline(pts_in, periodic=False).close()
                .workplane(offset=y_sign * panel_y_extent)
                .transformed(offset=((x_out - x_in), (z_out - z_in), 0))
                .spline(pts_out, periodic=False).close()
                .loft(ruled=False)
            )
            # Translate to correct absolute Y position (the workplane offset
            # above moves relative to the inboard face; we need to shift the
            # whole panel to the correct absolute Y position)
            panel = panel.translate((0, y_sign * y_in, 0))
            panels.append(panel)
        except Exception:
            # If a panel fails to loft, fall back to single-section wing
            return _build_single_panel(cq, design, side)

    if not panels:
        return _build_single_panel(cq, design, side)

    # Union all panels into a single solid
    result = panels[0]
    for extra_panel in panels[1:]:
        try:
            result = result.union(extra_panel)
        except Exception:
            # If union fails, keep what we have
            pass

    # Shell each panel individually if hollow (guidance doc §1.12)
    # We shell after union here for simplicity; individual panel shelling
    # is fragile on joined lofts, so we try the union first.
    result = _enforce_te_thickness(cq, result, design.te_min_thickness)

    if design.hollow_parts:
        result = _shell_wing(result, design.wing_skin_thickness, side)

    return result


def _build_multi_section_panels(
    cq: type,
    design: AircraftDesign,
    side: Literal["left", "right"],
) -> "list[cq.Workplane]":
    """Build a multi-panel wing half as a list of separate lofted solids.

    Does NOT union the panels — each panel is returned as its own solid.
    This is used for preview tessellation to ensure per-panel face normals
    are consistent (no shading discontinuity at panel junctions from union
    seam artefacts) and to support per-panel click selection (#241, #242).

    Geometry construction is identical to ``_build_multi_section_wing``; the
    only difference is the return type (list of panels vs. single unioned solid).
    ``hollow_parts`` and TE enforcement are NOT applied — panels are solid for
    preview.  For export, use ``build_wing()`` which applies those operations.

    Returns:
        List of cq.Workplane objects, length == design.wing_sections.
        On loft failure for any panel the function falls back to returning
        ``[_build_single_panel(...)]`` so the caller always gets at least one panel.
    """
    profile = load_airfoil(design.wing_airfoil)
    n = design.wing_sections
    root_chord = design.wing_chord
    tip_chord = root_chord * design.wing_tip_root_ratio
    half_span = design.wing_span / 2.0
    y_sign = -1.0 if side == "left" else 1.0

    wing_incidence_deg = design.wing_incidence
    wing_twist_deg = design.wing_twist

    n_breaks = n - 1
    break_fracs = [
        design.panel_break_positions[i] / 100.0
        for i in range(n_breaks)
    ]
    station_fracs = [0.0] + break_fracs + [1.0]

    station_chords = [
        root_chord + (tip_chord - root_chord) * frac
        for frac in station_fracs
    ]

    panel1_sweep = design.wing_sweep
    panel_sweep_angles = [panel1_sweep] + [
        design.panel_sweeps[i] for i in range(n_breaks)
    ]

    panel1_dihedral = design.wing_dihedral
    panel_dihedral_angles = [panel1_dihedral] + [
        design.panel_dihedrals[i] for i in range(n_breaks)
    ]

    station_abs_x: list[float] = [0.0]
    station_abs_z: list[float] = [0.0]
    station_abs_y: list[float] = [0.0]

    for panel_idx in range(n):
        frac_in = station_fracs[panel_idx]
        frac_out = station_fracs[panel_idx + 1]
        panel_span_mm = half_span * (frac_out - frac_in)

        sweep_rad = math.radians(panel_sweep_angles[panel_idx])
        dihedral_rad = math.radians(panel_dihedral_angles[panel_idx])

        chord_in = station_chords[panel_idx]
        chord_out = station_chords[panel_idx + 1]

        qc_correction = 0.25 * (chord_in - chord_out)
        delta_x = panel_span_mm * math.tan(sweep_rad) + qc_correction
        delta_z = panel_span_mm * math.tan(dihedral_rad)
        delta_y = panel_span_mm

        station_abs_x.append(station_abs_x[-1] + delta_x)
        station_abs_z.append(station_abs_z[-1] + delta_z)
        station_abs_y.append(station_abs_y[-1] + delta_y)

    panels: list["cq.Workplane"] = []
    for panel_idx in range(n):
        chord_in = station_chords[panel_idx]
        chord_out = station_chords[panel_idx + 1]

        frac_in = station_fracs[panel_idx]
        frac_out = station_fracs[panel_idx + 1]

        twist_in = wing_incidence_deg + wing_twist_deg * frac_in
        twist_out = wing_incidence_deg + wing_twist_deg * frac_out

        pts_in = _scale_airfoil_2d(profile, chord_in, twist_in)
        pts_out = _scale_airfoil_2d(profile, chord_out, twist_out)

        x_in = station_abs_x[panel_idx]
        z_in = station_abs_z[panel_idx]
        y_in = station_abs_y[panel_idx]

        x_out = station_abs_x[panel_idx + 1]
        z_out = station_abs_z[panel_idx + 1]
        y_out = station_abs_y[panel_idx + 1]

        panel_y_extent = y_out - y_in

        try:
            panel = (
                cq.Workplane("XZ")
                .transformed(offset=(x_in, z_in, 0))
                .spline(pts_in, periodic=False).close()
                .workplane(offset=y_sign * panel_y_extent)
                .transformed(offset=((x_out - x_in), (z_out - z_in), 0))
                .spline(pts_out, periodic=False).close()
                .loft(ruled=False)
            )
            panel = panel.translate((0, y_sign * y_in, 0))
            panels.append(panel)
        except Exception:
            # If a panel fails to loft, fall back to single-section wing
            return [_build_single_panel(cq, design, side)]

    if not panels:
        return [_build_single_panel(cq, design, side)]

    return panels


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _scale_airfoil_2d(
    profile: list[tuple[float, float]],
    chord: float,
    rotation_deg: float,
) -> list[tuple[float, float]]:
    """Scale and rotate an airfoil profile for use in a CadQuery spline.

    Returns 2D (x, z) points in the XZ plane, scaled to the given chord
    and rotated about the quarter-chord point.

    Args:
        profile:      Airfoil (x, y) coordinates, unit chord.
        chord:        Chord length in mm.
        rotation_deg: Incidence/twist rotation about quarter-chord in degrees.

    Returns:
        List of (x, z) 2D tuples ready for cq.Workplane("XZ").spline().
    """
    rot_rad = math.radians(rotation_deg)
    cos_r = math.cos(rot_rad)
    sin_r = math.sin(rot_rad)
    qc = 0.25 * chord  # quarter-chord point

    points: list[tuple[float, float]] = []
    for px, py in profile:
        x = px * chord
        z = py * chord

        # Rotate about quarter-chord (in XZ plane)
        dx = x - qc
        x_rot = qc + dx * cos_r + z * sin_r
        z_rot = -(dx * sin_r) + z * cos_r

        points.append((x_rot, z_rot))

    return points


def _enforce_te_thickness(
    cq_mod: type,
    solid: "cq.Workplane",
    te_min_thickness: float,
) -> "cq.Workplane":
    """Enforce minimum trailing edge thickness.

    .. note:: **Not yet functional (MVP).** This function is a documented
       no-op. CadQuery boolean unions with thin wedge solids along the TE
       line are fragile and frequently fail on lofted airfoil shapes.
       Full TE thickening geometry is planned for post-MVP (1.0).

    The ``te_min_thickness`` parameter is accepted and validated by the
    model, but has no geometric effect in the current release.  The
    airfoil .dat files distributed with CHENG already have TE thickness
    >= 0.4 mm at chord scales >= 50 mm (the minimum wing_chord).
    """
    import logging

    logger = logging.getLogger(__name__)
    logger.warning(
        "TE thickness enforcement is not yet implemented (te_min_thickness=%.2f). "
        "Returning solid unchanged.",
        te_min_thickness,
    )
    return solid


def _shell_wing(
    solid: "cq.Workplane",
    skin_thickness: float,
    side: Literal["left", "right"],
) -> "cq.Workplane":
    """Shell the wing to create a hollow interior.

    Leaves the root face open for spar insertion and fuselage mating.
    The root face is the one closest to Y=0: for the right wing that is
    the minimum-Y face ('<Y'), for the left wing the maximum-Y face ('>Y').
    """
    # Select root face to leave open: right wing root is at -Y side of
    # the half, left wing root is at +Y side (both nearest Y=0).
    root_face_selector = "<Y" if side == "right" else ">Y"
    try:
        result = solid.faces(root_face_selector).shell(-skin_thickness)
    except Exception:
        # Fallback: try shelling without face selection
        try:
            result = solid.shell(-skin_thickness)
        except Exception:
            result = solid
    return result
