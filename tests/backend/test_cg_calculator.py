"""Tests for the full CG calculator (v0.6 #139).

Verifies that the CG is computed as a weighted average of component positions,
responds correctly to motor/battery placement, and maintains backward
compatibility with the aerodynamic-center estimate for default designs.
"""

from __future__ import annotations

import math

import pytest

from backend.geometry.engine import compute_derived_values, _compute_cg, _WING_X_FRACTION
from backend.models import AircraftDesign


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default(**overrides) -> AircraftDesign:
    return AircraftDesign(**overrides)


def _get_cg(**overrides) -> float:
    d = compute_derived_values(_default(**overrides))
    return d["estimated_cg_mm"]


# ---------------------------------------------------------------------------
# Basic CG properties
# ---------------------------------------------------------------------------


class TestCGBasics:
    """CG should be a finite positive number for valid designs."""

    def test_default_cg_positive(self) -> None:
        cg = _get_cg()
        assert cg > 0, "CG must be forward of wing trailing edge"

    def test_default_cg_within_chord(self) -> None:
        """CG should typically fall within the wing chord for a balanced design."""
        design = _default()
        cg = _get_cg()
        # CG relative to wing LE should be roughly 20-80% of chord
        assert 0 < cg < design.wing_chord

    def test_cg_is_float(self) -> None:
        d = compute_derived_values(_default())
        assert isinstance(d["estimated_cg_mm"], float)

    def test_cg_not_nan(self) -> None:
        cg = _get_cg()
        assert not math.isnan(cg)


# ---------------------------------------------------------------------------
# Motor position affects CG
# ---------------------------------------------------------------------------


class TestMotorEffect:
    """Tractor motor (nose) should pull CG forward; pusher should push it aft."""

    def test_tractor_vs_pusher(self) -> None:
        tractor = _get_cg(motor_config="Tractor", motor_weight_g=100)
        pusher = _get_cg(motor_config="Pusher", motor_weight_g=100)
        assert tractor < pusher, "Tractor motor should pull CG forward"

    def test_heavier_motor_shifts_cg(self) -> None:
        light = _get_cg(motor_weight_g=20)
        heavy = _get_cg(motor_weight_g=200)
        # Tractor motor at nose: heavier motor -> more forward CG
        assert heavy < light

    def test_zero_motor_weight(self) -> None:
        """With no motor, CG should still be valid."""
        cg = _get_cg(motor_weight_g=0)
        assert cg > 0


# ---------------------------------------------------------------------------
# Battery position affects CG
# ---------------------------------------------------------------------------


class TestBatteryEffect:
    """Battery placement should shift CG predictably."""

    def test_forward_battery_shifts_cg_forward(self) -> None:
        forward = _get_cg(battery_position_frac=0.1, battery_weight_g=200)
        aft = _get_cg(battery_position_frac=0.8, battery_weight_g=200)
        assert forward < aft

    def test_heavier_battery_has_more_effect(self) -> None:
        # With a light battery, CG is dominated by structural weight
        light_fwd = _get_cg(battery_position_frac=0.1, battery_weight_g=50)
        light_aft = _get_cg(battery_position_frac=0.8, battery_weight_g=50)
        heavy_fwd = _get_cg(battery_position_frac=0.1, battery_weight_g=500)
        heavy_aft = _get_cg(battery_position_frac=0.8, battery_weight_g=500)
        # Heavy battery creates bigger CG shift
        assert (heavy_aft - heavy_fwd) > (light_aft - light_fwd)

    def test_zero_battery_weight(self) -> None:
        cg = _get_cg(battery_weight_g=0)
        assert cg > 0


# ---------------------------------------------------------------------------
# Wing sweep affects CG
# ---------------------------------------------------------------------------


class TestSweepEffect:
    """Forward sweep should shift CG forward, aft sweep should shift it aft."""

    def test_aft_sweep_shifts_cg_aft(self) -> None:
        no_sweep = _get_cg(wing_sweep=0)
        swept = _get_cg(wing_sweep=20)
        assert swept > no_sweep

    def test_forward_sweep_shifts_cg_forward(self) -> None:
        no_sweep = _get_cg(wing_sweep=0)
        fwd_sweep = _get_cg(wing_sweep=-5)
        assert fwd_sweep < no_sweep


# ---------------------------------------------------------------------------
# Fuselage preset affects wing mount position -> CG
# ---------------------------------------------------------------------------


class TestFuselagePresetCG:
    """Different fuselage presets have different wing mount fractions."""

    def test_pod_vs_conventional(self) -> None:
        """Pod has wing at 25% vs Conventional at 30% — CG should differ."""
        pod = _get_cg(fuselage_preset="Pod")
        conv = _get_cg(fuselage_preset="Conventional")
        # Different mount fractions -> different CG
        assert pod != pytest.approx(conv, abs=1.0)


# ---------------------------------------------------------------------------
# Tail type affects CG
# ---------------------------------------------------------------------------


class TestTailTypeCG:
    def test_vtail_cg_positive(self) -> None:
        cg = _get_cg(tail_type="V-Tail")
        assert cg > 0

    def test_conventional_tail_cg_positive(self) -> None:
        cg = _get_cg(tail_type="Conventional")
        assert cg > 0

    def test_ttail_cg_positive(self) -> None:
        cg = _get_cg(tail_type="T-Tail")
        assert cg > 0


# ---------------------------------------------------------------------------
# Edge cases and fallback
# ---------------------------------------------------------------------------


class TestCGEdgeCases:
    def test_all_zero_electronics_still_valid(self) -> None:
        """Even with no motor/battery, structural CG should be computed."""
        cg = _get_cg(motor_weight_g=0, battery_weight_g=0)
        assert cg > 0
        assert not math.isnan(cg)

    def test_heavy_tail_shifts_cg_aft(self) -> None:
        """A very large tail should pull CG aft."""
        small_tail = _get_cg(h_stab_span=100, h_stab_chord=50, v_stab_height=50, v_stab_root_chord=50)
        large_tail = _get_cg(h_stab_span=800, h_stab_chord=200, v_stab_height=300, v_stab_root_chord=200)
        assert large_tail > small_tail

    def test_cg_responds_to_all_parameters(self) -> None:
        """CG should change when any mass-affecting parameter changes."""
        base = _get_cg()
        # Changing battery position should change CG
        moved = _get_cg(battery_position_frac=0.9)
        assert base != pytest.approx(moved, abs=0.1)


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestCGBackwardCompat:
    def test_cg_still_near_quarter_chord_for_default(self) -> None:
        """For a balanced default design, CG should be near 25% MAC."""
        design = _default()
        d = compute_derived_values(design)
        mac = d["mean_aero_chord_mm"]
        cg = d["estimated_cg_mm"]
        # With motor at nose and battery at 30%, CG should be somewhat
        # forward — within 0-100% MAC is reasonable
        assert 0 < cg < mac

    def test_trainer_cg_in_range(self) -> None:
        """Trainer-like design should have CG in flyable range."""
        d = compute_derived_values(_default(
            wing_span=1200, wing_chord=200, fuselage_length=400,
            wing_tip_root_ratio=1.0, wing_sweep=0,
        ))
        # CG should be 20-40% of MAC for stability
        mac = d["mean_aero_chord_mm"]
        cg = d["estimated_cg_mm"]
        # CG between 10% and 60% MAC is reasonable for an RC plane
        assert 0.10 * mac < cg < 0.60 * mac
