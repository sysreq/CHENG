"""Tests for Pydantic models — AircraftDesign, DerivedValues, ValidationWarning, etc."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.models import (
    AircraftDesign,
    DesignSummary,
    DerivedValues,
    ExportRequest,
    GenerationResult,
    ValidationWarning,
)


class TestAircraftDesign:
    """Tests for the AircraftDesign model."""

    def test_defaults(self) -> None:
        """Default construction should produce a valid model."""
        d = AircraftDesign()
        assert d.version == "0.1.0"
        assert d.wing_span == 1000
        assert d.wing_chord == 180
        assert d.fuselage_preset == "Conventional"
        assert d.tail_type == "Conventional"

    def test_custom_values(self) -> None:
        """Construction with custom values should preserve them."""
        d = AircraftDesign(
            id="my-plane",
            name="My Plane",
            wing_span=1200,
            wing_chord=200,
        )
        assert d.id == "my-plane"
        assert d.name == "My Plane"
        assert d.wing_span == 1200
        assert d.wing_chord == 200

    def test_range_validation_wingspan(self) -> None:
        """Wingspan outside 300-3000 range should fail validation."""
        with pytest.raises(ValidationError):
            AircraftDesign(wing_span=100)  # below 300 minimum
        with pytest.raises(ValidationError):
            AircraftDesign(wing_span=5000)  # above 3000 maximum

    def test_range_validation_chord(self) -> None:
        """Wing chord outside 50-500 range should fail validation."""
        with pytest.raises(ValidationError):
            AircraftDesign(wing_chord=10)
        with pytest.raises(ValidationError):
            AircraftDesign(wing_chord=600)

    def test_range_validation_engine_count(self) -> None:
        """Engine count outside 0-1 should fail validation (#240).

        Values 2-4 are clamped to 1 for backward compat (see clamp_engine_count).
        Negative values are still rejected.
        """
        with pytest.raises(ValidationError):
            AircraftDesign(engine_count=-1)
        # Values above 1 that are <= 4 are silently clamped to 1 (legacy designs)
        d = AircraftDesign(engine_count=2)
        assert d.engine_count == 1
        d = AircraftDesign(engine_count=3)
        assert d.engine_count == 1
        d = AircraftDesign(engine_count=4)
        assert d.engine_count == 1
        # Values > 4 are also clamped (not rejected, since clamp runs before le check)
        # but primary constraint remains le=1 after clamping
        with pytest.raises(ValidationError):
            AircraftDesign(engine_count=-2)

    def test_engine_count_valid_values(self) -> None:
        """engine_count=0 and engine_count=1 are valid (#240)."""
        d0 = AircraftDesign(engine_count=0)
        assert d0.engine_count == 0
        d1 = AircraftDesign(engine_count=1)
        assert d1.engine_count == 1

    def test_range_validation_tip_root_ratio(self) -> None:
        """Tip/root ratio outside 0.3-1.0 should fail."""
        with pytest.raises(ValidationError):
            AircraftDesign(wing_tip_root_ratio=0.1)
        with pytest.raises(ValidationError):
            AircraftDesign(wing_tip_root_ratio=1.5)

    def test_literal_fuselage_preset(self) -> None:
        """Invalid fuselage preset should fail validation."""
        with pytest.raises(ValidationError):
            AircraftDesign(fuselage_preset="Invalid")

    def test_literal_tail_type(self) -> None:
        """Invalid tail type should fail validation."""
        with pytest.raises(ValidationError):
            AircraftDesign(tail_type="Invalid")

    def test_literal_motor_config(self) -> None:
        """Invalid motor config should fail validation."""
        with pytest.raises(ValidationError):
            AircraftDesign(motor_config="Invalid")

    def test_literal_support_strategy(self) -> None:
        """Invalid support strategy should fail validation."""
        with pytest.raises(ValidationError):
            AircraftDesign(support_strategy="invalid")

    def test_new_param_defaults(self) -> None:
        """New v0.3 parameters should have correct defaults."""
        d = AircraftDesign()
        assert d.wing_incidence == 2.0
        assert d.wing_twist == 0.0
        assert d.v_tail_sweep == 0.0
        assert d.wall_thickness == 1.5
        assert d.support_strategy == "minimal"

    def test_fuselage_section_pct_defaults(self) -> None:
        """Fuselage section transition-point defaults: 25% nose/cabin, 75% cabin/tail."""
        d = AircraftDesign()
        assert d.nose_cabin_break_pct == 25.0
        assert d.cabin_tail_break_pct == 75.0

    def test_fuselage_section_pct_range(self) -> None:
        """nose_cabin_break_pct and cabin_tail_break_pct enforce Pydantic ge/le bounds."""
        with pytest.raises(ValidationError):
            AircraftDesign(nose_cabin_break_pct=5.0)   # below ge=10
        with pytest.raises(ValidationError):
            AircraftDesign(nose_cabin_break_pct=90.0)  # above le=85
        with pytest.raises(ValidationError):
            AircraftDesign(cabin_tail_break_pct=10.0)  # below ge=15
        with pytest.raises(ValidationError):
            AircraftDesign(cabin_tail_break_pct=95.0)  # above le=90

    def test_fuselage_section_pct_custom(self) -> None:
        """Custom percentage values should be stored correctly."""
        d = AircraftDesign(nose_cabin_break_pct=20.0, cabin_tail_break_pct=60.0)
        assert d.nose_cabin_break_pct == 20.0
        assert d.cabin_tail_break_pct == 60.0

    def test_wing_incidence_range(self) -> None:
        """Wing incidence outside -5 to 15 should fail."""
        with pytest.raises(ValidationError):
            AircraftDesign(wing_incidence=-10)
        with pytest.raises(ValidationError):
            AircraftDesign(wing_incidence=20)

    def test_wing_twist_range(self) -> None:
        """Wing twist outside -5 to 5 should fail."""
        with pytest.raises(ValidationError):
            AircraftDesign(wing_twist=-10)
        with pytest.raises(ValidationError):
            AircraftDesign(wing_twist=10)

    def test_v_tail_sweep_range(self) -> None:
        """V-tail sweep outside -10 to 45 should fail."""
        with pytest.raises(ValidationError):
            AircraftDesign(v_tail_sweep=-15)
        with pytest.raises(ValidationError):
            AircraftDesign(v_tail_sweep=50)

    def test_wall_thickness_range(self) -> None:
        """Wall thickness outside 0.8 to 4.0 should fail."""
        with pytest.raises(ValidationError):
            AircraftDesign(wall_thickness=0.5)
        with pytest.raises(ValidationError):
            AircraftDesign(wall_thickness=5.0)

    def test_fuselage_section_lengths_derived(self) -> None:
        """Section lengths are derived from percentage breakpoints and fuselage_length."""
        d = AircraftDesign(
            fuselage_length=400,
            nose_cabin_break_pct=20.0,
            cabin_tail_break_pct=60.0,
        )
        # nose = 20% of 400 = 80mm
        # cabin = (60-20)% of 400 = 160mm
        # tail = (100-60)% of 400 = 160mm
        nose_len = d.nose_cabin_break_pct / 100.0 * d.fuselage_length
        cabin_len = (d.cabin_tail_break_pct - d.nose_cabin_break_pct) / 100.0 * d.fuselage_length
        tail_len = (100.0 - d.cabin_tail_break_pct) / 100.0 * d.fuselage_length
        assert abs(nose_len - 80.0) < 1e-9
        assert abs(cabin_len - 160.0) < 1e-9
        assert abs(tail_len - 160.0) < 1e-9
        # Sections always sum to fuselage_length
        assert abs(nose_len + cabin_len + tail_len - d.fuselage_length) < 1e-9

    def test_serialization_round_trip(self) -> None:
        """Serialize to dict and back should produce identical model."""
        original = AircraftDesign(id="round-trip", wing_span=1500)
        data = original.model_dump()
        restored = AircraftDesign(**data)
        assert original == restored

    def test_json_round_trip(self) -> None:
        """Serialize to JSON and back should produce identical model."""
        original = AircraftDesign(id="json-trip", wing_span=800)
        json_str = original.model_dump_json()
        restored = AircraftDesign.model_validate_json(json_str)
        assert original == restored


class TestDerivedValues:
    """Tests for DerivedValues model."""

    def test_construction(self) -> None:
        dv = DerivedValues(
            tip_chord_mm=200.0,
            wing_area_cm2=2400.0,
            aspect_ratio=6.0,
            mean_aero_chord_mm=200.0,
            taper_ratio=1.0,
            estimated_cg_mm=50.0,
            min_feature_thickness_mm=0.8,
            wall_thickness_mm=1.6,
        )
        assert dv.wing_area_cm2 == 2400.0
        assert dv.aspect_ratio == 6.0


class TestValidationWarning:
    """Tests for ValidationWarning model."""

    def test_default_level(self) -> None:
        w = ValidationWarning(id="V01", message="Test warning")
        assert w.level == "warn"
        assert w.fields == []

    def test_with_fields(self) -> None:
        w = ValidationWarning(
            id="V03",
            message="Tail arm exceeds fuselage",
            fields=["tail_arm", "fuselage_length"],
        )
        assert len(w.fields) == 2


class TestDesignSummary:
    """Tests for DesignSummary model."""

    def test_construction(self) -> None:
        s = DesignSummary(id="abc", name="Test", modified_at="2024-01-01T00:00:00Z")
        assert s.id == "abc"
        assert s.name == "Test"


class TestExportRequest:
    """Tests for ExportRequest model."""

    def test_default_format(self) -> None:
        req = ExportRequest(design=AircraftDesign())
        assert req.format == "stl"


class TestGenerationResult:
    """Tests for GenerationResult model."""

    def test_construction(self) -> None:
        result = GenerationResult(
            derived=DerivedValues(
                tip_chord_mm=200,
                wing_area_cm2=2400,
                aspect_ratio=6.0,
                mean_aero_chord_mm=200,
                taper_ratio=1.0,
                estimated_cg_mm=50,
                min_feature_thickness_mm=0.8,
                wall_thickness_mm=1.6,
            ),
            warnings=[],
        )
        assert result.derived.aspect_ratio == 6.0
        assert result.warnings == []
