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
  NP_frac_MAC = 0.25 + 0.88 × V_h  (0.88 ≈ tail/wing lift curve slope ratio)
  NP_mm = wing_le_ref_mm + NP_frac_MAC × mac_mm
  SM_pct = NP_pct_MAC - CG_pct_MAC  (positive = pitch stable)
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
) -> dict[str, float]:
    """Compute static stability metrics from existing derived geometry.

    Parameters:
        design          -- full AircraftDesign model (for tail dims, tail_type, etc.)
        wing_le_ref_mm  -- absolute X position of wing leading edge from nose (mm).
                           Corresponds to wing_x from _compute_wing_mount() in engine.py.
        estimated_cg_mm -- aircraft CG position from nose (mm), already computed by
                           engine._compute_cg(). Note: engine returns CG relative to
                           wing LE, so the absolute position is wing_le_ref_mm + estimated_cg_mm.
        mac_mm          -- mean aerodynamic chord (mm), already computed.
        wing_area_mm2   -- wing planform area (mm²), already computed.

    Returns:
        dict[str, float] with exactly 7 snake_case keys:
            neutral_point_mm       -- NP absolute position from nose (mm)
            neutral_point_pct_mac  -- NP as % of MAC from wing LE
            cg_pct_mac             -- CG as % of MAC from wing LE
            static_margin_pct      -- (NP% - CG%) positive = pitch-stable
            tail_volume_h          -- V_h horizontal tail volume coefficient
            tail_volume_v          -- V_v vertical tail volume coefficient
            wing_loading_g_dm2     -- total weight / wing area in g/dm²
    """
    # Guard: degenerate geometry
    if mac_mm <= 0.0 or wing_area_mm2 <= 0.0:
        return _zero_stability()

    # Tail volume coefficients
    v_h = _tail_volume_h(design, wing_area_mm2, mac_mm)
    v_v = _tail_volume_v(design, wing_area_mm2, design.wing_span)

    # Neutral point as % of MAC from wing LE
    np_pct_mac = _neutral_point_pct_mac(v_h)

    # CG position as % of MAC from wing LE.
    # engine._compute_cg() returns CG relative to wing LE (cg_x - wing_x),
    # so estimated_cg_mm here is already the offset from the wing LE.
    cg_pct_mac = (estimated_cg_mm / mac_mm) * 100.0 if mac_mm > 0.0 else 0.0

    # Static margin
    sm_pct = _static_margin_pct(cg_pct_mac, np_pct_mac)

    # Neutral point absolute position from nose
    np_mm = wing_le_ref_mm + (np_pct_mac / 100.0) * mac_mm

    # Wing loading
    from backend.geometry.engine import _compute_weight_estimates
    weights = _compute_weight_estimates(design)
    weight_total_g = (
        weights["weight_total_g"]
        + design.motor_weight_g
        + design.battery_weight_g
    )
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


def _tail_volume_h(design: AircraftDesign, wing_area_mm2: float, mac_mm: float) -> float:
    """Horizontal tail volume coefficient: V_h = (S_h * l_t) / (S_w * MAC).

    S_h = h_stab_span * h_stab_chord  [mm²]
    l_t = tail_arm                    [mm]
    S_w = wing_area_mm2               [mm²]
    MAC = mac_mm                      [mm]

    V-Tail: S_h_eff = v_tail_span * v_tail_chord * cos(v_tail_dihedral_rad)
    Flying wing / no tail (h_stab_span == 0 or BWB preset): return 0.0
    """
    denom = wing_area_mm2 * mac_mm
    if denom <= 0.0:
        return 0.0

    # Flying wing fallback: no horizontal tail contribution
    is_flying_wing = design.fuselage_preset == "Blended-Wing-Body"
    if is_flying_wing or design.h_stab_span == 0:
        return 0.0

    if design.tail_type == "V-Tail":
        # Geometric area projection: cos(dihedral) for horizontal component
        dihedral_rad = math.radians(design.v_tail_dihedral)
        s_h = design.v_tail_span * design.v_tail_chord * math.cos(dihedral_rad)
    else:
        s_h = design.h_stab_span * design.h_stab_chord

    return (s_h * design.tail_arm) / denom


def _tail_volume_v(design: AircraftDesign, wing_area_mm2: float, wing_span_mm: float) -> float:
    """Vertical tail volume coefficient: V_v = (S_v * l_t) / (S_w * b).

    S_v = v_stab_root_chord * v_stab_height  [mm²]
    l_t = tail_arm                           [mm]
    S_w = wing_area_mm2                      [mm²]
    b   = wing_span_mm                       [mm]

    V-Tail: S_v_eff = v_tail_span * v_tail_chord * sin(v_tail_dihedral_rad)
    """
    denom = wing_area_mm2 * wing_span_mm
    if denom <= 0.0:
        return 0.0

    if design.tail_type == "V-Tail":
        dihedral_rad = math.radians(design.v_tail_dihedral)
        s_v = design.v_tail_span * design.v_tail_chord * math.sin(dihedral_rad)
    else:
        s_v = design.v_stab_root_chord * design.v_stab_height

    return (s_v * design.tail_arm) / denom


def _neutral_point_pct_mac(v_h: float) -> float:
    """NP position as percentage of MAC from wing leading edge.

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
    """Return a safe all-zero stability dict for degenerate geometry."""
    return {
        "neutral_point_mm": 0.0,
        "neutral_point_pct_mac": 25.0,  # Wing AC as fallback
        "cg_pct_mac": 0.0,
        "static_margin_pct": 0.0,
        "tail_volume_h": 0.0,
        "tail_volume_v": 0.0,
        "wing_loading_g_dm2": 0.0,
    }
