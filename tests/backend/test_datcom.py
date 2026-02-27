"""Tests for backend/datcom.py.

Covers:
- compute_flight_condition(): ISA atmosphere, q_bar, CL_trim
- compute_stability_derivatives(): sign conventions (Cm_q < 0, Cn_beta > 0, etc.)
- compute_dynamic_modes(): all 6 presets, no NaN/inf in finite fields
- Phugoid period vs Lanchester formula
- Flying wing (BWB) completes without error
- ISA atmosphere density vs altitude
"""

from __future__ import annotations

import math

import pytest

from backend.datcom import (
    FlightCondition,
    StabilityDerivatives,
    DynamicModes,
    compute_flight_condition,
    compute_stability_derivatives,
    compute_dynamic_modes,
)
from backend.mass_properties import resolve_mass_properties
from backend.models import AircraftDesign


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derived(design: AircraftDesign) -> dict:
    from backend.geometry.engine import compute_derived_values
    return compute_derived_values(design)


def _mass_props(design: AircraftDesign, derived: dict):
    return resolve_mass_properties(design, derived)


def _trainer() -> AircraftDesign:
    return AircraftDesign(
        wing_span=1200,
        wing_chord=200,
        fuselage_length=400,
        fuselage_preset="Conventional",
        tail_arm=220,
        h_stab_span=400,
        h_stab_chord=120,
        v_stab_height=120,
        v_stab_root_chord=130,
        motor_weight_g=120.0,
        battery_weight_g=200.0,
        flight_speed_ms=15.0,  # reasonable cruise speed for 1.2m trainer
    )


def _flying_wing() -> AircraftDesign:
    return AircraftDesign(
        wing_span=800,
        wing_chord=250,
        fuselage_length=300,
        fuselage_preset="Blended-Wing-Body",
        tail_arm=150,
        motor_weight_g=100.0,
        battery_weight_g=160.0,
        flight_speed_ms=18.0,
    )


def _make_preset(preset: str) -> AircraftDesign:
    presets = {
        "Trainer": dict(wing_span=1200, wing_chord=200, fuselage_length=400,
                        fuselage_preset="Conventional", tail_arm=220,
                        h_stab_span=400, h_stab_chord=120,
                        v_stab_height=120, v_stab_root_chord=130,
                        motor_weight_g=120.0, battery_weight_g=200.0,
                        flight_speed_ms=15.0),
        "Sport": dict(wing_span=1000, wing_chord=180, fuselage_length=300,
                      fuselage_preset="Conventional", tail_arm=180,
                      h_stab_span=350, h_stab_chord=100,
                      v_stab_height=100, v_stab_root_chord=110,
                      motor_weight_g=100.0, battery_weight_g=180.0,
                      flight_speed_ms=20.0),
        "Aerobatic": dict(wing_span=900, wing_chord=200, fuselage_length=280,
                          fuselage_preset="Conventional", tail_arm=160,
                          h_stab_span=300, h_stab_chord=90,
                          v_stab_height=90, v_stab_root_chord=100,
                          motor_weight_g=90.0, battery_weight_g=150.0,
                          flight_speed_ms=20.0),
        "Glider": dict(wing_span=2000, wing_chord=150, fuselage_length=600,
                       fuselage_preset="Conventional", tail_arm=350,
                       h_stab_span=500, h_stab_chord=100,
                       v_stab_height=120, v_stab_root_chord=120,
                       motor_weight_g=80.0, battery_weight_g=100.0,
                       flight_speed_ms=12.0),
        "FlyingWing": dict(wing_span=800, wing_chord=250, fuselage_length=300,
                           fuselage_preset="Blended-Wing-Body", tail_arm=150,
                           motor_weight_g=100.0, battery_weight_g=160.0,
                           flight_speed_ms=18.0),
        "Scale": dict(wing_span=1500, wing_chord=220, fuselage_length=500,
                      fuselage_preset="Conventional", tail_arm=280,
                      h_stab_span=450, h_stab_chord=120,
                      v_stab_height=130, v_stab_root_chord=130,
                      motor_weight_g=150.0, battery_weight_g=250.0,
                      flight_speed_ms=17.0),
    }
    return AircraftDesign(**presets[preset])


# ---------------------------------------------------------------------------
# compute_flight_condition tests
# ---------------------------------------------------------------------------


class TestComputeFlightCondition:
    """Flight condition: ISA atmosphere, dynamic pressure, trim CL."""

    def setup_method(self) -> None:
        self.design = _trainer()
        self.derived = _derived(self.design)
        self.mp = _mass_props(self.design, self.derived)
        self.fc = compute_flight_condition(self.design, self.mp)

    def test_returns_flight_condition(self) -> None:
        assert isinstance(self.fc, FlightCondition)

    def test_rho_positive(self) -> None:
        """Air density must be positive."""
        assert self.fc.rho > 0.0

    def test_rho_sea_level_approx(self) -> None:
        """Sea level density should be close to ISA standard (1.225 kg/m³)."""
        assert 1.1 < self.fc.rho < 1.3, f"rho = {self.fc.rho} not near 1.225 kg/m³"

    def test_q_bar_positive(self) -> None:
        """Dynamic pressure must be positive."""
        assert self.fc.q_bar > 0.0

    def test_cl_trim_positive(self) -> None:
        """CL_trim must be positive at level flight (weight = lift)."""
        assert self.fc.CL_trim > 0.0

    def test_speed_matches_design(self) -> None:
        """Speed in flight condition must match design.flight_speed_ms."""
        assert self.fc.speed_ms == pytest.approx(self.design.flight_speed_ms)

    def test_isa_density_decreases_with_altitude(self) -> None:
        """Air density should decrease as altitude increases (ISA lapse rate)."""
        design_sl = _trainer()
        design_sl.flight_altitude_m = 0.0
        design_alt = _trainer()
        design_alt.flight_altitude_m = 1000.0

        derived_sl = _derived(design_sl)
        derived_alt = _derived(design_alt)

        mp_sl = _mass_props(design_sl, derived_sl)
        mp_alt = _mass_props(design_alt, derived_alt)

        fc_sl = compute_flight_condition(design_sl, mp_sl)
        fc_alt = compute_flight_condition(design_alt, mp_alt)

        assert fc_alt.rho < fc_sl.rho, (
            f"Density at 1000m ({fc_alt.rho:.4f}) should be less than at 0m ({fc_sl.rho:.4f})"
        )

    def test_isa_sea_level_density_value(self) -> None:
        """Sea level rho should be ~1.225 kg/m³ per ISA standard."""
        design = _trainer()
        design.flight_altitude_m = 0.0
        derived = _derived(design)
        mp = _mass_props(design, derived)
        fc = compute_flight_condition(design, mp)
        assert fc.rho == pytest.approx(1.225, abs=0.01), f"rho = {fc.rho}, expected ~1.225"


# ---------------------------------------------------------------------------
# compute_stability_derivatives tests
# ---------------------------------------------------------------------------


class TestComputeStabilityDerivatives:
    """Stability derivatives: sign conventions and physical ranges."""

    def setup_method(self) -> None:
        self.design = _trainer()
        self.derived = _derived(self.design)
        self.mp = _mass_props(self.design, self.derived)
        self.fc = compute_flight_condition(self.design, self.mp)
        self.derivs = compute_stability_derivatives(self.design, self.mp, self.fc)

    def test_returns_stability_derivatives(self) -> None:
        assert isinstance(self.derivs, StabilityDerivatives)

    def test_cm_q_negative(self) -> None:
        """Pitch damping Cm_q must be negative for a stable design."""
        assert self.derivs.Cm_q < 0.0, f"Cm_q = {self.derivs.Cm_q} should be < 0"

    def test_cn_beta_positive(self) -> None:
        """Weathercock stability Cn_beta must be positive (restoring yaw moment)."""
        assert self.derivs.Cn_beta > 0.0, f"Cn_beta = {self.derivs.Cn_beta} should be > 0"

    def test_cl_p_negative(self) -> None:
        """Roll damping Cl_p must be negative (opposes roll rate)."""
        assert self.derivs.Cl_p < 0.0, f"Cl_p = {self.derivs.Cl_p} should be < 0"

    def test_cl_alpha_in_physical_range(self) -> None:
        """Aircraft lift curve slope CL_alpha should be between 3 and 7 /rad."""
        assert 3.0 <= self.derivs.CL_alpha <= 7.0, (
            f"CL_alpha = {self.derivs.CL_alpha} out of physical range [3, 7] /rad"
        )

    def test_cm_alpha_negative(self) -> None:
        """Pitch stiffness Cm_alpha must be negative for pitch stability."""
        assert self.derivs.Cm_alpha < 0.0, f"Cm_alpha = {self.derivs.Cm_alpha} should be < 0"

    def test_cn_r_negative(self) -> None:
        """Yaw damping Cn_r must be negative."""
        assert self.derivs.Cn_r < 0.0, f"Cn_r = {self.derivs.Cn_r} should be < 0"


# ---------------------------------------------------------------------------
# compute_dynamic_modes tests
# ---------------------------------------------------------------------------


class TestComputeDynamicModes:
    """Dynamic modes: physical ranges for all 6 presets."""

    def _run_modes(self, preset: str) -> DynamicModes:
        design = _make_preset(preset)
        derived = _derived(design)
        mp = _mass_props(design, derived)
        fc = compute_flight_condition(design, mp)
        derivs = compute_stability_derivatives(design, mp, fc)
        return compute_dynamic_modes(design, mp, fc, derivs)

    @pytest.mark.parametrize("preset", ["Trainer", "Sport", "Aerobatic", "Glider", "FlyingWing", "Scale"])
    def test_no_nan_in_mode_parameters(self, preset: str) -> None:
        """No NaN values in the finite-expected mode parameters for all presets."""
        modes = self._run_modes(preset)
        finite_fields = [
            "sp_omega_n", "sp_zeta", "sp_period_s",
            "phugoid_omega_n", "phugoid_zeta", "phugoid_period_s",
            "dr_omega_n", "dr_zeta", "dr_period_s",
            "roll_tau_s", "spiral_tau_s",
        ]
        for field in finite_fields:
            val = getattr(modes, field)
            assert not math.isnan(val), f"Preset '{preset}': {field} = NaN"

    @pytest.mark.parametrize("preset", ["Trainer", "Sport", "Aerobatic", "Glider", "FlyingWing", "Scale"])
    def test_sp_omega_n_positive(self, preset: str) -> None:
        """Short-period natural frequency must be positive."""
        modes = self._run_modes(preset)
        assert modes.sp_omega_n > 0.0, (
            f"Preset '{preset}': sp_omega_n = {modes.sp_omega_n} should be > 0"
        )

    @pytest.mark.parametrize("preset", ["Trainer", "Sport", "Aerobatic", "Glider", "FlyingWing", "Scale"])
    def test_sp_zeta_in_physical_range(self, preset: str) -> None:
        """Short-period damping ratio should be in (0, 5) range."""
        modes = self._run_modes(preset)
        assert 0.0 < modes.sp_zeta < 5.0, (
            f"Preset '{preset}': sp_zeta = {modes.sp_zeta} out of physical range (0, 5)"
        )

    def test_phugoid_period_vs_lanchester_trainer(self) -> None:
        """Phugoid period should be within ±50% of Lanchester approximation for Trainer.

        Lanchester (1908): T_ph = 2*pi*V / (g*sqrt(2))
        """
        design = _make_preset("Trainer")
        derived = _derived(design)
        mp = _mass_props(design, derived)
        fc = compute_flight_condition(design, mp)
        derivs = compute_stability_derivatives(design, mp, fc)
        modes = compute_dynamic_modes(design, mp, fc, derivs)

        V = fc.speed_ms
        T_lanchester = 2.0 * math.pi * V / (9.80665 * math.sqrt(2.0))

        assert modes.phugoid_period_s == pytest.approx(T_lanchester, rel=0.5), (
            f"Phugoid period {modes.phugoid_period_s:.2f}s vs Lanchester {T_lanchester:.2f}s "
            f"(tolerance ±50%)"
        )

    def test_spiral_t2s_trainer(self) -> None:
        """Trainer spiral T2 should be math.inf or a large positive value."""
        modes = self._run_modes("Trainer")
        # Either inf (stable) or large positive (very slow divergence)
        assert math.isinf(modes.spiral_t2_s) or modes.spiral_t2_s > 0.0, (
            f"spiral_t2_s = {modes.spiral_t2_s} — must be inf or positive"
        )

    def test_flying_wing_no_error(self) -> None:
        """Flying wing preset must complete without error."""
        modes = self._run_modes("FlyingWing")
        assert isinstance(modes, DynamicModes)

    def test_returns_dynamic_modes_instance(self) -> None:
        """compute_dynamic_modes() must return a DynamicModes instance."""
        modes = self._run_modes("Trainer")
        assert isinstance(modes, DynamicModes)

    def test_roll_tau_s_positive(self) -> None:
        """Roll mode time constant must be positive."""
        modes = self._run_modes("Trainer")
        assert modes.roll_tau_s > 0.0, f"roll_tau_s = {modes.roll_tau_s} should be > 0"

    def test_derivative_passthrough_cl_alpha(self) -> None:
        """DynamicModes should have CL_alpha passthrough field populated."""
        modes = self._run_modes("Trainer")
        assert modes.CL_alpha > 0.0, (
            f"CL_alpha passthrough = {modes.CL_alpha} should be > 0"
        )

    def test_derivative_passthrough_cn_beta(self) -> None:
        """DynamicModes should have Cn_beta passthrough field populated."""
        modes = self._run_modes("Trainer")
        assert modes.Cn_beta > 0.0, (
            f"Cn_beta passthrough = {modes.Cn_beta} should be > 0"
        )

    def test_derivatives_estimated_flag(self) -> None:
        """derivatives_estimated field should be True by default."""
        modes = self._run_modes("Trainer")
        assert modes.derivatives_estimated is True

    @pytest.mark.parametrize("preset", ["Trainer", "Sport", "Aerobatic", "Glider", "Scale"])
    def test_no_inf_in_non_spiral_fields(self, preset: str) -> None:
        """All mode fields except spiral_t2_s should be finite for conventional configs."""
        modes = self._run_modes(preset)
        inf_disallowed = [
            "sp_omega_n", "sp_zeta", "sp_period_s",
            "phugoid_omega_n", "phugoid_zeta", "phugoid_period_s",
            "dr_omega_n", "dr_zeta", "dr_period_s",
            "roll_tau_s", "spiral_tau_s",
        ]
        for field in inf_disallowed:
            val = getattr(modes, field)
            assert math.isfinite(val), (
                f"Preset '{preset}': {field} = {val} — expected finite"
            )
