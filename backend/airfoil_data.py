"""
backend/airfoil_data.py

Loads and caches pre-computed NeuralFoil section aerodynamic data from
datcom/*.constants.json files. Implements interpolation on the scattered
(Re, Mach) points using the k-nearest-neighbor inverse-distance-weighted
method in (log Re, Mach) space.

Usage:
    from backend.airfoil_data import interpolate_section_aero
    result = interpolate_section_aero("NACA-2412", Re=300000, Mach=0.05)
    # result: {"cl_alpha_per_rad": ..., "cm_ac": ..., "cl_max": ...,
    #          "cd_min": ..., "cl_at_cd_min": ...}
"""

import json
import math
import pathlib

# --------------------------------------------------------------------------
# Module-level cache: stem -> full JSON document + processed grid arrays
# --------------------------------------------------------------------------
_AIRFOIL_CACHE: dict[str, dict] = {}
_PROCESSED_CACHE: dict[str, dict] = {}

# --------------------------------------------------------------------------
# Mapping from CHENG display names and frontend-hyphenated forms to JSON stems
# --------------------------------------------------------------------------
AIRFOIL_NAME_MAP: dict[str, str] = {
    # Flat plate
    "Flat-Plate": "flat_plate",
    "Flat Plate": "flat_plate",
    # NACA 0006
    "NACA-0006": "naca0006",
    "NACA 0006": "naca0006",
    # NACA 0009
    "NACA-0009": "naca0009",
    "NACA 0009": "naca0009",
    # NACA 0012
    "NACA-0012": "naca0012",
    "NACA 0012": "naca0012",
    # NACA 2412
    "NACA-2412": "naca2412",
    "NACA 2412": "naca2412",
    # NACA 4412
    "NACA-4412": "naca4412",
    "NACA 4412": "naca4412",
    # NACA 6412
    "NACA-6412": "naca6412",
    "NACA 6412": "naca6412",
    # Clark Y
    "Clark-Y": "clark_y",
    "Clark Y": "clark_y",
    # Eppler 193
    "Eppler-193": "eppler193",
    "Eppler 193": "eppler193",
    # Eppler 387
    "Eppler-387": "eppler387",
    "Eppler 387": "eppler387",
    # Selig 1223
    "Selig-1223": "selig1223",
    "Selig 1223": "selig1223",
    # AG-25
    "AG-25": "ag25",
    "AG 25": "ag25",
}

# Keys to interpolate from each condition record
_INTERPOLATED_KEYS = ("cl_alpha_per_rad", "cm_ac", "cl_max", "cd_min", "cl_at_cd_min")

# Path to datcom directory
_DATCOM_DIR = pathlib.Path(__file__).parent.parent / "datcom"

# Number of nearest neighbors for IDW interpolation
_K_NEIGHBORS = 4


def _stem_for_name(airfoil_name: str) -> str:
    """Resolve airfoil display/hyphenated name to JSON file stem."""
    stem = AIRFOIL_NAME_MAP.get(airfoil_name)
    if stem is None:
        # Try case-insensitive lookup
        lower = airfoil_name.lower()
        for k, v in AIRFOIL_NAME_MAP.items():
            if k.lower() == lower:
                return v
        raise KeyError(
            f"Unknown airfoil name '{airfoil_name}'. "
            f"Known names: {sorted(AIRFOIL_NAME_MAP.keys())}"
        )
    return stem


def load_airfoil_constants(airfoil_name: str) -> dict:
    """Load and cache the full constants JSON for the named airfoil.

    Args:
        airfoil_name: CHENG display name or hyphenated frontend name,
                      e.g. "NACA-2412", "Clark-Y", "Eppler-387".

    Returns:
        The full parsed JSON document as a dict.

    Raises:
        KeyError: if airfoil_name is not in AIRFOIL_NAME_MAP.
        FileNotFoundError: if the JSON file does not exist in datcom/.
    """
    stem = _stem_for_name(airfoil_name)
    if stem not in _AIRFOIL_CACHE:
        json_path = _DATCOM_DIR / f"{stem}.constants.json"
        with open(json_path, "r", encoding="utf-8") as fh:
            _AIRFOIL_CACHE[stem] = json.load(fh)
    return _AIRFOIL_CACHE[stem]


def get_available_airfoils() -> list[str]:
    """Return list of canonical JSON stems available in datcom/."""
    return sorted(
        p.name.replace(".constants.json", "")
        for p in _DATCOM_DIR.glob("*.constants.json")
    )


def _get_processed(stem: str) -> dict:
    """Build and cache the processed point arrays for a given stem.

    Returns dict with:
        log_re_arr: list[float]   — log(Re) for each condition
        mach_arr: list[float]     — Mach for each condition
        values: dict[str, list[float]]  — interpolated key values per condition
        re_range: tuple[float, float]   — (min_re, max_re)
        mach_range: tuple[float, float] — (min_mach, max_mach)
        mach_scale: float               — scale factor to normalize mach to log-Re units
    """
    if stem in _PROCESSED_CACHE:
        return _PROCESSED_CACHE[stem]

    doc = _AIRFOIL_CACHE[stem]
    conditions = doc["conditions"]

    log_re_arr = [math.log(c["Re"]) for c in conditions]
    mach_arr = [c["Mach"] for c in conditions]

    # Compute scale factor: normalize Mach range to log-Re range so both axes
    # contribute equally to the distance metric.
    min_log_re = min(log_re_arr)
    max_log_re = max(log_re_arr)
    min_mach = min(mach_arr)
    max_mach = max(mach_arr)

    log_re_span = max_log_re - min_log_re
    mach_span = max_mach - min_mach

    # mach_scale converts mach to equivalent log-re units
    mach_scale = log_re_span / mach_span if mach_span > 0 else 1.0

    values: dict[str, list[float]] = {k: [] for k in _INTERPOLATED_KEYS}
    for c in conditions:
        for k in _INTERPOLATED_KEYS:
            values[k].append(c[k])

    processed = {
        "log_re_arr": log_re_arr,
        "mach_arr": mach_arr,
        "values": values,
        "re_range": (min(c["Re"] for c in conditions), max(c["Re"] for c in conditions)),
        "mach_range": (min_mach, max_mach),
        "mach_scale": mach_scale,
        "min_log_re": min_log_re,
        "max_log_re": max_log_re,
    }
    _PROCESSED_CACHE[stem] = processed
    return processed


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value to [lo, hi]."""
    return max(lo, min(hi, value))


def interpolate_section_aero(
    airfoil_name: str,
    Re: float,
    Mach: float,
) -> dict[str, float]:
    """Interpolate section aerodynamic constants at (Re, Mach).

    Uses k-nearest-neighbor inverse-distance-weighted interpolation in the
    normalized (log Re, Mach) space. The Mach axis is scaled to match the
    log-Re range so both dimensions contribute proportionally.

    If Re/Mach is outside the grid bounds, clamps to the nearest boundary
    (returns boundary values — no exception, no NaN).

    Args:
        airfoil_name: CHENG airfoil name (e.g. "NACA-2412", "Clark-Y").
        Re: Reynolds number (e.g. 300000). Must be > 0.
        Mach: Mach number (e.g. 0.05). Must be > 0.

    Returns:
        dict with keys: cl_alpha_per_rad, cm_ac, cl_max, cd_min, cl_at_cd_min.
        All values are finite floats.
    """
    doc = load_airfoil_constants(airfoil_name)
    stem = _stem_for_name(airfoil_name)
    proc = _get_processed(stem)

    log_re_arr = proc["log_re_arr"]
    mach_arr = proc["mach_arr"]
    values = proc["values"]
    mach_scale = proc["mach_scale"]

    # Clamp query to grid bounds
    min_re, max_re = proc["re_range"]
    min_mach, max_mach = proc["mach_range"]
    re_clamped = _clamp(Re, min_re, max_re)
    mach_clamped = _clamp(Mach, min_mach, max_mach)

    log_re_q = math.log(re_clamped)
    mach_q = mach_clamped

    n = len(log_re_arr)
    k = min(_K_NEIGHBORS, n)

    # Compute squared distances in normalized (log_re, scaled_mach) space
    dists: list[tuple[float, int]] = []
    for i in range(n):
        d_lr = log_re_q - log_re_arr[i]
        d_m = (mach_q - mach_arr[i]) * mach_scale
        dist2 = d_lr * d_lr + d_m * d_m
        dists.append((dist2, i))

    # Sort by distance, take k nearest
    dists.sort(key=lambda x: x[0])
    nearest = dists[:k]

    # Check for exact match
    if nearest[0][0] < 1e-14:
        idx = nearest[0][1]
        return {key: values[key][idx] for key in _INTERPOLATED_KEYS}

    # Inverse-distance-weighted interpolation
    weights = [1.0 / max(d2, 1e-30) for d2, _ in nearest]
    total_weight = sum(weights)

    result: dict[str, float] = {}
    for key in _INTERPOLATED_KEYS:
        val_arr = values[key]
        weighted_sum = sum(weights[j] * val_arr[nearest[j][1]] for j in range(k))
        result[key] = weighted_sum / total_weight

    return result
