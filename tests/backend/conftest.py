"""Shared fixtures for backend tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.models import AircraftDesign
from backend.storage import LocalStorage


@pytest.fixture
def test_design() -> AircraftDesign:
    """Return a default AircraftDesign (Sport preset defaults)."""
    return AircraftDesign(id="test-001", name="Test Aircraft")


@pytest.fixture
def trainer_design() -> AircraftDesign:
    """Return a Trainer-preset design."""
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
    )


@pytest.fixture
def tmp_storage(tmp_path: Path) -> LocalStorage:
    """Return a LocalStorage instance backed by a temporary directory."""
    return LocalStorage(base_path=str(tmp_path))


@pytest.fixture
def populated_storage(tmp_storage: LocalStorage, test_design: AircraftDesign) -> LocalStorage:
    """Return a LocalStorage with one saved design."""
    tmp_storage.save_design(test_design.id, test_design.model_dump())
    return tmp_storage
