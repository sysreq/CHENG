"""Tests for tail arm clamping (#237) and Flying Wing preset fix (#236).

Verifies:
  - _compute_tail_x() never returns a value > fuselage_length (#237)
  - V32 validation warning fires when wing_x + tail_arm > fuselage_length (#237)
  - Flying Wing preset produces a valid, non-floating tail position (#236)
"""

from __future__ import annotations

import pytest

from backend.geometry.engine import _compute_tail_x, _WING_X_FRACTION
from backend.models import AircraftDesign
from backend.validation import compute_warnings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _warning_ids(design: AircraftDesign) -> set[str]:
    return {w.id for w in compute_warnings(design)}


# ---------------------------------------------------------------------------
# _compute_tail_x clamping (#237)
# ---------------------------------------------------------------------------


class TestComputeTailXClamping:
    """tail_x must never exceed fuselage_length."""

    def test_tail_x_clamped_when_arm_too_large(self) -> None:
        """wing_x + tail_arm > fuselage_length → tail_x clamped to fuselage_length."""
        # Conventional fuselage: wing_x_frac = 0.30
        # wing_x = 0.30 * 400 = 120mm
        # tail_arm = 900 → unclamped tail_x = 1020mm > fuselage_length=400
        design = AircraftDesign(
            fuselage_length=400,
            fuselage_preset="Conventional",
            tail_arm=900,
        )
        tail_x = _compute_tail_x(design)
        assert tail_x <= design.fuselage_length, (
            f"tail_x={tail_x:.1f} exceeds fuselage_length={design.fuselage_length}"
        )
        assert tail_x == pytest.approx(design.fuselage_length)

    def test_tail_x_unclamped_when_arm_fits(self) -> None:
        """When tail_arm fits within fuselage, tail_x is not altered."""
        # Conventional: wing_x = 0.30 * 400 = 120mm
        # tail_arm = 200 → tail_x = 320mm < 400mm → no clamping
        design = AircraftDesign(
            fuselage_length=400,
            fuselage_preset="Conventional",
            tail_arm=200,
        )
        tail_x = _compute_tail_x(design)
        assert tail_x <= design.fuselage_length
        # Should be exactly wing_x + tail_arm (200 > min_tail_arm)
        wing_x = 400 * 0.30
        assert tail_x == pytest.approx(wing_x + 200)

    def test_tail_x_at_fuselage_end_exactly(self) -> None:
        """tail_arm that exactly reaches fuselage_length should not be clamped."""
        # Conventional: wing_x = 0.30 * 500 = 150mm
        # max arm = 500 - 150 = 350mm. tail_arm=350 → tail_x = 500 = fuselage_length
        design = AircraftDesign(
            fuselage_length=500,
            fuselage_preset="Conventional",
            tail_arm=350,
        )
        tail_x = _compute_tail_x(design)
        assert tail_x == pytest.approx(500.0)

    def test_tail_x_clamped_for_pod_fuselage(self) -> None:
        """Clamping works for Pod fuselage (wing_x_frac = 0.25)."""
        # Pod: wing_x = 0.25 * 1000 = 250mm
        # tail_arm = 900 → unclamped = 1150mm > 1000mm
        design = AircraftDesign(
            fuselage_length=1000,
            fuselage_preset="Pod",
            tail_arm=900,
        )
        tail_x = _compute_tail_x(design)
        assert tail_x <= design.fuselage_length
        assert tail_x == pytest.approx(1000.0)

    def test_tail_x_clamped_for_bwb_fuselage(self) -> None:
        """Clamping works for Blended-Wing-Body fuselage (wing_x_frac = 0.35).

        This is the Flying Wing case — fin must sit at rear of short pod.
        """
        # BWB: wing_x = 0.35 * 200 = 70mm
        # tail_arm = 200 → unclamped = 270mm > 200mm
        design = AircraftDesign(
            fuselage_length=200,
            fuselage_preset="Blended-Wing-Body",
            tail_arm=200,
        )
        tail_x = _compute_tail_x(design)
        assert tail_x <= design.fuselage_length
        assert tail_x == pytest.approx(200.0)

    def test_tail_x_always_at_least_min_tail_pos(self) -> None:
        """Clamping does not push tail_x below the minimum floor."""
        # Conventional: wing_x = 0.30 * 400 = 120mm
        # min_tail_pos = 0.75 * 400 = 300mm
        # tail_arm = 80 (model minimum) → floor lifts it from 300mm
        # wing_x + 80 = 200 < 300 → min floor applies → tail_x = 300mm
        design = AircraftDesign(
            fuselage_length=400,
            fuselage_preset="Conventional",
            tail_arm=80,
        )
        tail_x = _compute_tail_x(design)
        min_tail_pos = 400 * 0.75
        assert tail_x >= min_tail_pos


# ---------------------------------------------------------------------------
# V32 validation warning (#237)
# ---------------------------------------------------------------------------


class TestV32Warning:
    """V32 fires when wing_x + tail_arm > fuselage_length (but tail_arm <= fuselage_length).

    V06 covers the case where tail_arm > fuselage_length.
    V32 covers the subtler case: tail_arm fits within fuselage_length
    but the wing mount offset means wing_x + tail_arm still overshoots.
    """

    def test_v32_fires_when_arm_places_tail_beyond_fuselage(self) -> None:
        """V32 should trigger when wing_x + tail_arm > fuselage_length (subtle case)."""
        # Conventional: wing_x = 0.30 * 400 = 120mm
        # tail_arm = 350 <= 400 (no V06), but 120 + 350 = 470 > 400 → V32
        design = AircraftDesign(
            fuselage_length=400,
            fuselage_preset="Conventional",
            tail_arm=350,
        )
        assert "V32" in _warning_ids(design)
        assert "V06" not in _warning_ids(design)  # V32 fires, not V06

    def test_v32_not_fired_when_tail_fits(self) -> None:
        """V32 should not trigger when tail fits within fuselage."""
        # Conventional: wing_x = 0.30 * 400 = 120mm
        # tail_arm = 200 → wing_x + tail_arm = 320 < 400 → no V32
        design = AircraftDesign(
            fuselage_length=400,
            fuselage_preset="Conventional",
            tail_arm=200,
        )
        assert "V32" not in _warning_ids(design)

    def test_v32_boundary_exactly_at_fuselage_end(self) -> None:
        """V32 should not trigger when wing_x + tail_arm == fuselage_length."""
        # Conventional: wing_x = 0.30 * 500 = 150mm; tail_arm = 350
        # wing_x + tail_arm = 500 == fuselage_length → no V32
        design = AircraftDesign(
            fuselage_length=500,
            fuselage_preset="Conventional",
            tail_arm=350,
        )
        assert "V32" not in _warning_ids(design)

    def test_v32_warning_has_correct_fields(self) -> None:
        """V32 warning must reference tail_arm and fuselage_length."""
        design = AircraftDesign(
            fuselage_length=400,
            fuselage_preset="Conventional",
            tail_arm=350,
        )
        warnings = compute_warnings(design)
        v32 = [w for w in warnings if w.id == "V32"]
        assert len(v32) == 1
        assert "tail_arm" in v32[0].fields
        assert "fuselage_length" in v32[0].fields
        assert v32[0].level == "warn"

    def test_v32_fires_for_bwb_preset(self) -> None:
        """V32 fires for Blended-Wing-Body when wing offset causes overshoot."""
        # BWB: wing_x = 0.35 * 200 = 70mm
        # tail_arm = 150 <= 200 (no V06), but 70 + 150 = 220 > 200 → V32
        design = AircraftDesign(
            fuselage_length=200,
            fuselage_preset="Blended-Wing-Body",
            tail_arm=150,
        )
        assert "V32" in _warning_ids(design)
        assert "V06" not in _warning_ids(design)

    def test_v32_not_fired_when_v06_fires(self) -> None:
        """V32 must be suppressed when V06 already fires (mutual exclusivity)."""
        # tail_arm = 500 > fuselage_length = 400 → V06 fires, V32 should NOT
        design = AircraftDesign(
            fuselage_length=400,
            fuselage_preset="Conventional",
            tail_arm=500,
        )
        ids = _warning_ids(design)
        assert "V06" in ids
        assert "V32" not in ids


# ---------------------------------------------------------------------------
# Flying Wing preset tail position (#236)
# ---------------------------------------------------------------------------


class TestFlyingWingTailPosition:
    """Flying Wing preset should produce a fin at or near the fuselage rear."""

    def _flying_wing_design(self) -> AircraftDesign:
        """Reproduce the Flying Wing preset values (after #236 fix).

        Uses model-minimum values for h_stab to suppress horizontal surface.
        vStabHeight=35mm (≤ 20% of 200mm fuselage) for a small dorsal fin.
        tailArm=130mm → wing_x(70) + 130 = 200 = fuselage_length (no overshoot).
        """
        return AircraftDesign(
            fuselage_length=200,
            fuselage_preset="Blended-Wing-Body",
            motor_config="Pusher",
            wing_span=1100,
            wing_chord=250,
            tail_type="Conventional",
            v_stab_height=35,
            v_stab_root_chord=30,
            h_stab_span=100,   # model minimum
            h_stab_chord=30,   # model minimum
            tail_arm=130,
        )

    def test_tail_x_within_fuselage(self) -> None:
        """Flying Wing tail_x must not exceed fuselage_length."""
        design = self._flying_wing_design()
        tail_x = _compute_tail_x(design)
        assert tail_x <= design.fuselage_length, (
            f"tail_x={tail_x:.1f} exceeds fuselage_length={design.fuselage_length}"
        )

    def test_tail_x_near_fuselage_end(self) -> None:
        """Flying Wing fin should sit within the rear 10% of the fuselage pod."""
        design = self._flying_wing_design()
        tail_x = _compute_tail_x(design)
        # Should be at >= 90% of fuselage_length (near the rear)
        assert tail_x >= 0.90 * design.fuselage_length, (
            f"tail_x={tail_x:.1f} is not near the fuselage end "
            f"(expected >= {0.90 * design.fuselage_length:.1f})"
        )

    def test_v_stab_height_is_reasonable(self) -> None:
        """vStabHeight should be <= 20% of fuselage_length for a dorsal fin."""
        design = self._flying_wing_design()
        assert design.v_stab_height <= 0.20 * design.fuselage_length, (
            f"v_stab_height={design.v_stab_height}mm is more than 20% of "
            f"fuselage_length={design.fuselage_length}mm"
        )

    def test_no_v32_warning_with_preset_values(self) -> None:
        """Flying Wing preset with corrected tail_arm should not trigger V32."""
        # BWB: wing_x = 0.35 * 200 = 70mm; tail_arm = 130
        # wing_x + tail_arm = 200 == fuselage_length → no V32
        design = self._flying_wing_design()
        assert "V32" not in _warning_ids(design)
