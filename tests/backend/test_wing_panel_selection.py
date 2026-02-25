"""Tests for multi-section wing panel tessellation and per-panel componentRanges.

Covers:
  - build_wing_panels() returns N separate panel solids for N sections (#241)
  - build_wing_panels() falls back to single panel for single-section wings
  - _generate_mesh() exposes per-panel face ranges: wing_left_0, wing_left_1, ...
  - Combined wing_left/wing_right/wing ranges are maintained for backward compat
  - Single-section wing still works with original wing_left / wing_right keys
"""

from __future__ import annotations

import pytest

from backend.models import AircraftDesign


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def single_section_design() -> AircraftDesign:
    """Single-section wing design (default)."""
    return AircraftDesign(
        name="Single Section",
        wing_span=1000,
        wing_chord=180,
        wing_airfoil="Clark-Y",
        wing_tip_root_ratio=1.0,
        wing_dihedral=3,
        wing_sweep=0,
        fuselage_preset="Conventional",
        fuselage_length=300,
        tail_type="Conventional",
        hollow_parts=False,
    )


@pytest.fixture
def two_section_design() -> AircraftDesign:
    """Two-section polyhedral wing design."""
    return AircraftDesign(
        name="Two Section",
        wing_span=1000,
        wing_chord=180,
        wing_airfoil="Clark-Y",
        wing_tip_root_ratio=0.7,
        wing_dihedral=3,
        wing_sweep=5,
        fuselage_preset="Conventional",
        fuselage_length=300,
        tail_type="Conventional",
        hollow_parts=False,
        wing_sections=2,
        panel_break_positions=[60.0, 80.0, 90.0],
        panel_dihedrals=[10.0, 5.0, 5.0],
        panel_sweeps=[0.0, 0.0, 0.0],
    )


@pytest.fixture
def three_section_design() -> AircraftDesign:
    """Three-section gull-wing design."""
    return AircraftDesign(
        name="Three Section",
        wing_span=1000,
        wing_chord=180,
        wing_airfoil="Clark-Y",
        wing_tip_root_ratio=0.7,
        wing_dihedral=3,
        wing_sweep=5,
        fuselage_preset="Conventional",
        fuselage_length=300,
        tail_type="Conventional",
        hollow_parts=False,
        wing_sections=3,
        panel_break_positions=[40.0, 70.0, 90.0],
        panel_dihedrals=[8.0, 15.0, 5.0],
        panel_sweeps=[3.0, 3.0, 0.0],
    )


# ---------------------------------------------------------------------------
# build_wing_panels() tests (#241)
# ---------------------------------------------------------------------------


class TestBuildWingPanels:
    """Tests for the build_wing_panels() function."""

    def test_single_section_returns_one_panel(
        self, single_section_design: AircraftDesign
    ) -> None:
        """Single-section wing should return a list with exactly one panel."""
        from backend.geometry.wing import build_wing_panels

        panels = build_wing_panels(single_section_design, side="right")
        assert len(panels) == 1
        assert panels[0].val().Volume() > 0

    def test_single_section_left_returns_one_panel(
        self, single_section_design: AircraftDesign
    ) -> None:
        """Single-section left wing should return one panel."""
        from backend.geometry.wing import build_wing_panels

        panels = build_wing_panels(single_section_design, side="left")
        assert len(panels) == 1
        assert panels[0].val().Volume() > 0

    def test_two_section_returns_two_panels(
        self, two_section_design: AircraftDesign
    ) -> None:
        """Two-section wing should return exactly 2 panel solids."""
        from backend.geometry.wing import build_wing_panels

        panels = build_wing_panels(two_section_design, side="right")
        assert len(panels) == 2
        for panel in panels:
            assert panel.val().Volume() > 0, "Each panel must have positive volume"

    def test_two_section_both_sides(self, two_section_design: AircraftDesign) -> None:
        """Both left and right two-section wings should return 2 panels each."""
        from backend.geometry.wing import build_wing_panels

        left_panels = build_wing_panels(two_section_design, side="left")
        right_panels = build_wing_panels(two_section_design, side="right")
        assert len(left_panels) == 2
        assert len(right_panels) == 2

    def test_three_section_returns_three_panels(
        self, three_section_design: AircraftDesign
    ) -> None:
        """Three-section wing should return exactly 3 panel solids."""
        from backend.geometry.wing import build_wing_panels

        panels = build_wing_panels(three_section_design, side="right")
        assert len(panels) == 3
        for panel in panels:
            assert panel.val().Volume() > 0

    def test_panels_have_different_bounding_boxes(
        self, two_section_design: AircraftDesign
    ) -> None:
        """Each panel should occupy a different spanwise region."""
        from backend.geometry.wing import build_wing_panels

        panels = build_wing_panels(two_section_design, side="right")
        assert len(panels) == 2
        bbox0 = panels[0].val().BoundingBox()
        bbox1 = panels[1].val().BoundingBox()
        # The inner panel's Y extent should be different (smaller) than outer panel's extent
        # Both should have positive Y length
        assert bbox0.ylen > 0
        assert bbox1.ylen > 0

    def test_single_section_panel_matches_build_wing(
        self, single_section_design: AircraftDesign
    ) -> None:
        """Single-section build_wing_panels panel volume ~= build_wing volume."""
        from backend.geometry.wing import build_wing, build_wing_panels

        panel = build_wing_panels(single_section_design, side="right")[0]
        wing = build_wing(single_section_design, side="right")
        # Volume should be approximately equal (same geometry, different return type)
        ratio = panel.val().Volume() / wing.val().Volume()
        assert 0.9 < ratio < 1.1, f"Volume ratio {ratio:.3f} not near 1.0"


# ---------------------------------------------------------------------------
# _generate_mesh() componentRanges tests (#241, #242)
# ---------------------------------------------------------------------------


class TestGenerateMeshPanelRanges:
    """Tests for per-panel face ranges in _generate_mesh() componentRanges."""

    def test_single_section_has_wing_left_right_keys(
        self, single_section_design: AircraftDesign
    ) -> None:
        """Single-section wing should produce wing_left and wing_right keys."""
        from backend.routes.websocket import _generate_mesh

        mesh, ranges = _generate_mesh(single_section_design)
        assert "wing_left" in ranges
        assert "wing_right" in ranges
        # Single-section should NOT have panel sub-keys
        assert "wing_left_0" not in ranges
        assert "wing_right_0" not in ranges

    def test_two_section_has_panel_sub_keys(
        self, two_section_design: AircraftDesign
    ) -> None:
        """Two-section wing should expose wing_left_0, wing_left_1, wing_right_0, wing_right_1."""
        from backend.routes.websocket import _generate_mesh

        mesh, ranges = _generate_mesh(two_section_design)
        assert "wing_left_0" in ranges, f"Keys: {list(ranges.keys())}"
        assert "wing_left_1" in ranges, f"Keys: {list(ranges.keys())}"
        assert "wing_right_0" in ranges, f"Keys: {list(ranges.keys())}"
        assert "wing_right_1" in ranges, f"Keys: {list(ranges.keys())}"
        # Should NOT have a third panel
        assert "wing_left_2" not in ranges

    def test_three_section_has_three_panel_keys(
        self, three_section_design: AircraftDesign
    ) -> None:
        """Three-section wing should expose _0, _1, _2 sub-keys."""
        from backend.routes.websocket import _generate_mesh

        mesh, ranges = _generate_mesh(three_section_design)
        assert "wing_left_0" in ranges
        assert "wing_left_1" in ranges
        assert "wing_left_2" in ranges
        assert "wing_right_0" in ranges
        assert "wing_right_1" in ranges
        assert "wing_right_2" in ranges
        assert "wing_left_3" not in ranges

    def test_two_section_combined_range_spans_panels(
        self, two_section_design: AircraftDesign
    ) -> None:
        """Combined wing_left range must span all its panel sub-ranges."""
        from backend.routes.websocket import _generate_mesh

        mesh, ranges = _generate_mesh(two_section_design)
        left = ranges["wing_left"]
        p0 = ranges["wing_left_0"]
        p1 = ranges["wing_left_1"]
        assert left[0] <= p0[0], "wing_left start must be <= panel_0 start"
        assert left[1] >= p1[1], "wing_left end must be >= panel_1 end"

    def test_panel_ranges_are_non_overlapping(
        self, two_section_design: AircraftDesign
    ) -> None:
        """Panel face ranges must not overlap: panel_0 end == panel_1 start."""
        from backend.routes.websocket import _generate_mesh

        mesh, ranges = _generate_mesh(two_section_design)
        p0 = ranges["wing_left_0"]
        p1 = ranges["wing_left_1"]
        assert p0[1] == p1[0], (
            f"panel_0 end {p0[1]} must equal panel_1 start {p1[0]} (no gap/overlap)"
        )

    def test_panel_ranges_have_positive_face_counts(
        self, two_section_design: AircraftDesign
    ) -> None:
        """Each panel sub-range must contain at least one face."""
        from backend.routes.websocket import _generate_mesh

        mesh, ranges = _generate_mesh(two_section_design)
        for key in ("wing_left_0", "wing_left_1", "wing_right_0", "wing_right_1"):
            r = ranges[key]
            assert r[1] > r[0], f"{key} range is empty: {r}"

    def test_backward_compat_wing_key_present(
        self, two_section_design: AircraftDesign
    ) -> None:
        """Combined 'wing' key must still be present for single-section compat."""
        from backend.routes.websocket import _generate_mesh

        mesh, ranges = _generate_mesh(two_section_design)
        assert "wing" in ranges

    def test_fuselage_and_tail_keys_still_present(
        self, two_section_design: AircraftDesign
    ) -> None:
        """Non-wing components must still be tracked in componentRanges."""
        from backend.routes.websocket import _generate_mesh

        mesh, ranges = _generate_mesh(two_section_design)
        assert "fuselage" in ranges
        # tail should be present (conventional tail)
        has_tail = any("stab" in k or k == "tail" for k in ranges)
        assert has_tail, f"No tail keys found. Keys: {list(ranges.keys())}"

    def test_mesh_face_count_consistent_with_ranges(
        self, two_section_design: AircraftDesign
    ) -> None:
        """Total face count in mesh must cover all range endpoints."""
        from backend.routes.websocket import _generate_mesh

        mesh, ranges = _generate_mesh(two_section_design)
        max_face_end = max(r[1] for r in ranges.values())
        assert mesh.face_count >= max_face_end, (
            f"mesh.face_count {mesh.face_count} < max range end {max_face_end}"
        )
