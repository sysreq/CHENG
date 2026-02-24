"""Tests for validation rules — V01-V06 (structural) and V16-V23 (print)."""

from __future__ import annotations

import pytest

from backend.models import AircraftDesign
from backend.validation import compute_warnings


def _warning_ids(design: AircraftDesign) -> set[str]:
    """Helper: return the set of warning IDs for a design."""
    return {w.id for w in compute_warnings(design)}


# ---------------------------------------------------------------------------
# V01: wingspan > 2000 mm
# ---------------------------------------------------------------------------


class TestV01:
    def test_triggers_on_large_wingspan(self) -> None:
        design = AircraftDesign(wing_span=2500)
        assert "V01" in _warning_ids(design)

    def test_does_not_trigger_on_normal_wingspan(self) -> None:
        design = AircraftDesign(wing_span=1200)
        assert "V01" not in _warning_ids(design)

    def test_boundary_does_not_trigger(self) -> None:
        design = AircraftDesign(wing_span=2000)
        assert "V01" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V02: wing loading too high
# ---------------------------------------------------------------------------


class TestV02:
    def test_triggers_on_thick_skin_small_area(self) -> None:
        """Thick skin with large span/chord product should trigger high loading."""
        design = AircraftDesign(
            wing_span=3000,
            wing_chord=500,
            wing_skin_thickness=3.0,
        )
        ids = _warning_ids(design)
        assert "V02" in ids

    def test_does_not_trigger_on_normal_design(self) -> None:
        design = AircraftDesign()  # defaults
        assert "V02" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V03: tail arm > fuselage length
# ---------------------------------------------------------------------------


class TestV03:
    def test_triggers_when_tail_exceeds_fuselage(self) -> None:
        design = AircraftDesign(tail_arm=500, fuselage_length=300)
        assert "V03" in _warning_ids(design)

    def test_does_not_trigger_when_tail_within_fuselage(self) -> None:
        design = AircraftDesign(tail_arm=180, fuselage_length=300)
        assert "V03" not in _warning_ids(design)

    def test_equal_values_do_not_trigger(self) -> None:
        design = AircraftDesign(tail_arm=300, fuselage_length=300)
        assert "V03" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V04: tail volume coefficient too low
# ---------------------------------------------------------------------------


class TestV04:
    def test_triggers_on_small_tail(self) -> None:
        """Very small h-stab with long wing should trigger."""
        design = AircraftDesign(
            wing_span=2000,
            wing_chord=200,
            h_stab_span=100,
            h_stab_chord=30,
            tail_arm=100,
        )
        assert "V04" in _warning_ids(design)

    def test_does_not_trigger_on_adequate_tail(self) -> None:
        """A design with large enough tail surfaces should not trigger."""
        design = AircraftDesign(
            wing_span=1000,
            wing_chord=180,
            h_stab_span=400,
            h_stab_chord=150,
            tail_arm=300,
        )
        assert "V04" not in _warning_ids(design)

    def test_v_tail_uses_projected_area(self) -> None:
        """V-tail should use projected horizontal area."""
        design = AircraftDesign(
            tail_type="V-Tail",
            wing_span=2000,
            wing_chord=200,
            v_tail_span=80,
            v_tail_chord=30,
            v_tail_dihedral=45,
            tail_arm=100,
        )
        assert "V04" in _warning_ids(design)


# ---------------------------------------------------------------------------
# V05: tip chord too small
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
# V06: aspect ratio extreme (< 4 or > 12)
# ---------------------------------------------------------------------------


class TestV06:
    def test_triggers_on_low_ar(self) -> None:
        """Short span, wide chord = low AR."""
        design = AircraftDesign(wing_span=300, wing_chord=500)
        # AR = 300^2 / (0.5 * (500 + 500) * 300) = 90000/150000 = 0.6
        assert "V06" in _warning_ids(design)

    def test_triggers_on_high_ar(self) -> None:
        """Long span, narrow chord = high AR."""
        design = AircraftDesign(wing_span=3000, wing_chord=50)
        # AR = 3000^2 / (0.5 * (50 + 50) * 3000) = 9000000/150000 = 60
        assert "V06" in _warning_ids(design)

    def test_does_not_trigger_on_normal_ar(self) -> None:
        """Default design has normal AR (about 5.56)."""
        design = AircraftDesign()
        assert "V06" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V16: wall thickness < 1.2 mm
# ---------------------------------------------------------------------------


class TestV16:
    def test_triggers_on_thin_skin(self) -> None:
        design = AircraftDesign(wing_skin_thickness=0.8)
        assert "V16" in _warning_ids(design)

    def test_does_not_trigger_on_adequate_skin(self) -> None:
        design = AircraftDesign(wing_skin_thickness=1.2)
        assert "V16" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V17: section exceeds print bed (when auto-section disabled)
# ---------------------------------------------------------------------------


class TestV17:
    def test_triggers_when_oversized_no_autosection(self) -> None:
        design = AircraftDesign(
            wing_span=1000,  # half-span = 500mm
            auto_section=False,
            print_bed_x=220,
            print_bed_y=220,
        )
        assert "V17" in _warning_ids(design)

    def test_does_not_trigger_with_autosection(self) -> None:
        design = AircraftDesign(
            wing_span=1000,
            auto_section=True,
            print_bed_x=220,
        )
        assert "V17" not in _warning_ids(design)

    def test_does_not_trigger_when_fits(self) -> None:
        design = AircraftDesign(
            wing_span=400,  # half-span = 200mm, fits in 220mm bed
            fuselage_length=200,
            auto_section=False,
            print_bed_x=220,
            print_bed_y=220,
        )
        assert "V17" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V18: overhang concern (high dihedral + thin skin)
# ---------------------------------------------------------------------------


class TestV18:
    def test_triggers_on_high_dihedral_thin_skin(self) -> None:
        design = AircraftDesign(wing_dihedral=10, wing_skin_thickness=1.2)
        assert "V18" in _warning_ids(design)

    def test_does_not_trigger_on_low_dihedral(self) -> None:
        design = AircraftDesign(wing_dihedral=3, wing_skin_thickness=1.2)
        assert "V18" not in _warning_ids(design)

    def test_does_not_trigger_on_thick_skin(self) -> None:
        design = AircraftDesign(wing_dihedral=10, wing_skin_thickness=2.0)
        assert "V18" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V20: estimated part count > 20
# ---------------------------------------------------------------------------


class TestV20:
    def test_triggers_on_large_plane_small_bed(self) -> None:
        design = AircraftDesign(
            wing_span=3000,
            fuselage_length=2000,
            auto_section=True,
            print_bed_x=100,
            print_bed_y=100,
        )
        assert "V20" in _warning_ids(design)

    def test_does_not_trigger_on_normal_design(self) -> None:
        design = AircraftDesign()  # defaults: 1000mm span, 220mm bed
        assert "V20" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V21: estimated print time > 48h
# ---------------------------------------------------------------------------


class TestV21:
    def test_triggers_on_huge_design(self) -> None:
        design = AircraftDesign(
            wing_span=3000,
            wing_chord=500,
            fuselage_length=2000,
            wing_skin_thickness=3.0,
        )
        ids = _warning_ids(design)
        assert "V21" in ids

    def test_does_not_trigger_on_normal_design(self) -> None:
        design = AircraftDesign()
        assert "V21" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V22: joint tolerance too tight (< 0.1 mm)
# ---------------------------------------------------------------------------


class TestV22:
    def test_triggers_on_tight_tolerance(self) -> None:
        design = AircraftDesign(joint_tolerance=0.05)
        assert "V22" in _warning_ids(design)

    def test_does_not_trigger_on_normal_tolerance(self) -> None:
        design = AircraftDesign(joint_tolerance=0.15)
        assert "V22" not in _warning_ids(design)

    def test_boundary_does_not_trigger(self) -> None:
        design = AircraftDesign(joint_tolerance=0.1)
        assert "V22" not in _warning_ids(design)


# ---------------------------------------------------------------------------
# V23: TE min thickness < 2 * nozzle_diameter
# ---------------------------------------------------------------------------


class TestV23:
    def test_triggers_when_te_below_threshold(self) -> None:
        design = AircraftDesign(te_min_thickness=0.6, nozzle_diameter=0.4)
        # 2 * 0.4 = 0.8 > 0.6 → should trigger
        assert "V23" in _warning_ids(design)

    def test_does_not_trigger_when_te_adequate(self) -> None:
        design = AircraftDesign(te_min_thickness=0.8, nozzle_diameter=0.4)
        # 2 * 0.4 = 0.8 = 0.8 → not below, should not trigger
        assert "V23" not in _warning_ids(design)

    def test_triggers_with_large_nozzle(self) -> None:
        design = AircraftDesign(te_min_thickness=1.0, nozzle_diameter=0.6)
        # 2 * 0.6 = 1.2 > 1.0 → should trigger
        assert "V23" in _warning_ids(design)


# ---------------------------------------------------------------------------
# Integration: default design should have minimal warnings
# ---------------------------------------------------------------------------


class TestDefaultDesign:
    def test_default_has_few_warnings(self) -> None:
        """Default design parameters should produce a flyable, printable design."""
        design = AircraftDesign()
        warnings = compute_warnings(design)
        ids = {w.id for w in warnings}
        # The default design should not trigger any of the critical structural warnings
        # V03 might trigger since default tail_arm(180) < fuselage_length(300) is fine
        assert "V01" not in ids  # wingspan 1000 is fine
        assert "V05" not in ids  # tip chord 180mm is fine
        assert "V22" not in ids  # tolerance 0.15 is fine

    def test_all_warnings_have_required_fields(self) -> None:
        """Every warning should have id, level, and message."""
        # Create a design that triggers multiple warnings
        design = AircraftDesign(
            wing_span=2500,
            wing_chord=50,
            tail_arm=500,
            fuselage_length=200,
            wing_skin_thickness=0.8,
            joint_tolerance=0.05,
            te_min_thickness=0.4,
            nozzle_diameter=0.4,
        )
        warnings = compute_warnings(design)
        for w in warnings:
            assert w.id, "Warning must have an id"
            assert w.level == "warn", "All MVP warnings are level=warn"
            assert w.message, "Warning must have a message"
            assert isinstance(w.fields, list), "fields must be a list"
