"""Tests for #264 — _estimate_weight_kg() computed exactly once per compute_warnings().

The refactor passes a pre-computed weight_kg to _check_v09, _check_v12, and
_check_v13 instead of each calling _estimate_weight_kg() internally.  These
tests verify the call count is 1 per compute_warnings() invocation and that
the weight value propagates correctly into each check.
"""

from __future__ import annotations

from unittest.mock import patch, call

import pytest

from backend.models import AircraftDesign
from backend import validation
from backend.validation import compute_warnings, _estimate_weight_kg


class TestWeightComputedOnce:
    """_estimate_weight_kg() must be called exactly once per compute_warnings() call."""

    def test_weight_called_once_per_compute_warnings(self) -> None:
        """Mock _estimate_weight_kg and verify it is called exactly once."""
        design = AircraftDesign()
        with patch.object(
            validation,
            "_estimate_weight_kg",
            wraps=validation._estimate_weight_kg,
        ) as mock_weight:
            compute_warnings(design)
            assert mock_weight.call_count == 1, (
                f"_estimate_weight_kg called {mock_weight.call_count} times — "
                "expected exactly 1 (pre-computed once in compute_warnings)"
            )

    def test_weight_called_once_heavy_design(self) -> None:
        """Same check for a design that triggers V09/V12/V13 (all three weight checks)."""
        design = AircraftDesign(
            wing_span=400,
            wing_chord=80,
            wing_skin_thickness=0.8,
            battery_weight_g=500,
            motor_weight_g=200,
        )
        with patch.object(
            validation,
            "_estimate_weight_kg",
            wraps=validation._estimate_weight_kg,
        ) as mock_weight:
            warnings = compute_warnings(design)
            assert mock_weight.call_count == 1, (
                f"_estimate_weight_kg called {mock_weight.call_count} times — "
                "expected 1 even when V09, V12, V13 all trigger"
            )
            # Sanity check: the design does trigger at least V12 or V13
            warning_ids = {w.id for w in warnings}
            assert warning_ids & {"V09", "V12", "V13"}, (
                "Expected heavy/small-wing design to trigger at least one of V09/V12/V13"
            )

    def test_weight_called_once_multiple_invocations(self) -> None:
        """Each separate call to compute_warnings() calls _estimate_weight_kg exactly once."""
        design = AircraftDesign()
        with patch.object(
            validation,
            "_estimate_weight_kg",
            wraps=validation._estimate_weight_kg,
        ) as mock_weight:
            compute_warnings(design)
            compute_warnings(design)
            compute_warnings(design)
            assert mock_weight.call_count == 3, (
                f"3 compute_warnings() calls should produce 3 weight estimates, "
                f"got {mock_weight.call_count}"
            )

    def test_mocked_weight_propagates_to_all_aero_checks(self) -> None:
        """If _estimate_weight_kg returns a sentinel value, V09/V12/V13 all use it.

        Use an absurdly large weight to force all three weight-dependent
        checks to fire, confirming they each received the pre-computed value.
        """
        design = AircraftDesign(
            wing_span=1200,
            wing_chord=200,
            wing_skin_thickness=1.2,
        )
        # 1000 kg — guaranteed to trigger V09, V12, and V13
        SENTINEL_WEIGHT = 1000.0

        with patch.object(
            validation,
            "_estimate_weight_kg",
            return_value=SENTINEL_WEIGHT,
        ) as mock_weight:
            warnings = compute_warnings(design)
            assert mock_weight.call_count == 1

        warning_ids = {w.id for w in warnings}
        assert "V09" in warning_ids, "V09 should fire with 1000 kg weight"
        assert "V12" in warning_ids, "V12 should fire with 1000 kg weight"
        assert "V13" in warning_ids, "V13 should fire with 1000 kg weight"
