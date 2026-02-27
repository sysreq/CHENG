"""Tests for validation rules — V01-V06 (structural) and V16-V23 (print).

All warning conditions are defined in docs/mvp_spec.md §9.2 and §9.3.
"""

from __future__ import annotations

import pytest

from backend.models import AircraftDesign
from backend.validation import compute_warnings


def _warning_ids(design: AircraftDesign) -> set[str]:
    """Helper: return the set of warning IDs for a design."""
    return {w.id for w in compute_warnings(design)}


# ---------------------------------------------------------------------------
# V01: wingspan > 10 * fuselageLength
# ---------------------------------------------------------------------------


class TestV01:
    def test_triggers_when_wingspan_far_exceeds_fuselage(self) -> None:
        # 2000 > 10 * 150 = 1500
        design = AircraftDesign(wing_span=2000, fuselage_length=150)
        assert "V01" in _warning_ids(design)

    def test_does_not_trigger_on_normal_wingspan(self) -> None:
        design = AircraftDesign(wing_span=1200, fuselage_length=300)
        assert "V01" not in _warning_ids(design)

    def test_boundary_does_not_trigger(self) -> None:
        # 10 * 200 = 2000, wingspan=2000 is NOT > 2000
        design = AircraftDesign(wing_span=2000, fuselage_length=200)
        assert "V01" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V02: tipRootRatio < 0.3
# ---------------------------------------------------------------------------


class TestV02:
    def test_boundary_does_not_trigger(self) -> None:
        """Model min is 0.3, so the boundary value should not trigger."""
        design = AircraftDesign(wing_tip_root_ratio=0.3)
        assert "V02" not in _warning_ids(design)

    def test_does_not_trigger_on_normal_taper(self) -> None:
        design = AircraftDesign(wing_tip_root_ratio=0.7)
        assert "V02" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V03: fuselageLength < wingChord
# ---------------------------------------------------------------------------


class TestV03:
    def test_triggers_when_fuselage_shorter_than_chord(self) -> None:
        design = AircraftDesign(fuselage_length=150, wing_chord=200)
        assert "V03" in _warning_ids(design)

    def test_does_not_trigger_when_fuselage_longer(self) -> None:
        design = AircraftDesign(fuselage_length=300, wing_chord=180)
        assert "V03" not in _warning_ids(design)

    def test_equal_values_do_not_trigger(self) -> None:
        design = AircraftDesign(fuselage_length=200, wing_chord=200)
        assert "V03" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V04: tailArm < 2 * MAC
# ---------------------------------------------------------------------------


class TestV04:
    def test_triggers_on_short_tail_arm(self) -> None:
        # MAC for default chord=180, ratio=1.0 => MAC=180*2/3*(1+1+1)/(1+1)=180
        # 2 * 180 = 360. tail_arm=80 < 360 => triggers
        design = AircraftDesign(tail_arm=80, wing_chord=200)
        assert "V04" in _warning_ids(design)

    def test_does_not_trigger_on_adequate_tail_arm(self) -> None:
        # MAC for chord=100, ratio=1.0 => MAC=100. 2*100=200. tail_arm=500 >= 200
        design = AircraftDesign(
            tail_arm=500,
            wing_chord=100,
        )
        assert "V04" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V05: wingChord * tipRootRatio < 30
# ---------------------------------------------------------------------------


class TestV05:
    def test_triggers_on_tiny_tip(self) -> None:
        """50mm chord * 0.3 ratio = 15mm tip — should trigger."""
        design = AircraftDesign(wing_chord=50, wing_tip_root_ratio=0.3)
        assert "V05" in _warning_ids(design)

    def test_does_not_trigger_on_normal_tip(self) -> None:
        design = AircraftDesign(wing_chord=180, wing_tip_root_ratio=0.5)
        # 180 * 0.5 = 90mm — well above 30mm
        assert "V05" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V06: tailArm > fuselageLength
# ---------------------------------------------------------------------------


class TestV06:
    def test_triggers_when_tail_exceeds_fuselage(self) -> None:
        design = AircraftDesign(tail_arm=500, fuselage_length=400)
        assert "V06" in _warning_ids(design)

    def test_does_not_trigger_when_within(self) -> None:
        design = AircraftDesign(tail_arm=180, fuselage_length=300)
        assert "V06" not in _warning_ids(design)

    def test_equal_values_do_not_trigger(self) -> None:
        design = AircraftDesign(tail_arm=300, fuselage_length=300)
        assert "V06" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V16: skinThickness < 2 * nozzleDiameter
# ---------------------------------------------------------------------------


class TestV16:
    def test_triggers_on_thin_skin(self) -> None:
        # 0.8 < 2 * 0.6 = 1.2
        design = AircraftDesign(wing_skin_thickness=0.8, nozzle_diameter=0.6)
        assert "V16" in _warning_ids(design)

    def test_does_not_trigger_on_adequate_skin(self) -> None:
        # 1.2 >= 2 * 0.4 = 0.8
        design = AircraftDesign(wing_skin_thickness=1.2, nozzle_diameter=0.4)
        assert "V16" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V17: skinThickness % nozzleDiameter > 0.01
# ---------------------------------------------------------------------------


class TestV17:
    def test_triggers_when_not_clean_multiple(self) -> None:
        # 1.3 % 0.4 = 0.1 > 0.01
        design = AircraftDesign(wing_skin_thickness=1.3, nozzle_diameter=0.4)
        assert "V17" in _warning_ids(design)

    def test_does_not_trigger_on_clean_multiple(self) -> None:
        # 1.2 % 0.4 = 0.0
        design = AircraftDesign(wing_skin_thickness=1.2, nozzle_diameter=0.4)
        assert "V17" not in _warning_ids(design)

    def test_does_not_trigger_on_exact_double(self) -> None:
        # 0.8 % 0.4 = 0.0
        design = AircraftDesign(wing_skin_thickness=0.8, nozzle_diameter=0.4)
        assert "V17" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V18: skinThickness < 1.0mm (absolute structural minimum)
# ---------------------------------------------------------------------------


class TestV18:
    def test_triggers_on_thin_skin(self) -> None:
        # 0.8 < 1.0 absolute minimum
        design = AircraftDesign(wing_skin_thickness=0.8)
        assert "V18" in _warning_ids(design)

    def test_does_not_trigger_on_adequate_skin(self) -> None:
        # 1.2 >= 1.0 absolute minimum
        design = AircraftDesign(wing_skin_thickness=1.2)
        assert "V18" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V20: part exceeds bed size AND auto-section disabled
# ---------------------------------------------------------------------------


class TestV20:
    def test_triggers_when_oversized_no_autosection(self) -> None:
        design = AircraftDesign(
            wing_span=1000,  # half-span = 500mm > 220mm bed
            auto_section=False,
            print_bed_x=220,
            print_bed_y=220,
        )
        assert "V20" in _warning_ids(design)

    def test_does_not_trigger_with_autosection(self) -> None:
        design = AircraftDesign(
            wing_span=1000,
            auto_section=True,
            print_bed_x=220,
        )
        assert "V20" not in _warning_ids(design)

    def test_does_not_trigger_when_fits(self) -> None:
        design = AircraftDesign(
            wing_span=400,  # half-span = 200mm, fits in 220mm bed
            fuselage_length=200,
            auto_section=False,
            print_bed_x=220,
            print_bed_y=220,
        )
        assert "V20" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V21: jointOverlap < 10 AND wingspan > 800
# ---------------------------------------------------------------------------


class TestV21:
    def test_triggers_on_short_overlap_large_span(self) -> None:
        design = AircraftDesign(
            section_overlap=5,  # min is 5 per model, < 10
            wing_span=1000,     # > 800
        )
        assert "V21" in _warning_ids(design)

    def test_does_not_trigger_on_adequate_overlap(self) -> None:
        design = AircraftDesign(section_overlap=15, wing_span=1000)
        assert "V21" not in _warning_ids(design)

    def test_does_not_trigger_on_small_wingspan(self) -> None:
        design = AircraftDesign(section_overlap=5, wing_span=600)
        assert "V21" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V22: jointTolerance > 0.3
# ---------------------------------------------------------------------------


class TestV22:
    def test_triggers_on_loose_tolerance(self) -> None:
        design = AircraftDesign(joint_tolerance=0.4)
        assert "V22" in _warning_ids(design)

    def test_does_not_trigger_on_normal_tolerance(self) -> None:
        design = AircraftDesign(joint_tolerance=0.15)
        assert "V22" not in _warning_ids(design)

    def test_boundary_does_not_trigger(self) -> None:
        design = AircraftDesign(joint_tolerance=0.3)
        assert "V22" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V23: jointTolerance < 0.05
# ---------------------------------------------------------------------------


class TestV23:
    def test_boundary_does_not_trigger(self) -> None:
        """Model min is 0.05, so boundary should not trigger."""
        design = AircraftDesign(joint_tolerance=0.05)
        assert "V23" not in _warning_ids(design)

    def test_does_not_trigger_on_normal_tolerance(self) -> None:
        design = AircraftDesign(joint_tolerance=0.15)
        assert "V23" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# Integration: default design should have minimal warnings
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# V07: nose_cabin_break_pct must be < cabin_tail_break_pct (gap >= 5%)
# ---------------------------------------------------------------------------


class TestV07:
    def test_triggers_when_gap_too_small(self) -> None:
        """noseCabinBreakPct = 60, cabinTailBreakPct = 63 → gap = 3% → V07."""
        design = AircraftDesign(
            nose_cabin_break_pct=60.0,
            cabin_tail_break_pct=63.0,  # gap = 3% < 5%
        )
        assert "V07" in _warning_ids(design)

    def test_triggers_at_zero_gap(self) -> None:
        """noseCabinBreakPct = cabin_tail_break_pct → gap = 0% → V07."""
        design = AircraftDesign(
            nose_cabin_break_pct=50.0,
            cabin_tail_break_pct=50.0,  # gap = 0%
        )
        assert "V07" in _warning_ids(design)

    def test_does_not_trigger_with_valid_gap(self) -> None:
        """Default values (25%/75%) give gap=50% → no V07."""
        design = AircraftDesign(
            nose_cabin_break_pct=25.0,
            cabin_tail_break_pct=75.0,
        )
        assert "V07" not in _warning_ids(design)

    def test_does_not_trigger_at_minimum_gap(self) -> None:
        """Gap exactly 5% should not trigger V07."""
        design = AircraftDesign(
            nose_cabin_break_pct=30.0,
            cabin_tail_break_pct=35.0,  # gap = 5%
        )
        assert "V07" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V08: wall_thickness < 2 * nozzle_diameter
# ---------------------------------------------------------------------------


class TestV08:
    def test_triggers_on_thin_wall(self) -> None:
        """Wall 0.8mm < 2 * 0.4mm nozzle should not trigger (0.8 == 0.8)."""
        # Actually 0.8 is not < 0.8, so we need a thinner wall
        design = AircraftDesign(wall_thickness=0.8, nozzle_diameter=0.6)
        assert "V08" in _warning_ids(design)

    def test_does_not_trigger_on_adequate_wall(self) -> None:
        design = AircraftDesign(wall_thickness=1.5, nozzle_diameter=0.4)
        assert "V08" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# Integration: default design should have minimal warnings
# ---------------------------------------------------------------------------


class TestDefaultDesign:
    @pytest.mark.smoke
    def test_default_has_few_warnings(self) -> None:
        """Default design parameters should produce a flyable, printable design."""
        design = AircraftDesign()
        warnings = compute_warnings(design)
        ids = {w.id for w in warnings}
        # Default design should not trigger structural problems
        assert "V01" not in ids
        assert "V05" not in ids
        assert "V22" not in ids

    def test_all_warnings_have_required_fields(self) -> None:
        """Every warning should have id, level, and message."""
        # Create a design that triggers multiple warnings
        design = AircraftDesign(
            wing_span=2500,
            wing_chord=50,
            tail_arm=500,
            fuselage_length=200,
            wing_skin_thickness=0.8,
            joint_tolerance=0.4,
            te_min_thickness=0.4,
            nozzle_diameter=0.4,
        )
        warnings = compute_warnings(design)
        for w in warnings:
            assert w.id, "Warning must have an id"
            assert w.level == "warn", "All MVP warnings are level=warn"
            assert w.message, "Warning must have a message"
            assert isinstance(w.fields, list), "fields must be a list"
