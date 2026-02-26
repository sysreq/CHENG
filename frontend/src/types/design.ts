// ============================================================================
// CHENG — Canonical Frontend Type Definitions
// Mirrors backend/models.py Pydantic models (snake_case -> camelCase)
// ============================================================================

// ---------------------------------------------------------------------------
// Enum / Literal Types
// ---------------------------------------------------------------------------

/** Aircraft preset names. 'Custom' auto-selected when any param is manually edited. */
export type PresetName = 'Trainer' | 'Sport' | 'Aerobatic' | 'Glider' | 'FlyingWing' | 'Scale' | 'Custom';

/** Fuselage body style. Controls cross-section shape and wallThickness. */
export type FuselagePreset = 'Pod' | 'Conventional' | 'Blended-Wing-Body';

/** Motor mounting position relative to the fuselage. */
export type MotorConfig = 'Tractor' | 'Pusher';

/** Vertical placement of the wing on the fuselage. */
export type WingMountType = 'High-Wing' | 'Mid-Wing' | 'Low-Wing' | 'Shoulder-Wing';

/** Tail configuration. Determines which tail params are visible in the UI. */
export type TailType = 'Conventional' | 'T-Tail' | 'V-Tail' | 'Cruciform';

/** Available airfoil profiles. Corresponding .dat files in airfoils/ directory. */
export type WingAirfoil =
  | 'Flat-Plate' | 'NACA-0012' | 'NACA-2412' | 'NACA-4412' | 'NACA-6412'
  | 'Clark-Y' | 'Eppler-193' | 'Eppler-387' | 'Selig-1223' | 'AG-25';

/** Joint mechanism for sectioned parts. */
export type JointType = 'Tongue-and-Groove' | 'Dowel-Pin' | 'Flat-with-Alignment-Pins';

/** 3D print support generation strategy. */
export type SupportStrategy = 'none' | 'minimal' | 'full';

/** Landing gear configuration. */
export type LandingGearType = 'None' | 'Tricycle' | 'Taildragger';

/** Selectable component in the 3D viewport. 'global' is the inlined global params tab. */
export type ComponentSelection = 'global' | 'wing' | 'tail' | 'fuselage' | 'landing_gear' | null;

/** Sub-element within a wing component. */
export type WingSubElement = 'left-panel' | 'right-panel';
/** Sub-element within a tail component. */
export type TailSubElement = 'h-stab' | 'v-stab' | 'left-panel' | 'right-panel';
/** Sub-element within a fuselage component. */
export type FuselageSubElement = 'nose' | 'cabin' | 'tail-cone';
/** Union of all sub-element types. */
export type SubElementSelection = WingSubElement | TailSubElement | FuselageSubElement | null;

/** Sub-elements available for each component.
 *  Wing includes multi-section panel labels for #143 (extra entries are harmless
 *  when only single-section is active — cycler only traverses those that exist). */
export const COMPONENT_SUB_ELEMENTS: Record<Exclude<ComponentSelection, null>, readonly string[]> = {
  global: [] as const,
  wing: ['left-panel', 'right-panel', 'inner-panel', 'mid-panel', 'outer-panel'] as const,
  tail: ['h-stab', 'v-stab'] as const,
  fuselage: ['nose', 'cabin', 'tail-cone'] as const,
  landing_gear: ['main_left', 'main_right', 'nose_gear', 'tail_wheel'] as const,
};

/** Infill density hint for per-component print settings. */
export type InfillHint = 'low' | 'medium' | 'high';

/** Per-component print settings overrides. All fields optional (use global defaults when unset). */
export interface ComponentPrintSettings {
  /** Wall thickness override. @unit mm */
  wallThickness?: number;
  /** Infill density hint. */
  infillHint?: InfillHint;
  /** Support generation strategy. */
  supportStrategy?: SupportStrategy;
}

/** Map of component name to its print settings overrides. */
export type PerComponentPrintSettings = Partial<Record<'wing' | 'tail' | 'fuselage' | 'landing_gear', ComponentPrintSettings>>;

/** Source of a parameter change — controls debounce/throttle timing. */
export type ChangeSource = 'slider' | 'text' | 'immediate';

// ---------------------------------------------------------------------------
// AircraftDesign — mirrors backend Pydantic model
// ---------------------------------------------------------------------------

/**
 * Complete aircraft design parameters. Sent to backend on every change via
 * WebSocket (/ws/preview) or REST (POST /api/generate).
 */
export interface AircraftDesign {
  // ── Meta ──────────────────────────────────────────────────────────
  /** Protocol version. Always "0.1.0" for MVP. */
  version: string;
  /** UUID v4 identifier. Generated client-side on new designs. */
  id: string;
  /** User-assigned design name. Default: "Untitled Aircraft". */
  name: string;

  // ── Global / Fuselage ─────────────────────────────────────────────
  /** Fuselage body style. @see FuselagePreset */
  fuselagePreset: FuselagePreset;
  /** Motor present: 0 = no motor (glider/unpowered), 1 = single motor.
   *  Values 2–4 are reserved for future multi-engine nacelle support (TODO v0.8).
   *  @min 0 @max 1 @default 1 */
  engineCount: number;
  /** Motor position. "Tractor" = nose, "Pusher" = rear. @default "Tractor" */
  motorConfig: MotorConfig;
  /** Total wingspan tip-to-tip. @unit mm @min 300 @max 3000 @default 1000 */
  wingSpan: number;
  /** Wing root chord. Tip = wingChord x wingTipRootRatio. @unit mm @min 50 @max 500 @default 180 */
  wingChord: number;
  /** Wing vertical placement on fuselage. @default "High-Wing" */
  wingMountType: WingMountType;
  /** Fuselage length nose to tail. @unit mm @min 150 @max 2000 @default 300 */
  fuselageLength: number;
  /** Tail configuration type. @default "Conventional" */
  tailType: TailType;

  // ── Wing ──────────────────────────────────────────────────────────
  /** Airfoil profile name. Must match a .dat file. @default "Clark-Y" */
  wingAirfoil: WingAirfoil;
  /** Sweep angle. Positive = swept back. @unit deg @min -10 @max 45 @default 0 */
  wingSweep: number;
  /** Tip/root chord ratio. 1.0 = rectangular. @min 0.3 @max 1.0 @default 1.0 */
  wingTipRootRatio: number;
  /** Dihedral per panel. Positive = tips up. @unit deg @min -10 @max 15 @default 3 */
  wingDihedral: number;
  /** Wing skin wall thickness. @unit mm @min 0.8 @max 3.0 @default 1.2 */
  wingSkinThickness: number;
  /** Wing incidence angle. Positive = nose up. @unit deg @min -5 @max 15 @default 2.0 */
  wingIncidence: number;
  /** Wing twist (washout at tip). @unit deg @min -5 @max 5 @default 0.0 */
  wingTwist: number;

  // ── Multi-Section Wing (Issue #143) ───────────────────────────────
  /** Number of spanwise panels per half-wing. 1 = straight, 2–4 = polyhedral/cranked.
   *  @min 1 @max 4 @default 1 @integer */
  wingSections: number;
  /** Break positions as % of half-span where panel n meets panel n+1.
   *  Array length >= wingSections - 1. Values must be strictly increasing 10–90%.
   *  e.g. [60] for 2-section, [40, 70] for 3-section.
   *  @unit % @min 10 @max 90 */
  panelBreakPositions: number[];
  /** Dihedral angle per panel starting from panel 2 (panel 1 uses global wingDihedral).
   *  Array length >= wingSections - 1.
   *  @unit deg @min -10 @max 45 */
  panelDihedrals: number[];
  /** Sweep angle override per panel starting from panel 2 (panel 1 uses global wingSweep).
   *  Array length >= wingSections - 1.
   *  @unit deg @min -10 @max 45 */
  panelSweeps: number[];
  /** W12: per-panel airfoil overrides for panels 2–4. null = inherit wingAirfoil.
   *  Array length = 3 (index 0 = panel 2, index 1 = panel 3, index 2 = panel 4). */
  panelAirfoils: (WingAirfoil | null)[];

  // ── Tail (Conventional / T-Tail / Cruciform) ──────────────────────
  /** H-stab span. @unit mm @min 100 @max 1200 @default 350 */
  hStabSpan: number;
  /** H-stab chord. @unit mm @min 30 @max 250 @default 100 */
  hStabChord: number;
  /** H-stab incidence. Negative = LE down. @unit deg @min -5 @max 5 @default -1 */
  hStabIncidence: number;
  /** Vertical fin height. @unit mm @min 30 @max 400 @default 100 */
  vStabHeight: number;
  /** Vertical fin root chord. @unit mm @min 30 @max 300 @default 110 */
  vStabRootChord: number;

  // ── Tail (V-Tail) ────────────────────────────────────────────────
  /** V-tail dihedral from horizontal. @unit deg @min 20 @max 60 @default 35 */
  vTailDihedral: number;
  /** V-tail span. @unit mm @min 80 @max 600 @default 280 */
  vTailSpan: number;
  /** V-tail chord. @unit mm @min 30 @max 200 @default 90 */
  vTailChord: number;
  /** V-tail incidence. @unit deg @min -3 @max 3 @default 0 */
  vTailIncidence: number;
  /** V-tail sweep angle. Only for V-Tail type. @unit deg @min -10 @max 45 @default 0 */
  vTailSweep: number;

  // ── Shared Tail ───────────────────────────────────────────────────
  /** Wing AC to tail AC distance. @unit mm @min 80 @max 1500 @default 180 */
  tailArm: number;

  // ── Fuselage Section Transition Points (F11/F12) ──────────────────
  /** Where nose ends / cabin begins, as % of fuselage length. @unit % @min 10 @max 85 @default 25 */
  noseCabinBreakPct: number;
  /** Where cabin ends / tail begins, as % of fuselage length. @unit % @min 15 @max 90 @default 75 */
  cabinTailBreakPct: number;

  // ── Fuselage Wall Thickness ───────────────────────────────────────
  /** Fuselage wall thickness. @unit mm @min 0.8 @max 4.0 @default 1.5 */
  wallThickness: number;

  // ── Control Surfaces (Issue #144) ─────────────────────────────────

  // Ailerons (Wing) — C01–C04
  /** Enable aileron cutouts on the wing. @default false */
  aileronEnable: boolean;
  /** Aileron inboard edge as % of half-span from root. @unit % @min 30 @max 70 @default 55 */
  aileronSpanStart: number;
  /** Aileron outboard edge as % of half-span from root. @unit % @min 70 @max 98 @default 95 */
  aileronSpanEnd: number;
  /** Aileron chord as % of local wing chord. @unit % @min 15 @max 40 @default 25 */
  aileronChordPercent: number;

  // Elevator (H-Stab) — C11–C13
  /** Enable elevator on H-stab. @default false */
  elevatorEnable: boolean;
  /** Elevator span as % of total H-stab span. @unit % @min 50 @max 100 @default 100 */
  elevatorSpanPercent: number;
  /** Elevator chord as % of H-stab chord. @unit % @min 20 @max 50 @default 35 */
  elevatorChordPercent: number;

  // Rudder (V-Stab) — C15–C17
  /** Enable rudder on V-stab. @default false */
  rudderEnable: boolean;
  /** Rudder height as % of fin height. @unit % @min 50 @max 100 @default 90 */
  rudderHeightPercent: number;
  /** Rudder chord as % of fin chord. @unit % @min 20 @max 50 @default 35 */
  rudderChordPercent: number;

  // Ruddervators (V-Tail) — C18–C20
  /** Enable ruddervators on V-tail surfaces. @default false */
  ruddervatorEnable: boolean;
  /** Ruddervator chord as % of V-tail chord. @unit % @min 20 @max 50 @default 35 */
  ruddervatorChordPercent: number;
  /** Ruddervator span as % of V-tail surface span. @unit % @min 60 @max 100 @default 90 */
  ruddervatorSpanPercent: number;

  // Elevons (Flying Wing) — C21–C24
  /** Enable elevon cutouts (for flying-wing/delta). @default false */
  elevonEnable: boolean;
  /** Elevon inboard edge as % of half-span. @unit % @min 10 @max 40 @default 20 */
  elevonSpanStart: number;
  /** Elevon outboard edge as % of half-span. @unit % @min 60 @max 98 @default 90 */
  elevonSpanEnd: number;
  /** Elevon chord as % of local wing chord. @unit % @min 15 @max 35 @default 20 */
  elevonChordPercent: number;

  // ── Landing Gear (L01-L11) ────────────────────────────────────────
  /** Landing gear configuration. @default 'None' */
  landingGearType: LandingGearType;
  /** Main gear longitudinal position as % of fuselage length from nose.
   *  @unit % @min 25 @max 55 @default 35 */
  mainGearPosition: number;
  /** Main gear strut height (ground clearance). @unit mm @min 15 @max 150 @default 40 */
  mainGearHeight: number;
  /** Lateral distance between left and right main wheels. @unit mm @min 30 @max 400 @default 120 */
  mainGearTrack: number;
  /** Main wheel diameter. @unit mm @min 10 @max 80 @default 30 */
  mainWheelDiameter: number;
  /** Nose gear strut height (Tricycle only). @unit mm @min 15 @max 150 @default 45 */
  noseGearHeight: number;
  /** Nose wheel diameter (Tricycle only). @unit mm @min 8 @max 60 @default 20 */
  noseWheelDiameter: number;
  /** Tail wheel diameter (Taildragger only). @unit mm @min 5 @max 40 @default 12 */
  tailWheelDiameter: number;
  /** Tail gear longitudinal position as % of fuselage length from nose (Taildragger only).
   *  @unit % @min 85 @max 98 @default 92 */
  tailGearPosition: number;

  // ── Export / Print ────────────────────────────────────────────────
  /** Printer bed X. @unit mm @min 100 @max 500 @default 220 */
  printBedX: number;
  /** Printer bed Y. @unit mm @min 100 @max 500 @default 220 */
  printBedY: number;
  /** Printer bed Z. @unit mm @min 50 @max 500 @default 250 */
  printBedZ: number;
  /** Auto-section parts exceeding bed. @default true */
  autoSection: boolean;
  /** Joint overlap length. @unit mm @min 5 @max 30 @default 15 */
  sectionOverlap: number;
  /** Joint mechanism. @default "Tongue-and-Groove" */
  jointType: JointType;
  /** Joint clearance per side. @unit mm @min 0.05 @max 0.5 @default 0.15 */
  jointTolerance: number;
  /** FDM nozzle diameter. @unit mm @min 0.2 @max 1.0 @default 0.4 */
  nozzleDiameter: number;
  /** Hollow out solid parts. @default true */
  hollowParts: boolean;
  /** Trailing edge min thickness. @unit mm @min 0.4 @max 2.0 @default 0.8 */
  teMinThickness: number;
  /** 3D print support strategy. @default "minimal" */
  supportStrategy: SupportStrategy;
}

// ---------------------------------------------------------------------------
// DerivedValues — computed by backend, read-only on frontend
// ---------------------------------------------------------------------------

/** Backend-computed values from WebSocket JSON trailer. */
export interface DerivedValues {
  /** Tip chord = wingChord x wingTipRootRatio. @unit mm */
  tipChordMm: number;
  /** Wing area (both panels). @unit cm2 */
  wingAreaCm2: number;
  /** Aspect ratio = span^2 / area. */
  aspectRatio: number;
  /** Mean Aerodynamic Chord. @unit mm */
  meanAeroChordMm: number;
  /** Taper ratio = tipChord / rootChord. */
  taperRatio: number;
  /** Balance point = 25% MAC from wing LE. @unit mm */
  estimatedCgMm: number;
  /** Min feature thickness = 2 x nozzle. @unit mm */
  minFeatureThicknessMm: number;
  /** Fuselage wall thickness (preset-controlled). @unit mm */
  wallThicknessMm: number;
}

// ---------------------------------------------------------------------------
// ValidationWarning
// ---------------------------------------------------------------------------

/** Structural warning IDs (V01-V08). */
export type StructuralWarningId = 'V01' | 'V02' | 'V03' | 'V04' | 'V05' | 'V06' | 'V07' | 'V08';
/** Print warning IDs (V16-V23). */
export type PrintWarningId = 'V16' | 'V17' | 'V18' | 'V20' | 'V21' | 'V22' | 'V23';
/** Aero analysis warning IDs (V09-V13). */
export type AeroWarningId = 'V09' | 'V10' | 'V11' | 'V12' | 'V13';
/** Printability warning IDs (V24-V28). */
export type PrintabilityWarningId = 'V24' | 'V25' | 'V26' | 'V27' | 'V28';
/** Multi-section wing warning IDs (V29). */
export type MultiSectionWarningId = 'V29';
/** Control surface warning IDs (V30). */
export type ControlSurfaceWarningId = 'V30';
/** Landing gear warning IDs (V31). */
export type LandingGearWarningId = 'V31';
/** Tail arm clamping warning IDs (V32). */
export type TailArmWarningId = 'V32';
/** All warning IDs. */
export type WarningId = StructuralWarningId | PrintWarningId | AeroWarningId | PrintabilityWarningId | MultiSectionWarningId | ControlSurfaceWarningId | LandingGearWarningId | TailArmWarningId;

/** Non-blocking validation warning from the backend. */
export interface ValidationWarning {
  id: WarningId;
  level: 'warn';
  message: string;
  /** camelCase field names affected — for displaying warning icons. */
  fields: string[];
}

// ---------------------------------------------------------------------------
// MeshData — parsed from WebSocket binary frame
// ---------------------------------------------------------------------------

/** Per-component face index ranges for selection highlighting.
 *  Includes control surfaces, multi-section wing panel sub-keys, and landing gear.
 *  wing_left/wing_right are separate halves for distinct shading (#228).
 *  Per-panel sub-keys wing_left_0, wing_left_1, … wing_right_0, wing_right_1, …
 *  are present when wing_sections > 1 (#241, #242). */
export type ComponentRanges = Partial<Record<
  | 'fuselage' | 'wing' | 'wing_left' | 'wing_right' | 'tail'
  | 'aileron_left' | 'aileron_right'
  | 'elevator_left' | 'elevator_right'
  | 'rudder'
  | 'ruddervator_left' | 'ruddervator_right'
  | 'elevon_left' | 'elevon_right'
  // Per-panel sub-keys for multi-section wings (#241, #242): wing_left_0..3, wing_right_0..3
  | 'wing_left_0' | 'wing_left_1' | 'wing_left_2' | 'wing_left_3'
  | 'wing_right_0' | 'wing_right_1' | 'wing_right_2' | 'wing_right_3'
  | 'gear_main_left' | 'gear_main_right' | 'gear_nose' | 'gear_tail',
  [number, number]
>>;

/** Parsed mesh from WebSocket binary protocol (spec S6.2). */
export interface MeshData {
  /** Flat vertex positions [x0,y0,z0, x1,y1,z1, ...]. */
  vertices: Float32Array;
  /** Flat vertex normals [nx0,ny0,nz0, ...]. */
  normals: Float32Array;
  /** Flat face indices [i0,i1,i2, ...] (3 per triangle). */
  faces: Uint32Array;
  vertexCount: number;
  faceCount: number;
  /** Per-component face ranges from backend. */
  componentRanges: ComponentRanges | null;
}

// ---------------------------------------------------------------------------
// REST Response Types
// ---------------------------------------------------------------------------

/** REST fallback response from POST /api/generate. */
export interface GenerationResult {
  vertices: number[][];
  normals: number[][];
  faces: number[][];
  derived: Record<string, number>;
  validation: Array<{ id: string; level: string; message: string; fields?: string[] }>;
}

/** Summary for design listing (GET /api/designs). */
export interface DesignSummary {
  id: string;
  name: string;
  createdAt: string;
  modifiedAt: string;
}

/** Summary of a custom preset (from GET /api/presets). */
export interface CustomPresetSummary {
  id: string;
  name: string;
  createdAt: string;
}

/** Supported export formats. */
export type ExportFormat = 'stl' | 'step' | 'dxf' | 'svg';

/** Request body for POST /api/export. */
export interface ExportRequest {
  design: AircraftDesign;
  format: ExportFormat;
}

/** Metadata for a single sectioned part in the export preview. */
export interface ExportPreviewPart {
  filename: string;
  component: string;
  side: string;
  sectionNum: number;
  totalSections: number;
  dimensionsMm: [number, number, number];
  printOrientation: string;
  assemblyOrder: number;
  fitsBed: boolean;
  /** Actual cut position in mm from the component bounding-box origin.
   *  Only present for components with multiple sections. (Issue #147) */
  cutPositionMm?: number | null;
  /** Whether this cut was adjusted away from the midpoint to avoid an
   *  internal feature (spar channel, wing root, fuselage saddle). (Issue #147) */
  cutAdjusted?: boolean;
  /** Human-readable reason for the cut adjustment. (Issue #147) */
  cutAdjustReason?: string;
}

/** Response from POST /api/export/preview. */
export interface ExportPreviewResponse {
  parts: ExportPreviewPart[];
  totalParts: number;
  bedDimensionsMm: [number, number, number];
  partsThatFit: number;
  partsThatExceed: number;
}
