"""Static stability math module for RC aircraft design.

Pure math module — no CadQuery, no I/O. Called from engine.compute_derived_values().

Computes the seven new derived stability fields:
  - neutral_point_mm
  - neutral_point_pct_mac
  - cg_pct_mac
  - static_margin_pct
  - tail_volume_h
  - tail_volume_v
  - wing_loading_g_dm2

Aerodynamic basis (spec section 2.2):
  Wing AC at 25% MAC for all RC airfoils (NACA-2412, 4412, Clark-Y, symmetric).
  NP_frac_MAC = 0.25 + 0.88 * V_h  (0.88 = tail/wing lift curve slope ratio)
  NP_mm = wing_root_le_mm + mac_le_offset_mm + NP_frac_MAC * mac_mm
  SM_pct = NP_pct_MAC - CG_pct_MAC  (positive = pitch stable)

Coordinate conventions (matches engine.py):
  - All absolute X positions measured from aircraft nose (X=0, +X aft).
  - wing_le_ref_mm  = absolute position of wing root LE from nose (wing_x).
  - estimated_cg_mm = CG distance aft of wing root LE (= abs_cg - wing_x).
  - mac_le_offset   = y_mac * tan(sweep_rad) = sweep offset of MAC LE from root LE.
  - CG_pct_MAC      = (estimated_cg_mm - mac_le_offset) / mac_mm * 100
  - effective_tail_arm = tail_x - wing_x (from engine._compute_tail_x()).
"""

from __future__ import annotations

import math

from backend.models import AircraftDesign

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_static_stability(
    design: AircraftDesign,
    wing_le_ref_mm: float,
    estimated_cg_mm: float,
    mac_mm: float,
    wing_area_mm2: float,
    y_mac_mm: float,
    effective_tail_arm_mm: float,
    weight_total_g: float,
) -> dict[str, float]:
    """Compute static stability metrics from existing derived geometry.

    Parameters:
        design                -- full AircraftDesign model (for tail dims, tail_type, etc.)
        wing_le_ref_mm        -- absolute X position of wing root LE from nose (mm).
                                 Corresponds to wing_x from _compute_wing_mount().
        estimated_cg_mm       -- CG distance aft of wing root LE (mm), from _compute_cg().
                                 Note: this is cg_x - wing_x, NOT absolute from nose.
        mac_mm                -- mean aerodynamic chord (mm), already computed.
        wing_area_mm2         -- wing planform area (mm²), already computed.
        y_mac_mm              -- spanwise position of MAC from wing root (mm), from
                                 _compute_mac_cranked(). Used to compute sweep-corrected
                                 MAC LE offset: mac_le_offset = y_mac * tan(sweep_rad).
        effective_tail_arm_mm -- effective tail arm from wing LE to tail LE (mm).
                                 = _compute_tail_x(design) - wing_x. Use this rather than
                                 design.tail_arm directly so stability matches the 3D model.
        weight_total_g        -- total aircraft weight in grams (airframe + motor + battery),
                                 passed from the engine to avoid circular import.

    Returns:
        dict[str, float] with exactly 7 snake_case keys:
            neutral_point_mm       -- NP absolute position from nose (mm)
            neutral_point_pct_mac  -- NP as % of MAC from MAC LE
            cg_pct_mac             -- CG as % of MAC from MAC LE
            static_margin_pct      -- (NP% - CG%) positive = pitch-stable
            tail_volume_h          -- V_h horizontal tail volume coefficient
            tail_volume_v          -- V_v vertical tail volume coefficient
            wing_loading_g_dm2     -- total weight / wing area in g/dm²
    """
    # Guard: degenerate geometry
    if mac_mm <= 0.0 or wing_area_mm2 <= 0.0:
        return _zero_stability()

    # Sweep-corrected MAC LE offset from wing root LE.
    # design.wing_sweep is the quarter-chord sweep angle, so the LE offset is:
    #   mac_le_offset = 0.25 * (root_chord - mac_mm) + y_mac * tan(qc_sweep)
    # The first term corrects for the taper-induced shift from QC sweep to LE sweep;
    # the second is the standard sweep contribution along the span.
    # Note: multi-section panel_sweeps are not individually accumulated here;
    # this is a single-sweep approximation valid for all current CHENG presets.
    sweep_rad = math.radians(design.wing_sweep)
    mac_le_offset = 0.25 * (design.wing_chord - mac_mm) + y_mac_mm * math.tan(sweep_rad)

    # Tail volume coefficients — use effective_tail_arm_mm so stability
    # is consistent with the actual 3D geometry (tail clamped to fuselage).
    v_h = _tail_volume_h(design, wing_area_mm2, mac_mm, effective_tail_arm_mm)
    v_v = _tail_volume_v(design, wing_area_mm2, design.wing_span, effective_tail_arm_mm)

    # Neutral point as % of MAC from MAC LE
    np_pct_mac = _neutral_point_pct_mac(v_h)

    # CG as % of MAC from MAC LE.
    # estimated_cg_mm is distance aft of wing root LE; subtract mac_le_offset
    # to express it relative to the MAC LE itself.
    cg_from_mac_le = estimated_cg_mm - mac_le_offset
    cg_pct_mac = (cg_from_mac_le / mac_mm) * 100.0 if mac_mm > 0.0 else 0.0

    # Static margin
    sm_pct = _static_margin_pct(cg_pct_mac, np_pct_mac)

    # Neutral point absolute position from nose:
    # wing root LE + MAC LE sweep offset + NP as fraction of MAC
    np_mm = wing_le_ref_mm + mac_le_offset + (np_pct_mac / 100.0) * mac_mm

    # Wing loading
    wing_area_cm2 = wing_area_mm2 / 100.0
    wl = _wing_loading(weight_total_g, wing_area_cm2)

    return {
        "neutral_point_mm": round(np_mm, 2),
        "neutral_point_pct_mac": round(np_pct_mac, 2),
        "cg_pct_mac": round(cg_pct_mac, 2),
        "static_margin_pct": round(sm_pct, 2),
        "tail_volume_h": round(v_h, 4),
        "tail_volume_v": round(v_v, 4),
        "wing_loading_g_dm2": round(wl, 2),
    }


# ---------------------------------------------------------------------------
# Helper functions (module-private, prefixed with _)
# ---------------------------------------------------------------------------


def _tail_volume_h(
    design: AircraftDesign,
    wing_area_mm2: float,
    mac_mm: float,
    effective_tail_arm_mm: float,
) -> float:
    """Horizontal tail volume coefficient: V_h = (S_h * l_t) / (S_w * MAC).

    S_h = h_stab_span * h_stab_chord  [mm²]
    l_t = effective_tail_arm_mm        [mm]  (clamped, matches 3D geometry)
    S_w = wing_area_mm2                [mm²]
    MAC = mac_mm                       [mm]

    V-Tail: S_h_eff = v_tail_span * v_tail_chord * cos(v_tail_dihedral_rad)
            (geometric area projection — cos(dihedral) not cos² as in V10 aero effectiveness)
    Flying wing (BWB preset) or h_stab_span == 0: return 0.0
    """
    denom = wing_area_mm2 * mac_mm
    if denom <= 0.0:
        return 0.0

    # Flying wing fallback: no horizontal tail contribution
    is_flying_wing = design.fuselage_preset == "Blended-Wing-Body"
    if is_flying_wing or design.h_stab_span == 0:
        return 0.0

    if design.tail_type == "V-Tail":
        # Geometric area projection for horizontal component.
        # Spec section 5.1 specifies cos(dihedral) for area projection
        # (not cos² which validation.py uses for aerodynamic effectiveness).
        dihedral_rad = math.radians(design.v_tail_dihedral)
        s_h = design.v_tail_span * design.v_tail_chord * math.cos(dihedral_rad)
    else:
        s_h = design.h_stab_span * design.h_stab_chord

    return (s_h * effective_tail_arm_mm) / denom


def _tail_volume_v(
    design: AircraftDesign,
    wing_area_mm2: float,
    wing_span_mm: float,
    effective_tail_arm_mm: float,
) -> float:
    """Vertical tail volume coefficient: V_v = (S_v * l_t) / (S_w * b).

    S_v = v_stab_root_chord * v_stab_height  [mm²]
    l_t = effective_tail_arm_mm               [mm]  (clamped, matches 3D geometry)
    S_w = wing_area_mm2                       [mm²]
    b   = wing_span_mm                        [mm]

    V-Tail: S_v_eff = v_tail_span * v_tail_chord * sin(v_tail_dihedral_rad)
    """
    denom = wing_area_mm2 * wing_span_mm
    if denom <= 0.0:
        return 0.0

    if design.tail_type == "V-Tail":
        dihedral_rad = math.radians(design.v_tail_dihedral)
        s_v = design.v_tail_span * design.v_tail_chord * math.sin(dihedral_rad)
    else:
        # tail.py hardcodes v_stab taper_ratio=0.6, so average chord = 0.8 * root_chord.
        # Trapezoidal area = 0.5 * (1.0 + 0.6) * root_chord * height = 0.8 * root * h
        s_v = 0.8 * design.v_stab_root_chord * design.v_stab_height

    return (s_v * effective_tail_arm_mm) / denom


def _neutral_point_pct_mac(v_h: float) -> float:
    """NP position as percentage of MAC from MAC leading edge.

    Formula: NP_frac = 0.25 + 0.88 * V_h  (percentage = * 100)

    Where:
      0.25  = wing aerodynamic center (25% MAC for all low-Re RC airfoils)
      0.88  = approximate ratio of tail/wing lift curve slopes (dCL_tail/dCL_wing)

    Typical RC range: V_h 0.3-0.8 gives NP at 51.4%-95.4% MAC.
    """
    return (0.25 + 0.88 * v_h) * 100.0


def _static_margin_pct(cg_pct_mac: float, np_pct_mac: float) -> float:
    """Static margin as % MAC: SM = NP% - CG%.

    Positive = CG ahead of NP = pitch-stable (returns to trim after perturbation).
    Negative = CG behind NP = pitch-unstable (diverges after perturbation).
    """
    return np_pct_mac - cg_pct_mac


def _wing_loading(weight_total_g: float, wing_area_cm2: float) -> float:
    """Wing loading in g/dm²: weight_total_g / (wing_area_cm2 / 100).

    Converts wing area from cm² to dm² (divide by 100) then divides weight.
    Returns 0.0 if wing area is zero.
    """
    if wing_area_cm2 <= 0.0:
        return 0.0
    # wing_area_cm2 / 100 = wing_area_dm2
    return weight_total_g / (wing_area_cm2 / 100.0)


def _zero_stability() -> dict[str, float]:
    """Return a safe all-zero stability dict for degenerate geometry.

    Uses NP=25% MAC (wing AC) and CG=0%, giving SM=25% — indicating stable
    but clearly degenerate. This avoids confusing the frontend with a negative
    static margin for zero-MAC cases.
    """
    return {
        "neutral_point_mm": 0.0,
        "neutral_point_pct_mac": 25.0,   # Wing AC as NP fallback
        "cg_pct_mac": 0.0,
        "static_margin_pct": 25.0,        # NP% - CG% = 25 - 0 = 25 (internally consistent)
        "tail_volume_h": 0.0,
        "tail_volume_v": 0.0,
        "wing_loading_g_dm2": 0.0,
    }
