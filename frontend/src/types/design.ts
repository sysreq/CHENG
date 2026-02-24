// ============================================================================
// CHENG — Canonical Frontend Type Definitions
// Mirrors backend/models.py Pydantic models (snake_case -> camelCase)
// ============================================================================

// ---------------------------------------------------------------------------
// Enum / Literal Types
// ---------------------------------------------------------------------------

/** Aircraft preset names. 'Custom' auto-selected when any param is manually edited. */
export type PresetName = 'Trainer' | 'Sport' | 'Aerobatic' | 'Custom';

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

/** Selectable component in the 3D viewport. */
export type ComponentSelection = 'wing' | 'tail' | 'fuselage' | null;

/** Infill density hint for per-component print settings. */
export type InfillHint = 'low' | 'medium' | 'high';

/** Support generation strategy for per-component print settings. */
export type SupportStrategy = 'none' | 'minimal' | 'normal' | 'everywhere';

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
export type PerComponentPrintSettings = Partial<Record<'wing' | 'tail' | 'fuselage', ComponentPrintSettings>>;

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
  /** Number of engines. @min 0 @max 4 @default 1 */
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

  // ── Shared Tail ───────────────────────────────────────────────────
  /** Wing AC to tail AC distance. @unit mm @min 80 @max 1500 @default 180 */
  tailArm: number;

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

/** Structural warning IDs (V01-V06). */
export type StructuralWarningId = 'V01' | 'V02' | 'V03' | 'V04' | 'V05' | 'V06';
/** Print warning IDs (V16-V23). */
export type PrintWarningId = 'V16' | 'V17' | 'V18' | 'V20' | 'V21' | 'V22' | 'V23';
/** All warning IDs. */
export type WarningId = StructuralWarningId | PrintWarningId;

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

/** Per-component face index ranges for selection highlighting. */
export type ComponentRanges = Partial<Record<'fuselage' | 'wing' | 'tail', [number, number]>>;

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

/** Request body for POST /api/export. */
export interface ExportRequest {
  design: AircraftDesign;
  format: 'stl';
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
}

/** Response from POST /api/export/preview. */
export interface ExportPreviewResponse {
  parts: ExportPreviewPart[];
  totalParts: number;
  bedDimensionsMm: [number, number, number];
  partsThatFit: number;
  partsThatExceed: number;
}
