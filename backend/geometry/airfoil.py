"""Airfoil profile loader -- reads .dat files and returns normalised coordinates.

Supports Selig-format .dat files (header line + x y pairs).
Special case: "Flat-Plate" can use the .dat file or generate programmatically.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default dir is the repo-level airfoils/ folder; in Docker this is /app/airfoils.
# Can be overridden via the CHENG_AIRFOIL_DIR environment variable.
AIRFOIL_DIR: str = os.environ.get(
    "CHENG_AIRFOIL_DIR",
    str(Path(__file__).resolve().parent.parent.parent / "airfoils"),
)

SUPPORTED_AIRFOILS: list[str] = [
    "Flat-Plate",
    "NACA-0006",
    "NACA-0009",
    "NACA-0012",
    "NACA-2412",
    "NACA-4412",
    "NACA-6412",
    "Clark-Y",
    "Eppler-193",
    "Eppler-387",
    "Selig-1223",
    "AG-25",
]

# Symmetric airfoils suitable for tail surfaces (low-drag, symmetric profiles).
# NACA-0012 is kept as the default for backward compatibility.
TAIL_AIRFOILS: list[str] = [
    "Flat-Plate",
    "NACA-0006",
    "NACA-0009",
    "NACA-0012",
]

# Map display name -> filename on disk.
# NOTE: NACA files have NO underscore (matches actual files in airfoils/).
_NAME_TO_FILE: dict[str, str] = {
    "Flat-Plate": "flat_plate.dat",
    "NACA-0006": "naca0006.dat",
    "NACA-0009": "naca0009.dat",
    "NACA-0012": "naca0012.dat",
    "NACA-2412": "naca2412.dat",
    "NACA-4412": "naca4412.dat",
    "NACA-6412": "naca6412.dat",
    "Clark-Y": "clark_y.dat",
    "Eppler-193": "eppler193.dat",
    "Eppler-387": "eppler387.dat",
    "Selig-1223": "selig1223.dat",
    "AG-25": "ag25.dat",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_airfoil(name: str) -> list[tuple[float, float]]:
    """Load an airfoil profile from a .dat file.

    File lookup uses the explicit ``_NAME_TO_FILE`` mapping.  Fallback:
    lowercase the name, replace hyphens with underscores, and append ".dat".

    Parses Selig format: first line is the airfoil name, remaining lines are
    ``x  y`` coordinate pairs.  Lines that cannot be parsed as two floats are
    silently skipped (handles blank lines & multi-word headers).

    Returns coordinates in Selig order: TE upper -> LE -> TE lower.
    Normalised to unit chord (x in [0, 1]).  Minimum 10 points enforced.

    Special case: "Flat-Plate" uses the programmatic ``generate_flat_plate()``
    generator instead of the .dat file.  The .dat file only achieves 3% total
    thickness (1.5% per surface), which is insufficient for stable CadQuery
    lofting in combination with sweep, taper, or incidence.  The programmatic
    profile guarantees a 6% diamond cross-section that is geometrically robust
    across all parameter combinations, and requires no file I/O.

    Args:
        name: Display name of the airfoil (e.g. "Clark-Y", "NACA-2412").

    Returns:
        List of (x, y) tuples normalised to unit chord.

    Raises:
        FileNotFoundError: If .dat file not found.
        ValueError: If fewer than 10 valid coordinate pairs, or name unsupported.
    """
    if name not in SUPPORTED_AIRFOILS:
        raise ValueError(
            f"Unsupported airfoil '{name}'. "
            f"Supported: {', '.join(SUPPORTED_AIRFOILS)}"
        )

    # Flat-Plate: use programmatic generator instead of the .dat file.
    # flat_plate.dat is only 3% total thickness (1.5% per surface).  Under
    # sweep, taper, or high incidence, this thin profile can produce an invalid
    # or degenerate loft solid in CadQuery.  generate_flat_plate() produces a
    # 6% diamond that is robust across all parameter combinations.
    if name == "Flat-Plate":
        return generate_flat_plate()

    # Resolve filename via explicit map, with fallback
    filename = _NAME_TO_FILE.get(name)
    if filename is None:
        filename = name.lower().replace("-", "_") + ".dat"

    filepath = Path(AIRFOIL_DIR) / filename
    if not filepath.is_file():
        raise FileNotFoundError(
            f"Airfoil data file not found: {filepath} (for airfoil '{name}')"
        )

    raw_text = filepath.read_text(encoding="utf-8", errors="replace")
    points = _parse_selig(raw_text)

    if len(points) < 10:
        raise ValueError(
            f"Airfoil '{name}' has only {len(points)} coordinate pairs "
            f"(minimum 10 required). File: {filepath}"
        )

    points = _normalise_to_unit_chord(points)
    return points


def generate_flat_plate(num_points: int = 65) -> list[tuple[float, float]]:
    """Generate a programmatic diamond/flat-plate profile at 3% max thickness.

    The profile is a symmetric diamond: max thickness at x = 0.5,
    zero at LE (x = 0) and TE (x = 1).

    Upper surface:  y =  0.03 * (1 - |2x - 1|)   (linear ramp)
    Lower surface:  y = -0.03 * (1 - |2x - 1|)   (mirror)

    Returns Selig-order coordinates: TE upper -> LE -> TE lower.

    Args:
        num_points: Total number of coordinate pairs (split between upper
                    and lower).  Must be >= 10.

    Returns:
        List of (x, y) tuples for a 3% diamond profile, unit chord.
    """
    if num_points < 10:
        raise ValueError(f"num_points must be >= 10, got {num_points}")

    half = num_points // 2

    upper: list[tuple[float, float]] = []
    lower: list[tuple[float, float]] = []

    # Upper surface: TE (x=1) -> LE (x=0)  [Selig upper order]
    for i in range(half + 1):
        x = 1.0 - i / half
        y = 0.03 * (1.0 - abs(2.0 * x - 1.0))
        upper.append((x, y))

    # Lower surface: LE (x~0) -> TE (x=1)  [Selig lower order, skip LE duplicate]
    for i in range(1, half + 1):
        x = i / half
        y = -0.03 * (1.0 - abs(2.0 * x - 1.0))
        lower.append((x, y))

    return upper + lower


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_COORD_RE = re.compile(
    r"^\s*([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)"
    r"\s+"
    r"([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)\s*$"
)


def _parse_selig(text: str) -> list[tuple[float, float]]:
    """Parse Selig-format airfoil data.

    Selig format:
        Line 1:  Name (text header -- skipped)
        Lines 2+:  x  y  coordinate pairs

    Lines that don't match the ``x y`` pattern are silently skipped.
    This handles blank lines, multi-word headers, and comment lines.
    """
    points: list[tuple[float, float]] = []
    for line in text.splitlines():
        m = _COORD_RE.match(line)
        if m:
            x = float(m.group(1))
            y = float(m.group(2))
            points.append((x, y))
    return points


def _normalise_to_unit_chord(
    points: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Scale coordinates so that x spans [0, 1]."""
    if not points:
        return points

    xs = [p[0] for p in points]
    x_min = min(xs)
    x_max = max(xs)
    chord = x_max - x_min

    if chord <= 0:
        return points  # degenerate -- return as-is

    if abs(chord - 1.0) < 1e-6 and abs(x_min) < 1e-6:
        return points  # already normalised

    return [((p[0] - x_min) / chord, p[1] / chord) for p in points]
