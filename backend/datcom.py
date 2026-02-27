"""
backend/datcom.py

USAF DATCOM empirical stability derivatives and dynamic mode analysis.

This module implements the core aerodynamics pipeline:
  1. Compute ISA flight condition (V, rho, q_bar, CL_trim)
  2. Compute stability derivatives using DATCOM empirical formulas, with
     section lift slopes supplied by NeuralFoil data (backend/airfoil_data.py)
  3. Assemble linearized equations of motion and compute dynamic mode
     characteristics via numpy eigenvalue analysis

All units are SI internally (kg, m, s, rad). Input geometry is in mm (CHENG
convention) and converted to metres at the start of each public function.

References:
  USAF DATCOM: Hoak, D.E. et al., "USAF Stability and Control DATCOM",
  Report AFWAL-TR-83-3048 (1978, rev. 1998)
  Lanchester, F.W., "Aerodonetics" (1908) — phugoid approximation
  Nelson, R.C., "Flight Stability and Automatic Control" (1998)
"""

from __future__ import annotations

import dataclasses
import math
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from backend.models import AircraftDesign
    from backend.mass_properties import MassProperties

from backend.airfoil_data import interpolate_section_aero

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

_G = 9.80665      # Standard gravity (m/s²)
_MU = 1.81e-5     # Air dynamic viscosity at sea level (Pa·s)
_SPEED_OF_SOUND_SL = 340.3  # Speed of sound at sea level (m/s)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FlightCondition:
    """Trimmed flight condition derived from design parameters."""

    speed_ms: float
    """True airspeed (m/s)."""

    altitude_m: float
    """Flight altitude above MSL (m)."""

    rho: float
    """Air density at altitude (kg/m³)."""

    q_bar: float
    """Dynamic pressure = 0.5 * rho * V² (Pa)."""

    CL_trim: float
    """Trim lift coefficient at cruise (dimensionless)."""

    alpha_trim_rad: float
    """Trim angle of attack (rad). Approximate."""


@dataclass
class StabilityDerivatives:
    """DATCOM stability derivatives (all per radian unless noted).

    All values are non-dimensional except where otherwise stated.
    """

    # ── Longitudinal ─────────────────────────────────────────────────────────
    CL_alpha: float
    """Aircraft lift curve slope dCL/dα (per rad). Typically 4–7 /rad."""

    CD_alpha: float
    """Drag slope dCD/dα (per rad)."""

    Cm_alpha: float
    """Pitch stiffness dCm/dα (per rad). Must be negative for stability."""

    CL_q: float
    """Lift due to pitch rate (per rad)."""

    Cm_q: float
    """Pitch damping dCm/d(qc/2V) (per rad). Must be negative."""

    CL_alphadot: float
    """Lift due to angle-of-attack rate (per rad)."""

    Cm_alphadot: float
    """Pitch due to angle-of-attack rate (per rad)."""

    # ── Lateral/directional ───────────────────────────────────────────────────
    CY_beta: float
    """Side force due to sideslip (per rad). Negative."""

    Cl_beta: float
    """Roll moment due to sideslip — dihedral effect (per rad). Negative = stable."""

    Cn_beta: float
    """Yaw moment due to sideslip — weathercock stability (per rad). Positive = stable."""

    CY_p: float
    """Side force due to roll rate."""

    Cl_p: float
    """Roll damping dCl/d(pb/2V) (per rad). Negative."""

    Cn_p: float
    """Yaw due to roll rate — adverse yaw (per rad)."""

    CY_r: float
    """Side force due to yaw rate."""

    Cl_r: float
    """Roll due to yaw rate (per rad). Positive for most configs."""

    Cn_r: float
    """Yaw damping dCn/d(rb/2V) (per rad). Negative."""


@dataclass
class DynamicModes:
    """Dynamic stability mode characteristics.

    Contains eigenvalue-derived parameters for all 5 classical dynamic modes.
    All frequencies in rad/s; periods in seconds; time constants in seconds.
    """

    # ── Longitudinal ─────────────────────────────────────────────────────────
    sp_omega_n: float
    """Short-period natural frequency (rad/s)."""

    sp_zeta: float
    """Short-period damping ratio (dimensionless)."""

    sp_period_s: float
    """Short-period period (s). Large value if over-damped."""

    phugoid_omega_n: float
    """Phugoid natural frequency (rad/s)."""

    phugoid_zeta: float
    """Phugoid damping ratio."""

    phugoid_period_s: float
    """Phugoid period (s)."""

    # ── Lateral/directional ───────────────────────────────────────────────────
    dr_omega_n: float
    """Dutch roll natural frequency (rad/s)."""

    dr_zeta: float
    """Dutch roll damping ratio."""

    dr_period_s: float
    """Dutch roll period (s)."""

    roll_tau_s: float
    """Roll mode time constant (s). Smaller = more responsive."""

    spiral_tau_s: float
    """Spiral mode time constant (s). Negative = divergent."""

    spiral_t2_s: float
    """Spiral time-to-double (s). math.inf for stable or convergent spiral."""

    # Derivative passthrough for engine.py convenience
    # (combined with StabilityDerivatives when creating DynamicStabilityResult)
    CL_alpha: float = 0.0
    CD_alpha: float = 0.0
    Cm_alpha: float = 0.0
    CL_q: float = 0.0
    Cm_q: float = 0.0
    CL_alphadot: float = 0.0
    Cm_alphadot: float = 0.0
    CY_beta: float = 0.0
    Cl_beta: float = 0.0
    Cn_beta: float = 0.0
    CY_p: float = 0.0
    Cl_p: float = 0.0
    Cn_p: float = 0.0
    CY_r: float = 0.0
    Cl_r: float = 0.0
    Cn_r: float = 0.0

    derivatives_estimated: bool = True


# ---------------------------------------------------------------------------
# ISA atmosphere model
# ---------------------------------------------------------------------------

def _isa_atmosphere(altitude_m: float) -> tuple[float, float, float]:
    """ISA standard atmosphere up to 11 km (troposphere).

    Returns:
        (T_K, rho_kg_m3, speed_of_sound_m_s)
    """
    # DATCOM uses standard ISA: linear temperature lapse in troposphere
    T = 288.15 - 0.0065 * min(altitude_m, 11000.0)
    rho = 1.225 * (T / 288.15) ** 4.256
    a = _SPEED_OF_SOUND_SL * math.sqrt(T / 288.15)
    return T, rho, a


# ---------------------------------------------------------------------------
# Finite-wing lift slope (DATCOM §4.1.3.2 — Polhamus)
# ---------------------------------------------------------------------------

def _finite_wing_cla(
    a_0: float,
    AR: float,
    sweep_le_rad: float,
    mach: float,
) -> float:
    """Polhamus finite-wing lift curve slope (per rad).

    # DATCOM §4.1.3.2

    a_0: section lift slope from NeuralFoil (per rad)
    AR: aspect ratio
    sweep_le_rad: leading-edge sweep angle (rad), positive aft
    mach: Mach number
    """
    # Half-chord sweep from LE sweep approximation:
    # Lambda_c2 ≈ Lambda_LE for thin wings (conservative)
    sweep_c2 = sweep_le_rad  # approximate

    beta = math.sqrt(max(1.0 - mach ** 2, 0.01))  # compressibility

    # Polhamus formula (DATCOM eq. 4.1.3.2-a)
    discriminant = 4.0 + (AR ** 2) * (1.0 + math.tan(sweep_c2) ** 2 / beta ** 2) * (a_0 / math.pi) ** 2
    a_w = (a_0 * AR) / (2.0 + math.sqrt(max(discriminant, 0.01)))
    return a_w


# ---------------------------------------------------------------------------
# Helper: compute Re and Mach for a lifting surface
# ---------------------------------------------------------------------------

def _surface_re_mach(
    speed_ms: float,
    chord_m: float,
    sweep_rad: float,
    rho: float,
    speed_of_sound: float,
) -> tuple[float, float]:
    """Compute Re and Mach for a lifting surface, accounting for sweep.

    Effective velocity normal to the leading edge:
        V_eff = V * cos(sweep)
    """
    V_eff = speed_ms * math.cos(sweep_rad)
    Re = rho * V_eff * chord_m / _MU
    Mach = V_eff / speed_of_sound
    return max(Re, 1.0), max(Mach, 1e-4)


# ---------------------------------------------------------------------------
# Public function 1: compute_flight_condition
# ---------------------------------------------------------------------------

def compute_flight_condition(
    design: "AircraftDesign",
    mass_props: "MassProperties",
) -> FlightCondition:
    """Compute the trimmed flight condition for DATCOM analysis.

    # DATCOM §1.2 (flight condition definitions)

    Args:
        design: Aircraft design parameters.
        mass_props: Resolved mass properties (from resolve_mass_properties).

    Returns:
        FlightCondition with V, rho, q_bar, CL_trim, alpha_trim.
    """
    V = design.flight_speed_ms
    h = design.flight_altitude_m

    _, rho, _ = _isa_atmosphere(h)
    q_bar = 0.5 * rho * V ** 2

    # Wing reference area (m²)
    tip_chord_m = (design.wing_chord * design.wing_tip_root_ratio) / 1000.0
    root_chord_m = design.wing_chord / 1000.0
    span_m = design.wing_span / 1000.0
    S_w_m2 = 0.5 * (root_chord_m + tip_chord_m) * span_m  # both halves

    mass_kg = mass_props.mass_g / 1000.0
    weight_N = mass_kg * _G

    CL_trim = weight_N / (q_bar * S_w_m2) if q_bar > 0 else 0.0

    # Approximate alpha_trim using a_0 ~ 2*pi and AR correction
    # Will be refined in derivatives step
    AR = span_m ** 2 / max(S_w_m2, 0.001)
    a_w_approx = (2.0 * math.pi * AR) / (2.0 + math.sqrt(4.0 + AR ** 2))
    alpha_trim_rad = CL_trim / max(a_w_approx, 0.1)

    return FlightCondition(
        speed_ms=V,
        altitude_m=h,
        rho=rho,
        q_bar=q_bar,
        CL_trim=CL_trim,
        alpha_trim_rad=alpha_trim_rad,
    )


# ---------------------------------------------------------------------------
# Public function 2: compute_stability_derivatives
# ---------------------------------------------------------------------------

def compute_stability_derivatives(
    design: "AircraftDesign",
    mass_props: "MassProperties",
    flight_cond: FlightCondition,
) -> StabilityDerivatives:
    """Compute DATCOM stability derivatives using NeuralFoil section data.

    All formulas reference DATCOM section numbers in inline comments.
    All lifting surface section slopes use NeuralFoil interpolation, NOT 2*pi.

    Args:
        design: Aircraft design parameters.
        mass_props: Resolved mass properties.
        flight_cond: Trimmed flight condition.

    Returns:
        StabilityDerivatives with all 16 derivatives.
    """
    V = flight_cond.speed_ms
    rho = flight_cond.rho
    q_bar = flight_cond.q_bar
    CL_trim = flight_cond.CL_trim

    _, _, speed_of_sound = _isa_atmosphere(flight_cond.altitude_m)

    # ── Geometry (SI) ───────────────────────────────────────────────────────
    b_m = design.wing_span / 1000.0
    root_chord_m = design.wing_chord / 1000.0
    tip_chord_m = root_chord_m * design.wing_tip_root_ratio
    S_w_m2 = 0.5 * (root_chord_m + tip_chord_m) * b_m
    c_bar_m = 2.0 / 3.0 * root_chord_m * (
        (1.0 + design.wing_tip_root_ratio + design.wing_tip_root_ratio ** 2)
        / (1.0 + design.wing_tip_root_ratio)
    )  # Mean aerodynamic chord
    AR = b_m ** 2 / max(S_w_m2, 0.001)
    lam = design.wing_tip_root_ratio  # taper ratio

    sweep_le_rad = math.radians(design.wing_sweep)

    # Flying wing / BWB: no separate tail surfaces
    is_flying_wing = design.fuselage_preset == "Blended-Wing-Body"

    # ── Wing section aerodynamics (NeuralFoil) ─────────────────────────────
    Re_w, Mach_w = _surface_re_mach(V, c_bar_m, sweep_le_rad, rho, speed_of_sound)
    wing_aero = interpolate_section_aero(design.wing_airfoil, Re=Re_w, Mach=Mach_w)

    a_0_w = wing_aero["cl_alpha_per_rad"]  # NeuralFoil section slope — NOT 2π
    cd_min_w = wing_aero["cd_min"]
    cm_ac_w = wing_aero["cm_ac"]

    # ── Finite-wing lift slope (DATCOM §4.1.3.2) ───────────────────────────
    a_w = _finite_wing_cla(a_0_w, AR, sweep_le_rad, Mach_w)

    # ── Downwash gradient at horizontal tail (DATCOM §5.1) ─────────────────
    # Approximate formula for unswept/lightly swept wings:
    # dε/dα ≈ 2 * a_w / (π * AR)
    # # DATCOM §5.1.3.1
    de_da = 2.0 * a_w / (math.pi * AR)
    de_da = min(de_da, 0.9)  # physical limit

    # ── Tail geometry ─────────────────────────────────────────────────────
    if not is_flying_wing:
        if design.tail_type == "V-Tail":
            # V-tail: project to effective horizontal and vertical areas
            dih = math.radians(design.v_tail_dihedral)
            S_tail_per_surface = design.v_tail_chord * design.v_tail_span / 1e6  # m²
            # Both surfaces
            S_h_eff = 2.0 * S_tail_per_surface * math.cos(dih) ** 2
            S_v_eff = 2.0 * S_tail_per_surface * math.sin(dih) ** 2
            h_chord_m = design.v_tail_chord / 1000.0
            v_chord_m = design.v_tail_chord / 1000.0
            sweep_h_rad = math.radians(design.v_tail_sweep)
            sweep_v_rad = sweep_h_rad
            h_span_m = design.v_tail_span / 1000.0
            v_height_m = design.v_tail_span * math.sin(dih) / 1000.0
            l_t_m = design.tail_arm / 1000.0
            l_v_m = l_t_m
        else:
            # Conventional / T-Tail / Cruciform
            S_h_eff = design.h_stab_chord * design.h_stab_span / 1e6  # m²
            S_v_eff = 0.5 * design.v_stab_root_chord * design.v_stab_height / 1e6  # m² (triangle approx)
            h_chord_m = design.h_stab_chord / 1000.0
            v_chord_m = design.v_stab_root_chord / 1000.0
            sweep_h_rad = 0.0  # h-stab usually unswept
            sweep_v_rad = 0.0
            h_span_m = design.h_stab_span / 1000.0
            v_height_m = design.v_stab_height / 1000.0
            l_t_m = design.tail_arm / 1000.0
            l_v_m = l_t_m  # same arm for conventional tail

        # Horizontal tail section aerodynamics (NeuralFoil)
        Re_h, Mach_h = _surface_re_mach(V, h_chord_m, sweep_h_rad, rho, speed_of_sound)
        tail_aero = interpolate_section_aero(design.tail_airfoil, Re=Re_h, Mach=Mach_h)
        a_0_t = tail_aero["cl_alpha_per_rad"]

        # Horizontal tail aspect ratio and lift slope
        AR_h = h_span_m ** 2 / max(S_h_eff, 0.001)
        a_t = _finite_wing_cla(a_0_t, AR_h, sweep_h_rad, Mach_h)

        # Vertical tail section aerodynamics
        Re_v, Mach_v = _surface_re_mach(V, v_chord_m, sweep_v_rad, rho, speed_of_sound)
        vtail_aero = interpolate_section_aero(design.tail_airfoil, Re=Re_v, Mach=Mach_v)
        a_0_v = vtail_aero["cl_alpha_per_rad"]

        # Vertical fin effective aspect ratio
        AR_v = 2.0 * v_height_m ** 2 / max(S_v_eff, 0.001)  # factor 2 for endplate effect
        a_v = _finite_wing_cla(a_0_v, AR_v, sweep_v_rad, Mach_v)

        # Efficiency factors
        eta_t = 0.90   # horizontal tail dynamic pressure ratio
        eta_v = 0.90   # vertical fin dynamic pressure ratio

        # Volume ratios
        V_h = a_t * eta_t * S_h_eff / S_w_m2  # horizontal tail volume-like ratio
        V_v = a_v * eta_v * S_v_eff / S_w_m2  # vertical fin volume-like ratio

        # Vertical fin height above CG (approximate: half fin height)
        z_v_m = v_height_m / 2.0

    else:
        # Flying wing: no separate tail surfaces
        # Set all tail contributions to zero
        a_t = 0.0
        a_v = 0.0
        S_h_eff = 0.0
        S_v_eff = 0.0
        eta_t = 0.0
        eta_v = 0.0
        V_h = 0.0
        V_v = 0.0
        l_t_m = design.fuselage_length * 0.3 / 1000.0  # approximate
        l_v_m = l_t_m
        z_v_m = 0.0
        de_da = 0.0  # no downwash without ht for flying wing

    # ── CG and AC positions (fraction of MAC) ─────────────────────────────
    cg_x_mm = mass_props.cg_x_mm
    # Wing mount position (approximate)
    x_ac_w = 0.25  # aerodynamic center at 25% MAC for subsonic

    # CG as fraction of MAC from nose of MAC
    # We need x_cg_mac: CG position measured from wing LE as fraction of c_bar
    # estimate wing leading edge position
    wing_x_m = design.fuselage_length * 0.30 / 1000.0  # approx mount fraction
    cg_x_m = cg_x_mm / 1000.0
    x_ac_w_m = wing_x_m + x_ac_w * c_bar_m
    x_cg_mac = (cg_x_m - wing_x_m) / max(c_bar_m, 0.001)  # fraction of MAC

    # ── Longitudinal derivatives ─────────────────────────────────────────

    # CLα — total aircraft lift slope (DATCOM §4.1.3.2, §4.5)
    # # DATCOM §4.5 — wing + tail + fuselage body factor
    K_WB = 1.07  # Wing-Body interference factor (conventional layout)
    CL_alpha = K_WB * a_w + a_t * eta_t * (S_h_eff / S_w_m2) * (1.0 - de_da)

    # CDα — drag slope (DATCOM §4.1.5)
    # # DATCOM §4.1.5 — induced drag contribution
    e_oswald = 0.80  # Oswald efficiency factor
    CD0 = cd_min_w + CL_trim ** 2 / (math.pi * AR * e_oswald)
    CD_alpha = 2.0 * CL_trim / (math.pi * AR * e_oswald)

    # Cmα — pitch stiffness (DATCOM §4.5)
    # # DATCOM §4.5 — wing-body + tail contributions
    Cm_alpha = (
        a_w * K_WB * (x_cg_mac - x_ac_w)
        - a_t * eta_t * (S_h_eff / S_w_m2) * (l_t_m / c_bar_m) * (1.0 - de_da)
    )

    # CLq — lift due to pitch rate (DATCOM §7.1)
    # # DATCOM §7.1 — tail contribution dominates
    CL_q = 2.0 * a_t * eta_t * (S_h_eff / S_w_m2) * (l_t_m / c_bar_m)

    # Cmq — pitch damping (DATCOM §7.1)
    # # DATCOM §7.1 — must be negative
    Cm_q = -2.0 * a_t * eta_t * (S_h_eff / S_w_m2) * (l_t_m / c_bar_m) ** 2

    # CLalphadot, Cmalphadot — downwash-lag derivatives (DATCOM §7.1.2)
    # # DATCOM §7.1.2 — apparent mass terms
    CL_alphadot = 2.0 * a_t * eta_t * (S_h_eff / S_w_m2) * (l_t_m / c_bar_m) * de_da
    Cm_alphadot = -CL_alphadot * (l_t_m / c_bar_m)

    # ── Lateral/directional derivatives ─────────────────────────────────

    # CYβ — side force due to sideslip (DATCOM §6.1.4)
    # # DATCOM §6.1.4 — vertical fin contribution
    dsigma_dbeta = 0.20  # sidewash gradient (typical conventional fuselage)
    CY_beta = -a_v * eta_v * (S_v_eff / S_w_m2) * (1.0 + dsigma_dbeta)

    # Clβ — dihedral effect (DATCOM §6.1.5)
    # # DATCOM §6.1.5 — dihedral + sweep + fin contributions
    Gamma_eff_rad = math.radians(design.wing_dihedral)  # geometric dihedral
    Cl_beta_dihedral = -(a_0_w / (2.0 * math.pi)) * Gamma_eff_rad  # uses NeuralFoil slope
    Cl_beta_sweep = -CL_trim * math.tan(sweep_le_rad) / (4.0 * AR) if AR > 0 else 0.0
    Cl_beta_fin = -a_v * eta_v * (S_v_eff / S_w_m2) * (z_v_m / b_m)
    Cl_beta = Cl_beta_dihedral + Cl_beta_sweep + Cl_beta_fin

    # Cnβ — directional stability (DATCOM §6.1.4)
    # # DATCOM §6.1.4 — fin + wing + fuselage contributions
    Cn_beta_fin = a_v * eta_v * (S_v_eff / S_w_m2) * (l_v_m / b_m)
    Cn_beta_wing = -CL_trim * (1.0 - 3.0 * lam) / (6.0 * (1.0 + lam)) * math.tan(sweep_le_rad)

    # Fuselage contribution (destabilizing)
    # # DATCOM §6.1.4 — body contribution: k_n * k_rl * S_B_side * l_fus / (S_w * b)
    k_n = 0.01  # fuselage fineness correction (small for conventional fuselages)
    k_rl = 1.0  # Reynolds number correction (= 1.0 at Re > 1e5)
    S_B_side_m2 = (design.fuselage_length * design.wing_chord * 0.35) / 1e6  # approx side area
    l_fus_m = design.fuselage_length / 1000.0
    Cn_beta_fuselage = -k_n * k_rl * (S_B_side_m2 * l_fus_m) / (S_w_m2 * b_m)

    Cn_beta = Cn_beta_fin + Cn_beta_wing + Cn_beta_fuselage

    # Clp — roll damping (DATCOM §7.3)
    # # DATCOM §7.3 — wing roll damping, uses NeuralFoil section slope
    Cl_p = -(a_0_w / 8.0) * (1.0 + 3.0 * lam) / (1.0 + lam)  # per rad

    # Cnr — yaw damping (DATCOM §7.4)
    # # DATCOM §7.4 — fin + wing contributions
    Cn_r_fin = -a_v * eta_v * (S_v_eff / S_w_m2) * (l_v_m / b_m) ** 2
    Cn_r_wing = -(CL_trim ** 2 / (math.pi * AR) + cd_min_w / 8.0)
    Cn_r = Cn_r_fin + Cn_r_wing

    # Clr — roll due to yaw rate (DATCOM §7.4)
    # # DATCOM §7.4 — coupling derivative
    Cl_r_wing = CL_trim / 4.0
    Cl_r_fin = a_v * eta_v * (S_v_eff / S_w_m2) * (z_v_m / b_m) * (l_v_m / b_m)
    Cl_r = Cl_r_wing + Cl_r_fin

    # Cnp — yaw due to roll rate (DATCOM §7.5)
    # # DATCOM §7.5 — adverse yaw
    Cn_p = -CL_trim / 8.0 * (1.0 - 3.0 * lam) / (1.0 + lam)

    # CYp, CYr — side force rate derivatives (DATCOM §7.5, §7.4)
    # # DATCOM §7.5/7.4 — secondary terms
    CY_p = -a_v * eta_v * (S_v_eff / S_w_m2) * (z_v_m / b_m)
    CY_r = 2.0 * a_v * eta_v * (S_v_eff / S_w_m2) * (l_v_m / b_m)

    return StabilityDerivatives(
        CL_alpha=CL_alpha,
        CD_alpha=CD_alpha,
        Cm_alpha=Cm_alpha,
        CL_q=CL_q,
        Cm_q=Cm_q,
        CL_alphadot=CL_alphadot,
        Cm_alphadot=Cm_alphadot,
        CY_beta=CY_beta,
        Cl_beta=Cl_beta,
        Cn_beta=Cn_beta,
        CY_p=CY_p,
        Cl_p=Cl_p,
        Cn_p=Cn_p,
        CY_r=CY_r,
        Cl_r=Cl_r,
        Cn_r=Cn_r,
    )


# ---------------------------------------------------------------------------
# Eigenvalue helpers
# ---------------------------------------------------------------------------

def _damping_freq_from_eigenvalue(ev: complex) -> tuple[float, float, float]:
    """Extract (omega_n, zeta, period_s) from a complex eigenvalue.

    For a pair σ ± jω:
        omega_n = sqrt(σ² + ω²)
        zeta    = -σ / omega_n
        period  = 2π / ω

    Returns all zeros for non-oscillatory modes.
    """
    sigma = ev.real
    omega_d = abs(ev.imag)
    if omega_d < 1e-6:
        return 0.0, 0.0, 0.0
    omega_n = math.sqrt(sigma ** 2 + omega_d ** 2)
    zeta = -sigma / omega_n if omega_n > 0 else 0.0
    period = 2.0 * math.pi / omega_d
    return omega_n, zeta, period


# ---------------------------------------------------------------------------
# Public function 3: compute_dynamic_modes
# ---------------------------------------------------------------------------

def compute_dynamic_modes(
    design: "AircraftDesign",
    mass_props: "MassProperties",
    flight_cond: FlightCondition,
    derivs: StabilityDerivatives,
) -> DynamicModes:
    """Compute dynamic stability mode characteristics via eigenvalue analysis.

    Assembles 4×4 longitudinal and lateral state matrices in dimensional form,
    computes eigenvalues, and classifies the resulting modes.

    Longitudinal state: [Δu, Δw, q, Δθ]
    Lateral state: [β, p, r, φ]

    # DATCOM §8.1 (dynamic stability equations)
    # Nelson (1998) Chapters 4-5

    Args:
        design: Aircraft design.
        mass_props: Resolved mass properties.
        flight_cond: Trimmed flight condition.
        derivs: Stability derivatives (from compute_stability_derivatives).

    Returns:
        DynamicModes with all mode characteristics.
    """
    V = flight_cond.speed_ms
    rho = flight_cond.rho
    q_bar = flight_cond.q_bar
    CL_trim = flight_cond.CL_trim
    alpha_0 = flight_cond.alpha_trim_rad

    # ── Geometry and mass (SI) ─────────────────────────────────────────────
    b_m = design.wing_span / 1000.0
    root_chord_m = design.wing_chord / 1000.0
    tip_chord_m = root_chord_m * design.wing_tip_root_ratio
    S_w_m2 = 0.5 * (root_chord_m + tip_chord_m) * b_m
    c_bar_m = 2.0 / 3.0 * root_chord_m * (
        (1.0 + design.wing_tip_root_ratio + design.wing_tip_root_ratio ** 2)
        / (1.0 + design.wing_tip_root_ratio)
    )

    m_kg = mass_props.mass_g / 1000.0
    W_N = m_kg * _G
    Ixx = mass_props.ixx_kg_m2
    Iyy = mass_props.iyy_kg_m2
    Izz = mass_props.izz_kg_m2

    # ── Non-dimensional → dimensional conversion shortcuts ─────────────────
    qS = q_bar * S_w_m2
    qSc = qS * c_bar_m
    qSb = qS * b_m
    qSb2 = qSb * b_m

    # Non-dimensional time unit
    t_star = c_bar_m / (2.0 * V)   # longitudinal
    t_b = b_m / (2.0 * V)          # lateral

    # ── Longitudinal state matrix A_long (dimensional) ─────────────────────
    # State: [Δu, Δw, q, Δθ]
    # Reference: Nelson (1998) eq. 4.52

    # Dimensional stability derivatives
    X_u = -qS * (2.0 * CL_trim * math.sin(alpha_0) + derivs.CD_alpha * math.cos(alpha_0)) / (m_kg * V)
    X_w = qS * (CL_trim * math.cos(alpha_0) - derivs.CD_alpha * math.sin(alpha_0)) / (m_kg * V)
    Z_u = -qS * (2.0 * CL_trim * math.cos(alpha_0) + derivs.CD_alpha * math.sin(alpha_0)) / (m_kg * V)
    Z_w = -qS * derivs.CL_alpha / (m_kg * V)
    Z_q = qS * derivs.CL_q * c_bar_m / (2.0 * m_kg * V)
    Z_adot = qS * derivs.CL_alphadot * c_bar_m / (2.0 * m_kg * V)
    M_w = qSc * derivs.Cm_alpha / (Iyy * V)
    M_q = qSc * derivs.Cm_q * c_bar_m / (2.0 * Iyy * V)
    M_adot = qSc * derivs.Cm_alphadot * c_bar_m / (2.0 * Iyy * V)

    # A_long in [Δu, Δw, q, Δθ]
    # Row 0: Δu_dot = X_u*Δu + X_w*Δw - g*cos(theta0)*Δθ
    # Row 1: Δw_dot = Z_u*Δu + Z_w*Δw + (V + Z_q)*q - g*sin(theta0)*Δθ  (approx θ0~α0)
    # Row 2: q_dot  = M_u*Δu + (M_w + M_adot*Z_w/V)*Δw + M_q*q + M_adot*Z_q/V*q (simplified)
    # Row 3: θ_dot  = q

    theta0 = alpha_0  # assume theta0 ~ alpha0 for level flight

    A_long = np.array([
        [X_u,   X_w,   0.0,          -_G * math.cos(theta0)],
        [Z_u,   Z_w,   V + Z_q,      -_G * math.sin(theta0)],
        [0.0,   M_w + M_adot * Z_w / V,  M_q + M_adot * (V + Z_q) / V,  0.0],
        [0.0,   0.0,   1.0,           0.0],
    ], dtype=float)

    # ── Lateral state matrix A_lat (dimensional) ───────────────────────────
    # State: [β, p, r, φ]
    # Reference: Nelson (1998) eq. 5.31

    Y_beta = qS * derivs.CY_beta / (m_kg * V)
    Y_p = qS * derivs.CY_p * b_m / (2.0 * m_kg * V)
    Y_r = qS * derivs.CY_r * b_m / (2.0 * m_kg * V)
    L_beta = qSb * derivs.Cl_beta / Ixx
    L_p = qSb2 * derivs.Cl_p / (2.0 * Ixx * V)
    L_r = qSb2 * derivs.Cl_r / (2.0 * Ixx * V)
    N_beta = qSb * derivs.Cn_beta / Izz
    N_p = qSb2 * derivs.Cn_p / (2.0 * Izz * V)
    N_r = qSb2 * derivs.Cn_r / (2.0 * Izz * V)

    A_lat = np.array([
        [Y_beta,    1.0 + Y_p,    -(1.0 - Y_r),   _G / V],
        [L_beta,    L_p,           L_r,            0.0   ],
        [N_beta,    N_p,           N_r,            0.0   ],
        [0.0,       1.0,           0.0,            0.0   ],
    ], dtype=float)

    # ── Longitudinal eigenvalues ───────────────────────────────────────────
    try:
        evals_long = np.linalg.eig(A_long)[0]

        # Separate oscillatory (complex) roots from aperiodic (real) roots.
        # Threshold: |imag| > 1e-3 rad/s distinguishes oscillatory from aperiodic.
        osc_long = sorted(
            [e for e in evals_long if abs(e.imag) > 1e-3],
            key=lambda e: abs(e.imag),
            reverse=True,
        )

        if len(osc_long) >= 2:
            # Normal case: two complex-conjugate pairs.
            # Highest |imag| = short-period, lowest |imag| = phugoid.
            sp_ev = osc_long[0]
            sp_omega_n, sp_zeta, sp_period_s = _damping_freq_from_eigenvalue(sp_ev)
            # Phugoid is the other oscillatory mode (last pair after SP pair)
            ph_ev = osc_long[-1]
            ph_omega_n, ph_zeta, ph_period_s = _damping_freq_from_eigenvalue(ph_ev)
        elif len(osc_long) == 1:
            # Only short-period is oscillatory; phugoid is overdamped — real roots.
            sp_ev = osc_long[0]
            sp_omega_n, sp_zeta, sp_period_s = _damping_freq_from_eigenvalue(sp_ev)
            # Phugoid: fall back to Lanchester approximation
            ph_omega_n = _G * math.sqrt(2.0) / V
            ph_zeta = 0.05
            ph_period_s = 2.0 * math.pi / ph_omega_n
        else:
            # No oscillatory modes — pure fallback
            raise ValueError("No oscillatory longitudinal eigenvalues found")

        # Sanity check: phugoid frequency must be positive and finite
        ph_omega_lanchester = _G * math.sqrt(2.0) / V
        if ph_omega_n < 1e-6 or not math.isfinite(ph_omega_n):
            ph_omega_n = ph_omega_lanchester
            ph_period_s = 2.0 * math.pi / ph_omega_n

    except Exception as e:
        warnings.warn(f"Longitudinal eigenvalue computation failed: {e}")
        # Fallback: Lanchester approximation for phugoid
        ph_omega_n = _G * math.sqrt(2.0) / V
        ph_zeta = 0.05
        ph_period_s = 2.0 * math.pi / ph_omega_n
        sp_omega_n = max(abs(derivs.Cm_q), 0.5)
        sp_zeta = 0.5
        sp_period_s = 2.0 * math.pi / max(sp_omega_n, 0.01)

    # ── Lateral eigenvalues ────────────────────────────────────────────────
    try:
        evals_lat = np.linalg.eig(A_lat)[0]

        # Separate complex pairs (Dutch roll) from real roots (roll, spiral)
        complex_evs = [e for e in evals_lat if abs(e.imag) > 1e-3]
        real_evs = sorted(
            [e.real for e in evals_lat if abs(e.imag) <= 1e-3],
            key=lambda r: r  # ascending
        )

        # Dutch roll: complex conjugate pair
        if complex_evs:
            dr_ev = complex_evs[0]
            dr_omega_n, dr_zeta, dr_period_s = _damping_freq_from_eigenvalue(dr_ev)
        else:
            dr_omega_n, dr_zeta, dr_period_s = 0.0, 0.0, 0.0

        # Real roots: more negative = roll mode, less negative (or positive) = spiral
        if len(real_evs) >= 2:
            # Roll mode: most negative real eigenvalue (large negative = fast convergence)
            roll_ev = min(real_evs)  # most negative
            spiral_ev_val = max(real_evs)  # least negative (or positive = divergent)
        elif len(real_evs) == 1:
            roll_ev = real_evs[0]
            spiral_ev_val = 0.0
        else:
            roll_ev = -2.0  # default
            spiral_ev_val = 0.01

        roll_tau_s = -1.0 / roll_ev if abs(roll_ev) > 1e-6 else 10.0
        spiral_tau_s = 1.0 / spiral_ev_val if abs(spiral_ev_val) > 1e-6 else 1e6

        # Time to double for spiral (divergent if spiral_ev_val > 0)
        if spiral_ev_val > 1e-6:
            spiral_t2_s = math.log(2.0) / spiral_ev_val
        else:
            spiral_t2_s = math.inf  # stable or neutral

    except Exception as e:
        warnings.warn(f"Lateral eigenvalue computation failed: {e}")
        dr_omega_n, dr_zeta, dr_period_s = 1.0, 0.1, 6.0
        roll_tau_s = 0.3
        spiral_tau_s = 100.0
        spiral_t2_s = math.inf

    # Clamp NaN/inf to safe defaults
    def _safe(val: float, default: float = 0.0) -> float:
        if not math.isfinite(val):
            return default
        return val

    return DynamicModes(
        sp_omega_n=_safe(sp_omega_n, 2.0),
        sp_zeta=_safe(sp_zeta, 0.5),
        sp_period_s=_safe(sp_period_s, 2.0),
        phugoid_omega_n=_safe(ph_omega_n, 0.1),
        phugoid_zeta=_safe(ph_zeta, 0.05),
        phugoid_period_s=_safe(ph_period_s, 60.0),
        dr_omega_n=_safe(dr_omega_n, 1.0),
        dr_zeta=_safe(dr_zeta, 0.1),
        dr_period_s=_safe(dr_period_s, 4.0),
        roll_tau_s=_safe(roll_tau_s, 0.3),
        spiral_tau_s=_safe(spiral_tau_s, 100.0),
        spiral_t2_s=spiral_t2_s if math.isinf(spiral_t2_s) else _safe(spiral_t2_s, 1000.0),
        # Derivative passthrough
        CL_alpha=derivs.CL_alpha,
        CD_alpha=derivs.CD_alpha,
        Cm_alpha=derivs.Cm_alpha,
        CL_q=derivs.CL_q,
        Cm_q=derivs.Cm_q,
        CL_alphadot=derivs.CL_alphadot,
        Cm_alphadot=derivs.Cm_alphadot,
        CY_beta=derivs.CY_beta,
        Cl_beta=derivs.Cl_beta,
        Cn_beta=derivs.Cn_beta,
        CY_p=derivs.CY_p,
        Cl_p=derivs.Cl_p,
        Cn_p=derivs.Cn_p,
        CY_r=derivs.CY_r,
        Cl_r=derivs.Cl_r,
        Cn_r=derivs.Cn_r,
        derivatives_estimated=True,
    )
