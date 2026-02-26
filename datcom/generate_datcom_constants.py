"""
DATCOM Constants Generator — Design Space Edition
==================================================
Processes airfoil .DAT files using NeuralFoil across a full design space of
speed, chord, and sweep conditions. Results are stored per unique (Re, Mach)
condition and are ready for 2D interpolation in DATCOM calculations.

Key insight: sweep, speed, and chord all reduce to two NeuralFoil inputs:
    V_eff  = V * cos(sweep)         [cosine rule for swept wings]
    Re     = rho * V_eff * chord / mu
    Mach   = V_eff / speed_of_sound

The script deduplicates (Re, Mach) pairs across the grid so NeuralFoil is
only called once per unique aerodynamic condition.

Usage:
    pip install neuralfoil numpy
    python generate_datcom_constants.py [options]

    # Use defaults matching your design space:
    python generate_datcom_constants.py --dat-dir ./airfoils --out-dir ./output

Output per airfoil: {airfoil_name}.constants.json
"""

import os
import sys
import json
import argparse
import glob
import math
import numpy as np
from itertools import product

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    import neuralfoil as nf
except ImportError:
    sys.exit(
        "ERROR: neuralfoil not found.\n"
        "Install with:  pip install neuralfoil"
    )

# ── Physical constants ────────────────────────────────────────────────────────
RHO_SL          = 1.225       # kg/m3  sea-level density
MU_SL           = 1.81e-5     # Pa.s   dynamic viscosity
SPEED_OF_SOUND  = 340.3       # m/s    sea-level

# ── Default design space — matches your stated envelope ──────────────────────
# These define the grid from which unique (Re, Mach) pairs are extracted.
# Adjust freely via CLI args or by editing the defaults below.

# Airspeed sample points [m/s]
DEFAULT_SPEEDS_MS   = [10, 20, 30, 40, 50, 60, 75, 100]

# Chord sample points [m]  (50mm to 500mm)
DEFAULT_CHORDS_M    = [0.05, 0.08, 0.12, 0.18, 0.25, 0.33, 0.42, 0.50]

# Sweep angle sample points [deg]  (-10 to 45)
DEFAULT_SWEEPS_DEG  = [-10, -5, 0, 5, 10, 15, 20, 25, 30, 35, 40, 45]

# ── Alpha sweep ───────────────────────────────────────────────────────────────
ALPHA_SWEEP         = np.linspace(-14.0, 24.0, 191)   # 0.2 deg steps
LINEAR_ALPHA_LOW    = -5.0    # degrees - bounds for linear-region fit
LINEAR_ALPHA_HIGH   =  10.0   # degrees

# ── Deduplication tolerance ───────────────────────────────────────────────────
# Two conditions are considered identical if both Re and Mach are within these
# fractions of each other. Reduces run count without losing coverage.
RE_BIN_TOLERANCE    = 0.04    # 4%  - same aero within ~+-2% Re
MACH_BIN_TOLERANCE  = 0.005   # absolute - Mach steps below this aren't distinct

# ── NeuralFoil model size ─────────────────────────────────────────────────────
NF_MODEL            = "xlarge"


# ── Aerodynamic helpers ───────────────────────────────────────────────────────

def effective_velocity(V: float, sweep_deg: float) -> float:
    """Component of V normal to the leading edge (cosine rule)."""
    return V * math.cos(math.radians(sweep_deg))


def reynolds(V_eff: float, chord: float) -> float:
    return (RHO_SL * V_eff * chord) / MU_SL


def mach_number(V_eff: float) -> float:
    return V_eff / SPEED_OF_SOUND


def bin_key(Re: float, Ma: float) -> tuple:
    """
    Discretise (Re, Mach) into bins for deduplication.
    Re is binned logarithmically; Mach is binned linearly.
    """
    re_bin   = round(math.log10(max(Re, 1e3)) / RE_BIN_TOLERANCE)
    mach_bin = round(Ma / MACH_BIN_TOLERANCE)
    return (re_bin, mach_bin)


def build_condition_grid(speeds, chords, sweeps) -> list:
    """
    Enumerate all (speed, chord, sweep) combos, compute (Re, Mach),
    deduplicate with binning, and return a list of unique conditions.
    Each entry also records which (speed, chord, sweep) triples map to it.
    """
    bins = {}

    for V, c, sw in product(speeds, chords, sweeps):
        V_eff = effective_velocity(V, sw)
        Re    = reynolds(V_eff, c)
        Ma    = mach_number(V_eff)

        # Skip unphysically low Re - NeuralFoil accuracy degrades below ~20k
        if Re < 20_000:
            continue
        # Skip supersonic
        if Ma >= 0.85:
            continue

        key = bin_key(Re, Ma)

        if key not in bins:
            bins[key] = {
                "Re":      Re,
                "Mach":    Ma,
                "sources": []
            }
        bins[key]["sources"].append({
            "speed_ms":   V,
            "chord_m":    c,
            "sweep_deg":  sw,
            "Re_exact":   round(Re, 1),
            "Mach_exact": round(Ma, 5),
        })

    # Sort by Re then Mach for readability
    conditions = sorted(bins.values(), key=lambda x: (x["Re"], x["Mach"]))
    return conditions


def fit_linear_region(alphas_deg: np.ndarray, cl: np.ndarray):
    """Returns (cl_alpha [/rad], alpha_zero_lift [deg])."""
    mask = (alphas_deg >= LINEAR_ALPHA_LOW) & (alphas_deg <= LINEAR_ALPHA_HIGH)
    if mask.sum() < 3:
        mask = np.ones(len(alphas_deg), dtype=bool)

    alphas_rad = np.radians(alphas_deg[mask])
    coeffs     = np.polyfit(alphas_rad, cl[mask], 1)
    cl_alpha   = float(coeffs[0])
    cl_0       = float(coeffs[1])

    alpha_zl = float(np.degrees(-cl_0 / cl_alpha)) if abs(cl_alpha) > 1e-6 else 0.0
    return cl_alpha, alpha_zl


def find_stall(alphas_deg: np.ndarray, cl: np.ndarray):
    idx = int(np.argmax(cl))
    return float(cl[idx]), float(alphas_deg[idx])


def mean_linear(alphas_deg: np.ndarray, values: np.ndarray) -> float:
    mask = (alphas_deg >= LINEAR_ALPHA_LOW) & (alphas_deg <= LINEAR_ALPHA_HIGH)
    return float(np.mean(values[mask])) if mask.sum() > 0 else float(np.mean(values))


def cd_min_point(cl: np.ndarray, cd: np.ndarray):
    idx = int(np.argmin(cd))
    return float(cd[idx]), float(cl[idx])


# ── Core processing ───────────────────────────────────────────────────────────

def prandtl_glauert(value: float, mach: float) -> float:
    """
    Apply Prandtl-Glauert compressibility correction: value / sqrt(1 - Mach^2).
    Valid for Mach < ~0.7. Corrects cl_alpha and cl values upward with speed.
    """
    if mach >= 0.7:
        mach = 0.699  # clamp — PG diverges near M=1
    return value / math.sqrt(1.0 - mach ** 2)


def run_condition(dat_path: str, Re: float, Ma: float) -> dict:
    """
    Run NeuralFoil for one (Re, Mach) condition across the full alpha sweep.
    NeuralFoil has no mach parameter (incompressible solver); Prandtl-Glauert
    correction is applied post-hoc to cl_alpha and the full CL polar.
    Returns a dict of extracted aerodynamic constants + full polar.
    """
    aero = nf.get_aero_from_dat_file(
        filename   = dat_path,
        alpha      = ALPHA_SWEEP,
        Re         = Re,
        model_size = NF_MODEL,
    )

    # Raw incompressible results from NeuralFoil
    cl_inc = np.array(aero["CL"])
    cd     = np.array(aero["CD"])
    cm     = np.array(aero["CM"])

    # Apply Prandtl-Glauert compressibility correction to CL (not CD or CM)
    # At Mach 0.29 (100 m/s) this is ~+4%; at Mach 0.15 (~50 m/s) its ~+1%
    pg_factor = 1.0 / math.sqrt(max(1.0 - Ma ** 2, 0.01))
    cl = cl_inc * pg_factor

    cl_alpha, alpha_zl  = fit_linear_region(ALPHA_SWEEP, cl)
    cl_max, alpha_stall = find_stall(ALPHA_SWEEP, cl)
    cm_ac               = mean_linear(ALPHA_SWEEP, cm)
    cd_min, cl_cd_min   = cd_min_point(cl, cd)

    return {
        # ── DATCOM inputs ────────────────────────────────────────────────────
        "cl_alpha_per_rad":    round(cl_alpha, 5),
        "cl_alpha_per_deg":    round(cl_alpha / 57.2958, 6),
        "alpha_zero_lift_deg": round(alpha_zl, 4),
        "cm_ac":               round(cm_ac, 5),
        # ── Stall ────────────────────────────────────────────────────────────
        "cl_max":              round(cl_max, 4),
        "alpha_stall_deg":     round(alpha_stall, 2),
        # ── Drag ─────────────────────────────────────────────────────────────
        "cd_min":              round(cd_min, 6),
        "cl_at_cd_min":        round(cl_cd_min, 4),
        # ── Full polar for nonlinear interpolation ────────────────────────────
        "polar": {
            "alpha_deg": [round(a, 2)  for a in ALPHA_SWEEP.tolist()],
            "cl":        [round(v, 5)  for v in cl.tolist()],
            "cd":        [round(v, 6)  for v in cd.tolist()],
            "cm":        [round(v, 5)  for v in cm.tolist()],
        }
    }


def process_airfoil(dat_path: str, conditions: list) -> dict:
    """Run all conditions for one airfoil and assemble the output document."""
    airfoil_name = os.path.splitext(os.path.basename(dat_path))[0]
    n            = len(conditions)

    print(f"\n{'─'*60}")
    print(f"  Airfoil : {airfoil_name}")
    print(f"  Running : {n} unique (Re, Mach) conditions")
    print(f"{'─'*60}")

    # ── Smoke test: run one condition first so errors surface immediately ─────
    test_cond = conditions[len(conditions) // 2]  # pick middle condition
    try:
        run_condition(dat_path, test_cond["Re"], test_cond["Mach"])
    except Exception as e:
        import traceback
        print(f"\n  *** SMOKE TEST FAILED — aborting this airfoil ***")
        print(f"  Condition: Re={test_cond['Re']:.0f}, Mach={test_cond['Mach']:.4f}")
        traceback.print_exc()
        raise RuntimeError(f"Smoke test failed: {e}") from e

    grid_results = []
    failures     = 0
    first_error  = None

    for i, cond in enumerate(conditions):
        Re = cond["Re"]
        Ma = cond["Mach"]

        try:
            result = run_condition(dat_path, Re, Ma)
            grid_results.append({
                "Re":      round(Re, 1),
                "Mach":    round(Ma, 5),
                "sources": cond["sources"],
                **result
            })

            if (i + 1) % 10 == 0 or (i + 1) == n:
                print(f"  [{i+1:>3}/{n}]  Re={Re:>10,.0f}  Mach={Ma:.4f}  "
                      f"cl_a={result['cl_alpha_per_rad']:.3f}/rad  "
                      f"cl_max={result['cl_max']:.3f}")

        except Exception as e:
            failures += 1
            if first_error is None:
                first_error = str(e)
                import traceback
                print(f"\n  *** FIRST FAILURE (Re={Re:.0f}, Mach={Ma:.4f}) ***")
                traceback.print_exc()

    print(f"\n  Done: {len(grid_results)} succeeded, {failures} failed")

    if not grid_results:
        raise RuntimeError(
            f"All {failures} conditions failed. Root cause: {first_error}"
        )

    re_vals   = sorted(set(round(r["Re"],   -2) for r in grid_results))
    mach_vals = sorted(set(round(r["Mach"],  3) for r in grid_results))

    return {
        "airfoil":     airfoil_name,
        "source_file": os.path.abspath(dat_path),
        "generation": {
            "tool":               "NeuralFoil",
            "model_size":         NF_MODEL,
            "total_conditions":   len(grid_results),
            "alpha_sweep": {
                "start_deg": float(ALPHA_SWEEP[0]),
                "stop_deg":  float(ALPHA_SWEEP[-1]),
                "step_deg":  round(float(ALPHA_SWEEP[1] - ALPHA_SWEEP[0]), 3),
                "count":     len(ALPHA_SWEEP),
            },
        },
        "interpolation_notes": {
            "how_to_use": (
                "For a given (speed, chord, sweep): "
                "V_eff = speed * cos(sweep_rad), "
                "Re = 1.225 * V_eff * chord / 1.81e-5, "
                "Mach = V_eff / 340.3. "
                "Then 2D-interpolate cl_alpha_per_rad, cm_ac, etc. over (Re, Mach)."
            ),
            "recommended_interpolator": "scipy.interpolate.RegularGridInterpolator or griddata",
            "re_range":          [round(min(re_vals), 0), round(max(re_vals), 0)],
            "mach_range":        [round(min(mach_vals), 4), round(max(mach_vals), 4)],
            "unique_re_points":  len(re_vals),
            "unique_mach_points": len(mach_vals),
        },
        "datcom_field_notes": {
            "cl_alpha_per_rad":    "Section lift slope - replaces 2pi in CL_alpha, de/da, Cmq, Clp",
            "alpha_zero_lift_deg": "Alpha where CL=0 - used in twist/incidence correction terms",
            "cm_ac":               "Pitching moment at aerodynamic centre - feeds Cm0 and NP calculations",
            "cl_max":              "Maximum section CL - used to estimate 3D wing stall margin",
            "cd_min":              "Minimum drag - baseline for drag buildup",
        },
        "conditions": grid_results,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_float_list(s: str) -> list:
    return [float(x.strip()) for x in s.split(",")]


def main():
    parser = argparse.ArgumentParser(
        description="Generate DATCOM aerodynamic constants across a full design-space grid."
    )
    parser.add_argument("--dat-dir",  default=".",
                        help="Directory containing .dat files (default: .)")
    parser.add_argument("--out-dir",  default=".",
                        help="Output directory for .constants.json files (default: .)")
    parser.add_argument("--speeds",   default=None,
                        help="Comma-separated airspeeds in m/s "
                             "(default: 10,20,30,40,50,60,75,100)")
    parser.add_argument("--chords",   default=None,
                        help="Comma-separated chord lengths in m "
                             "(default: 0.05,0.08,0.12,0.18,0.25,0.33,0.42,0.50)")
    parser.add_argument("--sweeps",   default=None,
                        help="Comma-separated sweep angles in degrees "
                             "(default: -10,-5,0,5,10,15,20,25,30,35,40,45)")
    args = parser.parse_args()

    speeds = parse_float_list(args.speeds) if args.speeds else DEFAULT_SPEEDS_MS
    chords = parse_float_list(args.chords) if args.chords else DEFAULT_CHORDS_M
    sweeps = parse_float_list(args.sweeps) if args.sweeps else DEFAULT_SWEEPS_DEG

    dat_files = sorted(glob.glob(os.path.join(args.dat_dir, "*.dat")))
    if not dat_files:
        dat_files = sorted(glob.glob(os.path.join(args.dat_dir, "*.DAT")))
    if not dat_files:
        sys.exit(f"ERROR: No .dat files found in '{args.dat_dir}'")

    os.makedirs(args.out_dir, exist_ok=True)

    # ── Build condition grid once — shared across all airfoils ────────────────
    print(f"\n{'='*60}")
    print(f"  DATCOM Constants Generator - Design Space Edition")
    print(f"{'='*60}")
    print(f"  Speed range  : {min(speeds)}-{max(speeds)} m/s  ({len(speeds)} points)")
    print(f"  Chord range  : {min(chords)*1000:.0f}-{max(chords)*1000:.0f} mm  ({len(chords)} points)")
    print(f"  Sweep range  : {min(sweeps)}-{max(sweeps)} deg  ({len(sweeps)} points)")
    print(f"  Raw grid     : {len(speeds)*len(chords)*len(sweeps):,} combinations")

    conditions = build_condition_grid(speeds, chords, sweeps)

    re_vals   = [c["Re"]   for c in conditions]
    mach_vals = [c["Mach"] for c in conditions]
    print(f"  Unique (Re, Mach) after dedup : {len(conditions)}")
    print(f"  Re range     : {min(re_vals):,.0f} - {max(re_vals):,.0f}")
    print(f"  Mach range   : {min(mach_vals):.4f} - {max(mach_vals):.4f}")
    print(f"  Airfoils     : {len(dat_files)}")
    print(f"  Output dir   : {os.path.abspath(args.out_dir)}")

    successes, failures = [], []

    for dat_path in dat_files:
        airfoil_name = os.path.splitext(os.path.basename(dat_path))[0]
        out_path     = os.path.join(args.out_dir, f"{airfoil_name}.constants.json")

        try:
            result = process_airfoil(dat_path, conditions)
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)
            print(f"\n  Saved -> {out_path}")
            successes.append(airfoil_name)

        except Exception as e:
            print(f"\n  FAILED: {airfoil_name}  ->  {e}")
            failures.append((airfoil_name, str(e)))

    print(f"\n{'='*60}")
    print(f"  Complete: {len(successes)} succeeded, {len(failures)} failed")
    if failures:
        for name, err in failures:
            print(f"    x {name}: {err}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()