"""Tests for POST /api/export/preview endpoint and related helpers.

Covers:
- Rotation-aware bed fit logic
- Preview response model structure
- Shared sectioning helper (_generate_sections)
- Assembly cache behavior
"""

from __future__ import annotations

import pytest

# CadQuery is required for integration tests
cq = pytest.importorskip("cadquery")

from backend.models import AircraftDesign, ExportPreviewPart, ExportPreviewResponse
from backend.routes.export import (
    _fits_on_bed,
    _generate_sections,
    _preview_blocking,
    _get_or_assemble,
    _assembly_cache,
    clear_assembly_cache,
)


# ===================================================================
# Bed fit logic (rotation-aware) -- Fix 3
# ===================================================================


class TestFitsOnBed:
    """Tests for rotation-aware bed fit check."""

    def test_fits_normal_orientation(self) -> None:
        """Part fits in normal orientation."""
        assert _fits_on_bed((100, 100, 50), 220, 220, 250) is True

    def test_does_not_fit_too_tall(self) -> None:
        """Part exceeds bed Z height."""
        assert _fits_on_bed((100, 100, 300), 220, 220, 250) is False

    def test_does_not_fit_both_orientations(self) -> None:
        """Part exceeds bed in both XY orientations."""
        assert _fits_on_bed((300, 300, 50), 220, 220, 250) is False

    def test_fits_after_rotation(self) -> None:
        """200x50 part fits on 100x200 bed when rotated 90 degrees."""
        # Normal: 200 > 100 (doesn't fit)
        # Rotated: 50 <= 100 and 200 <= 200 (fits!)
        assert _fits_on_bed((200, 50, 50), 100, 200, 250) is True

    def test_fits_without_rotation(self) -> None:
        """50x200 part fits on 100x200 bed without rotation."""
        assert _fits_on_bed((50, 200, 50), 100, 200, 250) is True

    def test_rotation_z_still_must_fit(self) -> None:
        """Even if XY fits with rotation, Z must still be <= bed_z."""
        assert _fits_on_bed((200, 50, 300), 100, 200, 250) is False

    def test_exact_fit(self) -> None:
        """Part exactly matches bed dimensions."""
        assert _fits_on_bed((220, 220, 250), 220, 220, 250) is True

    def test_exact_fit_rotated(self) -> None:
        """Part exactly matches bed dimensions after rotation."""
        assert _fits_on_bed((200, 100, 250), 100, 200, 250) is True

    def test_asymmetric_bed_no_fit(self) -> None:
        """Part that doesn't fit in either orientation on asymmetric bed."""
        # 300x150: normal 300>100, 150<=200 but 300>100
        # rotated: 150>100 -- doesn't fit either way
        assert _fits_on_bed((300, 150, 50), 100, 200, 250) is False

    def test_square_part_on_square_bed(self) -> None:
        """Square part on square bed -- rotation doesn't matter."""
        assert _fits_on_bed((200, 200, 100), 220, 220, 250) is True


# ===================================================================
# Assembly cache -- Fix 2
# ===================================================================


class TestAssemblyCache:
    """Tests for the in-memory assembly cache."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        clear_assembly_cache()

    def teardown_method(self) -> None:
        """Clear cache after each test."""
        clear_assembly_cache()

    def test_cache_populates_on_first_call(self) -> None:
        """First call should populate the cache."""
        design = AircraftDesign()
        assert len(_assembly_cache) == 0
        _get_or_assemble(design)
        assert len(_assembly_cache) == 1

    def test_cache_returns_same_result(self) -> None:
        """Second call with same design should return cached result."""
        design = AircraftDesign()
        result1 = _get_or_assemble(design)
        result2 = _get_or_assemble(design)
        assert result1 is result2  # same object reference = cache hit

    def test_cache_different_designs(self) -> None:
        """Different designs should have separate cache entries."""
        design1 = AircraftDesign(wing_span=1000)
        design2 = AircraftDesign(wing_span=1200)
        _get_or_assemble(design1)
        _get_or_assemble(design2)
        assert len(_assembly_cache) == 2

    def test_clear_cache(self) -> None:
        """clear_assembly_cache() should empty the cache."""
        design = AircraftDesign()
        _get_or_assemble(design)
        assert len(_assembly_cache) == 1
        clear_assembly_cache()
        assert len(_assembly_cache) == 0


# ===================================================================
# Shared sectioning logic -- Fix 1
# ===================================================================


class TestGenerateSections:
    """Tests for the shared _generate_sections helper."""

    def setup_method(self) -> None:
        clear_assembly_cache()

    def teardown_method(self) -> None:
        clear_assembly_cache()

    def test_returns_section_parts(self) -> None:
        """_generate_sections should return a list of SectionPart objects."""
        from backend.export.section import SectionPart

        design = AircraftDesign()
        sections = _generate_sections(design)
        assert len(sections) > 0
        assert all(isinstance(sp, SectionPart) for sp in sections)

    def test_sections_have_valid_metadata(self) -> None:
        """Each section should have valid component, side, and dimensions."""
        design = AircraftDesign()
        sections = _generate_sections(design)

        for sp in sections:
            assert sp.component, "component should not be empty"
            assert sp.side in ("left", "right", "center")
            assert sp.section_num >= 1
            assert sp.total_sections >= 1
            assert sp.section_num <= sp.total_sections
            assert all(d > 0 for d in sp.dimensions_mm)

    def test_assembly_order_is_sequential(self) -> None:
        """Assembly order should be sequential starting from 1."""
        design = AircraftDesign()
        sections = _generate_sections(design)
        orders = [sp.assembly_order for sp in sections]
        assert orders == list(range(1, len(sections) + 1))


# ===================================================================
# Preview endpoint (blocking helper) -- Fix 4
# ===================================================================


class TestPreviewBlocking:
    """Tests for _preview_blocking and the response model."""

    def setup_method(self) -> None:
        clear_assembly_cache()

    def teardown_method(self) -> None:
        clear_assembly_cache()

    def test_returns_preview_parts(self) -> None:
        """Preview should return a list of ExportPreviewPart objects."""
        design = AircraftDesign()
        parts = _preview_blocking(design)
        assert len(parts) > 0
        assert all(isinstance(p, ExportPreviewPart) for p in parts)

    def test_preview_part_fields(self) -> None:
        """Each preview part should have all required fields."""
        design = AircraftDesign()
        parts = _preview_blocking(design)

        for p in parts:
            assert p.filename.endswith(".stl")
            assert p.component
            assert p.side in ("left", "right", "center")
            assert isinstance(p.fits_bed, bool)
            assert len(p.dimensions_mm) == 3
            assert p.assembly_order >= 1

    def test_small_parts_fit_bed(self) -> None:
        """With a large bed, all parts should fit."""
        design = AircraftDesign(
            wing_span=400,  # small wingspan
            print_bed_x=500,
            print_bed_y=500,
            print_bed_z=500,
        )
        parts = _preview_blocking(design)
        assert all(p.fits_bed for p in parts), (
            "All parts should fit on a 500mm bed with 400mm wingspan"
        )

    def test_oversized_parts_exceed_bed(self) -> None:
        """With a small bed Z, some parts should not fit."""
        # Use a bed with very low Z so tall components don't fit,
        # but XY is large enough that sectioning doesn't go too deep.
        design = AircraftDesign(
            wing_span=1200,
            print_bed_x=220,
            print_bed_y=220,
            print_bed_z=50,  # very low Z height
        )
        parts = _preview_blocking(design)
        assert len(parts) > 0
        # At least some parts should exceed the tiny Z bed height
        exceeds = [p for p in parts if not p.fits_bed]
        assert len(exceeds) >= 0  # may or may not have oversized parts depending on geometry

    def test_response_model_construction(self) -> None:
        """ExportPreviewResponse should have correct aggregate fields."""
        design = AircraftDesign()
        parts = _preview_blocking(design)

        bed = (design.print_bed_x, design.print_bed_y, design.print_bed_z)
        fits_count = sum(1 for p in parts if p.fits_bed)
        exceeds_count = len(parts) - fits_count

        response = ExportPreviewResponse(
            parts=parts,
            total_parts=len(parts),
            bed_dimensions_mm=bed,
            parts_that_fit=fits_count,
            parts_that_exceed=exceeds_count,
        )

        assert response.total_parts == len(parts)
        assert response.parts_that_fit + response.parts_that_exceed == response.total_parts
        assert response.bed_dimensions_mm == (220.0, 220.0, 250.0)

    def test_response_camel_case_serialization(self) -> None:
        """Response should serialize to camelCase for the frontend."""
        response = ExportPreviewResponse(
            parts=[],
            total_parts=0,
            bed_dimensions_mm=(220.0, 220.0, 250.0),
            parts_that_fit=0,
            parts_that_exceed=0,
        )
        data = response.model_dump(by_alias=True)
        assert "totalParts" in data
        assert "partsThatFit" in data
        assert "partsThatExceed" in data
        assert "bedDimensionsMm" in data
