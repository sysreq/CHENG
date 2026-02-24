"""Tests for new export formats (STEP, DXF, SVG) and bug fixes (#163, #166).

These tests require CadQuery.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

# CadQuery is required for these tests -- skip if not installed.
cq = pytest.importorskip("cadquery")


# ===================================================================
# Helpers
# ===================================================================


def _make_box(x: float, y: float, z: float) -> cq.Workplane:
    """Create a simple box centered at origin."""
    return cq.Workplane("XY").box(x, y, z)


def _bbox_dims(solid: cq.Workplane) -> tuple[float, float, float]:
    """Get bounding box dimensions of a solid."""
    bb = solid.val().BoundingBox()
    return (bb.xmax - bb.xmin, bb.ymax - bb.ymin, bb.zmax - bb.zmin)


# ===================================================================
# #163: Split axis propagation tests
# ===================================================================


class TestSplitAxisPropagation:
    """Tests for auto_section_with_axis and split axis in joints."""

    def test_auto_section_with_axis_returns_tuples(self) -> None:
        """auto_section_with_axis should return (solid, axis) tuples."""
        from backend.export.section import auto_section_with_axis

        # Box that needs splitting along X (500mm > usable 200mm)
        solid = _make_box(500, 100, 50)
        results = auto_section_with_axis(solid, bed_x=220, bed_y=220, bed_z=250)
        assert len(results) >= 2
        for item in results:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert item[1] in ("X", "Y", "Z")

    def test_x_axis_split_detected(self) -> None:
        """Splitting along X should report split_axis='X'."""
        from backend.export.section import auto_section_with_axis

        # Only oversize in X
        solid = _make_box(500, 100, 50)
        results = auto_section_with_axis(solid, bed_x=220, bed_y=220, bed_z=250)
        axes = [r[1] for r in results]
        assert all(a == "X" for a in axes)

    def test_y_axis_split_detected(self) -> None:
        """Splitting along Y should report split_axis='Y'."""
        from backend.export.section import auto_section_with_axis

        # Only oversize in Y
        solid = _make_box(100, 500, 50)
        results = auto_section_with_axis(solid, bed_x=220, bed_y=220, bed_z=250)
        axes = [r[1] for r in results]
        assert all(a == "Y" for a in axes)

    def test_backward_compat_auto_section(self) -> None:
        """auto_section should still return plain list of solids."""
        from backend.export.section import auto_section

        solid = _make_box(500, 100, 50)
        results = auto_section(solid, bed_x=220, bed_y=220, bed_z=250)
        assert len(results) >= 2
        # Should be plain workplane objects, not tuples
        for item in results:
            assert not isinstance(item, tuple)

    def test_section_parts_have_split_axis(self) -> None:
        """create_section_parts should set split_axis on each part."""
        from backend.export.section import auto_section_with_axis, create_section_parts

        solid = _make_box(500, 100, 50)
        results = auto_section_with_axis(solid, bed_x=220, bed_y=220, bed_z=250)
        pieces = [r[0] for r in results]
        axes = [r[1] for r in results]

        parts = create_section_parts("fuselage", "center", pieces, split_axes=axes)
        for part in parts:
            assert part.split_axis == "X"

    def test_joints_on_x_axis(self) -> None:
        """Joints on X-split sections should protrude along X."""
        from backend.export.joints import add_tongue_and_groove

        left = _make_box(100, 100, 50)
        right = _make_box(100, 100, 50).translate((100, 0, 0))

        mod_left, mod_right = add_tongue_and_groove(
            left, right, overlap=15, tolerance=0.15, nozzle_diameter=0.4,
            split_axis="X",
        )

        # Left should extend in +X (tongue protrudes)
        orig_xmax = left.val().BoundingBox().xmax
        mod_xmax = mod_left.val().BoundingBox().xmax
        assert mod_xmax > orig_xmax  # tongue extends in +X

    def test_joints_on_y_axis_default(self) -> None:
        """Default Y-axis joints should still work as before."""
        from backend.export.joints import add_tongue_and_groove

        left = _make_box(100, 100, 50)
        right = _make_box(100, 100, 50).translate((0, 100, 0))

        mod_left, _ = add_tongue_and_groove(
            left, right, overlap=15, tolerance=0.15, nozzle_diameter=0.4,
        )

        orig_ymax = left.val().BoundingBox().ymax
        mod_ymax = mod_left.val().BoundingBox().ymax
        assert mod_ymax > orig_ymax


# ===================================================================
# #166: Dimension recomputation tests
# ===================================================================


class TestDimensionRecomputation:
    """Tests for SectionPart.recompute_dimensions after joint features."""

    def test_recompute_dimensions_method(self) -> None:
        """recompute_dimensions should update dimensions_mm."""
        from backend.export.section import SectionPart

        solid = _make_box(100, 100, 50)
        part = SectionPart(
            solid=solid,
            filename="test_1of1.stl",
            component="wing",
            side="left",
            section_num=1,
            total_sections=1,
            dimensions_mm=(50.0, 50.0, 25.0),  # Intentionally wrong
            print_orientation="flat",
            assembly_order=1,
        )

        part.recompute_dimensions()
        assert part.dimensions_mm == (100.0, 100.0, 50.0)

    def test_dimensions_updated_after_joint(self) -> None:
        """After adding a tongue, dimensions should reflect the extension."""
        from backend.export.section import SectionPart
        from backend.export.joints import add_tongue_and_groove

        solid = _make_box(100, 100, 50)
        part = SectionPart(
            solid=solid,
            filename="test_1of2.stl",
            component="wing",
            side="left",
            section_num=1,
            total_sections=2,
            dimensions_mm=(100.0, 100.0, 50.0),
            print_orientation="flat",
            assembly_order=1,
        )

        right = _make_box(100, 100, 50).translate((0, 100, 0))
        mod_left, _ = add_tongue_and_groove(
            part.solid, right,
            overlap=15, tolerance=0.15, nozzle_diameter=0.4,
        )
        part.solid = mod_left
        part.recompute_dimensions()

        # Y dimension should be larger than original 100mm (tongue extends ~15mm)
        assert part.dimensions_mm[1] > 100.0


# ===================================================================
# #116: STEP export tests
# ===================================================================


class TestStepExport:
    """Tests for STEP export format."""

    def test_build_step_zip_creates_archive(self, tmp_path: Path) -> None:
        """build_step_zip should create a valid ZIP with STEP files."""
        from backend.export import package
        from backend.models import AircraftDesign

        original_tmp = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path

        try:
            components = {
                "fuselage": _make_box(300, 60, 60),
                "wing_left": _make_box(100, 500, 20),
            }
            design = AircraftDesign(id="test-step", name="StepTest")
            zip_path = package.build_step_zip(components, design)

            assert zip_path.exists()
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                assert "manifest.json" in names
                assert "fuselage.step" in names
                assert "wing_left.step" in names

                manifest = json.loads(zf.read("manifest.json"))
                assert manifest["format"] == "step"
                assert manifest["total_files"] == 2
        finally:
            package.EXPORT_TMP_DIR = original_tmp

    def test_step_files_have_content(self, tmp_path: Path) -> None:
        """STEP files should have non-trivial content."""
        from backend.export import package
        from backend.models import AircraftDesign

        original_tmp = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path

        try:
            components = {"box": _make_box(100, 100, 50)}
            design = AircraftDesign(id="test-step-content", name="StepContent")
            zip_path = package.build_step_zip(components, design)

            with zipfile.ZipFile(zip_path, "r") as zf:
                step_data = zf.read("box.step")
                # STEP files start with ISO-10303 header
                assert b"ISO-10303" in step_data or len(step_data) > 100
        finally:
            package.EXPORT_TMP_DIR = original_tmp

    def test_step_geometric_bounds_integrity(self, tmp_path: Path) -> None:
        """Exported STEP files should have valid ISO headers and match original geometric bounds."""
        from backend.export import package
        from backend.models import AircraftDesign
        import cadquery as cq

        original_tmp = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path

        try:
            # Create a box of known dimensions
            components = {"box": _make_box(120, 80, 40)}
            design = AircraftDesign(id="test-step-bounds", name="StepBounds")
            zip_path = package.build_step_zip(components, design)

            with zipfile.ZipFile(zip_path, "r") as zf:
                # Extract step file to temporary path
                step_data = zf.read("box.step")
                
                # Verify ISO-10303 header
                assert b"ISO-10303" in step_data[:1024]
                
                # Write to disk to read with cadquery
                step_file_path = tmp_path / "box.step"
                step_file_path.write_bytes(step_data)
                
                # Import STEP and check bounds
                imported_shape = cq.importers.importStep(str(step_file_path))
                bb = imported_shape.val().BoundingBox()
                
                # Assert geometric bounds match original solid
                assert abs((bb.xmax - bb.xmin) - 120.0) < 0.1
                assert abs((bb.ymax - bb.ymin) - 80.0) < 0.1
                assert abs((bb.zmax - bb.zmin) - 40.0) < 0.1

        finally:
            package.EXPORT_TMP_DIR = original_tmp


# ===================================================================
# #117: DXF export tests
# ===================================================================


class TestDxfExport:
    """Tests for DXF export format."""

    def test_build_dxf_zip_creates_archive(self, tmp_path: Path) -> None:
        """build_dxf_zip should create a valid ZIP with DXF files."""
        from backend.export import package
        from backend.models import AircraftDesign

        original_tmp = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path

        try:
            components = {
                "fuselage": _make_box(300, 60, 60),
            }
            design = AircraftDesign(id="test-dxf", name="DxfTest")
            zip_path = package.build_dxf_zip(components, design)

            assert zip_path.exists()
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                assert "manifest.json" in names
                # Should have at least some DXF cross-section files
                dxf_files = [n for n in names if n.endswith(".dxf")]
                assert len(dxf_files) >= 1

                manifest = json.loads(zf.read("manifest.json"))
                assert manifest["format"] == "dxf"
        finally:
            package.EXPORT_TMP_DIR = original_tmp

    def test_dxf_sections_are_planar_not_slivers(self, tmp_path: Path) -> None:
        """DXF cross-sections should be true 2D profiles, not 3D slivers.

        The old thin-box intersection approach produced ~3x as many LINE entities
        because it generated front face + back face + connecting edges.  The new
        .section() approach should produce clean single-outline profiles.
        """
        from backend.export import package
        from backend.models import AircraftDesign

        original_tmp = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path

        try:
            # A simple box: cross-section of a 300x60x60 box should be a
            # rectangle with exactly 4 LINE entities (one per edge).
            components = {
                "fuselage": _make_box(300, 60, 60),
            }
            design = AircraftDesign(id="test-dxf-planar", name="DxfPlanar")
            zip_path = package.build_dxf_zip(components, design)

            with zipfile.ZipFile(zip_path, "r") as zf:
                dxf_files = [n for n in zf.namelist() if n.endswith(".dxf")]
                assert len(dxf_files) >= 1

                # Check each DXF file has a reasonable number of LINE entities.
                # A rectangle cross-section should have ~4 lines (single outline),
                # NOT ~12+ lines (which would indicate double outlines from slivers).
                for dxf_name in dxf_files:
                    dxf_content = zf.read(dxf_name).decode("utf-8", errors="ignore")
                    line_count = dxf_content.count("\nLINE\n")
                    # A clean rectangular section = 4 lines; allow some margin
                    # but it must be far less than the ~12 the old approach produced
                    assert line_count <= 8, (
                        f"{dxf_name} has {line_count} LINE entities; "
                        "expected <= 8 for a clean 2D profile (old sliver approach "
                        "would produce ~12+)"
                    )
        finally:
            package.EXPORT_TMP_DIR = original_tmp


# ===================================================================
# #118: SVG export tests
# ===================================================================


class TestSvgExport:
    """Tests for SVG export format."""

    def test_build_svg_zip_creates_archive(self, tmp_path: Path) -> None:
        """build_svg_zip should create a valid ZIP with SVG files."""
        from backend.export import package
        from backend.models import AircraftDesign

        original_tmp = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path

        try:
            components = {
                "fuselage": _make_box(300, 60, 60),
            }
            design = AircraftDesign(id="test-svg", name="SvgTest")
            zip_path = package.build_svg_zip(components, design)

            assert zip_path.exists()
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                assert "manifest.json" in names
                svg_files = [n for n in names if n.endswith(".svg")]
                assert len(svg_files) >= 1

                manifest = json.loads(zf.read("manifest.json"))
                assert manifest["format"] == "svg"
        finally:
            package.EXPORT_TMP_DIR = original_tmp

    def test_svg_contains_svg_content(self, tmp_path: Path) -> None:
        """SVG files should contain valid SVG markup."""
        from backend.export import package
        from backend.models import AircraftDesign

        original_tmp = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path

        try:
            components = {"box": _make_box(100, 100, 50)}
            design = AircraftDesign(id="test-svg-content", name="SvgContent")
            zip_path = package.build_svg_zip(components, design)

            with zipfile.ZipFile(zip_path, "r") as zf:
                svg_files = [n for n in zf.namelist() if n.endswith(".svg")]
                if svg_files:
                    svg_data = zf.read(svg_files[0])
                    assert b"<svg" in svg_data or b"<?xml" in svg_data
        finally:
            package.EXPORT_TMP_DIR = original_tmp


# ===================================================================
# ExportRequest format validation
# ===================================================================


class TestExportRequestFormat:
    """Tests for ExportRequest model format field."""

    def test_default_format_is_stl(self) -> None:
        """Default format should be 'stl'."""
        from backend.models import ExportRequest, AircraftDesign
        req = ExportRequest(design=AircraftDesign())
        assert req.format == "stl"

    def test_accepts_step_format(self) -> None:
        """Should accept 'step' format."""
        from backend.models import ExportRequest, AircraftDesign
        req = ExportRequest(design=AircraftDesign(), format="step")
        assert req.format == "step"

    def test_accepts_dxf_format(self) -> None:
        """Should accept 'dxf' format."""
        from backend.models import ExportRequest, AircraftDesign
        req = ExportRequest(design=AircraftDesign(), format="dxf")
        assert req.format == "dxf"

    def test_accepts_svg_format(self) -> None:
        """Should accept 'svg' format."""
        from backend.models import ExportRequest, AircraftDesign
        req = ExportRequest(design=AircraftDesign(), format="svg")
        assert req.format == "svg"

    def test_rejects_invalid_format(self) -> None:
        """Should reject invalid format values."""
        from pydantic import ValidationError
        from backend.models import ExportRequest, AircraftDesign
        with pytest.raises(ValidationError):
            ExportRequest(design=AircraftDesign(), format="obj")
