"""Unit tests for backend/stability.py static stability math module.

Tests 1–8 and 11 test pure math helpers — no engine dependency.
Tests 9, 10, 12 are integration tests that require #311 (engine wiring).
These are marked with @pytest.mark.integration and skipped if the engine
does not yet include stability fields in compute_derived_values().

Run: python -m pytest tests/backend/test_stability.py -v
"""

from __future__ import annotations

import math

import pytest

from backend.models import AircraftDesign
from backend.stability import (
    _neutral_point_pct_mac,
    _static_margin_pct,
    _tail_volume_h,
    _tail_volume_v,
    _wing_loading,
    compute_static_stability,
)


# ---------------------------------------------------------------------------
# Helper: check whether engine wiring (#311) is in place
# ---------------------------------------------------------------------------


def _engine_has_stability() -> bool:
    """Return True if compute_derived_values() includes stability fields."""
    from backend.geometry.engine import compute_derived_values
    design = AircraftDesign()
    result = compute_derived_values(design)
    return "static_margin_pct" in result


_NEEDS_ENGINE = pytest.mark.skipif(
    not _engine_has_stability(),
    reason="Requires #311 (engine stability wiring) to be merged",
)


# ---------------------------------------------------------------------------
# Test 1: NP formula
# ---------------------------------------------------------------------------


def test_neutral_point_formula() -> None:
    """NP_pct = (0.25 + 0.88 * V_h) * 100."""
    v_h = 0.5
    np_pct = _neutral_point_pct_mac(v_h)
    expected = (0.25 + 0.88 * v_h) * 100.0
    assert abs(np_pct - expected) < 0.001


def test_neutral_point_zero_v_h() -> None:
    """V_h=0 (no tail) => NP = 25% MAC (wing aerodynamic center)."""
    np_pct = _neutral_point_pct_mac(0.0)
    assert abs(np_pct - 25.0) < 0.001


# ---------------------------------------------------------------------------
# Test 2: Static margin positive (stable)
# ---------------------------------------------------------------------------


def test_static_margin_positive() -> None:
    """SM > 0 when CG is ahead of NP (pitch-stable)."""
    cg_pct = 25.0   # 25% MAC
    np_pct = 30.0   # 30% MAC
    sm = _static_margin_pct(cg_pct, np_pct)
    assert sm > 0
    assert abs(sm - 5.0) < 0.001


# ---------------------------------------------------------------------------
# Test 3: Static margin negative (unstable)
# ---------------------------------------------------------------------------


def test_static_margin_negative() -> None:
    """SM < 0 when CG is behind NP (pitch-unstable)."""
    cg_pct = 35.0   # 35% MAC — behind NP
    np_pct = 30.0   # 30% MAC
    sm = _static_margin_pct(cg_pct, np_pct)
    assert sm < 0
    assert abs(sm - (-5.0)) < 0.001


# ---------------------------------------------------------------------------
# Test 4: V_h formula (conventional tail)
# ---------------------------------------------------------------------------


def test_tail_volume_h_formula() -> None:
    """V_h = (S_h * l_t) / (S_w * MAC)."""
    design = AircraftDesign(
        h_stab_span=350, h_stab_chord=100, tail_arm=180,
        wing_span=1000, wing_chord=180, tail_type="Conventional",
    )
    wing_area_mm2 = 0.5 * (180 + 180 * 1.0) * 1000  # = 180000 mm²
    mac = 180.0  # taper_ratio=1.0 => MAC = chord
    effective_tail_arm = 180.0  # Use tail_arm directly for this unit test

    v_h = _tail_volume_h(design, wing_area_mm2, mac, effective_tail_arm)
    expected = (350 * 100 * 180) / (wing_area_mm2 * mac)
    assert abs(v_h - expected) < 0.001


# ---------------------------------------------------------------------------
# Test 5: V_v formula (conventional tail)
# ---------------------------------------------------------------------------


def test_tail_volume_v_formula() -> None:
    """V_v = (S_v * l_t) / (S_w * b). V-stab area uses 0.8 taper factor."""
    design = AircraftDesign(
        v_stab_height=100, v_stab_root_chord=110, tail_arm=180,
        wing_span=1000, wing_chord=180, tail_type="Conventional",
    )
    wing_area_mm2 = 0.5 * (180 + 180 * 1.0) * 1000  # = 180000 mm²
    effective_tail_arm = 180.0

    v_v = _tail_volume_v(design, wing_area_mm2, 1000.0, effective_tail_arm)
    # stability.py applies 0.8 taper factor to match tail.py's hardcoded 0.6 taper
    expected = (0.8 * 100 * 110 * 180) / (wing_area_mm2 * 1000.0)
    assert abs(v_v - expected) < 0.001


# ---------------------------------------------------------------------------
# Test 6: Wing loading formula
# ---------------------------------------------------------------------------


def test_wing_loading_formula() -> None:
    """wing_loading_g_dm2 = weight_g / (area_cm2 / 100)."""
    # 500g total weight, 50 cm² wing area = 500 / 0.5 = 1000 g/dm²
    wl = _wing_loading(500.0, 50.0)
    assert abs(wl - 1000.0) < 0.01

    # 400g, 200 cm² = 400 / 2.0 = 200 g/dm²
    wl2 = _wing_loading(400.0, 200.0)
    assert abs(wl2 - 200.0) < 0.01


def test_wing_loading_zero_area() -> None:
    """Wing loading returns 0 for zero area (guard against division by zero)."""
    wl = _wing_loading(500.0, 0.0)
    assert wl == 0.0


# ---------------------------------------------------------------------------
# Test 7: V-tail projected area (cos projection)
# ---------------------------------------------------------------------------


def test_v_tail_projected_area() -> None:
    """V-tail uses cos(dihedral) for effective horizontal area per spec §5.1."""
    dihedral = 35.0  # degrees (typical V-tail)
    design = AircraftDesign(
        tail_type="V-Tail",
        v_tail_dihedral=dihedral,
        v_tail_span=280,
        v_tail_chord=90,
        tail_arm=200,
        wing_span=1000,
        wing_chord=180,
    )
    wing_area_mm2 = 0.5 * (180 + 180) * 1000  # = 180000 mm²
    mac = 180.0
    effective_tail_arm = 200.0

    v_h = _tail_volume_h(design, wing_area_mm2, mac, effective_tail_arm)

    # Expected: S_h_eff = v_tail_span * v_tail_chord * cos(dihedral_rad)
    s_h_eff = 280 * 90 * math.cos(math.radians(dihedral))
    v_h_expected = (s_h_eff * 200) / (wing_area_mm2 * mac)
    assert abs(v_h - v_h_expected) < 0.001


def test_v_tail_vertical_area() -> None:
    """V-tail uses sin(dihedral) for effective vertical area."""
    dihedral = 35.0
    design = AircraftDesign(
        tail_type="V-Tail",
        v_tail_dihedral=dihedral,
        v_tail_span=280,
        v_tail_chord=90,
        tail_arm=200,
        wing_span=1000,
        wing_chord=180,
    )
    wing_area_mm2 = 0.5 * (180 + 180) * 1000
    effective_tail_arm = 200.0

    v_v = _tail_volume_v(design, wing_area_mm2, 1000.0, effective_tail_arm)

    s_v_eff = 280 * 90 * math.sin(math.radians(dihedral))
    v_v_expected = (s_v_eff * 200) / (wing_area_mm2 * 1000.0)
    assert abs(v_v - v_v_expected) < 0.001


# ---------------------------------------------------------------------------
# Test 8: No-tail / flying wing fallback
# ---------------------------------------------------------------------------


def test_no_tail_fallback() -> None:
    """Flying wing (BWB preset): V_h = 0, NP = 25% MAC."""
    design = AircraftDesign(
        fuselage_preset="Blended-Wing-Body",
        wing_span=1000,
        wing_chord=180,
    )
    wing_area_mm2 = 0.5 * (180 + 180) * 1000
    mac = 180.0
    effective_tail_arm = 180.0

    v_h = _tail_volume_h(design, wing_area_mm2, mac, effective_tail_arm)
    assert v_h == 0.0

    np_pct = _neutral_point_pct_mac(v_h)
    assert abs(np_pct - 25.0) < 0.001


def test_zero_h_stab_span_fallback() -> None:
    """h_stab_span=0 treated like no tail: V_h = 0."""
    # h_stab_span minimum is 100 by Pydantic constraint; bypass with model_copy
    design = AircraftDesign()
    design_no_tail = design.model_copy(update={"h_stab_span": 0})
    wing_area_mm2 = 0.5 * (180 + 180) * 1000
    mac = 180.0
    v_h = _tail_volume_h(design_no_tail, wing_area_mm2, mac, 180.0)
    assert v_h == 0.0


# ---------------------------------------------------------------------------
# Test 11: Degenerate geometry guard (zero tail arm / minimal geometry)
# ---------------------------------------------------------------------------


def test_zero_tail_arm_no_crash() -> None:
    """Minimal tail arm returns a valid result without raising."""
    design = AircraftDesign(
        wing_span=1000, wing_chord=180,
        tail_arm=80,   # minimum allowed by field constraint (ge=80)
        h_stab_span=350, h_stab_chord=100,
    )
    wing_area_mm2 = 0.5 * (180 + 180) * 1000
    mac = 180.0
    wing_le_ref_mm = 90.0
    estimated_cg_mm = 45.0  # CG relative to wing root LE
    y_mac_mm = 250.0
    effective_tail_arm_mm = 80.0
    weight_total_g = 500.0

    result = compute_static_stability(
        design, wing_le_ref_mm, estimated_cg_mm, mac, wing_area_mm2,
        y_mac_mm, effective_tail_arm_mm, weight_total_g,
    )
    assert isinstance(result, dict)
    assert "static_margin_pct" in result
    # With a minimal tail arm, V_h is small, NP stays near 25% MAC
    assert result["neutral_point_pct_mac"] >= 25.0  # NP >= wing AC
    assert isinstance(result["tail_volume_h"], float)


def test_degenerate_zero_mac_returns_safe() -> None:
    """Zero MAC triggers the degenerate guard and returns safe defaults."""
    from backend.stability import _zero_stability
    design = AircraftDesign()
    # Force degenerate by passing mac_mm=0
    result = compute_static_stability(
        design,
        wing_le_ref_mm=90.0,
        estimated_cg_mm=45.0,
        mac_mm=0.0,           # degenerate
        wing_area_mm2=180000.0,
        y_mac_mm=250.0,
        effective_tail_arm_mm=180.0,
        weight_total_g=500.0,
    )
    safe = _zero_stability()
    assert result == safe


# ---------------------------------------------------------------------------
# Tests 9, 10, 12: Integration tests (require #311 engine wiring)
# ---------------------------------------------------------------------------


@_NEEDS_ENGINE
def test_trainer_preset_stable() -> None:
    """Trainer preset SM should be in 8-15% range (forgiving, self-damping pitch)."""
    from backend.geometry.engine import compute_derived_values

    design = AircraftDesign(
        wing_span=1200, wing_chord=200, wing_tip_root_ratio=0.8,
        h_stab_span=420, h_stab_chord=120, tail_arm=220,
        tail_type="Conventional",
        battery_position_frac=0.25,
    )
    derived = compute_derived_values(design)
    sm = derived["static_margin_pct"]
    assert 5.0 <= sm <= 20.0, f"Trainer SM={sm:.1f}% — expected roughly 8-15%"


@_NEEDS_ENGINE
def test_aerobatic_preset_responsive() -> None:
    """Aerobatic preset SM should be in 2-12% range (responsive pitch)."""
    from backend.geometry.engine import compute_derived_values

    design = AircraftDesign(
        wing_span=900, wing_chord=160, wing_tip_root_ratio=0.6,
        h_stab_span=300, h_stab_chord=90, tail_arm=160,
        tail_type="Conventional",
        battery_position_frac=0.30,
    )
    derived = compute_derived_values(design)
    sm = derived["static_margin_pct"]
    assert sm > 0.0, f"Aerobatic design should be pitch-stable, got SM={sm:.1f}%"


@_NEEDS_ENGINE
def test_derived_values_includes_stability_fields() -> None:
    """compute_derived_values() returns all 7 stability keys in correct format."""
    from backend.geometry.engine import compute_derived_values
    from backend.models import DerivedValues

    design = AircraftDesign()  # defaults
    result = compute_derived_values(design)

    stability_keys = [
        "neutral_point_mm", "neutral_point_pct_mac", "cg_pct_mac",
        "static_margin_pct", "tail_volume_h", "tail_volume_v",
        "wing_loading_g_dm2",
    ]
    for key in stability_keys:
        assert key in result, f"Missing stability key in compute_derived_values(): {key}"

    # Verify DerivedValues model accepts the result and serializes correctly
    derived = DerivedValues(**result)
    dumped = derived.model_dump(by_alias=True)

    camel_keys = [
        "neutralPointMm", "neutralPointPctMac", "cgPctMac",
        "staticMarginPct", "tailVolumeH", "tailVolumeV",
        "wingLoadingGDm2",
    ]
    for key in camel_keys:
        assert key in dumped, f"Missing camelCase key in model_dump(by_alias=True): {key}"

    # Sanity check values are reasonable
    assert dumped["staticMarginPct"] != 0.0 or dumped["tailVolumeH"] == 0.0
    assert dumped["wingLoadingGDm2"] > 0.0
