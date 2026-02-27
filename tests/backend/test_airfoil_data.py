"""Tests for backend/airfoil_data.py.

Covers:
- AIRFOIL_NAME_MAP completeness
- load_airfoil_constants for all 12 airfoils
- interpolate_section_aero return shape and value ranges
- Boundary clamping behavior
- get_available_airfoils()
"""

from __future__ import annotations

import math

import pytest

from backend.airfoil_data import (
    AIRFOIL_NAME_MAP,
    get_available_airfoils,
    interpolate_section_aero,
    load_airfoil_constants,
)


# ---------------------------------------------------------------------------
# All 12 CHENG airfoil variants (hyphenated + space forms)
# ---------------------------------------------------------------------------

ALL_HYPHENATED = [
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

ALL_SPACED = [
    "Flat Plate",
    "NACA 0006",
    "NACA 0009",
    "NACA 0012",
    "NACA 2412",
    "NACA 4412",
    "NACA 6412",
    "Clark Y",
    "Eppler 193",
    "Eppler 387",
    "Selig 1223",
    "AG 25",
]

_EXPECTED_KEYS = {"cl_alpha_per_rad", "cm_ac", "cl_max", "cd_min", "cl_at_cd_min"}

# Standard test condition
_RE = 300_000
_MACH = 0.05


# ---------------------------------------------------------------------------
# AIRFOIL_NAME_MAP tests
# ---------------------------------------------------------------------------


class TestAirfoilNameMap:
    """AIRFOIL_NAME_MAP completeness and correctness."""

    def test_contains_all_hyphenated_forms(self) -> None:
        """All 12 hyphenated forms must be in the name map."""
        for name in ALL_HYPHENATED:
            assert name in AIRFOIL_NAME_MAP, f"Missing hyphenated key: {name}"

    def test_contains_all_spaced_forms(self) -> None:
        """All 12 space-separated forms must be in the name map."""
        for name in ALL_SPACED:
            assert name in AIRFOIL_NAME_MAP, f"Missing spaced key: {name}"

    def test_map_has_expected_length(self) -> None:
        """Map should have exactly 24 entries (12 airfoils * 2 name forms)."""
        assert len(AIRFOIL_NAME_MAP) == 24

    def test_all_values_are_strings(self) -> None:
        """All map values (JSON file stems) must be non-empty strings."""
        for key, stem in AIRFOIL_NAME_MAP.items():
            assert isinstance(stem, str) and stem, f"Stem for '{key}' is not a non-empty string"


# ---------------------------------------------------------------------------
# load_airfoil_constants tests
# ---------------------------------------------------------------------------


class TestLoadAirfoilConstants:
    """load_airfoil_constants loads JSON and returns expected structure."""

    @pytest.mark.parametrize("name", ALL_HYPHENATED)
    def test_loads_all_12_airfoils_without_error(self, name: str) -> None:
        """Each of the 12 airfoils must load without exception."""
        doc = load_airfoil_constants(name)
        assert isinstance(doc, dict)

    def test_returns_conditions_list(self) -> None:
        """Loaded document must have a 'conditions' list with at least one entry."""
        doc = load_airfoil_constants("NACA-2412")
        assert "conditions" in doc
        assert isinstance(doc["conditions"], list)
        assert len(doc["conditions"]) > 0

    def test_conditions_have_required_fields(self) -> None:
        """Each condition entry must contain the 5 interpolated keys plus Re and Mach."""
        doc = load_airfoil_constants("NACA-2412")
        required = {"Re", "Mach", "cl_alpha_per_rad", "cm_ac", "cl_max", "cd_min", "cl_at_cd_min"}
        for cond in doc["conditions"]:
            for field in required:
                assert field in cond, f"Missing field '{field}' in condition: {cond}"

    def test_cache_returns_same_object(self) -> None:
        """Calling load twice returns the same cached object."""
        doc1 = load_airfoil_constants("Clark-Y")
        doc2 = load_airfoil_constants("Clark-Y")
        assert doc1 is doc2


# ---------------------------------------------------------------------------
# interpolate_section_aero tests
# ---------------------------------------------------------------------------


class TestInterpolateSectionAero:
    """interpolate_section_aero correctness, shape, and clamping."""

    def test_returns_all_5_keys(self) -> None:
        """Result must contain exactly the 5 expected keys."""
        result = interpolate_section_aero("NACA 2412", Re=_RE, Mach=_MACH)
        assert set(result.keys()) == _EXPECTED_KEYS

    def test_all_values_are_finite(self) -> None:
        """All returned values must be finite (no NaN, no inf)."""
        result = interpolate_section_aero("NACA 2412", Re=_RE, Mach=_MACH)
        for key, val in result.items():
            assert math.isfinite(val), f"Non-finite value for {key}: {val}"

    def test_cl_alpha_in_physical_range(self) -> None:
        """CL_alpha should be between 3 and 8 per rad for a lifting airfoil at low Mach."""
        result = interpolate_section_aero("NACA 2412", Re=_RE, Mach=_MACH)
        assert 3.0 < result["cl_alpha_per_rad"] < 8.0, (
            f"cl_alpha_per_rad = {result['cl_alpha_per_rad']} out of physical range"
        )

    def test_cl_max_positive(self) -> None:
        """CL_max must be positive for a lifting airfoil."""
        result = interpolate_section_aero("NACA 2412", Re=_RE, Mach=_MACH)
        assert result["cl_max"] > 0.0

    def test_cd_min_small_positive(self) -> None:
        """CD_min must be a small positive number (skin friction drag)."""
        result = interpolate_section_aero("NACA 2412", Re=_RE, Mach=_MACH)
        assert 0.001 < result["cd_min"] < 0.05

    def test_clamp_re_below_minimum_no_exception(self) -> None:
        """Re below grid minimum must be clamped without exception."""
        result = interpolate_section_aero("NACA 2412", Re=1.0, Mach=_MACH)
        for key, val in result.items():
            assert math.isfinite(val), f"Non-finite value for {key} at very low Re"

    def test_clamp_mach_above_maximum_no_exception(self) -> None:
        """Mach above grid maximum must be clamped without exception."""
        result = interpolate_section_aero("NACA 2412", Re=_RE, Mach=100.0)
        for key, val in result.items():
            assert math.isfinite(val), f"Non-finite value for {key} at very high Mach"

    def test_clamp_returns_boundary_not_nan(self) -> None:
        """Clamping at boundaries should return boundary values, not NaN."""
        result_low = interpolate_section_aero("Clark-Y", Re=1.0, Mach=0.001)
        result_high = interpolate_section_aero("Clark-Y", Re=1e9, Mach=99.0)
        for key in _EXPECTED_KEYS:
            assert math.isfinite(result_low[key]), f"NaN at low boundary for {key}"
            assert math.isfinite(result_high[key]), f"NaN at high boundary for {key}"

    @pytest.mark.parametrize("name", ALL_HYPHENATED)
    def test_all_12_airfoils_return_valid_values(self, name: str) -> None:
        """All 12 airfoils must return valid (non-NaN) values at standard conditions."""
        result = interpolate_section_aero(name, Re=_RE, Mach=_MACH)
        assert set(result.keys()) == _EXPECTED_KEYS
        for key, val in result.items():
            assert math.isfinite(val), f"Non-finite {key} for airfoil {name}"

    def test_hyphenated_and_spaced_names_match(self) -> None:
        """Hyphenated and space-separated names for the same airfoil should produce identical results."""
        r1 = interpolate_section_aero("NACA-4412", Re=_RE, Mach=_MACH)
        r2 = interpolate_section_aero("NACA 4412", Re=_RE, Mach=_MACH)
        for key in _EXPECTED_KEYS:
            assert r1[key] == pytest.approx(r2[key], rel=1e-9), (
                f"Mismatch for {key}: {r1[key]} vs {r2[key]}"
            )


# ---------------------------------------------------------------------------
# get_available_airfoils tests
# ---------------------------------------------------------------------------


class TestGetAvailableAirfoils:
    """get_available_airfoils() returns a usable list of stems."""

    def test_returns_non_empty_list(self) -> None:
        """get_available_airfoils() must return at least one entry."""
        result = get_available_airfoils()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_returns_12_airfoils(self) -> None:
        """Exactly 12 airfoil stems should be available."""
        result = get_available_airfoils()
        assert len(result) == 12, f"Expected 12, got {len(result)}: {result}"

    def test_stems_are_non_empty_strings(self) -> None:
        """All returned stems must be non-empty strings."""
        for stem in get_available_airfoils():
            assert isinstance(stem, str) and stem

    def test_naca2412_stem_present(self) -> None:
        """The naca2412 stem must be in the available list."""
        assert "naca2412" in get_available_airfoils()
