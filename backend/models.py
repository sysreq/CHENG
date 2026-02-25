"""Pydantic models — shared contract between all backend modules.

API Naming Contract:
  - Backend models use snake_case field names (Python convention).
  - Frontend expects camelCase (TypeScript convention).
  - Models that are serialized to the frontend (DerivedValues, ValidationWarning,
    GenerationResult, DesignSummary) use Pydantic alias_generator=to_camel so that
    model.model_dump(by_alias=True) produces camelCase keys automatically.
  - AircraftDesign also inherits CamelModel so REST responses (GET /api/designs/{id})
    return camelCase keys. The frontend sends snake_case via serializeDesign() in
    useWebSocket.ts, and Pydantic accepts both formats via populate_by_name=True.
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


# ---------------------------------------------------------------------------
# Enum / Literal Types
# ---------------------------------------------------------------------------

FuselagePreset = Literal["Pod", "Conventional", "Blended-Wing-Body"]
MotorConfig = Literal["Tractor", "Pusher"]
WingMountType = Literal["High-Wing", "Mid-Wing", "Low-Wing", "Shoulder-Wing"]
TailType = Literal["Conventional", "T-Tail", "V-Tail", "Cruciform"]
WingAirfoil = Literal[
    "Flat-Plate", "NACA-0012", "NACA-2412", "NACA-4412", "NACA-6412",
    "Clark-Y", "Eppler-193", "Eppler-387", "Selig-1223", "AG-25",
]
JointType = Literal["Tongue-and-Groove", "Dowel-Pin", "Flat-with-Alignment-Pins"]
SupportStrategy = Literal["none", "minimal", "full"]


# ---------------------------------------------------------------------------
# Base model for camelCase serialization
# ---------------------------------------------------------------------------

class CamelModel(BaseModel):
    """Base for models serialized to the frontend with camelCase keys."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


# ---------------------------------------------------------------------------
# AircraftDesign — 39 user-configurable parameters
# ---------------------------------------------------------------------------

class AircraftDesign(CamelModel):
    """Complete aircraft design parameters. Flat structure, snake_case fields.

    Inherits CamelModel so REST responses return camelCase for the frontend.
    Backend code always uses snake_case field names (populate_by_name=True).
    """

    # ── Meta ──────────────────────────────────────────────────────────
    version: str = "0.1.0"
    id: str = ""
    name: str = "Untitled Aircraft"

    # ── Global / Fuselage ─────────────────────────────────────────────
    fuselage_preset: FuselagePreset = "Conventional"
    engine_count: int = Field(default=1, ge=0, le=4)
    motor_config: MotorConfig = "Tractor"
    wing_span: float = Field(default=1000, ge=300, le=3000)
    wing_chord: float = Field(default=180, ge=50, le=500)
    wing_mount_type: WingMountType = "High-Wing"
    fuselage_length: float = Field(default=300, ge=150, le=2000)
    tail_type: TailType = "Conventional"

    # ── Wing ──────────────────────────────────────────────────────────
    wing_airfoil: WingAirfoil = "Clark-Y"
    wing_sweep: float = Field(default=0, ge=-10, le=45)
    wing_tip_root_ratio: float = Field(default=1.0, ge=0.3, le=1.0)
    wing_dihedral: float = Field(default=3, ge=-10, le=15)
    wing_skin_thickness: float = Field(default=1.2, ge=0.8, le=3.0)
    wing_incidence: float = Field(default=2.0, ge=-5, le=15)
    wing_twist: float = Field(default=0.0, ge=-5, le=5)

    # ── Tail (Conventional / T-Tail / Cruciform) ──────────────────────
    h_stab_span: float = Field(default=350, ge=100, le=1200)
    h_stab_chord: float = Field(default=100, ge=30, le=250)
    h_stab_incidence: float = Field(default=-1, ge=-5, le=5)
    v_stab_height: float = Field(default=100, ge=30, le=400)
    v_stab_root_chord: float = Field(default=110, ge=30, le=300)

    # ── Tail (V-Tail) ────────────────────────────────────────────────
    v_tail_dihedral: float = Field(default=35, ge=20, le=60)
    v_tail_span: float = Field(default=280, ge=80, le=600)
    v_tail_chord: float = Field(default=90, ge=30, le=200)
    v_tail_incidence: float = Field(default=0, ge=-3, le=3)
    v_tail_sweep: float = Field(default=0, ge=-10, le=45)

    # ── Shared Tail ───────────────────────────────────────────────────
    tail_arm: float = Field(default=180, ge=80, le=1500)

    # ── Fuselage Section Lengths ──────────────────────────────────────
    fuselage_nose_length: float = Field(default=75, ge=20, le=1000)
    fuselage_cabin_length: float = Field(default=150, ge=30, le=1500)
    fuselage_tail_length: float = Field(default=75, ge=20, le=1000)

    # ── Fuselage Wall Thickness ───────────────────────────────────────
    wall_thickness: float = Field(default=1.5, ge=0.8, le=4.0)

    # ── Export / Print ────────────────────────────────────────────────
    print_bed_x: float = Field(default=220, ge=100, le=500)
    print_bed_y: float = Field(default=220, ge=100, le=500)
    print_bed_z: float = Field(default=250, ge=50, le=500)
    auto_section: bool = True
    section_overlap: float = Field(default=15, ge=5, le=30)
    joint_type: JointType = "Tongue-and-Groove"
    joint_tolerance: float = Field(default=0.15, ge=0.05, le=0.5)
    nozzle_diameter: float = Field(default=0.4, ge=0.2, le=1.0)
    hollow_parts: bool = True
    te_min_thickness: float = Field(default=0.8, ge=0.4, le=2.0)
    support_strategy: SupportStrategy = "minimal"
    print_infill: float = Field(default=15.0, ge=0, le=100)
    material_density: float = Field(default=1.24, ge=0.5, le=10.0)

    # ── Propulsion / Electronics (for CG calculation) ────────────────
    motor_weight_g: float = Field(default=60.0, ge=0, le=500)
    battery_weight_g: float = Field(default=150.0, ge=0, le=2000)
    battery_position_frac: float = Field(default=0.30, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Derived Values — computed by geometry engine, read-only
# ---------------------------------------------------------------------------

class DerivedValues(CamelModel):
    """Backend-computed values returned in WebSocket JSON trailer."""

    tip_chord_mm: float
    wing_area_cm2: float
    aspect_ratio: float
    mean_aero_chord_mm: float
    taper_ratio: float
    estimated_cg_mm: float
    min_feature_thickness_mm: float
    wall_thickness_mm: float
    weight_wing_g: float = 0.0
    weight_tail_g: float = 0.0
    weight_fuselage_g: float = 0.0
    weight_total_g: float = 0.0


# ---------------------------------------------------------------------------
# Validation Warning
# ---------------------------------------------------------------------------

class ValidationWarning(CamelModel):
    """Non-blocking validation warning."""

    id: str  # V01-V06, V16-V23
    level: Literal["warn"] = "warn"
    message: str
    fields: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# REST Request/Response Types
# ---------------------------------------------------------------------------

class ExportRequest(CamelModel):
    """Request body for POST /api/export."""

    design: AircraftDesign
    format: Literal["stl", "step", "dxf", "svg"] = "stl"


class GenerationResult(CamelModel):
    """Response from POST /api/generate."""

    derived: DerivedValues
    warnings: list[ValidationWarning] = Field(default_factory=list)


class ExportPreviewPart(CamelModel):
    """Metadata for a single sectioned part in the export preview."""

    filename: str
    component: str
    side: str
    section_num: int
    total_sections: int
    dimensions_mm: tuple[float, float, float]
    print_orientation: str
    assembly_order: int
    fits_bed: bool
    # ── Issue #147: Smart split metadata (optional — only present for multi-section parts) ──
    cut_position_mm: float | None = None    # actual cut coordinate along split axis
    cut_adjusted: bool = False              # True if optimizer moved from midpoint
    cut_adjust_reason: str = ""             # e.g. "Avoided wing root zone"


class ExportPreviewResponse(CamelModel):
    """Response from POST /api/export/preview."""

    parts: list[ExportPreviewPart] = Field(default_factory=list)
    total_parts: int = 0
    bed_dimensions_mm: tuple[float, float, float] = (220.0, 220.0, 250.0)
    parts_that_fit: int = 0
    parts_that_exceed: int = 0


class DesignSummary(CamelModel):
    """Summary for design listing (GET /api/designs)."""

    id: str
    name: str
    modified_at: str


class PresetSummary(CamelModel):
    """Summary for custom preset listing (GET /api/presets)."""

    id: str
    name: str
    created_at: str


class SavePresetRequest(CamelModel):
    """Request body for POST /api/presets."""

    name: str
    design: AircraftDesign


class TestJointExportRequest(CamelModel):
    """Request body for POST /api/export/test-joint.

    Subset of AircraftDesign containing only the parameters that affect
    the joint geometry — no full design needed for this calibration print.
    """

    joint_type: JointType = "Tongue-and-Groove"   # PR10
    joint_tolerance: float = Field(default=0.15, ge=0.05, le=0.5)   # PR11, mm
    section_overlap: float = Field(default=15.0, ge=5.0, le=30.0)   # PR05, mm
    nozzle_diameter: float = Field(default=0.4, ge=0.2, le=1.0)     # PR06, mm
