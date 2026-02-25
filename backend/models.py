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
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


# ---------------------------------------------------------------------------
# Enum / Literal Types
# ---------------------------------------------------------------------------

FuselagePreset = Literal["Pod", "Conventional", "Blended-Wing-Body"]
MotorConfig = Literal["Tractor", "Pusher"]
WingMountType = Literal["High-Wing", "Mid-Wing", "Low-Wing", "Shoulder-Wing"]
TailType = Literal["Conventional", "T-Tail", "V-Tail", "Cruciform"]
LandingGearType = Literal["None", "Tricycle", "Taildragger"]
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
    # P01: 0 = no motor/glider, 1 = single motor. Values 2-4 are reserved for
    # future multi-engine nacelle support. TODO v0.8: multi-engine nacelles (engine_count 2-4)
    engine_count: int = Field(default=1, ge=0, le=1)
    motor_config: MotorConfig = "Tractor"

    @field_validator("engine_count", mode="before")
    @classmethod
    def clamp_engine_count(cls, v: object) -> int:
        """Clamp legacy engine_count values 2-4 to 1 for backward compatibility.

        Designs saved before v0.7.1 may have engine_count=2, 3, or 4.
        Rather than rejecting them outright, we silently promote to 1 (single motor).
        This prevents HTTP 422 errors when loading old JSON files.
        """
        try:
            n = int(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return v  # type: ignore[return-value]  # let Pydantic raise the type error
        if n > 1:
            return 1
        return n

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

    # ── Multi-section wing (W08-W11) ──────────────────────────────────
    # W08: number of spanwise panels per half-wing (1 = single panel, classic)
    wing_sections: int = Field(default=1, ge=1, le=4)
    # W09: break positions as % of half-span (index 0 = break between panel 1 and 2).
    # Store 3 values (max for 4-panel wing); only first wing_sections-1 are used.
    panel_break_positions: list[float] = Field(
        default_factory=lambda: [60.0, 80.0, 90.0]
    )
    # W10: dihedral angle for panels 2, 3, 4 (panel 1 uses wing_dihedral).
    panel_dihedrals: list[float] = Field(
        default_factory=lambda: [10.0, 5.0, 5.0]
    )
    # W11: sweep angle override for panels 2, 3, 4 (panel 1 uses wing_sweep).
    # NaN encodes "inherit panel 1 sweep" — stored as 0.0 by default here.
    panel_sweeps: list[float] = Field(
        default_factory=lambda: [0.0, 0.0, 0.0]
    )

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

    # ── Fuselage Section Transition Points (F11/F12) ──────────────────
    # Replace the three independent absolute-length sliders with two
    # percentage breakpoints so sections always sum to fuselage_length.
    #   nose_length  = nose_cabin_break_pct / 100 × fuselage_length
    #   cabin_length = (cabin_tail_break_pct - nose_cabin_break_pct) / 100 × fuselage_length
    #   tail_length  = (100 - cabin_tail_break_pct) / 100 × fuselage_length
    # Constraint: nose_cabin_break_pct < cabin_tail_break_pct (enforced via V07 warning).
    nose_cabin_break_pct: float = Field(default=25.0, ge=10.0, le=85.0)   # F11
    cabin_tail_break_pct: float = Field(default=75.0, ge=15.0, le=90.0)   # F12

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

    # === Control Surfaces — Ailerons (C01-C05) ===
    aileron_enable: bool = Field(default=False)
    aileron_span_start: float = Field(default=55.0, ge=30.0, le=70.0)   # % half-span
    aileron_span_end: float = Field(default=95.0, ge=70.0, le=98.0)     # % half-span
    aileron_chord_percent: float = Field(default=25.0, ge=15.0, le=40.0)  # % chord

    # === Control Surfaces — Elevator (C11-C13) ===
    elevator_enable: bool = Field(default=False)
    elevator_span_percent: float = Field(default=100.0, ge=50.0, le=100.0)  # % hstab span
    elevator_chord_percent: float = Field(default=35.0, ge=20.0, le=50.0)   # % hstab chord

    # === Control Surfaces — Rudder (C15-C17) ===
    rudder_enable: bool = Field(default=False)
    rudder_height_percent: float = Field(default=90.0, ge=50.0, le=100.0)  # % fin height
    rudder_chord_percent: float = Field(default=35.0, ge=20.0, le=50.0)    # % fin chord

    # === Control Surfaces — Ruddervators (C18-C20, V-tail only) ===
    ruddervator_enable: bool = Field(default=False)
    ruddervator_chord_percent: float = Field(default=35.0, ge=20.0, le=50.0)
    ruddervator_span_percent: float = Field(default=90.0, ge=60.0, le=100.0)

    # === Control Surfaces — Elevons (C21-C24, Flying-wing only) ===
    elevon_enable: bool = Field(default=False)
    elevon_span_start: float = Field(default=20.0, ge=10.0, le=40.0)   # % half-span
    elevon_span_end: float = Field(default=90.0, ge=60.0, le=98.0)     # % half-span
    elevon_chord_percent: float = Field(default=20.0, ge=15.0, le=35.0)

    # ── Landing Gear (L01-L11) ────────────────────────────────────────
    landing_gear_type: LandingGearType = "None"

    # Main gear (L03-L06) — applies to both Tricycle and Taildragger
    main_gear_position: float = Field(default=35.0, ge=25.0, le=55.0)   # % fuselage length
    main_gear_height: float = Field(default=40.0, ge=15.0, le=150.0)    # mm
    main_gear_track: float = Field(default=120.0, ge=30.0, le=400.0)    # mm
    main_wheel_diameter: float = Field(default=30.0, ge=10.0, le=80.0)  # mm

    # Nose gear (L08-L09) — Tricycle only
    nose_gear_height: float = Field(default=45.0, ge=15.0, le=150.0)    # mm
    nose_wheel_diameter: float = Field(default=20.0, ge=8.0, le=60.0)   # mm

    # Tail wheel (L10-L11) — Taildragger only
    tail_wheel_diameter: float = Field(default=12.0, ge=5.0, le=40.0)   # mm
    tail_gear_position: float = Field(default=92.0, ge=85.0, le=98.0)   # % fuselage length


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
