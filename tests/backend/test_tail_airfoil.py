"""Tests for tail surface airfoil selection (Issue #217 — T23).

Verifies:
  - NACA-0006 and NACA-0009 .dat files exist and parse correctly
  - TailAirfoil field defaults to NACA-0012
  - All four tail airfoil options are accepted by AircraftDesign
  - airfoil.py TAIL_AIRFOILS list contains all four expected options
  - SUPPORTED_AIRFOILS includes NACA-0006 and NACA-0009
  - load_airfoil() succeeds for NACA-0006 and NACA-0009
"""

from __future__ import annotations

import pytest

from backend.models import AircraftDesign
from backend.geometry.airfoil import load_airfoil, SUPPORTED_AIRFOILS, TAIL_AIRFOILS


# ---------------------------------------------------------------------------
# TAIL_AIRFOILS constant
# ---------------------------------------------------------------------------


class TestTailAirfoilsConstant:
    """TAIL_AIRFOILS exported from airfoil.py must contain all four options."""

    def test_tail_airfoils_contains_flat_plate(self) -> None:
        assert "Flat-Plate" in TAIL_AIRFOILS

    def test_tail_airfoils_contains_naca_0006(self) -> None:
        assert "NACA-0006" in TAIL_AIRFOILS

    def test_tail_airfoils_contains_naca_0009(self) -> None:
        assert "NACA-0009" in TAIL_AIRFOILS

    def test_tail_airfoils_contains_naca_0012(self) -> None:
        assert "NACA-0012" in TAIL_AIRFOILS

    def test_tail_airfoils_has_four_entries(self) -> None:
        assert len(TAIL_AIRFOILS) == 4

    def test_all_tail_airfoils_in_supported_airfoils(self) -> None:
        """Every tail airfoil must be in the global SUPPORTED_AIRFOILS list."""
        for a in TAIL_AIRFOILS:
            assert a in SUPPORTED_AIRFOILS, f"{a!r} in TAIL_AIRFOILS but not SUPPORTED_AIRFOILS"


# ---------------------------------------------------------------------------
# NACA-0006 and NACA-0009 dat files
# ---------------------------------------------------------------------------


class TestNacaDatFiles:
    """NACA-0006 and NACA-0009 .dat files must be present and parseable."""

    def test_naca_0006_loads_successfully(self) -> None:
        pts = load_airfoil("NACA-0006")
        assert len(pts) >= 10, "Expected at least 10 coordinate pairs"

    def test_naca_0009_loads_successfully(self) -> None:
        pts = load_airfoil("NACA-0009")
        assert len(pts) >= 10, "Expected at least 10 coordinate pairs"

    def test_naca_0006_is_symmetric(self) -> None:
        """NACA-0006 is a symmetric airfoil: y values should span +/- range."""
        pts = load_airfoil("NACA-0006")
        ys = [p[1] for p in pts]
        assert max(ys) > 0, "Upper surface y-values should be positive"
        assert min(ys) < 0, "Lower surface y-values should be negative"

    def test_naca_0009_is_symmetric(self) -> None:
        """NACA-0009 is a symmetric airfoil: y values should span +/- range."""
        pts = load_airfoil("NACA-0009")
        ys = [p[1] for p in pts]
        assert max(ys) > 0, "Upper surface y-values should be positive"
        assert min(ys) < 0, "Lower surface y-values should be negative"

    def test_naca_0006_thinner_than_0009(self) -> None:
        """NACA-0006 maximum thickness should be less than NACA-0009."""
        pts_06 = load_airfoil("NACA-0006")
        pts_09 = load_airfoil("NACA-0009")
        max_y_06 = max(p[1] for p in pts_06)
        max_y_09 = max(p[1] for p in pts_09)
        assert max_y_06 < max_y_09, (
            f"NACA-0006 max thickness ({max_y_06:.4f}) should be less than "
            f"NACA-0009 ({max_y_09:.4f})"
        )

    def test_naca_0009_thinner_than_0012(self) -> None:
        """NACA-0009 maximum thickness should be less than NACA-0012."""
        pts_09 = load_airfoil("NACA-0009")
        pts_12 = load_airfoil("NACA-0012")
        max_y_09 = max(p[1] for p in pts_09)
        max_y_12 = max(p[1] for p in pts_12)
        assert max_y_09 < max_y_12, (
            f"NACA-0009 max thickness ({max_y_09:.4f}) should be less than "
            f"NACA-0012 ({max_y_12:.4f})"
        )

    def test_naca_0006_x_range(self) -> None:
        """NACA-0006 x coordinates should span [0, 1] (unit chord)."""
        pts = load_airfoil("NACA-0006")
        xs = [p[0] for p in pts]
        assert min(xs) == pytest.approx(0.0, abs=1e-4)
        assert max(xs) == pytest.approx(1.0, abs=1e-4)

    def test_naca_0009_x_range(self) -> None:
        """NACA-0009 x coordinates should span [0, 1] (unit chord)."""
        pts = load_airfoil("NACA-0009")
        xs = [p[0] for p in pts]
        assert min(xs) == pytest.approx(0.0, abs=1e-4)
        assert max(xs) == pytest.approx(1.0, abs=1e-4)


# ---------------------------------------------------------------------------
# AircraftDesign model — tail_airfoil field
# ---------------------------------------------------------------------------


class TestAircraftDesignTailAirfoil:
    """AircraftDesign.tail_airfoil field default and accepted values."""

    def test_default_tail_airfoil_is_naca_0012(self) -> None:
        """Backward compatibility: default tail_airfoil must be NACA-0012."""
        design = AircraftDesign()
        assert design.tail_airfoil == "NACA-0012"

    def test_tail_airfoil_accepts_naca_0006(self) -> None:
        design = AircraftDesign(tail_airfoil="NACA-0006")
        assert design.tail_airfoil == "NACA-0006"

    def test_tail_airfoil_accepts_naca_0009(self) -> None:
        design = AircraftDesign(tail_airfoil="NACA-0009")
        assert design.tail_airfoil == "NACA-0009"

    def test_tail_airfoil_accepts_naca_0012(self) -> None:
        design = AircraftDesign(tail_airfoil="NACA-0012")
        assert design.tail_airfoil == "NACA-0012"

    def test_tail_airfoil_accepts_flat_plate(self) -> None:
        design = AircraftDesign(tail_airfoil="Flat-Plate")
        assert design.tail_airfoil == "Flat-Plate"

    def test_tail_airfoil_rejects_invalid(self) -> None:
        """Pydantic should reject unknown airfoil names."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AircraftDesign(tail_airfoil="Clark-Y")  # type: ignore[arg-type]

    def test_tail_airfoil_camelcase_alias(self) -> None:
        """Model should accept tailAirfoil (camelCase) via populate_by_name."""
        design = AircraftDesign(**{"tailAirfoil": "NACA-0006"})
        assert design.tail_airfoil == "NACA-0006"

    def test_tail_airfoil_in_model_dump(self) -> None:
        """tail_airfoil must be present in model dump."""
        design = AircraftDesign(tail_airfoil="NACA-0009")
        d = design.model_dump()
        assert "tail_airfoil" in d
        assert d["tail_airfoil"] == "NACA-0009"

    def test_tail_airfoil_camelcase_in_model_dump_by_alias(self) -> None:
        """tailAirfoil must appear in camelCase dump (for frontend)."""
        design = AircraftDesign(tail_airfoil="NACA-0009")
        d = design.model_dump(by_alias=True)
        assert "tailAirfoil" in d
        assert d["tailAirfoil"] == "NACA-0009"


# ---------------------------------------------------------------------------
# SUPPORTED_AIRFOILS extension
# ---------------------------------------------------------------------------


class TestSupportedAirfoils:
    """NACA-0006 and NACA-0009 must be in SUPPORTED_AIRFOILS."""

    def test_naca_0006_in_supported(self) -> None:
        assert "NACA-0006" in SUPPORTED_AIRFOILS

    def test_naca_0009_in_supported(self) -> None:
        assert "NACA-0009" in SUPPORTED_AIRFOILS

    def test_naca_0012_still_in_supported(self) -> None:
        """Existing NACA-0012 must remain supported (backward compatibility)."""
        assert "NACA-0012" in SUPPORTED_AIRFOILS
