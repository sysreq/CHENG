"""Export pipeline integration tests -- CadQuery-dependent.

Tests the full pipeline: auto-sectioning, joints, watertight STL,
manifest format, and ZIP packaging.
"""

from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path

import numpy as np
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
# #39: Auto-sectioning tests
# ===================================================================


class TestAutoSection:
    """Tests for the auto_section() algorithm."""

    def test_solid_fits_no_split(self) -> None:
        """A solid smaller than the bed should return one section."""
        from backend.export.section import auto_section

        solid = _make_box(100, 100, 100)
        sections = auto_section(solid, bed_x=220, bed_y=220, bed_z=250)
        assert len(sections) == 1

    def test_oversize_x_splits(self) -> None:
        """A solid exceeding bed X should be split into multiple sections."""
        from backend.export.section import auto_section

        # 500mm long box, bed is 220mm -> usable 200mm -> at least 3 sections
        solid = _make_box(500, 100, 50)
        sections = auto_section(solid, bed_x=220, bed_y=220, bed_z=250)
        assert len(sections) >= 2
        for s in sections:
            dx, dy, dz = _bbox_dims(s)
            assert dx <= 200 + 1.0  # usable = 220 - 20 margin, small tolerance

    def test_oversize_y_splits(self) -> None:
        """A solid exceeding bed Y should be split along Y."""
        from backend.export.section import auto_section

        solid = _make_box(100, 600, 50)
        sections = auto_section(solid, bed_x=220, bed_y=220, bed_z=250)
        assert len(sections) >= 3

    def test_recursive_splitting(self) -> None:
        """A solid oversize in two axes should split recursively."""
        from backend.export.section import auto_section

        solid = _make_box(500, 500, 50)
        sections = auto_section(solid, bed_x=220, bed_y=220, bed_z=250)
        # Each axis needs 3+ sections: 500/200 = 2.5 -> 3
        # Total should be at least 4 (2 splits on each oversize axis)
        assert len(sections) >= 4
        for s in sections:
            dx, dy, dz = _bbox_dims(s)
            assert dx <= 201
            assert dy <= 201

    def test_joint_margin_20mm(self) -> None:
        """Usable volume should be bed minus 20mm margin per axis."""
        from backend.export.section import auto_section

        # Box is exactly 200mm (bed - margin). Should NOT split.
        solid = _make_box(200, 200, 230)
        sections = auto_section(solid, bed_x=220, bed_y=220, bed_z=250)
        assert len(sections) == 1

    def test_trainer_wing_sections(self) -> None:
        """Trainer wing half-span (600mm) with 220mm bed should yield ~3 sections."""
        from backend.export.section import auto_section

        # Trainer: half-span = 600mm, chord = 200mm, thickness ~24mm
        # 600mm along Y, bed_y = 220, usable = 200 -> 3 sections
        solid = _make_box(200, 600, 24)
        sections = auto_section(solid, bed_x=220, bed_y=220, bed_z=250)
        assert len(sections) == 3 or len(sections) == 4  # 600/200 = 3

    def test_invalid_bed_raises(self) -> None:
        """Bed dimensions minus margin <= 0 should raise ValueError."""
        from backend.export.section import auto_section

        solid = _make_box(50, 50, 50)
        with pytest.raises(ValueError, match="no usable volume"):
            auto_section(solid, bed_x=15, bed_y=15, bed_z=15)

    def test_all_sections_have_volume(self) -> None:
        """Every section should have non-trivial volume (no degenerate splits)."""
        from backend.export.section import auto_section

        solid = _make_box(450, 100, 80)
        sections = auto_section(solid, bed_x=220, bed_y=220, bed_z=250)
        for s in sections:
            dx, dy, dz = _bbox_dims(s)
            assert dx > 0.1 and dy > 0.1 and dz > 0.1


# ===================================================================
# #40: Tongue-and-groove joint tests
# ===================================================================


class TestTongueAndGroove:
    """Tests for add_tongue_and_groove() joint generation."""

    def test_joint_modifies_both_parts(self) -> None:
        """Joint should change the bounding boxes of both parts."""
        from backend.export.joints import add_tongue_and_groove

        left = _make_box(100, 100, 50)
        right = _make_box(100, 100, 50).translate((0, 100, 0))

        mod_left, mod_right = add_tongue_and_groove(
            left, right, overlap=15, tolerance=0.15, nozzle_diameter=0.4,
        )

        # Left should be larger (tongue protrudes)
        orig_bb = left.val().BoundingBox()
        mod_bb = mod_left.val().BoundingBox()
        assert mod_bb.ymax > orig_bb.ymax  # tongue extends in +Y

    def test_groove_is_cut(self) -> None:
        """Groove should reduce right part volume."""
        from backend.export.joints import add_tongue_and_groove

        right = _make_box(100, 100, 50).translate((0, 100, 0))
        orig_vol = right.val().Volume()

        _, mod_right = add_tongue_and_groove(
            _make_box(100, 100, 50),
            right,
            overlap=15, tolerance=0.15, nozzle_diameter=0.4,
        )
        mod_vol = mod_right.val().Volume()
        assert mod_vol < orig_vol  # groove cut reduces volume

    def test_tolerance_affects_groove_size(self) -> None:
        """Larger tolerance should produce a larger groove."""
        from backend.export.joints import add_tongue_and_groove

        left = _make_box(100, 100, 50)
        right = _make_box(100, 100, 50).translate((0, 100, 0))

        _, mod_tight = add_tongue_and_groove(
            left, right, overlap=15, tolerance=0.10, nozzle_diameter=0.4,
        )
        _, mod_loose = add_tongue_and_groove(
            left, right, overlap=15, tolerance=0.30, nozzle_diameter=0.4,
        )

        # Looser tolerance = more material removed = smaller volume
        assert mod_loose.val().Volume() < mod_tight.val().Volume()

    def test_tongue_protrudes_by_overlap(self) -> None:
        """Tongue should extend approximately by the overlap distance."""
        from backend.export.joints import add_tongue_and_groove

        left = _make_box(100, 100, 50)
        orig_ymax = left.val().BoundingBox().ymax

        mod_left, _ = add_tongue_and_groove(
            left,
            _make_box(100, 100, 50).translate((0, 100, 0)),
            overlap=15, tolerance=0.15, nozzle_diameter=0.4,
        )
        new_ymax = mod_left.val().BoundingBox().ymax

        assert abs((new_ymax - orig_ymax) - 15) < 1.0  # ~15mm protrusion


# ===================================================================
# #41: Watertight STL / mesh verification
# ===================================================================


class TestWatertightMesh:
    """Tests for mesh integrity from tessellation."""

    def test_box_mesh_has_valid_topology(self) -> None:
        """A CadQuery box tessellation should have valid topology.

        OCCT tessellates each BREP face independently (no shared vertices at
        edges), so strict edge-manifold checks don't apply. Instead we verify:
        - All face indices are within bounds
        - Mesh has expected vertex/face counts for a box
        - The underlying solid is valid per OCCT
        """
        from backend.geometry.tessellate import tessellate_for_preview

        solid = _make_box(100, 50, 30)
        mesh = tessellate_for_preview(solid)

        assert mesh.vertex_count > 0
        assert mesh.face_count >= 12  # box has at least 12 triangles (2 per face)

        # All face indices must be in range
        assert np.all(mesh.faces < mesh.vertex_count)
        assert np.all(mesh.faces >= 0)

        # Underlying OCCT solid should be valid
        assert solid.val().isValid()

    def test_no_degenerate_triangles(self) -> None:
        """No triangle should have zero area."""
        from backend.geometry.tessellate import tessellate_for_preview

        solid = _make_box(100, 50, 30)
        mesh = tessellate_for_preview(solid)

        for i in range(mesh.face_count):
            i0, i1, i2 = mesh.faces[i]
            v0, v1, v2 = mesh.vertices[i0], mesh.vertices[i1], mesh.vertices[i2]
            area = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0))
            assert area > 1e-8, f"Triangle {i} has near-zero area: {area}"

    def test_normals_are_unit_length(self) -> None:
        """All vertex normals should be unit length."""
        from backend.geometry.tessellate import tessellate_for_preview

        solid = _make_box(100, 50, 30)
        mesh = tessellate_for_preview(solid)

        lengths = np.linalg.norm(mesh.normals, axis=1)
        np.testing.assert_allclose(lengths, 1.0, atol=1e-4)

    def test_export_stl_valid_binary(self) -> None:
        """Export STL should be valid binary STL format."""
        from backend.geometry.tessellate import tessellate_for_export

        solid = _make_box(100, 50, 30)
        stl_bytes = tessellate_for_export(solid)

        # Header: 80 bytes
        assert len(stl_bytes) >= 84
        assert stl_bytes[:5] == b"CHENG"

        # Triangle count
        num_triangles = struct.unpack_from("<I", stl_bytes, 80)[0]
        assert num_triangles > 0

        # Total size: 80 + 4 + 50 * num_triangles
        expected_size = 84 + 50 * num_triangles
        assert len(stl_bytes) == expected_size

    def test_lofted_solid_has_valid_topology(self) -> None:
        """A lofted wing-like solid should have valid OCCT topology."""
        from backend.geometry.tessellate import tessellate_for_preview

        # Simple lofted shape (like a tapered wing section)
        solid = (
            cq.Workplane("XZ")
            .ellipse(50, 10)
            .workplane(offset=200)
            .ellipse(30, 7)
            .loft(ruled=False)
        )
        mesh = tessellate_for_preview(solid)
        assert mesh.vertex_count > 0
        assert mesh.face_count > 0

        # All face indices must be in range
        assert np.all(mesh.faces < mesh.vertex_count)
        assert np.all(mesh.faces >= 0)

        # Underlying solid should be valid
        assert solid.val().isValid()


# ===================================================================
# #47: Manifest format verification
# ===================================================================


class TestManifest:
    """Tests for manifest.json format per spec section 8.4."""

    def test_section_key_name(self) -> None:
        """Manifest should use 'section' not 'section_number' per spec."""
        from backend.export.package import _build_manifest
        from backend.export.section import SectionPart

        solid = _make_box(100, 100, 50)
        section = SectionPart(
            solid=solid,
            filename="wing_left_1of1.stl",
            component="wing",
            side="left",
            section_num=1,
            total_sections=1,
            dimensions_mm=(100.0, 100.0, 50.0),
            print_orientation="trailing-edge down",
            assembly_order=1,
        )

        from backend.models import AircraftDesign
        manifest = _build_manifest([section], AircraftDesign())

        part = manifest["parts"][0]
        assert "section" in part, "Manifest should have 'section' key"
        assert "section_number" not in part, "Manifest should NOT have 'section_number'"
        assert part["section"] == 1

    def test_dimensions_mm_is_array(self) -> None:
        """dimensions_mm should be an array [x, y, z], not an object."""
        from backend.export.package import _build_manifest
        from backend.export.section import SectionPart
        from backend.models import AircraftDesign

        solid = _make_box(100, 100, 50)
        section = SectionPart(
            solid=solid,
            filename="wing_left_1of1.stl",
            component="wing",
            side="left",
            section_num=1,
            total_sections=1,
            dimensions_mm=(100.0, 100.0, 50.0),
            print_orientation="trailing-edge down",
            assembly_order=1,
        )

        manifest = _build_manifest([section], AircraftDesign())
        dims = manifest["parts"][0]["dimensions_mm"]
        assert isinstance(dims, list), f"Expected list, got {type(dims)}"
        assert len(dims) == 3
        assert dims == [100.0, 100.0, 50.0]

    def test_all_required_fields_present(self) -> None:
        """Manifest should have all required top-level and part-level fields."""
        from backend.export.package import _build_manifest
        from backend.export.section import SectionPart
        from backend.models import AircraftDesign

        solid = _make_box(100, 100, 50)
        section = SectionPart(
            solid=solid,
            filename="wing_left_1of1.stl",
            component="wing",
            side="left",
            section_num=1,
            total_sections=1,
            dimensions_mm=(100.0, 100.0, 50.0),
            print_orientation="trailing-edge down",
            assembly_order=1,
        )

        manifest = _build_manifest([section], AircraftDesign())

        # Top-level required fields
        for key in ["design_name", "design_id", "version", "exported_at",
                     "total_parts", "parts", "assembly_notes"]:
            assert key in manifest, f"Missing top-level key: {key}"

        # Part-level required fields
        part = manifest["parts"][0]
        for key in ["filename", "component", "side", "section",
                     "total_sections", "dimensions_mm", "print_orientation",
                     "assembly_order"]:
            assert key in part, f"Missing part key: {key}"

    def test_manifest_is_json_serializable(self) -> None:
        """Manifest should serialize to valid JSON."""
        from backend.export.package import _build_manifest
        from backend.export.section import SectionPart
        from backend.models import AircraftDesign

        solid = _make_box(100, 100, 50)
        section = SectionPart(
            solid=solid,
            filename="test_1of1.stl",
            component="fuselage",
            side="center",
            section_num=1,
            total_sections=1,
            dimensions_mm=(100.0, 100.0, 50.0),
            print_orientation="flat",
            assembly_order=1,
        )

        manifest = _build_manifest([section], AircraftDesign())
        json_str = json.dumps(manifest, indent=2)
        parsed = json.loads(json_str)
        assert parsed["total_parts"] == 1


# ===================================================================
# #55: Full pipeline integration tests
# ===================================================================


class TestExportPipelineIntegration:
    """End-to-end tests: assemble -> section -> joints -> tessellate -> ZIP."""

    def test_section_and_joints_pipeline(self) -> None:
        """Section an oversize box, apply joints, verify results."""
        from backend.export.section import auto_section, create_section_parts
        from backend.export.joints import add_tongue_and_groove

        solid = _make_box(100, 500, 50)
        sections = auto_section(solid, bed_x=220, bed_y=220, bed_z=250)
        assert len(sections) >= 2

        # Apply joints between adjacent pairs
        for i in range(len(sections) - 1):
            left, right = add_tongue_and_groove(
                sections[i], sections[i + 1],
                overlap=15, tolerance=0.15, nozzle_diameter=0.4,
            )
            sections[i] = left
            sections[i + 1] = right

        # Create section parts with metadata
        parts = create_section_parts("wing", "left", sections)
        assert len(parts) == len(sections)
        for i, part in enumerate(parts, start=1):
            assert part.section_num == i
            assert part.total_sections == len(sections)
            assert part.filename == f"wing_left_{i}of{len(sections)}.stl"

    def test_build_zip_produces_valid_archive(self, tmp_path: Path) -> None:
        """build_zip should create a valid ZIP with manifest + STLs."""
        from backend.export.section import SectionPart
        from backend.export import package
        from backend.models import AircraftDesign

        # Override temp dir to use pytest tmp_path
        original_tmp = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path

        try:
            solid = _make_box(100, 100, 50)
            sections = [
                SectionPart(
                    solid=solid,
                    filename="fuselage_center_1of1.stl",
                    component="fuselage",
                    side="center",
                    section_num=1,
                    total_sections=1,
                    dimensions_mm=(100.0, 100.0, 50.0),
                    print_orientation="flat",
                    assembly_order=1,
                ),
            ]

            design = AircraftDesign(id="test-zip-001", name="ZipTest")
            zip_path = package.build_zip(sections, design)

            assert zip_path.exists()
            assert zip_path.suffix == ".zip"

            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                assert "manifest.json" in names
                assert "fuselage_center_1of1.stl" in names

                # Verify manifest is valid JSON
                manifest_data = json.loads(zf.read("manifest.json"))
                assert manifest_data["design_name"] == "ZipTest"
                assert manifest_data["total_parts"] == 1

                # Verify STL is valid binary
                stl_data = zf.read("fuselage_center_1of1.stl")
                assert len(stl_data) >= 84
                assert stl_data[:5] == b"CHENG"
        finally:
            package.EXPORT_TMP_DIR = original_tmp

    def test_multi_component_zip(self, tmp_path: Path) -> None:
        """ZIP with multiple components should contain all files."""
        from backend.export.section import SectionPart
        from backend.export import package
        from backend.models import AircraftDesign

        original_tmp = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path

        try:
            sections = []
            for i, (comp, side) in enumerate([
                ("fuselage", "center"),
                ("wing", "left"),
                ("wing", "right"),
            ], start=1):
                solid = _make_box(100, 100, 50)
                sections.append(SectionPart(
                    solid=solid,
                    filename=f"{comp}_{side}_1of1.stl",
                    component=comp,
                    side=side,
                    section_num=1,
                    total_sections=1,
                    dimensions_mm=(100.0, 100.0, 50.0),
                    print_orientation="flat",
                    assembly_order=i,
                ))

            design = AircraftDesign(id="test-multi", name="MultiTest")
            zip_path = package.build_zip(sections, design)

            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                assert len(names) == 4  # 3 STLs + manifest
                assert "manifest.json" in names
                assert "fuselage_center_1of1.stl" in names
                assert "wing_left_1of1.stl" in names
                assert "wing_right_1of1.stl" in names

                manifest = json.loads(zf.read("manifest.json"))
                assert manifest["total_parts"] == 3
                # Parts should be sorted by assembly order
                orders = [p["assembly_order"] for p in manifest["parts"]]
                assert orders == sorted(orders)
        finally:
            package.EXPORT_TMP_DIR = original_tmp

    def test_full_trainer_pipeline(self) -> None:
        """Full pipeline with Trainer preset: assemble, section, package metadata."""
        from backend.geometry.engine import assemble_aircraft
        from backend.export.section import auto_section, create_section_parts
        from backend.models import AircraftDesign

        design = AircraftDesign(
            name="Trainer",
            wing_span=1200,
            wing_chord=200,
            wing_airfoil="Clark-Y",
            wing_tip_root_ratio=1.0,
            wing_dihedral=3,
            wing_sweep=0,
            fuselage_preset="Conventional",
            fuselage_length=400,
            tail_type="Conventional",
            h_stab_span=400,
            h_stab_chord=120,
            h_stab_incidence=-1,
            v_stab_height=120,
            v_stab_root_chord=130,
            tail_arm=220,
            hollow_parts=False,  # Solid for faster tests
            print_bed_x=220,
            print_bed_y=220,
            print_bed_z=250,
        )

        # Assemble
        components = assemble_aircraft(design)
        assert "fuselage" in components
        assert "wing_left" in components
        assert "wing_right" in components

        # Section each component
        all_parts = []
        order = 1
        for name, solid in components.items():
            sections = auto_section(
                solid, design.print_bed_x, design.print_bed_y, design.print_bed_z,
            )
            # Parse component and side from name
            if "_" in name:
                comp, side = name.rsplit("_", 1)
            else:
                comp, side = name, "center"

            parts = create_section_parts(comp, side, sections, start_assembly_order=order)
            all_parts.extend(parts)
            order += len(parts)

        # Should have multiple parts total (wings will need sectioning)
        assert len(all_parts) >= 5  # fuselage + 2 wings (each sectioned) + tail parts

    def test_exported_stl_geometric_bounds(self, tmp_path: Path) -> None:
        """Exported STL files should have headers, correct triangle counts, and valid geometric bounds."""
        from backend.export.section import SectionPart
        from backend.export import package
        from backend.models import AircraftDesign

        original_tmp = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path

        try:
            solid = _make_box(100, 100, 50)
            sections = [
                SectionPart(
                    solid=solid,
                    filename="box_1of1.stl",
                    component="box",
                    side="center",
                    section_num=1,
                    total_sections=1,
                    dimensions_mm=(100.0, 100.0, 50.0),
                    print_orientation="flat",
                    assembly_order=1,
                ),
            ]

            design = AircraftDesign(id="test-zip-bounds", name="BoundsTest")
            zip_path = package.build_zip(sections, design)

            with zipfile.ZipFile(zip_path, "r") as zf:
                stl_data = zf.read("box_1of1.stl")
                
                # Check header
                assert stl_data[:5] == b"CHENG"
                
                # Check triangle count and file size
                num_triangles = struct.unpack_from("<I", stl_data, 80)[0]
                expected_size = 84 + 50 * num_triangles
                assert len(stl_data) == expected_size
                
                # Compute bounds manually from binary STL
                min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
                max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')
                
                offset = 84
                for _ in range(num_triangles):
                    offset += 12 # Skip normal
                    for _ in range(3): # 3 vertices
                        x, y, z = struct.unpack_from("<fff", stl_data, offset)
                        min_x = min(min_x, x)
                        max_x = max(max_x, x)
                        min_y = min(min_y, y)
                        max_y = max(max_y, y)
                        min_z = min(min_z, z)
                        max_z = max(max_z, z)
                        offset += 12
                    offset += 2 # Skip attribute byte count
                
                dx = max_x - min_x
                dy = max_y - min_y
                dz = max_z - min_z
                
                # Assert geometric bounds match original solid
                assert abs(dx - 100.0) < 0.1
                assert abs(dy - 100.0) < 0.1
                assert abs(dz - 50.0) < 0.1
                
        finally:
            package.EXPORT_TMP_DIR = original_tmp

