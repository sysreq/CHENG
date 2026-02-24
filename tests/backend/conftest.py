"""Shared fixtures for backend tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.models import AircraftDesign
from backend.storage import LocalStorage


# ---------------------------------------------------------------------------
# Design Fixtures (used by geometry & validation tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def default_design() -> AircraftDesign:
    """An AircraftDesign with all default values (Trainer-like)."""
    return AircraftDesign()


@pytest.fixture
def test_design() -> AircraftDesign:
    """Return a default AircraftDesign for route/storage tests."""
    return AircraftDesign(id="test-001", name="Test Aircraft")


@pytest.fixture
def trainer_design() -> AircraftDesign:
    """Trainer preset: 1200 mm wingspan, Clark-Y, Conventional tail."""
    return AircraftDesign(
        id="trainer-001",
        name="Trainer",
        fuselage_preset="Conventional",
        engine_count=1,
        motor_config="Tractor",
        wing_span=1200,
        wing_chord=200,
        wing_mount_type="High-Wing",
        fuselage_length=400,
        tail_type="Conventional",
        wing_airfoil="Clark-Y",
        wing_sweep=0,
        wing_tip_root_ratio=1.0,
        wing_dihedral=3,
        wing_skin_thickness=1.2,
        h_stab_span=400,
        h_stab_chord=120,
        h_stab_incidence=-1,
        v_stab_height=120,
        v_stab_root_chord=130,
        tail_arm=220,
        hollow_parts=True,
    )


@pytest.fixture
def sport_design() -> AircraftDesign:
    """Sport preset: 1000 mm wingspan, NACA-2412, tapered."""
    return AircraftDesign(
        name="Sport",
        wing_span=1000,
        wing_chord=180,
        wing_airfoil="NACA-2412",
        wing_tip_root_ratio=0.67,
        wing_dihedral=3,
        wing_sweep=5,
        fuselage_preset="Conventional",
        fuselage_length=300,
        tail_type="Conventional",
        h_stab_span=350,
        h_stab_chord=100,
        tail_arm=180,
        hollow_parts=True,
        wing_skin_thickness=1.2,
    )


@pytest.fixture
def aerobatic_design() -> AircraftDesign:
    """Aerobatic preset: 900 mm wingspan, NACA-0012, symmetric."""
    return AircraftDesign(
        name="Aerobatic",
        wing_span=900,
        wing_chord=200,
        wing_airfoil="NACA-0012",
        wing_tip_root_ratio=0.8,
        wing_dihedral=0,
        wing_sweep=0,
        fuselage_preset="Conventional",
        fuselage_length=280,
        tail_type="Conventional",
        h_stab_span=300,
        h_stab_chord=90,
        tail_arm=160,
        hollow_parts=True,
        wing_skin_thickness=1.2,
    )


@pytest.fixture
def bwb_design() -> AircraftDesign:
    """BWB variant for testing wall_thickness logic."""
    return AircraftDesign(
        name="BWB Test",
        fuselage_preset="Blended-Wing-Body",
        wing_skin_thickness=2.0,
    )


@pytest.fixture
def vtail_design() -> AircraftDesign:
    """V-Tail configuration."""
    return AircraftDesign(
        name="V-Tail Test",
        tail_type="V-Tail",
        v_tail_dihedral=35,
        v_tail_span=280,
        v_tail_chord=90,
        v_tail_incidence=0,
    )


# ---------------------------------------------------------------------------
# Storage Fixtures (used by route/storage tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_storage(tmp_path: Path) -> LocalStorage:
    """Return a LocalStorage instance backed by a temporary directory."""
    return LocalStorage(base_path=str(tmp_path))


@pytest.fixture
def populated_storage(tmp_storage: LocalStorage, test_design: AircraftDesign) -> LocalStorage:
    """Return a LocalStorage with one saved design."""
    tmp_storage.save_design(test_design.id, test_design.model_dump())
    return tmp_storage
