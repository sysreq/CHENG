"""Tests for the geometry engine -- airfoil loader and derived values.

These tests exercise code paths that do NOT require CadQuery,
so they can run in any environment.
"""

from __future__ import annotations

import math

import pytest

from backend.geometry.airfoil import (
    SUPPORTED_AIRFOILS,
    generate_flat_plate,
    load_airfoil,
)
from backend.geometry.engine import compute_derived_values
from backend.models import AircraftDesign


# ===================================================================
# Airfoil loader tests
# ===================================================================


class TestLoadAirfoil:
    """Tests for load_airfoil()."""

    @pytest.mark.parametrize("name", SUPPORTED_AIRFOILS)
    def test_load_all_supported_airfoils(self, name: str) -> None:
        """Every supported airfoil should load successfully."""
        points = load_airfoil(name)
        assert len(points) >= 10, f"{name} has only {len(points)} points"

    @pytest.mark.parametrize("name", SUPPORTED_AIRFOILS)
    def test_unit_chord_normalisation(self, name: str) -> None:
        """All loaded airfoils should have x values in [0, 1]."""
        points = load_airfoil(name)
        xs = [p[0] for p in points]
        assert min(xs) >= -0.01, f"{name}: min x = {min(xs)}"
        assert max(xs) <= 1.01, f"{name}: max x = {max(xs)}"

    def test_clark_y_is_cambered(self) -> None:
        """Clark-Y is a cambered airfoil -- should have positive y values."""
        points = load_airfoil("Clark-Y")
        max_y = max(p[1] for p in points)
        assert max_y > 0.05, f"Clark-Y max y = {max_y}, expected > 0.05"

    def test_naca0012_is_symmetric(self) -> None:
        """NACA-0012 should have symmetric upper and lower surfaces."""
        points = load_airfoil("NACA-0012")
        max_y = max(p[1] for p in points)
        min_y = min(p[1] for p in points)
        # Should be roughly symmetric about y=0
        assert abs(max_y + min_y) < 0.01, (
            f"NACA-0012 asymmetry: max_y={max_y:.4f}, min_y={min_y:.4f}"
        )

    def test_unsupported_airfoil_raises(self) -> None:
        """Requesting an unsupported airfoil should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported airfoil"):
            load_airfoil("Nonexistent-Foil")

    def test_minimum_points(self) -> None:
        """All airfoils must have at least 10 points."""
        for name in SUPPORTED_AIRFOILS:
            points = load_airfoil(name)
            assert len(points) >= 10

    def test_airfoil_points_are_tuples(self) -> None:
        """Each point should be a 2-tuple of floats."""
        points = load_airfoil("Clark-Y")
        for pt in points:
            assert isinstance(pt, tuple)
            assert len(pt) == 2
            assert isinstance(pt[0], float)
            assert isinstance(pt[1], float)


class TestGenerateFlatPlate:
    """Tests for generate_flat_plate()."""

    def test_default_generation(self) -> None:
        """Default flat plate should produce a valid profile."""
        points = generate_flat_plate()
        assert len(points) >= 10

    def test_3_percent_thickness(self) -> None:
        """Max thickness should be approximately 3% of chord."""
        points = generate_flat_plate(num_points=100)
        max_y = max(abs(p[1]) for p in points)
        assert abs(max_y - 0.03) < 0.005, f"Max thickness = {max_y}, expected ~0.03"

    def test_symmetric(self) -> None:
        """Profile should be vertically symmetric."""
        points = generate_flat_plate(num_points=100)
        max_y = max(p[1] for p in points)
        min_y = min(p[1] for p in points)
        assert abs(max_y + min_y) < 0.001

    def test_min_points_validation(self) -> None:
        """Should raise if fewer than 10 points requested."""
        with pytest.raises(ValueError, match="num_points must be >= 10"):
            generate_flat_plate(num_points=5)

    def test_unit_chord(self) -> None:
        """Points should span x in [0, 1]."""
        points = generate_flat_plate()
        xs = [p[0] for p in points]
        assert min(xs) >= 0.0
        assert max(xs) <= 1.0


# ===================================================================
# Derived values tests
# ===================================================================


class TestComputeDerivedValues:
    """Tests for compute_derived_values()."""

    def test_default_design(self, default_design: AircraftDesign) -> None:
        """Derived values should compute for default parameters."""
        result = compute_derived_values(default_design)
        assert isinstance(result, dict)
        assert len(result) == 12

    def test_all_keys_present(self, default_design: AircraftDesign) -> None:
        """All 12 derived value keys must be present."""
        result = compute_derived_values(default_design)
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
        assert set(result.keys()) == expected_keys

    def test_all_values_are_floats(self, default_design: AircraftDesign) -> None:
        """All derived values should be numeric (float)."""
        result = compute_derived_values(default_design)
        for key, val in result.items():
            assert isinstance(val, (int, float)), f"{key} is {type(val)}"

    def test_wing_tip_chord_rectangular(self) -> None:
        """With taper_ratio=1.0, tip chord == root chord."""
        design = AircraftDesign(wing_chord=200, wing_tip_root_ratio=1.0)
        result = compute_derived_values(design)
        assert result["tip_chord_mm"] == pytest.approx(200.0)

    def test_wing_tip_chord_tapered(self) -> None:
        """Tip chord should be chord * taper ratio."""
        design = AircraftDesign(wing_chord=180, wing_tip_root_ratio=0.67)
        result = compute_derived_values(design)
        assert result["tip_chord_mm"] == pytest.approx(180 * 0.67, rel=1e-4)

    def test_wing_area_rectangular(self) -> None:
        """Rectangular wing: area = span * chord / 100 (mm^2 -> cm^2)."""
        design = AircraftDesign(wing_span=1000, wing_chord=200, wing_tip_root_ratio=1.0)
        result = compute_derived_values(design)
        expected = (1000 * 200) / 100.0  # = 2000 cm^2
        assert result["wing_area_cm2"] == pytest.approx(expected)

    def test_wing_area_tapered(self) -> None:
        """Tapered wing area: 0.5 * (root + tip) * span / 100."""
        design = AircraftDesign(wing_span=1000, wing_chord=200, wing_tip_root_ratio=0.5)
        result = compute_derived_values(design)
        tip_chord = 200 * 0.5
        expected = 0.5 * (200 + tip_chord) * 1000 / 100.0
        assert result["wing_area_cm2"] == pytest.approx(expected)

    def test_aspect_ratio_rectangular(self) -> None:
        """AR = span^2 / area_mm^2 for rectangular wing."""
        design = AircraftDesign(wing_span=1000, wing_chord=200, wing_tip_root_ratio=1.0)
        result = compute_derived_values(design)
        area_mm2 = 1000 * 200
        expected_ar = (1000 ** 2) / area_mm2
        assert result["aspect_ratio"] == pytest.approx(expected_ar)

    def test_mac_rectangular(self) -> None:
        """For rectangular wing (lambda=1), MAC = chord."""
        design = AircraftDesign(wing_chord=200, wing_tip_root_ratio=1.0)
        result = compute_derived_values(design)
        # (2/3)*200*(1+1+1)/(1+1) = (2/3)*200*3/2 = 200
        assert result["mean_aero_chord_mm"] == pytest.approx(200.0)

    def test_mac_tapered(self) -> None:
        """MAC formula for tapered wing."""
        design = AircraftDesign(wing_chord=180, wing_tip_root_ratio=0.5)
        result = compute_derived_values(design)
        l = 0.5
        expected = (2.0 / 3.0) * 180 * (1 + l + l**2) / (1 + l)
        assert result["mean_aero_chord_mm"] == pytest.approx(expected)

    def test_taper_ratio(self) -> None:
        """Taper ratio should equal wing_tip_root_ratio in MVP."""
        design = AircraftDesign(wing_tip_root_ratio=0.67)
        result = compute_derived_values(design)
        assert result["taper_ratio"] == pytest.approx(0.67)

    def test_estimated_cg(self) -> None:
        """CG estimate = 0.25 * MAC."""
        design = AircraftDesign(wing_chord=200, wing_tip_root_ratio=1.0)
        result = compute_derived_values(design)
        expected_cg = 0.25 * 200.0  # MAC = 200 for rectangular
        assert result["estimated_cg_mm"] == pytest.approx(expected_cg)

    def test_min_feature_thickness(self) -> None:
        """Min feature = 2 * nozzle_diameter."""
        design = AircraftDesign(nozzle_diameter=0.4)
        result = compute_derived_values(design)
        assert result["min_feature_thickness_mm"] == pytest.approx(0.8)

    def test_wall_thickness_conventional(self) -> None:
        """Wall thickness reflects design.wall_thickness (F14)."""
        design = AircraftDesign(fuselage_preset="Conventional", wall_thickness=1.6)
        result = compute_derived_values(design)
        assert result["wall_thickness_mm"] == pytest.approx(1.6)

    def test_wall_thickness_pod(self) -> None:
        """Wall thickness reflects design.wall_thickness (F14)."""
        design = AircraftDesign(fuselage_preset="Pod", wall_thickness=2.0)
        result = compute_derived_values(design)
        assert result["wall_thickness_mm"] == pytest.approx(2.0)

    def test_wall_thickness_bwb(self, bwb_design: AircraftDesign) -> None:
        """BWB wall thickness should use design.wall_thickness (F14)."""
        result = compute_derived_values(bwb_design)
        assert result["wall_thickness_mm"] == pytest.approx(bwb_design.wall_thickness)

    def test_positive_values(self, trainer_design: AircraftDesign) -> None:
        """All derived values should be positive for a valid design."""
        result = compute_derived_values(trainer_design)
        for key, val in result.items():
            assert val > 0, f"{key} = {val}, expected > 0"

    def test_sport_preset(self, sport_design: AircraftDesign) -> None:
        """Sport preset should produce reasonable derived values."""
        result = compute_derived_values(sport_design)
        # AR for 1000mm span, 180mm chord, 0.67 taper should be around 6-8
        assert 4.0 < result["aspect_ratio"] < 12.0
        # Tip chord should be ~120mm
        assert result["tip_chord_mm"] == pytest.approx(180 * 0.67, rel=0.01)

    def test_aerobatic_preset(self, aerobatic_design: AircraftDesign) -> None:
        """Aerobatic preset should produce reasonable derived values."""
        result = compute_derived_values(aerobatic_design)
        # 900mm span, 200mm chord, 0.8 taper
        assert 3.0 < result["aspect_ratio"] < 10.0
        assert result["tip_chord_mm"] == pytest.approx(200 * 0.8)


# ===================================================================
# Validation warnings tests
# ===================================================================


class TestComputeWarnings:
    """Tests for validation warnings via backend.validation.compute_warnings()."""

    def test_no_warnings_for_default(self, default_design: AircraftDesign) -> None:
        """Default design should produce few or no warnings."""
        from backend.validation import compute_warnings

        warnings = compute_warnings(default_design)
        assert isinstance(warnings, list)

    def test_v01_wingspan_vs_fuselage(self) -> None:
        """V01: wingspan > 10 * fuselageLength."""
        from backend.validation import compute_warnings

        design = AircraftDesign(wing_span=2000, fuselage_length=150)
        warnings = compute_warnings(design)
        warning_ids = [w.id for w in warnings]
        assert "V01" in warning_ids

    def test_v02_aggressive_taper(self) -> None:
        """V02: tipRootRatio < 0.3 -- model min is 0.3 so boundary is exact."""
        from backend.validation import compute_warnings

        # Model min is 0.3 so 0.3 should NOT trigger (not strictly less)
        design = AircraftDesign(wing_tip_root_ratio=0.3)
        warnings = compute_warnings(design)
        warning_ids = [w.id for w in warnings]
        assert "V02" not in warning_ids

    def test_v03_short_fuselage(self) -> None:
        """V03: fuselageLength < wingChord."""
        from backend.validation import compute_warnings

        design = AircraftDesign(fuselage_length=150, wing_chord=200)
        warnings = compute_warnings(design)
        warning_ids = [w.id for w in warnings]
        assert "V03" in warning_ids

    def test_v04_short_tail_arm(self) -> None:
        """V04: tailArm < 2 * MAC."""
        from backend.validation import compute_warnings

        design = AircraftDesign(tail_arm=80, wing_chord=200)
        warnings = compute_warnings(design)
        warning_ids = [w.id for w in warnings]
        assert "V04" in warning_ids

    def test_v05_small_tip_chord(self) -> None:
        """V05: wingChord * tipRootRatio < 30."""
        from backend.validation import compute_warnings

        design = AircraftDesign(wing_chord=80, wing_tip_root_ratio=0.3)
        warnings = compute_warnings(design)
        warning_ids = [w.id for w in warnings]
        assert "V05" in warning_ids

    def test_v06_tail_past_fuselage(self) -> None:
        """V06: tailArm > fuselageLength."""
        from backend.validation import compute_warnings

        design = AircraftDesign(tail_arm=500, fuselage_length=400)
        warnings = compute_warnings(design)
        warning_ids = [w.id for w in warnings]
        assert "V06" in warning_ids

    def test_v16_wall_too_thin(self) -> None:
        """V16: skinThickness < 2 * nozzleDiameter."""
        from backend.validation import compute_warnings

        # skin=0.8 (model min), nozzle=0.6 -> 0.8 < 1.2 triggers V16
        design = AircraftDesign(wing_skin_thickness=0.8, nozzle_diameter=0.6)
        warnings = compute_warnings(design)
        warning_ids = [w.id for w in warnings]
        assert "V16" in warning_ids

    def test_v17_wall_not_clean_multiple(self) -> None:
        """V17: skinThickness % nozzleDiameter > 0.01."""
        from backend.validation import compute_warnings

        design = AircraftDesign(wing_skin_thickness=1.3, nozzle_diameter=0.4)
        warnings = compute_warnings(design)
        warning_ids = [w.id for w in warnings]
        assert "V17" in warning_ids

    def test_v22_loose_tolerance(self) -> None:
        """V22: jointTolerance > 0.3."""
        from backend.validation import compute_warnings

        design = AircraftDesign(joint_tolerance=0.4)
        warnings = compute_warnings(design)
        warning_ids = [w.id for w in warnings]
        assert "V22" in warning_ids

    def test_v23_tight_tolerance(self) -> None:
        """V23: jointTolerance < 0.05 -- but model min is 0.05, so edge case."""
        from backend.validation import compute_warnings

        # joint_tolerance min is 0.05 in model, so 0.05 should NOT trigger
        design = AircraftDesign(joint_tolerance=0.05)
        warnings = compute_warnings(design)
        warning_ids = [w.id for w in warnings]
        assert "V23" not in warning_ids

    def test_warning_structure(self) -> None:
        """Warnings should have proper structure."""
        from backend.validation import compute_warnings

        # Use a design that triggers at least one warning (V05: tip chord < 30)
        design = AircraftDesign(wing_chord=80, wing_tip_root_ratio=0.3)
        warnings = compute_warnings(design)

        for w in warnings:
            assert hasattr(w, "id")
            assert hasattr(w, "level")
            assert hasattr(w, "message")
            assert hasattr(w, "fields")
            assert w.level == "warn"
            assert isinstance(w.message, str)
            assert isinstance(w.fields, list)
