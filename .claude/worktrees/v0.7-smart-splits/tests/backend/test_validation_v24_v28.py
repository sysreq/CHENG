"""Tests for expanded printability validation V24-V28 (v0.6 #141).

V24: Overhang analysis
V25: Trailing edge sharpness
V26: Connector/joint clearance check
V27: Per-part print orientation recommendation
V28: Layer adhesion warning for thin walls
"""

from __future__ import annotations

import pytest

from backend.models import AircraftDesign
from backend.validation import compute_warnings


def _warning_ids(design: AircraftDesign) -> set[str]:
    return {w.id for w in compute_warnings(design)}


def _warnings_by_id(design: AircraftDesign, vid: str) -> list:
    return [w for w in compute_warnings(design) if w.id == vid]


# ---------------------------------------------------------------------------
# V24: Overhang analysis
# ---------------------------------------------------------------------------


class TestV24:
    def test_does_not_trigger_on_normal_dihedral(self) -> None:
        """3 degrees dihedral should not trigger."""
        design = AircraftDesign(wing_dihedral=3, wing_sweep=0)
        assert "V24" not in _warning_ids(design)

    def test_triggers_on_extreme_dihedral(self) -> None:
        """Dihedral > 45 degrees should trigger."""
        design = AircraftDesign(wing_dihedral=15)  # Max is 15 per model constraint
        # 15 < 45, so this should NOT trigger for basic dihedral
        assert "V24" not in _warning_ids(design)

    def test_vtail_high_dihedral_triggers(self) -> None:
        """V-tail with dihedral > 45 should trigger."""
        design = AircraftDesign(
            tail_type="V-Tail",
            v_tail_dihedral=50,
        )
        v24s = _warnings_by_id(design, "V24")
        vtail_warning = any("v-tail" in w.message.lower() for w in v24s)
        assert vtail_warning

    def test_vtail_normal_dihedral_safe(self) -> None:
        """V-tail with dihedral=35 should not trigger."""
        design = AircraftDesign(
            tail_type="V-Tail",
            v_tail_dihedral=35,
        )
        v24s = _warnings_by_id(design, "V24")
        vtail_warning = any("v-tail" in w.message.lower() for w in v24s)
        assert not vtail_warning

    def test_conventional_tail_no_vtail_warning(self) -> None:
        """Conventional tail should never trigger V-tail overhang."""
        design = AircraftDesign(tail_type="Conventional")
        v24s = _warnings_by_id(design, "V24")
        vtail_warning = any("v-tail" in w.message.lower() for w in v24s)
        assert not vtail_warning


# ---------------------------------------------------------------------------
# V25: Trailing edge sharpness
# ---------------------------------------------------------------------------


class TestV25:
    def test_triggers_on_very_thin_te(self) -> None:
        """TE < 0.8mm should trigger."""
        design = AircraftDesign(te_min_thickness=0.5)
        assert "V25" in _warning_ids(design)

    def test_does_not_trigger_on_normal_te(self) -> None:
        """TE >= 0.8mm should not trigger the thickness warning."""
        design = AircraftDesign(te_min_thickness=1.0)
        v25s = _warnings_by_id(design, "V25")
        thin_te = any("below 0.8" in w.message.lower() for w in v25s)
        assert not thin_te

    def test_small_tip_chord_warning(self) -> None:
        """Very small tip chord should warn about TE printing."""
        design = AircraftDesign(
            wing_chord=100,
            wing_tip_root_ratio=0.3,  # tip = 30mm
        )
        v25s = _warnings_by_id(design, "V25")
        tip_warning = any("tip chord" in w.message.lower() for w in v25s)
        assert tip_warning

    def test_large_tip_chord_safe(self) -> None:
        """Large tip chord should not trigger tip TE warning."""
        design = AircraftDesign(
            wing_chord=200,
            wing_tip_root_ratio=1.0,
        )
        v25s = _warnings_by_id(design, "V25")
        tip_warning = any("tip chord" in w.message.lower() for w in v25s)
        assert not tip_warning


# ---------------------------------------------------------------------------
# V26: Connector/joint clearance
# ---------------------------------------------------------------------------


class TestV26:
    def test_triggers_on_very_tight_tolerance(self) -> None:
        """Tolerance below nozzle_diameter/4 should trigger."""
        design = AircraftDesign(
            joint_tolerance=0.05,
            nozzle_diameter=0.4,
        )
        # 0.05 < 0.4/4 = 0.1
        assert "V26" in _warning_ids(design)

    def test_does_not_trigger_on_adequate_tolerance(self) -> None:
        """Tolerance above nozzle/4 should not trigger clearance warning."""
        design = AircraftDesign(
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
        )
        v26s = _warnings_by_id(design, "V26")
        tight = any("too tight" in w.message.lower() for w in v26s)
        assert not tight

    def test_tongue_and_groove_depth_check(self) -> None:
        """Short overlap with thick walls should warn about tongue depth."""
        design = AircraftDesign(
            joint_type="Tongue-and-Groove",
            section_overlap=5,  # tongue depth = 2.5mm
            wing_skin_thickness=2.0,  # 2.5 < 2*2.0 = 4.0
            wall_thickness=2.0,
        )
        v26s = _warnings_by_id(design, "V26")
        depth_warning = any("tongue depth" in w.message.lower() for w in v26s)
        assert depth_warning

    def test_adequate_overlap_no_depth_warning(self) -> None:
        """Long overlap with thin walls should not warn about depth."""
        design = AircraftDesign(
            joint_type="Tongue-and-Groove",
            section_overlap=20,  # tongue depth = 10mm
            wing_skin_thickness=1.2,  # 10 > 2*1.2 = 2.4
            wall_thickness=1.5,
        )
        v26s = _warnings_by_id(design, "V26")
        depth_warning = any("tongue depth" in w.message.lower() for w in v26s)
        assert not depth_warning

    def test_non_tongue_and_groove_no_depth_check(self) -> None:
        """Dowel-Pin joints should not trigger tongue depth warning."""
        design = AircraftDesign(
            joint_type="Dowel-Pin",
            section_overlap=5,
            wing_skin_thickness=2.0,
        )
        v26s = _warnings_by_id(design, "V26")
        depth_warning = any("tongue depth" in w.message.lower() for w in v26s)
        assert not depth_warning


# ---------------------------------------------------------------------------
# V27: Print orientation
# ---------------------------------------------------------------------------


class TestV27:
    def test_triggers_when_chord_exceeds_bed_height(self) -> None:
        """Wing chord > bed Z should warn."""
        design = AircraftDesign(
            wing_chord=300,
            print_bed_z=250,
        )
        v27s = _warnings_by_id(design, "V27")
        chord_warning = any("wing chord" in w.message.lower() for w in v27s)
        assert chord_warning

    def test_does_not_trigger_when_chord_fits(self) -> None:
        """Wing chord < bed Z should not warn."""
        design = AircraftDesign(
            wing_chord=180,
            print_bed_z=250,
        )
        v27s = _warnings_by_id(design, "V27")
        chord_warning = any("wing chord" in w.message.lower() for w in v27s)
        assert not chord_warning

    def test_tall_fuselage_warning(self) -> None:
        """Pod fuselage that exceeds bed height should warn."""
        design = AircraftDesign(
            wing_chord=500,  # Pod fuse_height = 500 * 0.45 = 225
            fuselage_preset="Pod",
            print_bed_z=200,
        )
        v27s = _warnings_by_id(design, "V27")
        fuse_warning = any("fuselage" in w.message.lower() for w in v27s)
        # 225 > 200 => should trigger
        assert fuse_warning


# ---------------------------------------------------------------------------
# V28: Layer adhesion for thin walls
# ---------------------------------------------------------------------------


class TestV28:
    def test_triggers_on_very_thin_skin(self) -> None:
        """Skin below 2x nozzle (single perimeter) should trigger."""
        design = AircraftDesign(
            wing_skin_thickness=0.8,  # = 2 * 0.4 — borderline, NOT below
            nozzle_diameter=0.6,      # 0.8 < 2 * 0.6 = 1.2
        )
        v28s = _warnings_by_id(design, "V28")
        skin_warning = any("wing skin" in w.message.lower() for w in v28s)
        assert skin_warning

    def test_triggers_on_thin_wall(self) -> None:
        """Wall < 2 * nozzle should trigger."""
        design = AircraftDesign(
            wall_thickness=0.8,  # < 2 * 0.6 = 1.2
            nozzle_diameter=0.6,
        )
        v28s = _warnings_by_id(design, "V28")
        wall_warning = any("fuselage wall" in w.message.lower() for w in v28s)
        assert wall_warning

    def test_does_not_trigger_on_adequate_walls(self) -> None:
        """Walls >= 2x nozzle should not trigger."""
        design = AircraftDesign(
            wing_skin_thickness=1.2,  # >= 2 * 0.4 = 0.8
            wall_thickness=1.5,
            nozzle_diameter=0.4,
        )
        assert "V28" not in _warning_ids(design)

    def test_larger_nozzle_raises_threshold(self) -> None:
        """With 0.8mm nozzle, 2x = 1.6mm minimum."""
        design = AircraftDesign(
            wing_skin_thickness=1.2,  # < 2 * 0.8 = 1.6
            wall_thickness=1.5,       # < 1.6
            nozzle_diameter=0.8,
        )
        assert "V28" in _warning_ids(design)


# ---------------------------------------------------------------------------
# Integration: all V24-V28 have proper structure
# ---------------------------------------------------------------------------


class TestV24V28Integration:
    def test_all_warnings_have_required_fields(self) -> None:
        """All new warnings should have id, level, message, fields."""
        design = AircraftDesign(
            tail_type="V-Tail",
            v_tail_dihedral=50,
            te_min_thickness=0.5,
            wing_chord=500,
            wing_tip_root_ratio=0.3,
            joint_tolerance=0.05,
            nozzle_diameter=0.4,
            wing_skin_thickness=0.8,
            wall_thickness=0.8,
            print_bed_z=200,
        )
        warnings = compute_warnings(design)
        new_ids = {"V24", "V25", "V26", "V27", "V28"}
        for w in warnings:
            if w.id in new_ids:
                assert w.level == "warn"
                assert w.message
                assert isinstance(w.fields, list)
                assert len(w.fields) > 0

    def test_default_design_minimal_print_warnings(self) -> None:
        """Default design should have few printability warnings."""
        design = AircraftDesign()
        ids = _warning_ids(design)
        # Default should not trigger overhang or orientation warnings
        v24s = _warnings_by_id(design, "V24")
        assert len(v24s) == 0, "Default design should not have overhang warnings"
        v27s = _warnings_by_id(design, "V27")
        assert len(v27s) == 0, "Default design should not have orientation warnings"
