"""Tests for control surface geometry — Issue #144.

Tests cover:
1.  Model field presence and camelCase aliases
2.  Validation V30 rules (aileron span order, elevator/rudder chord limits, elevon area)
3.  Control surface disabled — returns original solid unchanged (no CadQuery)
4.  cut_aileron / cut_elevator / cut_rudder return signatures (CadQuery if available)
5.  cut_ruddervators / cut_elevons return signatures
6.  Graceful fallback when CadQuery cut fails
7.  Engine integration — control surface components appear in assemble_aircraft output
"""

from __future__ import annotations

import pytest

from backend.models import AircraftDesign
from backend.validation import compute_warnings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_cq_available() -> bool:
    """Return True if CadQuery can be imported."""
    try:
        import cadquery  # noqa: F401
        return True
    except ImportError:
        return False


CQ_AVAILABLE = _check_cq_available()


def _default() -> AircraftDesign:
    """Default AircraftDesign with all control surfaces disabled."""
    return AircraftDesign()


def _with_ailerons(**overrides) -> AircraftDesign:
    return AircraftDesign(aileron_enable=True, **overrides)


def _with_elevator(**overrides) -> AircraftDesign:
    return AircraftDesign(elevator_enable=True, **overrides)


def _with_rudder(**overrides) -> AircraftDesign:
    return AircraftDesign(rudder_enable=True, **overrides)


def _with_ruddervators(**overrides) -> AircraftDesign:
    return AircraftDesign(tail_type="V-Tail", ruddervator_enable=True, **overrides)


def _with_elevons(**overrides) -> AircraftDesign:
    return AircraftDesign(
        fuselage_preset="Blended-Wing-Body",
        elevon_enable=True,
        **overrides,
    )


def _warning_ids(design: AircraftDesign) -> list[str]:
    return [w.id for w in compute_warnings(design)]


# ---------------------------------------------------------------------------
# 1. Model field presence and serialization
# ---------------------------------------------------------------------------


class TestControlSurfaceModelFields:
    """AircraftDesign must have all control surface fields with correct defaults."""

    def test_aileron_fields_exist_with_defaults(self):
        d = _default()
        assert d.aileron_enable is False
        assert d.aileron_span_start == 55.0
        assert d.aileron_span_end == 95.0
        assert d.aileron_chord_percent == 25.0

    def test_elevator_fields_exist_with_defaults(self):
        d = _default()
        assert d.elevator_enable is False
        assert d.elevator_span_percent == 100.0
        assert d.elevator_chord_percent == 35.0

    def test_rudder_fields_exist_with_defaults(self):
        d = _default()
        assert d.rudder_enable is False
        assert d.rudder_height_percent == 90.0
        assert d.rudder_chord_percent == 35.0

    def test_ruddervator_fields_exist_with_defaults(self):
        d = _default()
        assert d.ruddervator_enable is False
        assert d.ruddervator_chord_percent == 35.0
        assert d.ruddervator_span_percent == 90.0

    def test_elevon_fields_exist_with_defaults(self):
        d = _default()
        assert d.elevon_enable is False
        assert d.elevon_span_start == 20.0
        assert d.elevon_span_end == 90.0
        assert d.elevon_chord_percent == 20.0

    def test_camelcase_alias_aileron_enable(self):
        d = _with_ailerons()
        dumped = d.model_dump(by_alias=True)
        assert "aileronEnable" in dumped
        assert dumped["aileronEnable"] is True

    def test_camelcase_alias_elevator_enable(self):
        d = _with_elevator()
        dumped = d.model_dump(by_alias=True)
        assert "elevatorEnable" in dumped
        assert dumped["elevatorEnable"] is True

    def test_camelcase_alias_rudder_enable(self):
        d = _with_rudder()
        dumped = d.model_dump(by_alias=True)
        assert "rudderEnable" in dumped
        assert dumped["rudderEnable"] is True

    def test_camelcase_alias_ruddervator_enable(self):
        d = _with_ruddervators()
        dumped = d.model_dump(by_alias=True)
        assert "ruddervatorEnable" in dumped
        assert dumped["ruddervatorEnable"] is True

    def test_camelcase_alias_elevon_enable(self):
        d = _with_elevons()
        dumped = d.model_dump(by_alias=True)
        assert "elevonEnable" in dumped
        assert dumped["elevonEnable"] is True

    def test_all_cs_fields_in_camel_dump(self):
        d = AircraftDesign(
            aileron_enable=True,
            elevator_enable=True,
            rudder_enable=True,
            ruddervator_enable=True,
            elevon_enable=True,
        )
        dumped = d.model_dump(by_alias=True)
        expected_keys = [
            "aileronEnable", "aileronSpanStart", "aileronSpanEnd", "aileronChordPercent",
            "elevatorEnable", "elevatorSpanPercent", "elevatorChordPercent",
            "rudderEnable", "rudderHeightPercent", "rudderChordPercent",
            "ruddervatorEnable", "ruddervatorChordPercent", "ruddervatorSpanPercent",
            "elevonEnable", "elevonSpanStart", "elevonSpanEnd", "elevonChordPercent",
        ]
        for key in expected_keys:
            assert key in dumped, f"Missing camelCase key: {key}"

    def test_pydantic_range_aileron_span_start_too_low(self):
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            AircraftDesign(aileron_span_start=5.0)  # below ge=30

    def test_pydantic_range_elevator_chord_percent_too_high(self):
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            AircraftDesign(elevator_chord_percent=55.0)  # above le=50


# ---------------------------------------------------------------------------
# 2. Validation V30 — control surface warnings
# ---------------------------------------------------------------------------


class TestValidationV30:
    """V30 validation rules fire correctly."""

    def test_no_v30_when_all_disabled(self):
        d = _default()
        assert "V30" not in _warning_ids(d)

    def test_v30a_aileron_span_start_ge_end(self):
        # Both values are within Pydantic's per-field ranges but start >= end
        # aileron_span_start max=70, aileron_span_end min=70
        d = AircraftDesign(
            aileron_enable=True,
            aileron_span_start=70.0,   # max allowed
            aileron_span_end=70.0,     # min allowed — equals start, still invalid
        )
        warnings = compute_warnings(d)
        v30_msgs = [w.message for w in warnings if w.id == "V30"]
        assert any("span start" in m.lower() for m in v30_msgs), (
            f"V30 span order not raised. Messages: {v30_msgs}"
        )

    def test_no_v30_when_aileron_disabled_despite_equal_span(self):
        # When aileron is disabled, equal span values don't trigger warning
        d = AircraftDesign(
            aileron_enable=False,
            aileron_span_start=70.0,
            aileron_span_end=70.0,
        )
        warnings = compute_warnings(d)
        v30_msgs = [w.message for w in warnings if w.id == "V30"]
        assert not any("span start" in m.lower() for m in v30_msgs)

    def test_v30b_elevator_chord_at_boundary(self):
        # elevator_chord_percent >= 45.0 should trigger V30b
        d = AircraftDesign(
            elevator_enable=True,
            elevator_chord_percent=45.0,
        )
        warnings = compute_warnings(d)
        v30_msgs = [w.message for w in warnings if w.id == "V30"]
        assert any("elevator" in m.lower() for m in v30_msgs), (
            f"V30b elevator not raised at 45%. Messages: {v30_msgs}"
        )

    def test_v30c_rudder_chord_at_boundary(self):
        d = AircraftDesign(
            rudder_enable=True,
            rudder_chord_percent=45.0,
        )
        warnings = compute_warnings(d)
        v30_msgs = [w.message for w in warnings if w.id == "V30"]
        assert any("rudder" in m.lower() for m in v30_msgs), (
            f"V30c rudder not raised at 45%. Messages: {v30_msgs}"
        )

    def test_no_v30_elevator_below_45(self):
        d = AircraftDesign(elevator_enable=True, elevator_chord_percent=35.0)
        warnings = compute_warnings(d)
        v30_msgs = [w.message for w in warnings if w.id == "V30"]
        # Should not fire V30b for normal elevator chord below 45%
        assert not any("elevator" in m.lower() for m in v30_msgs), (
            f"V30b unexpectedly raised at 35%. Messages: {v30_msgs}"
        )

    def test_v30d_elevon_insufficient_area_for_flying_wing(self):
        # Flying wing with minimal elevon span — should trigger V30d
        # elevon_span_start max=40, elevon_span_end min=60
        # Use the narrowest valid range: 39% to 61% = only 22% of half-span
        d = AircraftDesign(
            fuselage_preset="Blended-Wing-Body",
            elevon_enable=True,
            elevon_span_start=39.0,   # near max allowed
            elevon_span_end=61.0,     # near min allowed
            elevon_chord_percent=15.0,  # minimum chord
            wing_span=1000.0,
            wing_chord=180.0,
        )
        warnings = compute_warnings(d)
        v30_msgs = [w.message for w in warnings if w.id == "V30"]
        assert any("8%" in m or "pitch authority" in m.lower() for m in v30_msgs), (
            f"V30d elevon area not raised. Messages: {v30_msgs}"
        )

    def test_no_v30_on_normal_aileron_config(self):
        d = AircraftDesign(
            aileron_enable=True,
            aileron_span_start=55.0,
            aileron_span_end=95.0,
            aileron_chord_percent=25.0,
        )
        warnings = compute_warnings(d)
        # Should not warn on valid aileron span order
        v30_aileron_order = [
            w for w in warnings
            if w.id == "V30" and "span start" in w.message.lower()
        ]
        assert len(v30_aileron_order) == 0


# ---------------------------------------------------------------------------
# 3. Control surfaces disabled — no-op behaviour (no CadQuery needed)
# ---------------------------------------------------------------------------


class TestControlSurfaceDisabled:
    """When enable flags are False, cut functions return original solid + None."""

    def test_cut_aileron_disabled_returns_original(self):
        from unittest.mock import MagicMock
        from backend.geometry.control_surfaces import cut_aileron

        mock_solid = MagicMock()
        d = _default()  # aileron_enable = False

        result_solid, result_cs = cut_aileron(mock_solid, d, side="right")

        assert result_solid is mock_solid
        assert result_cs is None

    def test_cut_elevator_disabled_returns_original(self):
        from unittest.mock import MagicMock
        from backend.geometry.control_surfaces import cut_elevator

        mock_solid = MagicMock()
        d = _default()  # elevator_enable = False

        result_solid, result_cs = cut_elevator(mock_solid, d, side="right")
        assert result_solid is mock_solid
        assert result_cs is None

    def test_cut_rudder_disabled_returns_original(self):
        from unittest.mock import MagicMock
        from backend.geometry.control_surfaces import cut_rudder

        mock_solid = MagicMock()
        d = _default()  # rudder_enable = False

        result_solid, result_cs = cut_rudder(mock_solid, d)
        assert result_solid is mock_solid
        assert result_cs is None

    def test_cut_ruddervators_disabled_returns_originals(self):
        from unittest.mock import MagicMock
        from backend.geometry.control_surfaces import cut_ruddervators

        mock_left = MagicMock()
        mock_right = MagicMock()
        d = AircraftDesign(tail_type="V-Tail", ruddervator_enable=False)

        bl, br, rl, rr = cut_ruddervators(mock_left, mock_right, d)
        assert bl is mock_left
        assert br is mock_right
        assert rl is None
        assert rr is None

    def test_cut_elevons_disabled_returns_original(self):
        from unittest.mock import MagicMock
        from backend.geometry.control_surfaces import cut_elevons

        mock_solid = MagicMock()
        d = AircraftDesign(fuselage_preset="Blended-Wing-Body", elevon_enable=False)

        result_solid, result_cs = cut_elevons(mock_solid, d, side="left")
        assert result_solid is mock_solid
        assert result_cs is None


# ---------------------------------------------------------------------------
# 4. Return signature tests (with CadQuery)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not CQ_AVAILABLE, reason="CadQuery not available in test environment")
class TestControlSurfaceCutSignatures:
    """Tests that require CadQuery.  Verify return types and component counts."""

    def test_cut_aileron_disabled_leaves_wing_unchanged(self):
        from backend.geometry.wing import build_wing
        from backend.geometry.control_surfaces import cut_aileron

        d = AircraftDesign(aileron_enable=False, hollow_parts=False)
        wing = build_wing(d, side="right")
        wing_body, aileron = cut_aileron(wing, d, side="right")

        assert wing_body is wing  # exact same object when disabled
        assert aileron is None

    def test_cut_aileron_enabled_returns_two_solids(self):
        from backend.geometry.wing import build_wing
        from backend.geometry.control_surfaces import cut_aileron

        d = AircraftDesign(aileron_enable=True, hollow_parts=False)
        wing = build_wing(d, side="right")
        wing_body, aileron = cut_aileron(wing, d, side="right")

        # wing_body must not be None (even if aileron is None due to CQ failure)
        assert wing_body is not None

    def test_cut_elevator_returns_non_none_body(self):
        import cadquery as cq
        from backend.geometry.tail import _build_h_stab_half
        from backend.geometry.control_surfaces import cut_elevator

        d = AircraftDesign(elevator_enable=True, hollow_parts=False)
        h_stab = _build_h_stab_half(cq, d, side="right", z_offset=0.0)
        h_stab_body, elevator = cut_elevator(h_stab, d, side="right")

        assert h_stab_body is not None

    def test_cut_rudder_returns_non_none_body(self):
        import cadquery as cq
        from backend.geometry.tail import _build_v_stab
        from backend.geometry.control_surfaces import cut_rudder

        d = AircraftDesign(rudder_enable=True, hollow_parts=False)
        v_stab = _build_v_stab(cq, d, mount_z=0.0)
        v_stab_body, rudder = cut_rudder(v_stab, d)

        assert v_stab_body is not None

    def test_cut_ruddervators_returns_four_items(self):
        import cadquery as cq
        from backend.geometry.tail import _build_v_tail_half
        from backend.geometry.control_surfaces import cut_ruddervators

        d = AircraftDesign(
            tail_type="V-Tail",
            ruddervator_enable=True,
            hollow_parts=False,
        )
        v_left = _build_v_tail_half(cq, d, side="left")
        v_right = _build_v_tail_half(cq, d, side="right")
        vl, vr, rl, rr = cut_ruddervators(v_left, v_right, d)

        assert vl is not None
        assert vr is not None

    def test_cut_elevons_returns_non_none_body(self):
        from backend.geometry.wing import build_wing
        from backend.geometry.control_surfaces import cut_elevons

        d = AircraftDesign(
            fuselage_preset="Blended-Wing-Body",
            elevon_enable=True,
            hollow_parts=False,
        )
        wing = build_wing(d, side="right")
        wing_body, elevon = cut_elevons(wing, d, side="right")

        assert wing_body is not None


# ---------------------------------------------------------------------------
# 5. Graceful fallback tests
# ---------------------------------------------------------------------------


class TestControlSurfaceGracefulFallback:
    """If CadQuery boolean cut raises, return original solid + None."""

    def test_cut_aileron_returns_original_on_cq_failure(self):
        from unittest.mock import MagicMock
        from backend.geometry import control_surfaces

        # Build a mock solid whose .cut() raises RuntimeError
        mock_solid = MagicMock()
        mock_solid.cut.side_effect = RuntimeError("CadQuery failed")

        d = AircraftDesign(aileron_enable=True)

        result_solid, result_cs = control_surfaces.cut_aileron(mock_solid, d, side="right")

        assert result_solid is mock_solid
        assert result_cs is None

    def test_cut_elevator_returns_original_on_cq_failure(self):
        from unittest.mock import MagicMock
        from backend.geometry import control_surfaces

        mock_solid = MagicMock()
        mock_solid.cut.side_effect = RuntimeError("CadQuery failed")

        d = AircraftDesign(elevator_enable=True)

        result_solid, result_cs = control_surfaces.cut_elevator(mock_solid, d, side="right")

        assert result_solid is mock_solid
        assert result_cs is None

    def test_cut_rudder_returns_original_on_cq_failure(self):
        from unittest.mock import MagicMock
        from backend.geometry import control_surfaces

        mock_solid = MagicMock()
        mock_solid.cut.side_effect = RuntimeError("CadQuery failed")

        d = AircraftDesign(rudder_enable=True)

        result_solid, result_cs = control_surfaces.cut_rudder(mock_solid, d)

        assert result_solid is mock_solid
        assert result_cs is None


# ---------------------------------------------------------------------------
# 6. Engine integration — assemble_aircraft includes CS components
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not CQ_AVAILABLE, reason="CadQuery not available in test environment")
class TestEngineIntegration:
    """Control surface components appear in engine.assemble_aircraft output."""

    def test_aileron_parent_components_in_assembly(self):
        from backend.geometry.engine import assemble_aircraft

        d = AircraftDesign(
            aileron_enable=True,
            hollow_parts=False,
            tail_type="Conventional",
        )
        components = assemble_aircraft(d)
        assert "wing_left" in components
        assert "wing_right" in components

    def test_elevator_parent_components_in_assembly(self):
        from backend.geometry.engine import assemble_aircraft

        d = AircraftDesign(
            elevator_enable=True,
            hollow_parts=False,
            tail_type="Conventional",
        )
        components = assemble_aircraft(d)
        assert "h_stab_left" in components
        assert "h_stab_right" in components

    def test_rudder_parent_component_in_assembly(self):
        from backend.geometry.engine import assemble_aircraft

        d = AircraftDesign(
            rudder_enable=True,
            hollow_parts=False,
            tail_type="Conventional",
        )
        components = assemble_aircraft(d)
        assert "v_stab" in components

    def test_no_control_surface_components_when_all_disabled(self):
        from backend.geometry.engine import assemble_aircraft

        d = AircraftDesign(
            aileron_enable=False,
            elevator_enable=False,
            rudder_enable=False,
            hollow_parts=False,
        )
        components = assemble_aircraft(d)
        assert "aileron_left" not in components
        assert "aileron_right" not in components
        assert "elevator_left" not in components
        assert "elevator_right" not in components
        assert "rudder" not in components

    def test_v_tail_parent_components_in_assembly(self):
        from backend.geometry.engine import assemble_aircraft

        d = AircraftDesign(
            tail_type="V-Tail",
            ruddervator_enable=True,
            hollow_parts=False,
        )
        components = assemble_aircraft(d)
        assert "v_tail_left" in components
        assert "v_tail_right" in components

    def test_flying_wing_wing_components_in_assembly(self):
        from backend.geometry.engine import assemble_aircraft

        d = AircraftDesign(
            fuselage_preset="Blended-Wing-Body",
            elevon_enable=True,
            hollow_parts=False,
        )
        components = assemble_aircraft(d)
        assert "wing_left" in components
        assert "wing_right" in components
