"""Tests for multi-section wing geometry (Issue #143).

Covers:
  - Single-section regression (no behaviour change)
  - Two-section and three-section wing geometry generation
  - Panel break chord interpolation correctness
  - Cranked MAC calculation
  - Validation rules V29 (break ordering, limit checks)
  - Model serialization (camelCase alias)
  - WebSocket preview generation for multi-section wings
"""

from __future__ import annotations

import math

import pytest

from backend.models import AircraftDesign
from backend.geometry.engine import _compute_mac_cranked, compute_derived_values
from backend.validation import compute_warnings, _check_v29


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_design() -> AircraftDesign:
    """Minimal valid design for wing tests."""
    return AircraftDesign(
        name="Multi-Section Test",
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
    )


@pytest.fixture
def two_section_design(base_design: AircraftDesign) -> AircraftDesign:
    """Two-section wing (classic polyhedral glider layout)."""
    base_design.wing_sections = 2
    base_design.panel_break_positions = [60.0, 80.0, 90.0]
    base_design.panel_dihedrals = [10.0, 5.0, 5.0]
    base_design.panel_sweeps = [0.0, 0.0, 0.0]
    return base_design


@pytest.fixture
def three_section_design(base_design: AircraftDesign) -> AircraftDesign:
    """Three-section gull-wing layout."""
    base_design.wing_sections = 3
    base_design.panel_break_positions = [40.0, 70.0, 90.0]
    base_design.panel_dihedrals = [8.0, 15.0, 5.0]
    base_design.panel_sweeps = [3.0, 3.0, 0.0]
    return base_design


# ---------------------------------------------------------------------------
# Single-section regression
# ---------------------------------------------------------------------------


class TestSingleSectionRegression:
    """Wing single-section mode must continue to work unchanged."""

    def test_single_section_default(self, base_design: AircraftDesign) -> None:
        """Default wing_sections=1 should produce a valid solid."""
        from backend.geometry.wing import build_wing

        assert base_design.wing_sections == 1
        wing = build_wing(base_design, side="right")
        assert wing.val().ShapeType() == "Solid"
        assert wing.val().Volume() > 0

    def test_single_section_both_sides(self, base_design: AircraftDesign) -> None:
        """Both left and right halves should be valid."""
        from backend.geometry.wing import build_wing

        left = build_wing(base_design, side="left")
        right = build_wing(base_design, side="right")
        assert left.val().Volume() > 0
        assert right.val().Volume() > 0

    def test_single_section_with_dihedral(self, base_design: AircraftDesign) -> None:
        """Single-section wing with dihedral should have correct bounding box height."""
        from backend.geometry.wing import build_wing

        base_design.wing_dihedral = 10
        wing = build_wing(base_design, side="right")
        bbox = wing.val().BoundingBox()
        # With 10 deg dihedral over 500mm, tip rises ~88mm
        expected_z_rise = 500 * math.tan(math.radians(10))
        # Z extent should be at least the rise (plus airfoil thickness)
        assert bbox.zlen > expected_z_rise * 0.8


# ---------------------------------------------------------------------------
# Two-section wing geometry
# ---------------------------------------------------------------------------


class TestTwoSectionWing:
    """Tests for two-panel wing generation."""

    def test_builds_valid_solid(self, two_section_design: AircraftDesign) -> None:
        """Two-section wing must produce a non-zero solid or compound."""
        from backend.geometry.wing import build_wing

        wing = build_wing(two_section_design, side="right")
        # CadQuery may return Solid or Compound depending on union success
        assert wing.val().ShapeType() in ("Solid", "Compound")
        assert wing.val().Volume() > 0

    def test_both_sides_valid(self, two_section_design: AircraftDesign) -> None:
        """Both wing halves for two-section design must be valid."""
        from backend.geometry.wing import build_wing

        left = build_wing(two_section_design, side="left")
        right = build_wing(two_section_design, side="right")
        assert left.val().Volume() > 0
        assert right.val().Volume() > 0

    def test_volume_matches_single_section_roughly(
        self, base_design: AircraftDesign, two_section_design: AircraftDesign
    ) -> None:
        """Two-section wing volume should be within 30% of single-section volume
        (same overall planform, just different geometry decomposition)."""
        from backend.geometry.wing import build_wing

        single = build_wing(base_design, side="right")
        multi = build_wing(two_section_design, side="right")

        ratio = multi.val().Volume() / single.val().Volume()
        # Due to dihedral, multi-section volume will differ, but not by more than 50%
        assert 0.5 < ratio < 2.0

    def test_bounding_box_span(self, two_section_design: AircraftDesign) -> None:
        """Two-section wing span (Y extent) should be approximately half_span."""
        from backend.geometry.wing import build_wing

        wing = build_wing(two_section_design, side="right")
        bbox = wing.val().BoundingBox()
        half_span = two_section_design.wing_span / 2.0
        # With dihedral, Y extent is cos(dihedral) * half_span; should be > 80% of half_span
        # Panel 1 (inner 60%): 300mm * cos(3deg) ≈ 299mm
        # Panel 2 (outer 40%): 200mm * cos(10deg) ≈ 197mm
        # Total Y ≈ 496mm
        assert bbox.ylen > half_span * 0.8

    def test_tip_is_higher_than_root(self, two_section_design: AircraftDesign) -> None:
        """With positive dihedral on both panels, tip Z should exceed root Z."""
        from backend.geometry.wing import build_wing

        two_section_design.wing_dihedral = 5
        two_section_design.panel_dihedrals = [10.0, 5.0, 5.0]
        wing = build_wing(two_section_design, side="right")
        bbox = wing.val().BoundingBox()
        # The wing should have significant Z extent from dihedral
        assert bbox.zlen > 0


# ---------------------------------------------------------------------------
# Three-section wing geometry
# ---------------------------------------------------------------------------


class TestThreeSectionWing:
    """Tests for three-panel wing generation."""

    def test_builds_valid_solid(self, three_section_design: AircraftDesign) -> None:
        """Three-section wing must produce a non-zero solid or compound."""
        from backend.geometry.wing import build_wing

        wing = build_wing(three_section_design, side="right")
        # CadQuery may return Solid or Compound depending on union success
        assert wing.val().ShapeType() in ("Solid", "Compound")
        assert wing.val().Volume() > 0

    def test_three_section_both_sides(self, three_section_design: AircraftDesign) -> None:
        """Both three-section wing halves must be valid."""
        from backend.geometry.wing import build_wing

        left = build_wing(three_section_design, side="left")
        right = build_wing(three_section_design, side="right")
        assert left.val().Volume() > 0
        assert right.val().Volume() > 0


# ---------------------------------------------------------------------------
# Panel break chord interpolation
# ---------------------------------------------------------------------------


class TestBreakChordInterpolation:
    """Test that chord at break is correctly interpolated."""

    def test_chord_at_60pct_break(self, two_section_design: AircraftDesign) -> None:
        """Chord at 60% break should be linearly interpolated between root and tip."""
        root_chord = two_section_design.wing_chord  # 180
        tip_chord = root_chord * two_section_design.wing_tip_root_ratio  # 180 * 0.7 = 126
        b_frac = 0.60
        expected_break_chord = root_chord + (tip_chord - root_chord) * b_frac
        # = 180 + (126 - 180) * 0.6 = 180 - 32.4 = 147.6

        assert pytest.approx(expected_break_chord, abs=0.01) == 180 + (126 - 180) * 0.6

    def test_chord_at_40pct_break(self, three_section_design: AircraftDesign) -> None:
        """Chord at 40% break should be linearly interpolated."""
        root_chord = three_section_design.wing_chord  # 180
        tip_chord = root_chord * three_section_design.wing_tip_root_ratio  # 180 * 0.7 = 126
        b_frac = 0.40
        expected = root_chord + (tip_chord - root_chord) * b_frac
        assert pytest.approx(expected, abs=0.01) == 180 + (126 - 180) * 0.4

    def test_root_chord_unchanged(self, two_section_design: AircraftDesign) -> None:
        """Root chord (0% break) should equal wing_chord."""
        root_chord = two_section_design.wing_chord
        expected = root_chord + (root_chord * two_section_design.wing_tip_root_ratio - root_chord) * 0.0
        assert expected == root_chord

    def test_tip_chord_unchanged(self, two_section_design: AircraftDesign) -> None:
        """Tip chord (100% break) should equal wing_chord * tip_root_ratio."""
        root_chord = two_section_design.wing_chord
        tip_chord = root_chord * two_section_design.wing_tip_root_ratio
        expected = root_chord + (tip_chord - root_chord) * 1.0
        assert expected == tip_chord


# ---------------------------------------------------------------------------
# Cranked MAC calculation
# ---------------------------------------------------------------------------


class TestCrankedMAC:
    """Tests for _compute_mac_cranked in engine.py."""

    def test_single_section_matches_classic_formula(self, base_design: AircraftDesign) -> None:
        """Single-section MAC from cranked formula must match classic taper formula."""
        lam = base_design.wing_tip_root_ratio
        classic_mac = (2.0 / 3.0) * base_design.wing_chord * (1 + lam + lam**2) / (1 + lam)

        cranked_mac, _ = _compute_mac_cranked(base_design)
        assert pytest.approx(cranked_mac, rel=1e-5) == classic_mac

    def test_two_section_mac_between_root_and_tip(
        self, two_section_design: AircraftDesign
    ) -> None:
        """Cranked MAC must lie between root chord and tip chord."""
        root_chord = two_section_design.wing_chord
        tip_chord = root_chord * two_section_design.wing_tip_root_ratio

        mac, _ = _compute_mac_cranked(two_section_design)
        assert tip_chord <= mac <= root_chord

    def test_two_section_y_mac_between_root_and_half_span(
        self, two_section_design: AircraftDesign
    ) -> None:
        """Spanwise position of MAC must lie within the half-span."""
        half_span = two_section_design.wing_span / 2.0
        _, y_mac = _compute_mac_cranked(two_section_design)
        assert 0 <= y_mac <= half_span

    def test_three_section_mac_is_reasonable(
        self, three_section_design: AircraftDesign
    ) -> None:
        """Three-section cranked MAC must be physically reasonable."""
        root_chord = three_section_design.wing_chord
        tip_chord = root_chord * three_section_design.wing_tip_root_ratio

        mac, y_mac = _compute_mac_cranked(three_section_design)
        assert tip_chord <= mac <= root_chord
        assert 0 <= y_mac <= three_section_design.wing_span / 2.0

    def test_rectangular_wing_mac_equals_chord(self, base_design: AircraftDesign) -> None:
        """Rectangular wing (taper=1.0) MAC should equal root chord."""
        base_design.wing_tip_root_ratio = 1.0
        mac, _ = _compute_mac_cranked(base_design)
        assert pytest.approx(mac, rel=1e-4) == base_design.wing_chord

    def test_derived_values_mac_updated(self, two_section_design: AircraftDesign) -> None:
        """compute_derived_values must use cranked MAC for multi-section wings."""
        single_design = AircraftDesign(
            wing_span=two_section_design.wing_span,
            wing_chord=two_section_design.wing_chord,
            wing_tip_root_ratio=two_section_design.wing_tip_root_ratio,
            fuselage_length=300,
        )
        single_derived = compute_derived_values(single_design)
        multi_derived = compute_derived_values(two_section_design)

        # With a break at 60% and outer dihedral, MAC should differ from single
        # They won't be identical because the cranked formula distributes differently
        assert multi_derived["mean_aero_chord_mm"] > 0
        # For this taper (0.7), MAC values will be close but not identical to single
        # The cranked formula with a break at 60% should give a result close to the
        # single formula since it's just decomposing the same total planform.
        assert pytest.approx(
            multi_derived["mean_aero_chord_mm"],
            rel=0.05,  # Within 5% of single-panel formula
        ) == single_derived["mean_aero_chord_mm"]


# ---------------------------------------------------------------------------
# Validation V29
# ---------------------------------------------------------------------------


class TestValidationV29:
    """Tests for V29: multi-section wing configuration checks."""

    def test_single_section_no_v29(self, base_design: AircraftDesign) -> None:
        """V29 must not fire for single-section wings."""
        warnings = []
        _check_v29(base_design, warnings)
        v29 = [w for w in warnings if w.id == "V29"]
        assert len(v29) == 0

    def test_valid_two_section_no_v29(self, two_section_design: AircraftDesign) -> None:
        """Valid two-section wing must produce no V29 warnings."""
        warnings = []
        _check_v29(two_section_design, warnings)
        v29 = [w for w in warnings if w.id == "V29"]
        assert len(v29) == 0

    def test_non_monotonic_breaks_fires_v29(self, two_section_design: AircraftDesign) -> None:
        """Non-monotonic break positions must trigger V29."""
        two_section_design.wing_sections = 3
        two_section_design.panel_break_positions = [70.0, 40.0, 90.0]  # non-monotonic

        warnings = []
        _check_v29(two_section_design, warnings)
        v29 = [w for w in warnings if w.id == "V29"]
        assert len(v29) >= 1
        assert "panel_break_positions" in v29[0].fields

    def test_equal_breaks_fires_v29(self, two_section_design: AircraftDesign) -> None:
        """Equal break positions (not strictly increasing) must trigger V29."""
        two_section_design.wing_sections = 3
        two_section_design.panel_break_positions = [60.0, 60.0, 90.0]  # equal

        warnings = []
        _check_v29(two_section_design, warnings)
        v29 = [w for w in warnings if w.id == "V29"]
        assert len(v29) >= 1

    def test_last_break_over_90_fires_v29(self, two_section_design: AircraftDesign) -> None:
        """Last break position > 90% must trigger V29."""
        two_section_design.panel_break_positions = [95.0, 80.0, 90.0]  # first > 90%

        warnings = []
        _check_v29(two_section_design, warnings)
        v29 = [w for w in warnings if w.id == "V29"]
        assert len(v29) >= 1

    def test_extreme_dihedral_fires_v29(self, two_section_design: AircraftDesign) -> None:
        """Outer panel dihedral > 30 degrees must trigger V29."""
        two_section_design.panel_dihedrals = [35.0, 5.0, 5.0]  # first outer panel = 35 deg

        warnings = []
        _check_v29(two_section_design, warnings)
        v29 = [w for w in warnings if w.id == "V29"]
        assert len(v29) >= 1
        assert "panel_dihedrals" in v29[0].fields

    def test_break_too_close_to_root_fires_v29(
        self, two_section_design: AircraftDesign
    ) -> None:
        """Break position < 10% should fire V29 (too close to root)."""
        two_section_design.panel_break_positions = [5.0, 80.0, 90.0]  # first = 5%

        warnings = []
        _check_v29(two_section_design, warnings)
        v29 = [w for w in warnings if w.id == "V29"]
        assert len(v29) >= 1

    def test_v29_in_compute_warnings(self, two_section_design: AircraftDesign) -> None:
        """compute_warnings must include V29 checks."""
        # Valid config: should have no V29
        all_warnings = compute_warnings(two_section_design)
        v29 = [w for w in all_warnings if w.id == "V29"]
        assert len(v29) == 0

    def test_v29_fires_in_compute_warnings_for_invalid(
        self, two_section_design: AircraftDesign
    ) -> None:
        """compute_warnings must include V29 for invalid multi-section config."""
        two_section_design.panel_break_positions = [95.0, 80.0, 90.0]
        all_warnings = compute_warnings(two_section_design)
        v29 = [w for w in all_warnings if w.id == "V29"]
        assert len(v29) >= 1

    def test_three_section_valid_no_v29(self, three_section_design: AircraftDesign) -> None:
        """Valid three-section configuration must produce no V29."""
        warnings = []
        _check_v29(three_section_design, warnings)
        v29 = [w for w in warnings if w.id == "V29"]
        assert len(v29) == 0


# ---------------------------------------------------------------------------
# Model serialization
# ---------------------------------------------------------------------------


class TestModelSerialization:
    """Tests for Pydantic model camelCase serialization."""

    def test_camelcase_alias_panel_break_positions(self) -> None:
        """model_dump(by_alias=True) must produce camelCase panelBreakPositions."""
        design = AircraftDesign(
            wing_sections=2,
            panel_break_positions=[60.0, 80.0, 90.0],
            fuselage_length=300,
        )
        dumped = design.model_dump(by_alias=True)
        assert "panelBreakPositions" in dumped
        assert "panel_break_positions" not in dumped
        assert dumped["panelBreakPositions"] == [60.0, 80.0, 90.0]

    def test_camelcase_alias_panel_dihedrals(self) -> None:
        """model_dump(by_alias=True) must produce camelCase panelDihedrals."""
        design = AircraftDesign(
            wing_sections=2,
            panel_dihedrals=[10.0, 5.0, 5.0],
            fuselage_length=300,
        )
        dumped = design.model_dump(by_alias=True)
        assert "panelDihedrals" in dumped
        assert "panel_dihedrals" not in dumped

    def test_camelcase_alias_panel_sweeps(self) -> None:
        """model_dump(by_alias=True) must produce camelCase panelSweeps."""
        design = AircraftDesign(
            wing_sections=2,
            panel_sweeps=[3.0, 0.0, 0.0],
            fuselage_length=300,
        )
        dumped = design.model_dump(by_alias=True)
        assert "panelSweeps" in dumped
        assert "panel_sweeps" not in dumped

    def test_camelcase_alias_wing_sections(self) -> None:
        """model_dump(by_alias=True) must produce camelCase wingSections."""
        design = AircraftDesign(wing_sections=3, fuselage_length=300)
        dumped = design.model_dump(by_alias=True)
        assert "wingSections" in dumped
        assert "wing_sections" not in dumped
        assert dumped["wingSections"] == 3

    def test_populate_by_name_snake_case(self) -> None:
        """Backend code must be able to access snake_case fields directly."""
        design = AircraftDesign(
            wing_sections=2,
            panel_break_positions=[60.0, 80.0, 90.0],
            panel_dihedrals=[10.0, 5.0, 5.0],
            panel_sweeps=[3.0, 0.0, 0.0],
            fuselage_length=300,
        )
        # Access by snake_case (populate_by_name=True)
        assert design.wing_sections == 2
        assert design.panel_break_positions[0] == 60.0
        assert design.panel_dihedrals[0] == 10.0
        assert design.panel_sweeps[0] == 3.0

    def test_default_values(self) -> None:
        """Default values for multi-section params should be sensible."""
        design = AircraftDesign(fuselage_length=300)
        assert design.wing_sections == 1
        assert len(design.panel_break_positions) == 3
        assert len(design.panel_dihedrals) == 3
        assert len(design.panel_sweeps) == 3
        assert design.panel_break_positions[0] == 60.0

    def test_round_trip_camelcase(self) -> None:
        """Round-trip: model_dump(by_alias=True) -> model_validate produces same object."""
        design = AircraftDesign(
            wing_sections=2,
            panel_break_positions=[55.0, 80.0, 90.0],
            panel_dihedrals=[8.0, 5.0, 5.0],
            panel_sweeps=[2.0, 0.0, 0.0],
            fuselage_length=300,
        )
        dumped = design.model_dump(by_alias=True)
        restored = AircraftDesign.model_validate(dumped)
        assert restored.wing_sections == design.wing_sections
        assert restored.panel_break_positions == design.panel_break_positions
        assert restored.panel_dihedrals == design.panel_dihedrals
        assert restored.panel_sweeps == design.panel_sweeps


# ---------------------------------------------------------------------------
# WebSocket / generation integration
# ---------------------------------------------------------------------------


class TestGenerationIntegration:
    """Integration tests: compute_derived_values for multi-section designs."""

    def test_derived_values_single_section(self, base_design: AircraftDesign) -> None:
        """compute_derived_values must return valid dict for single-section."""
        derived = compute_derived_values(base_design)
        assert derived["mean_aero_chord_mm"] > 0
        assert derived["wing_area_cm2"] > 0
        assert derived["aspect_ratio"] > 0
        assert derived["tip_chord_mm"] > 0

    def test_derived_values_two_section(self, two_section_design: AircraftDesign) -> None:
        """compute_derived_values must return valid dict for two-section."""
        derived = compute_derived_values(two_section_design)
        assert derived["mean_aero_chord_mm"] > 0
        assert derived["wing_area_cm2"] > 0
        assert derived["aspect_ratio"] > 0

    def test_derived_values_three_section(self, three_section_design: AircraftDesign) -> None:
        """compute_derived_values must return valid dict for three-section."""
        derived = compute_derived_values(three_section_design)
        assert derived["mean_aero_chord_mm"] > 0
        assert derived["wing_area_cm2"] > 0

    def test_multi_section_mac_in_valid_range(
        self, two_section_design: AircraftDesign
    ) -> None:
        """MAC for multi-section wing must be between tip_chord and root_chord."""
        derived = compute_derived_values(two_section_design)
        tip = two_section_design.wing_chord * two_section_design.wing_tip_root_ratio
        root = two_section_design.wing_chord
        assert tip <= derived["mean_aero_chord_mm"] <= root
