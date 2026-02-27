"""Tests for backend/mass_properties.py.

Covers:
- resolve_mass_properties() with all overrides set
- resolve_mass_properties() with no overrides (estimates)
- ixx_estimated / iyy_estimated / izz_estimated flags
- estimate_inertia() physical ordering (Ixx < Iyy) for all 6 presets
- Partial overrides
- SI unit correctness
"""

from __future__ import annotations

import pytest

from backend.models import AircraftDesign
from backend.mass_properties import MassProperties, estimate_inertia, resolve_mass_properties


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trainer() -> AircraftDesign:
    """Trainer-like design (1200 mm span, conventional)."""
    return AircraftDesign(
        wing_span=1200,
        wing_chord=200,
        fuselage_length=400,
        fuselage_preset="Conventional",
        tail_arm=220,
        motor_weight_g=120.0,
        battery_weight_g=200.0,
    )


def _derived(design: AircraftDesign | None = None) -> dict:
    """Compute derived values dict for a design."""
    from backend.geometry.engine import compute_derived_values
    if design is None:
        design = _trainer()
    return compute_derived_values(design)


def _make_design(preset: str) -> AircraftDesign:
    """Create a minimal design for each preset name."""
    if preset == "Trainer":
        return AircraftDesign(
            wing_span=1200, wing_chord=200, fuselage_length=400,
            fuselage_preset="Conventional", tail_arm=220,
            motor_weight_g=120.0, battery_weight_g=200.0,
        )
    elif preset == "Sport":
        return AircraftDesign(
            wing_span=1000, wing_chord=180, fuselage_length=300,
            fuselage_preset="Conventional", tail_arm=180,
            motor_weight_g=100.0, battery_weight_g=180.0,
        )
    elif preset == "Aerobatic":
        return AircraftDesign(
            wing_span=900, wing_chord=200, fuselage_length=280,
            fuselage_preset="Conventional", tail_arm=160,
            motor_weight_g=90.0, battery_weight_g=150.0,
        )
    elif preset == "Glider":
        return AircraftDesign(
            wing_span=2000, wing_chord=150, fuselage_length=600,
            fuselage_preset="Conventional", tail_arm=350,
            motor_weight_g=80.0, battery_weight_g=100.0,
        )
    elif preset == "FlyingWing":
        return AircraftDesign(
            wing_span=800, wing_chord=250, fuselage_length=300,
            fuselage_preset="Blended-Wing-Body", tail_arm=150,
            motor_weight_g=100.0, battery_weight_g=160.0,
        )
    elif preset == "Scale":
        return AircraftDesign(
            wing_span=1500, wing_chord=220, fuselage_length=500,
            fuselage_preset="Conventional", tail_arm=280,
            motor_weight_g=150.0, battery_weight_g=250.0,
        )
    else:
        raise ValueError(f"Unknown preset: {preset}")


# ---------------------------------------------------------------------------
# resolve_mass_properties — with all overrides set
# ---------------------------------------------------------------------------


class TestResolveMassPropertiesWithOverrides:
    """All MP01-MP07 overrides active — resolver returns exact override values."""

    def setup_method(self) -> None:
        self.design = _trainer()
        self.design.mass_total_override_g = 850.0
        self.design.cg_override_x_mm = 120.0
        self.design.cg_override_z_mm = 5.0
        self.design.cg_override_y_mm = -2.0
        self.design.ixx_override_kg_m2 = 0.012
        self.design.iyy_override_kg_m2 = 0.045
        self.design.izz_override_kg_m2 = 0.055
        self.derived = _derived(self.design)
        self.mp = resolve_mass_properties(self.design, self.derived)

    def test_mass_uses_override(self) -> None:
        assert self.mp.mass_g == pytest.approx(850.0)

    def test_cg_x_uses_override(self) -> None:
        assert self.mp.cg_x_mm == pytest.approx(120.0)

    def test_cg_z_uses_override(self) -> None:
        assert self.mp.cg_z_mm == pytest.approx(5.0)

    def test_cg_y_uses_override(self) -> None:
        assert self.mp.cg_y_mm == pytest.approx(-2.0)

    def test_ixx_uses_override(self) -> None:
        assert self.mp.ixx_kg_m2 == pytest.approx(0.012)

    def test_iyy_uses_override(self) -> None:
        assert self.mp.iyy_kg_m2 == pytest.approx(0.045)

    def test_izz_uses_override(self) -> None:
        assert self.mp.izz_kg_m2 == pytest.approx(0.055)

    def test_ixx_estimated_false(self) -> None:
        assert self.mp.ixx_estimated is False

    def test_iyy_estimated_false(self) -> None:
        assert self.mp.iyy_estimated is False

    def test_izz_estimated_false(self) -> None:
        assert self.mp.izz_estimated is False


# ---------------------------------------------------------------------------
# resolve_mass_properties — with no overrides (all estimated)
# ---------------------------------------------------------------------------


class TestResolveMassPropertiesNoOverrides:
    """No overrides — resolver returns estimated values."""

    def setup_method(self) -> None:
        self.design = _trainer()
        self.derived = _derived(self.design)
        self.mp = resolve_mass_properties(self.design, self.derived)

    def test_returns_mass_properties_instance(self) -> None:
        assert isinstance(self.mp, MassProperties)

    def test_mass_g_positive(self) -> None:
        """Total mass must be positive (airframe + motor + battery)."""
        assert self.mp.mass_g > 0.0

    def test_mass_includes_motor_and_battery(self) -> None:
        """Estimated mass must be at least motor + battery weight."""
        min_mass = self.design.motor_weight_g + self.design.battery_weight_g
        assert self.mp.mass_g >= min_mass

    def test_cg_x_mm_positive(self) -> None:
        """Nose-referenced CG must be positive (forward of nose = impossible)."""
        assert self.mp.cg_x_mm > 0.0

    def test_ixx_estimated_true(self) -> None:
        assert self.mp.ixx_estimated is True

    def test_iyy_estimated_true(self) -> None:
        assert self.mp.iyy_estimated is True

    def test_izz_estimated_true(self) -> None:
        assert self.mp.izz_estimated is True

    def test_ixx_is_si_units_range(self) -> None:
        """Ixx for a ~1.2m wingspan model should be in 0.001 – 1.0 kg·m² range."""
        assert 0.001 <= self.mp.ixx_kg_m2 <= 1.0, (
            f"Ixx = {self.mp.ixx_kg_m2} kg·m² out of expected range for model aircraft"
        )

    def test_iyy_is_si_units_range(self) -> None:
        """Iyy for a ~400mm fuselage model should be in 0.001 – 5.0 kg·m² range."""
        assert 0.001 <= self.mp.iyy_kg_m2 <= 5.0, (
            f"Iyy = {self.mp.iyy_kg_m2} kg·m² out of expected range"
        )


# ---------------------------------------------------------------------------
# estimate_inertia — physical ordering for all 6 presets
# ---------------------------------------------------------------------------


class TestEstimateInertiaPhysicalOrdering:
    """estimate_inertia() must satisfy Ixx < Iyy for all presets.

    RC models have wide wingspans relative to fuselage length, so the
    dominant inertia axis is pitch (Iyy) not roll (Ixx).
    """

    @pytest.mark.parametrize("preset", ["Trainer", "Sport", "Aerobatic", "Glider", "FlyingWing", "Scale"])
    def test_ixx_less_than_iyy(self, preset: str) -> None:
        """Ixx < Iyy for all presets."""
        design = _make_design(preset)
        from backend.geometry.engine import compute_derived_values
        derived = compute_derived_values(design)
        ixx, iyy, izz = estimate_inertia(design, derived)
        assert ixx < iyy, (
            f"Preset '{preset}': Ixx={ixx:.6f} >= Iyy={iyy:.6f} kg·m² — physical ordering violated"
        )

    @pytest.mark.parametrize("preset", ["Trainer", "Sport", "Aerobatic", "Glider", "FlyingWing", "Scale"])
    def test_all_inertia_positive(self, preset: str) -> None:
        """All three inertia values must be strictly positive."""
        design = _make_design(preset)
        from backend.geometry.engine import compute_derived_values
        derived = compute_derived_values(design)
        ixx, iyy, izz = estimate_inertia(design, derived)
        assert ixx > 0.0, f"Preset '{preset}': Ixx <= 0"
        assert iyy > 0.0, f"Preset '{preset}': Iyy <= 0"
        assert izz > 0.0, f"Preset '{preset}': Izz <= 0"


# ---------------------------------------------------------------------------
# Partial overrides
# ---------------------------------------------------------------------------


class TestPartialOverrides:
    """Partial override: only mass set, inertia is still estimated."""

    def setup_method(self) -> None:
        self.design = _trainer()
        self.design.mass_total_override_g = 750.0
        # No inertia overrides
        self.derived = _derived(self.design)
        self.mp = resolve_mass_properties(self.design, self.derived)

    def test_mass_uses_override(self) -> None:
        assert self.mp.mass_g == pytest.approx(750.0)

    def test_ixx_estimated_true(self) -> None:
        """Without MP05, Ixx must still be estimated."""
        assert self.mp.ixx_estimated is True

    def test_iyy_estimated_true(self) -> None:
        """Without MP06, Iyy must still be estimated."""
        assert self.mp.iyy_estimated is True

    def test_izz_estimated_true(self) -> None:
        """Without MP07, Izz must still be estimated."""
        assert self.mp.izz_estimated is True

    def test_cg_x_is_nose_referenced(self) -> None:
        """Without MP02 override, CG fallback is 30% of fuselage_length from nose."""
        expected = self.design.fuselage_length * 0.30
        assert self.mp.cg_x_mm == pytest.approx(expected)


# ---------------------------------------------------------------------------
# SI unit correctness
# ---------------------------------------------------------------------------


class TestSIUnits:
    """Inertia values must be in kg·m², not gram-based or mm-based units."""

    def test_inertia_not_in_grams(self) -> None:
        """If inertia were in g·mm², values would be millions — check they are not."""
        design = _trainer()
        derived = _derived(design)
        ixx, iyy, izz = estimate_inertia(design, derived)
        # kg·m² for a 1kg model: ~0.001 – 1.0; g·mm² would be ~1e6 times larger
        assert ixx < 100.0, f"Ixx={ixx} suspiciously large — check units"
        assert iyy < 100.0, f"Iyy={iyy} suspiciously large — check units"
        assert izz < 100.0, f"Izz={izz} suspiciously large — check units"

    def test_inertia_not_too_small(self) -> None:
        """Inertia in SI must be > 1e-6 for any reasonable RC model."""
        design = _trainer()
        derived = _derived(design)
        ixx, iyy, izz = estimate_inertia(design, derived)
        assert ixx > 1e-6, f"Ixx={ixx} suspiciously small"
        assert iyy > 1e-6, f"Iyy={iyy} suspiciously small"
        assert izz > 1e-6, f"Izz={izz} suspiciously small"
