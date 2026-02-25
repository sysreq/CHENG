"""Tests for derived values accuracy across all 3 presets.

Verifies compute_derived_values() matches the spec expectations from
docs/mvp_spec.md and implementation_guide.md.

Expected values:
  Trainer:   tipChord=200, wingArea=2400cm2, AR=6.0, MAC=200
  Sport:     tipChord=120.6, wingArea=1503cm2, AR=6.655, MAC~153.2
  Aerobatic: tipChord=220, wingArea=1980cm2, AR=4.09, MAC=220

Also tests:
  - PR08: minFeatureThickness = 2 * nozzleDiameter
  - Edge case: wingTipRootRatio=0.3 (minimum taper)
"""

import math
import pytest

from backend.geometry.engine import compute_derived_values
from backend.models import AircraftDesign


# ---------------------------------------------------------------------------
# Preset factory helpers (mirrors frontend presets.ts)
# ---------------------------------------------------------------------------

def _trainer() -> AircraftDesign:
    return AircraftDesign(
        wing_span=1200,
        wing_chord=200,
        wing_tip_root_ratio=1.0,
        wing_sweep=0,
        wing_mount_type="High-Wing",
        fuselage_length=400,
        fuselage_preset="Conventional",
        engine_count=1,
        motor_config="Tractor",
        tail_type="Conventional",
        wing_airfoil="Clark-Y",
        wing_dihedral=3,
        wing_skin_thickness=1.2,
        h_stab_span=400,
        h_stab_chord=120,
        h_stab_incidence=-1,
        v_stab_height=120,
        v_stab_root_chord=130,
        tail_arm=220,
        nozzle_diameter=0.4,
    )


def _sport() -> AircraftDesign:
    return AircraftDesign(
        wing_span=1000,
        wing_chord=180,
        wing_tip_root_ratio=0.67,
        wing_sweep=5,
        wing_mount_type="Mid-Wing",
        fuselage_length=300,
        fuselage_preset="Conventional",
        engine_count=1,
        motor_config="Tractor",
        tail_type="Conventional",
        wing_airfoil="NACA-2412",
        wing_dihedral=3,
        wing_skin_thickness=1.2,
        h_stab_span=350,
        h_stab_chord=100,
        h_stab_incidence=-1,
        v_stab_height=100,
        v_stab_root_chord=110,
        tail_arm=180,
        nozzle_diameter=0.4,
    )


def _aerobatic() -> AircraftDesign:
    return AircraftDesign(
        wing_span=900,
        wing_chord=220,
        wing_tip_root_ratio=1.0,
        wing_sweep=0,
        wing_mount_type="Mid-Wing",
        fuselage_length=280,
        fuselage_preset="Conventional",
        engine_count=1,
        motor_config="Tractor",
        tail_type="Conventional",
        wing_airfoil="NACA-0012",
        wing_dihedral=0,
        wing_skin_thickness=1.2,
        h_stab_span=350,
        h_stab_chord=110,
        h_stab_incidence=0,
        v_stab_height=120,
        v_stab_root_chord=120,
        tail_arm=170,
        nozzle_diameter=0.4,
    )


# ---------------------------------------------------------------------------
# Trainer Preset Tests
# ---------------------------------------------------------------------------

class TestTrainerDerived:
    """Trainer: span=1200, chord=200, taper=1.0, sweep=0."""

    def setup_method(self):
        self.d = compute_derived_values(_trainer())

    def test_tip_chord(self):
        assert self.d["tip_chord_mm"] == pytest.approx(200.0)

    def test_wing_area(self):
        # area = 0.5 * (200 + 200) * 1200 / 100 = 2400 cm2
        assert self.d["wing_area_cm2"] == pytest.approx(2400.0)

    def test_aspect_ratio(self):
        # AR = 1200^2 / (0.5*(200+200)*1200) = 1440000 / 240000 = 6.0
        assert self.d["aspect_ratio"] == pytest.approx(6.0)

    def test_mac(self):
        # Rectangular wing (taper=1): MAC = chord = 200
        assert self.d["mean_aero_chord_mm"] == pytest.approx(200.0)

    def test_taper_ratio(self):
        assert self.d["taper_ratio"] == pytest.approx(1.0)

    def test_cg_no_sweep(self):
        # v0.6: CG is now a weighted average of component positions (not just 25% MAC).
        # For a trainer (sweep=0, tractor motor, default battery at 30% fuselage),
        # CG should be forward of 25% MAC due to motor/battery at nose.
        cg = self.d["estimated_cg_mm"]
        mac = self.d["mean_aero_chord_mm"]
        # CG should be within 0-100% MAC for a balanced design
        assert 0 < cg < mac


# ---------------------------------------------------------------------------
# Sport Preset Tests
# ---------------------------------------------------------------------------

class TestSportDerived:
    """Sport: span=1000, chord=180, taper=0.67, sweep=5deg."""

    def setup_method(self):
        self.d = compute_derived_values(_sport())

    def test_tip_chord(self):
        # 180 * 0.67 = 120.6
        assert self.d["tip_chord_mm"] == pytest.approx(120.6)

    def test_wing_area(self):
        # area = 0.5 * (180 + 120.6) * 1000 / 100 = 1503 cm2
        assert self.d["wing_area_cm2"] == pytest.approx(1503.0)

    def test_aspect_ratio(self):
        # AR = 1000^2 / (0.5*(180+120.6)*1000) = 1e6 / 150300 ≈ 6.6534
        expected = 1000**2 / (0.5 * (180 + 120.6) * 1000)
        assert self.d["aspect_ratio"] == pytest.approx(expected, rel=1e-3)

    def test_mac(self):
        # MAC = (2/3) * 180 * (1 + 0.67 + 0.67^2) / (1 + 0.67)
        lam = 0.67
        expected = (2/3) * 180 * (1 + lam + lam**2) / (1 + lam)
        assert self.d["mean_aero_chord_mm"] == pytest.approx(expected, rel=1e-3)

    def test_taper_ratio(self):
        assert self.d["taper_ratio"] == pytest.approx(0.67)

    def test_cg_with_sweep(self):
        # v0.6: CG is a weighted average including motor/battery positions.
        # With sweep=5°, CG should be aft of the zero-sweep case.
        cg = self.d["estimated_cg_mm"]
        mac = self.d["mean_aero_chord_mm"]
        # CG should be within 0-100% MAC for a balanced design
        assert 0 < cg < mac


# ---------------------------------------------------------------------------
# Aerobatic Preset Tests
# ---------------------------------------------------------------------------

class TestAerobaticDerived:
    """Aerobatic: span=900, chord=220, taper=1.0, sweep=0."""

    def setup_method(self):
        self.d = compute_derived_values(_aerobatic())

    def test_tip_chord(self):
        assert self.d["tip_chord_mm"] == pytest.approx(220.0)

    def test_wing_area(self):
        # area = 0.5 * (220 + 220) * 900 / 100 = 1980 cm2
        assert self.d["wing_area_cm2"] == pytest.approx(1980.0)

    def test_aspect_ratio(self):
        # AR = 900^2 / (0.5*(220+220)*900) = 810000/198000 ≈ 4.0909
        expected = 900**2 / (0.5 * (220 + 220) * 900)
        assert self.d["aspect_ratio"] == pytest.approx(expected, rel=1e-3)

    def test_mac(self):
        # Rectangular wing: MAC = 220
        assert self.d["mean_aero_chord_mm"] == pytest.approx(220.0)


# ---------------------------------------------------------------------------
# Cross-cutting Tests
# ---------------------------------------------------------------------------

class TestDerivedEdgeCases:
    """Edge cases and cross-cutting derived value tests."""

    def test_min_feature_thickness_pr08(self):
        """PR08: minFeatureThickness = 2 * nozzleDiameter."""
        design = _trainer()
        design.nozzle_diameter = 0.4
        d = compute_derived_values(design)
        assert d["min_feature_thickness_mm"] == pytest.approx(0.8)

    def test_min_feature_thickness_large_nozzle(self):
        design = _trainer()
        design.nozzle_diameter = 0.8
        d = compute_derived_values(design)
        assert d["min_feature_thickness_mm"] == pytest.approx(1.6)

    def test_tip_root_ratio_030(self):
        """Edge case: aggressive taper ratio=0.3."""
        design = _trainer()
        design.wing_tip_root_ratio = 0.3
        d = compute_derived_values(design)

        # tip_chord = 200 * 0.3 = 60mm
        assert d["tip_chord_mm"] == pytest.approx(60.0)

        # area = 0.5 * (200 + 60) * 1200 / 100 = 1560 cm2
        assert d["wing_area_cm2"] == pytest.approx(1560.0)

        # taper_ratio = 0.3
        assert d["taper_ratio"] == pytest.approx(0.3)

        # MAC = (2/3) * 200 * (1 + 0.3 + 0.09) / (1 + 0.3)
        lam = 0.3
        expected_mac = (2/3) * 200 * (1 + lam + lam**2) / (1 + lam)
        assert d["mean_aero_chord_mm"] == pytest.approx(expected_mac, rel=1e-3)

    def test_wall_thickness_returns_skin_thickness(self):
        """wall_thickness_mm should equal wing_skin_thickness."""
        design = _trainer()
        design.wing_skin_thickness = 1.5
        d = compute_derived_values(design)
        assert d["wall_thickness_mm"] == pytest.approx(1.5)

    def test_all_derived_keys_present(self):
        """All 12 derived keys should be in the result."""
        d = compute_derived_values(_trainer())
        expected_keys = {
            "tip_chord_mm",
            "wing_area_cm2",
            "aspect_ratio",
            "mean_aero_chord_mm",
            "taper_ratio",
            "estimated_cg_mm",
            "min_feature_thickness_mm",
            "wall_thickness_mm",
            "weight_wing_g",
            "weight_tail_g",
            "weight_fuselage_g",
            "weight_total_g",
        }
        assert set(d.keys()) == expected_keys
