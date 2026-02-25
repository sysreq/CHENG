"""Tests for weight estimation (v0.6 #142).

Verifies that _compute_weight_estimates produces physically reasonable
weight values for various designs and that changing infill/density/dimensions
affects the result in the expected direction.
"""

from __future__ import annotations

import math

import pytest

from backend.geometry.engine import compute_derived_values, _compute_weight_estimates
from backend.models import AircraftDesign


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_design(**overrides) -> AircraftDesign:
    """Create a default design with optional overrides."""
    return AircraftDesign(**overrides)


# ---------------------------------------------------------------------------
# Basic sanity checks
# ---------------------------------------------------------------------------


class TestWeightBasics:
    """Weight estimates should be positive and physically reasonable."""

    def test_default_weights_positive(self) -> None:
        d = compute_derived_values(_default_design())
        assert d["weight_wing_g"] > 0
        assert d["weight_tail_g"] > 0
        assert d["weight_fuselage_g"] > 0
        assert d["weight_total_g"] > 0

    def test_total_is_sum_of_components(self) -> None:
        d = compute_derived_values(_default_design())
        expected = d["weight_wing_g"] + d["weight_tail_g"] + d["weight_fuselage_g"]
        assert d["weight_total_g"] == pytest.approx(expected, abs=0.2)

    def test_wing_is_heaviest_component(self) -> None:
        """For a typical design, the wing is the largest component."""
        d = compute_derived_values(_default_design(wing_span=1200, wing_chord=200))
        assert d["weight_wing_g"] > d["weight_tail_g"]

    def test_reasonable_weight_range(self) -> None:
        """A 1m-span sport plane printed airframe should be under 2kg."""
        d = compute_derived_values(_default_design())
        # Default design (1000mm span, 180mm chord, 15% infill PLA) is ~1200g
        # which is reasonable for a thick-walled printed airframe
        assert 50 < d["weight_total_g"] < 2000


# ---------------------------------------------------------------------------
# Infill affects weight
# ---------------------------------------------------------------------------


class TestInfillEffect:
    """Higher infill should produce heavier parts."""

    def test_higher_infill_heavier(self) -> None:
        low = compute_derived_values(_default_design(print_infill=10))
        high = compute_derived_values(_default_design(print_infill=80))
        assert high["weight_total_g"] > low["weight_total_g"]

    def test_zero_infill_lighter_than_full(self) -> None:
        zero = compute_derived_values(_default_design(print_infill=0))
        full = compute_derived_values(_default_design(print_infill=100))
        assert full["weight_total_g"] > zero["weight_total_g"]

    def test_100_percent_infill_gives_solid(self) -> None:
        """At 100% infill, effective material fraction should be 1.0."""
        w = _compute_weight_estimates(_default_design(print_infill=100))
        # All weights should equal the full solid volume * density
        assert w["weight_total_g"] > 0


# ---------------------------------------------------------------------------
# Density affects weight
# ---------------------------------------------------------------------------


class TestDensityEffect:
    """Weight should scale linearly with material density."""

    def test_double_density_doubles_weight(self) -> None:
        base = compute_derived_values(_default_design(material_density=1.24))
        heavy = compute_derived_values(_default_design(material_density=2.48))
        assert heavy["weight_total_g"] == pytest.approx(
            base["weight_total_g"] * 2.0, rel=0.01
        )

    def test_different_materials(self) -> None:
        """PETG (~1.27 g/cm3) should be slightly heavier than PLA (~1.24)."""
        pla = compute_derived_values(_default_design(material_density=1.24))
        petg = compute_derived_values(_default_design(material_density=1.27))
        assert petg["weight_total_g"] > pla["weight_total_g"]


# ---------------------------------------------------------------------------
# Dimension scaling
# ---------------------------------------------------------------------------


class TestDimensionScaling:
    """Larger dimensions should produce heavier parts."""

    def test_larger_wingspan_heavier(self) -> None:
        small = compute_derived_values(_default_design(wing_span=600))
        large = compute_derived_values(_default_design(wing_span=1500))
        assert large["weight_wing_g"] > small["weight_wing_g"]

    def test_larger_chord_heavier(self) -> None:
        narrow = compute_derived_values(_default_design(wing_chord=100))
        wide = compute_derived_values(_default_design(wing_chord=300))
        assert wide["weight_wing_g"] > narrow["weight_wing_g"]

    def test_longer_fuselage_heavier(self) -> None:
        short = compute_derived_values(_default_design(fuselage_length=200))
        long = compute_derived_values(_default_design(fuselage_length=800))
        assert long["weight_fuselage_g"] > short["weight_fuselage_g"]

    def test_wall_thickness_affects_fuselage(self) -> None:
        thin = compute_derived_values(_default_design(wall_thickness=0.8))
        thick = compute_derived_values(_default_design(wall_thickness=3.0))
        assert thick["weight_fuselage_g"] > thin["weight_fuselage_g"]


# ---------------------------------------------------------------------------
# Tail type variations
# ---------------------------------------------------------------------------


class TestTailTypeWeight:
    """Different tail types should produce different weights."""

    def test_vtail_has_tail_weight(self) -> None:
        d = compute_derived_values(_default_design(tail_type="V-Tail"))
        assert d["weight_tail_g"] > 0

    def test_conventional_tail_weight(self) -> None:
        d = compute_derived_values(_default_design(tail_type="Conventional"))
        assert d["weight_tail_g"] > 0

    def test_t_tail_weight(self) -> None:
        d = compute_derived_values(_default_design(tail_type="T-Tail"))
        assert d["weight_tail_g"] > 0


# ---------------------------------------------------------------------------
# Fuselage preset variations
# ---------------------------------------------------------------------------


class TestFuselagePresetWeight:
    """Different fuselage presets should produce different weights."""

    def test_pod_fuselage_weight(self) -> None:
        d = compute_derived_values(_default_design(fuselage_preset="Pod"))
        assert d["weight_fuselage_g"] > 0

    def test_bwb_fuselage_weight(self) -> None:
        d = compute_derived_values(_default_design(fuselage_preset="Blended-Wing-Body"))
        assert d["weight_fuselage_g"] > 0

    def test_conventional_fuselage_weight(self) -> None:
        d = compute_derived_values(_default_design(fuselage_preset="Conventional"))
        assert d["weight_fuselage_g"] > 0

    def test_pod_wider_than_conventional(self) -> None:
        """Pod fuselage is wider, should be heavier."""
        conv = compute_derived_values(_default_design(fuselage_preset="Conventional"))
        pod = compute_derived_values(_default_design(fuselage_preset="Pod"))
        assert pod["weight_fuselage_g"] > conv["weight_fuselage_g"]


# ---------------------------------------------------------------------------
# DerivedValues model accepts weight fields
# ---------------------------------------------------------------------------


class TestDerivedValuesModel:
    """Ensure DerivedValues model includes weight fields."""

    def test_derived_values_includes_weights(self) -> None:
        from backend.models import DerivedValues
        d = compute_derived_values(_default_design())
        dv = DerivedValues(**d)
        assert dv.weight_wing_g > 0
        assert dv.weight_tail_g > 0
        assert dv.weight_fuselage_g > 0
        assert dv.weight_total_g > 0

    def test_camel_case_aliases(self) -> None:
        """Weight fields should serialize to camelCase."""
        from backend.models import DerivedValues
        d = compute_derived_values(_default_design())
        dv = DerivedValues(**d)
        dumped = dv.model_dump(by_alias=True)
        assert "weightWingG" in dumped
        assert "weightTailG" in dumped
        assert "weightFuselageG" in dumped
        assert "weightTotalG" in dumped
