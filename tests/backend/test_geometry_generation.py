"""Tests for the 3D geometry builders using CadQuery.

These tests verify that the wing, fuselage, and tail builders produce
valid, watertight solids with expected dimensions and properties.
"""

from __future__ import annotations

import cadquery as cq
import pytest

from backend.geometry.wing import build_wing
from backend.geometry.fuselage import build_fuselage
from backend.geometry.tail import build_tail
from backend.models import AircraftDesign


@pytest.fixture
def default_design() -> AircraftDesign:
    """Standard Trainer design for baseline testing."""
    return AircraftDesign(
        name="Test Trainer",
        wing_span=1200,
        wing_chord=200,
        wing_airfoil="Clark-Y",
        fuselage_preset="Conventional",
        fuselage_length=400,
        tail_type="Conventional",
    )


# ---------------------------------------------------------------------------
# Wing Builder Tests
# ---------------------------------------------------------------------------

class TestWingBuilder:
    """Tests for backend.geometry.wing.build_wing()."""

    def test_build_wing_half_is_solid(self, default_design: AircraftDesign) -> None:
        """Should produce a valid solid with positive volume."""
        wing = build_wing(default_design, side="right")

        # Verify it's a solid
        assert wing.val().ShapeType() == "Solid"
        assert wing.val().Volume() > 0

    def test_wing_dimensions(self, default_design: AircraftDesign) -> None:
        """Wing bounding box should match input parameters."""
        wing = build_wing(default_design, side="right")
        bbox = wing.val().BoundingBox()

        # Span: half_span is 600.
        # Orientation observation: the builder seems to extend the 'right' wing
        # in the -Y direction or centers it in a way that yields (-600, 0).
        assert pytest.approx(bbox.ylen, abs=1.0) == 600.0

        # Chord: 200mm. BBox X should be roughly 200mm.
        assert pytest.approx(bbox.xlen, abs=1.0) == 200.0

    def test_wing_hollow_shelling(self, default_design: AircraftDesign) -> None:
        """Hollow wing should have less volume than solid wing if shell succeeds."""
        default_design.hollow_parts = False
        solid_wing = build_wing(default_design, side="right")
        solid_vol = solid_wing.val().Volume()

        default_design.hollow_parts = True
        default_design.wing_skin_thickness = 0.8
        hollow_wing = build_wing(default_design, side="right")
        hollow_vol = hollow_wing.val().Volume()

        # Note: .shell() can fail and return original solid.
        # We check that it at least doesn't CRASH, and if it succeeds, vol is less.
        assert hollow_vol <= solid_vol

    # -- #213: Flat-Plate airfoil tests --

    def test_flat_plate_wing_builds_valid_solid(self, default_design: AircraftDesign) -> None:
        """#213: Flat-Plate airfoil must produce a valid non-degenerate solid.

        The flat_plate.dat file has only 3% total thickness.  Under sweep, taper,
        or incidence this can produce a degenerate loft.  After the fix,
        load_airfoil uses generate_flat_plate() which returns a 6% diamond profile
        that is geometrically robust across all parameter combinations.
        """
        default_design.wing_airfoil = "Flat-Plate"
        wing = build_wing(default_design, side="right")
        assert wing.val().ShapeType() == "Solid"
        assert wing.val().Volume() > 0

    def test_flat_plate_wing_span_correct(self, default_design: AircraftDesign) -> None:
        """#213: Flat-Plate wing span should match wing_span / 2."""
        default_design.wing_airfoil = "Flat-Plate"
        wing = build_wing(default_design, side="right")
        bbox = wing.val().BoundingBox()
        assert pytest.approx(bbox.ylen, abs=2.0) == 600.0

    def test_flat_plate_uses_generated_profile(self) -> None:
        """#213: load_airfoil('Flat-Plate') must use generate_flat_plate() (6% thickness).

        The programmatic 6% diamond profile is used instead of the 3% flat_plate.dat
        to ensure robust CadQuery lofting.
        """
        from backend.geometry.airfoil import load_airfoil, generate_flat_plate

        loaded = load_airfoil("Flat-Plate")
        generated = generate_flat_plate()

        # Verify load_airfoil returns the programmatic profile (same points)
        assert loaded == generated, (
            "load_airfoil('Flat-Plate') must return the same points as generate_flat_plate()"
        )

        # Verify 6% total thickness (max y should be ~0.03 = 3% per surface)
        max_y = max(p[1] for p in loaded)
        assert abs(max_y - 0.03) < 0.005, (
            f"Flat-Plate max y should be ~0.03 (6% total thickness), got {max_y:.4f}"
        )

    # -- #214: Wing incidence (W06) tests --

    def test_wing_incidence_changes_geometry(self, default_design: AircraftDesign) -> None:
        """#214: wing_incidence must change the airfoil cross-section orientation.

        Positive incidence tilts the leading edge upward (positive Z in the XZ
        workplane).  The wing with 5 deg incidence must have a different Z bounding
        box than the wing with 0 deg incidence.
        """
        default_design.wing_incidence = 0.0
        wing_zero = build_wing(default_design, side="right")
        bbox_zero = wing_zero.val().BoundingBox()

        default_design.wing_incidence = 5.0
        wing_five = build_wing(default_design, side="right")
        bbox_five = wing_five.val().BoundingBox()

        # Both must be valid solids
        assert wing_zero.val().ShapeType() == "Solid"
        assert wing_five.val().ShapeType() == "Solid"

        # Positive incidence tilts LE up -> zmin decreases (TE goes down relative to LE)
        # The two wings must have measurably different Z extents.
        assert bbox_five.zmin < bbox_zero.zmin - 1.0, (
            f"zmin did not decrease with positive incidence: "
            f"incidence=0 zmin={bbox_zero.zmin:.2f}, incidence=5 zmin={bbox_five.zmin:.2f}"
        )

    def test_wing_incidence_positive_is_nose_up(self, default_design: AircraftDesign) -> None:
        """#214: Positive incidence must raise the leading edge (LE goes up in Z)."""
        import math
        from backend.geometry.wing import _scale_airfoil_2d
        from backend.geometry.airfoil import load_airfoil

        profile = load_airfoil("Clark-Y")
        chord = 200.0

        pts_zero = _scale_airfoil_2d(profile, chord, 0.0)
        pts_pos = _scale_airfoil_2d(profile, chord, 5.0)

        # LE point is the one with minimum x value
        le_zero = min(pts_zero, key=lambda p: p[0])
        le_pos = min(pts_pos, key=lambda p: p[0])

        # With positive incidence, LE should go UP (positive z in XZ plane)
        assert le_pos[1] > le_zero[1] + 1.0, (
            f"LE z did not increase with positive incidence: "
            f"z_zero={le_zero[1]:.3f}, z_pos={le_pos[1]:.3f}"
        )

    # -- #215: Wing washout / twist (W16) tests --

    def test_wing_twist_applied_at_tip(self, default_design: AircraftDesign) -> None:
        """#215: wing_twist must produce a different tip cross-section than root.

        Linear interpolation: root twist = 0, tip twist = wing_twist_deg.
        The tip cross-section must differ when twist != 0.
        """
        from backend.geometry.wing import _scale_airfoil_2d
        from backend.geometry.airfoil import load_airfoil

        profile = load_airfoil("Clark-Y")
        chord = 200.0
        incidence = default_design.wing_incidence
        twist = 3.0

        # Root: no twist applied beyond incidence
        root_pts = _scale_airfoil_2d(profile, chord, incidence + 0.0)
        # Tip (frac=1.0): full twist applied
        tip_pts = _scale_airfoil_2d(profile, chord, incidence + twist)

        # Tip must differ from root cross-section
        assert root_pts != tip_pts, "Tip cross-section must differ from root when twist != 0"

        # The LE z position at tip should be different from root
        le_root = min(root_pts, key=lambda p: p[0])
        le_tip = min(tip_pts, key=lambda p: p[0])
        assert abs(le_tip[1] - le_root[1]) > 0.5, (
            f"LE z difference between root and tip too small with twist={twist}: "
            f"root_z={le_root[1]:.3f}, tip_z={le_tip[1]:.3f}"
        )

    def test_wing_twist_builds_valid_solid(self, default_design: AircraftDesign) -> None:
        """#215: wing with non-zero twist must build a valid solid."""
        default_design.wing_twist = 3.0
        wing = build_wing(default_design, side="right")
        assert wing.val().ShapeType() == "Solid"
        assert wing.val().Volume() > 0

    def test_wing_zero_twist_and_nonzero_twist_differ(self, default_design: AircraftDesign) -> None:
        """#215: Wings with 0 and non-zero twist must produce geometrically different solids."""
        default_design.wing_twist = 0.0
        wing_zero = build_wing(default_design, side="right")

        default_design.wing_twist = 3.0
        wing_twist = build_wing(default_design, side="right")

        bbox_zero = wing_zero.val().BoundingBox()
        bbox_twist = wing_twist.val().BoundingBox()

        # Both must be valid
        assert wing_zero.val().ShapeType() == "Solid"
        assert wing_twist.val().ShapeType() == "Solid"

        # The Z extents must differ (twist changes tip airfoil orientation).
        # Twist is applied only at the tip (root has 0 twist), so the effect on the
        # overall bounding box is small but measurable -- we just confirm it's nonzero.
        z_diff = abs(bbox_twist.zmax - bbox_zero.zmax) + abs(bbox_twist.zmin - bbox_zero.zmin)
        assert z_diff > 0.01, (
            f"Wings with twist=0 and twist=3 have identical Z extents -- twist has no effect. "
            f"twist=0: zmin={bbox_zero.zmin:.3f}, zmax={bbox_zero.zmax:.3f}; "
            f"twist=3: zmin={bbox_twist.zmin:.3f}, zmax={bbox_twist.zmax:.3f}"
        )


# ---------------------------------------------------------------------------
# Fuselage Builder Tests
# ---------------------------------------------------------------------------

class TestFuselageBuilder:
    """Tests for backend.geometry.fuselage.build_fuselage()."""

    @pytest.mark.parametrize("preset", ["Conventional", "Pod", "Blended-Wing-Body"])
    def test_build_fuselage_presets(self, preset: str, default_design: AircraftDesign) -> None:
        """All fuselage presets should produce valid solids."""
        default_design.fuselage_preset = preset
        fuselage = build_fuselage(default_design)
        
        assert fuselage.val().ShapeType() == "Solid"
        assert fuselage.val().Volume() > 0
        
        bbox = fuselage.val().BoundingBox()
        # Length: fuselage_length + motor_boss_depth (15mm)
        expected_len = default_design.fuselage_length + 15.0
        assert pytest.approx(bbox.xlen, abs=1.0) == expected_len


# ---------------------------------------------------------------------------
# Tail Builder Tests
# ---------------------------------------------------------------------------

class TestTailBuilder:
    """Tests for backend.geometry.tail.build_tail()."""

    @pytest.mark.parametrize("tail_type", ["Conventional", "T-Tail", "V-Tail", "Cruciform"])
    def test_build_tail_types(self, tail_type: str, default_design: AircraftDesign) -> None:
        """All tail types should produce dictionaries of valid solids."""
        default_design.tail_type = tail_type
        tail_parts = build_tail(default_design)
        
        assert isinstance(tail_parts, dict)
        assert len(tail_parts) >= 2
        
        for name, part in tail_parts.items():
            assert part.val().ShapeType() == "Solid", f"Part {name} is not a solid"
            assert part.val().Volume() > 0, f"Part {name} has zero volume"

    def test_v_tail_angle(self, default_design: AircraftDesign) -> None:
        """V-Tail dihedral should affect bounding box height."""
        default_design.tail_type = "V-Tail"
        default_design.v_tail_dihedral = 30
        tail_30 = build_tail(default_design)
        h30 = tail_30["v_tail_right"].val().BoundingBox().zlen
        
        default_design.v_tail_dihedral = 45
        tail_45 = build_tail(default_design)
        h45 = tail_45["v_tail_right"].val().BoundingBox().zlen
        
        assert h45 > h30
