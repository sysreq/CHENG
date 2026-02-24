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
        """Engine count outside 0-4 should fail validation."""
        with pytest.raises(ValidationError):
            AircraftDesign(engine_count=-1)
        with pytest.raises(ValidationError):
            AircraftDesign(engine_count=5)

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
            wing_tip_chord_mm=200.0,
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
                wing_tip_chord_mm=200,
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
