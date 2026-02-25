import type { AircraftDesign, PresetName } from '../types/design';

// ---------------------------------------------------------------------------
// Preset Descriptions
// ---------------------------------------------------------------------------

export const PRESET_DESCRIPTIONS: Record<Exclude<PresetName, 'Custom'>, string> = {
  Trainer: 'Stable, forgiving high-wing trainer for beginners',
  Sport: 'Versatile mid-wing sport plane for intermediate pilots',
  Aerobatic: 'Symmetrical-airfoil aerobatic plane for advanced pilots',
  Glider: 'High aspect ratio soaring plane with V-tail for thermals',
  FlyingWing: 'Swept flying wing with reflex airfoil — no conventional tail',
  Scale: 'Realistic scale-model proportions with conventional layout',
};

// ---------------------------------------------------------------------------
// Shared Print/Export Defaults (identical across all presets)
// ---------------------------------------------------------------------------

const PRINT_DEFAULTS = {
  printBedX: 220,
  printBedY: 220,
  printBedZ: 250,
  autoSection: true,
  sectionOverlap: 15,
  jointType: 'Tongue-and-Groove' as const,
  jointTolerance: 0.15,
  nozzleDiameter: 0.4,
  hollowParts: true,
  teMinThickness: 0.8,
};

// Shared V-tail defaults (populated even for non-V-tail presets)
const VTAIL_DEFAULTS = {
  vTailDihedral: 35,
  vTailSpan: 280,
  vTailChord: 90,
  vTailIncidence: 0,
  vTailSweep: 0,
};

// Shared control surface defaults — all disabled by default (Issue #144)
const CONTROL_SURFACE_DEFAULTS = {
  aileronEnable: false,
  aileronSpanStart: 55,
  aileronSpanEnd: 95,
  aileronChordPercent: 25,
  elevatorEnable: false,
  elevatorSpanPercent: 100,
  elevatorChordPercent: 35,
  rudderEnable: false,
  rudderHeightPercent: 90,
  rudderChordPercent: 35,
  ruddervatorEnable: false,
  ruddervatorChordPercent: 35,
  ruddervatorSpanPercent: 90,
  elevonEnable: false,
  elevonSpanStart: 20,
  elevonSpanEnd: 90,
  elevonChordPercent: 20,
};

// Multi-section wing defaults (single panel — no breaks active)
const MULTI_SECTION_DEFAULTS = {
  wingSections: 1,
  panelBreakPositions: [60.0, 80.0, 90.0],
  panelDihedrals: [10.0, 5.0, 5.0],
  panelSweeps: [0.0, 0.0, 0.0],
};

// Shared landing gear defaults — all presets default to 'None' (belly land)
const LANDING_GEAR_DEFAULTS = {
  landingGearType: 'None' as const,
  mainGearPosition: 35,
  mainGearHeight: 40,
  mainGearTrack: 120,
  mainWheelDiameter: 30,
  noseGearHeight: 45,
  noseWheelDiameter: 20,
  tailWheelDiameter: 12,
  tailGearPosition: 92,
};

// ---------------------------------------------------------------------------
// Preset Factory Functions
// ---------------------------------------------------------------------------

function generateId(): string {
  return crypto.randomUUID();
}

function createTrainerPreset(): AircraftDesign {
  return {
    version: '0.1.0',
    id: generateId(),
    name: 'Untitled Aircraft',

    // Global / Fuselage
    fuselagePreset: 'Conventional',
    engineCount: 1,
    motorConfig: 'Tractor',
    wingSpan: 1200,
    wingChord: 200,
    wingMountType: 'High-Wing',
    fuselageLength: 400,
    tailType: 'Conventional',

    // Wing
    wingAirfoil: 'Clark-Y',
    wingSweep: 0,
    wingTipRootRatio: 1.0,
    wingDihedral: 3,
    wingSkinThickness: 1.2,
    wingIncidence: 2.0,
    wingTwist: -1.0,

    // Tail (Conventional)
    hStabSpan: 400,
    hStabChord: 120,
    hStabIncidence: -1,
    vStabHeight: 120,
    vStabRootChord: 130,
    tailArm: 220,

    // V-tail defaults
    ...VTAIL_DEFAULTS,

    // Fuselage section transition points (F11/F12)
    // nose=100/400=25%, nose+cabin=300/400=75%
    noseCabinBreakPct: 25,
    cabinTailBreakPct: 75,

    // Fuselage wall
    wallThickness: 1.6,

    // Landing gear (belly land by default)
    ...LANDING_GEAR_DEFAULTS,

    // Print/Export
    ...PRINT_DEFAULTS,

    // Control surfaces — all disabled by default
    ...CONTROL_SURFACE_DEFAULTS,

    // Support strategy
    supportStrategy: 'minimal',

    // Multi-section wing defaults (single panel)
    ...MULTI_SECTION_DEFAULTS,
  };
}

function createSportPreset(): AircraftDesign {
  return {
    version: '0.1.0',
    id: generateId(),
    name: 'Untitled Aircraft',

    // Global / Fuselage
    fuselagePreset: 'Conventional',
    engineCount: 1,
    motorConfig: 'Tractor',
    wingSpan: 1000,
    wingChord: 180,
    wingMountType: 'Mid-Wing',
    fuselageLength: 300,
    tailType: 'Conventional',

    // Wing
    wingAirfoil: 'NACA-2412',
    wingSweep: 5,
    wingTipRootRatio: 0.67,
    wingDihedral: 3,
    wingSkinThickness: 1.2,
    wingIncidence: 2.0,
    wingTwist: -0.5,

    // Tail (Conventional)
    hStabSpan: 350,
    hStabChord: 100,
    hStabIncidence: -1,
    vStabHeight: 100,
    vStabRootChord: 110,
    tailArm: 180,

    // V-tail defaults
    ...VTAIL_DEFAULTS,

    // Fuselage section transition points (F11/F12)
    // nose=75/300=25%, nose+cabin=225/300=75%
    noseCabinBreakPct: 25,
    cabinTailBreakPct: 75,

    // Fuselage wall
    wallThickness: 1.5,

    // Landing gear (belly land by default)
    ...LANDING_GEAR_DEFAULTS,

    // Print/Export
    ...PRINT_DEFAULTS,

    // Control surfaces — all disabled by default
    ...CONTROL_SURFACE_DEFAULTS,

    // Support strategy
    supportStrategy: 'minimal',

    // Multi-section wing defaults (single panel)
    ...MULTI_SECTION_DEFAULTS,
  };
}

function createAerobaticPreset(): AircraftDesign {
  return {
    version: '0.1.0',
    id: generateId(),
    name: 'Untitled Aircraft',

    // Global / Fuselage
    fuselagePreset: 'Conventional',
    engineCount: 1,
    motorConfig: 'Tractor',
    wingSpan: 900,
    wingChord: 220,
    wingMountType: 'Mid-Wing',
    fuselageLength: 280,
    tailType: 'Conventional',

    // Wing
    wingAirfoil: 'NACA-0012',
    wingSweep: 0,
    wingTipRootRatio: 1.0,
    wingDihedral: 0,
    wingSkinThickness: 1.2,
    wingIncidence: 0.0,
    wingTwist: 0.0,

    // Tail (Conventional)
    hStabSpan: 350,
    hStabChord: 110,
    hStabIncidence: 0,
    vStabHeight: 120,
    vStabRootChord: 120,
    tailArm: 170,

    // V-tail defaults
    ...VTAIL_DEFAULTS,

    // Fuselage section transition points (F11/F12)
    // nose=70/280=25%, nose+cabin=210/280=75%
    noseCabinBreakPct: 25,
    cabinTailBreakPct: 75,

    // Fuselage wall
    wallThickness: 1.5,

    // Landing gear (belly land by default)
    ...LANDING_GEAR_DEFAULTS,

    // Print/Export
    ...PRINT_DEFAULTS,

    // Control surfaces — all disabled by default
    ...CONTROL_SURFACE_DEFAULTS,

    // Support strategy
    supportStrategy: 'none',

    // Multi-section wing defaults (single panel)
    ...MULTI_SECTION_DEFAULTS,
  };
}

function createGliderPreset(): AircraftDesign {
  return {
    version: '0.1.0',
    id: generateId(),
    name: 'Untitled Aircraft',

    // Global / Fuselage
    fuselagePreset: 'Pod',
    engineCount: 0,
    motorConfig: 'Tractor',
    wingSpan: 2000,
    wingChord: 130,
    wingMountType: 'High-Wing',
    fuselageLength: 1000,
    tailType: 'V-Tail',

    // Wing
    wingAirfoil: 'Eppler-387',
    wingSweep: 3,
    wingTipRootRatio: 0.5,
    wingDihedral: 5,
    wingSkinThickness: 1.0,
    wingIncidence: 2.0,
    wingTwist: -2.0,

    // Tail (Conventional fields — populated even for V-tail)
    hStabSpan: 400,
    hStabChord: 100,
    hStabIncidence: -1,
    vStabHeight: 120,
    vStabRootChord: 100,
    tailArm: 650,

    // V-tail — sized for adequate volume coefficients (Vh~0.38, Vv~0.025)
    vTailDihedral: 40,
    vTailSpan: 450,
    vTailChord: 100,
    vTailIncidence: 0,
    vTailSweep: 5,

    // Fuselage section transition points (F11/F12)
    // nose=200/1000=20%, nose+cabin=500/1000=50%
    noseCabinBreakPct: 20,
    cabinTailBreakPct: 50,

    // Fuselage wall
    wallThickness: 1.2,

    // Landing gear (belly land by default)
    ...LANDING_GEAR_DEFAULTS,

    // Print/Export
    ...PRINT_DEFAULTS,

    // Control surfaces — all disabled by default
    ...CONTROL_SURFACE_DEFAULTS,

    // Support strategy
    supportStrategy: 'none',

    // Multi-section wing: Glider uses 2-panel polyhedral (inner flat, outer angled)
    wingSections: 2,
    panelBreakPositions: [60.0, 80.0, 90.0],
    panelDihedrals: [10.0, 5.0, 5.0],
    panelSweeps: [0.0, 0.0, 0.0],
  };
}

function createFlyingWingPreset(): AircraftDesign {
  return {
    version: '0.1.0',
    id: generateId(),
    name: 'Untitled Aircraft',

    // Global / Fuselage
    fuselagePreset: 'Blended-Wing-Body',
    engineCount: 1,
    motorConfig: 'Pusher',
    wingSpan: 1100,
    wingChord: 250,
    wingMountType: 'Mid-Wing',
    fuselageLength: 200,
    tailType: 'Conventional',

    // Wing — high sweep + washout for pitch stability without a meaningful tail
    // Symmetrical airfoil avoids nose-down pitching moment of cambered profiles
    wingAirfoil: 'NACA-0012',
    wingSweep: 25,
    wingTipRootRatio: 0.4,
    wingDihedral: 2,
    wingSkinThickness: 1.5,
    wingIncidence: 3.0,
    wingTwist: -3.0,

    // Tail — minimal vestigial (backend requires tail geometry; flying wing
    // relies on sweep + washout for pitch stability). Vertical fin sized for
    // basic yaw damping on a pusher configuration.
    hStabSpan: 100,
    hStabChord: 30,
    hStabIncidence: 0,
    vStabHeight: 150,
    vStabRootChord: 80,
    tailArm: 80,

    // V-tail defaults
    ...VTAIL_DEFAULTS,

    // Fuselage section transition points (F11/F12)
    // nose=60/200=30%, nose+cabin=160/200=80%
    noseCabinBreakPct: 30,
    cabinTailBreakPct: 80,

    // Fuselage wall
    wallThickness: 1.5,

    // Landing gear (belly land by default)
    ...LANDING_GEAR_DEFAULTS,

    // Print/Export
    ...PRINT_DEFAULTS,

    // Control surfaces — all disabled by default
    ...CONTROL_SURFACE_DEFAULTS,

    // Support strategy
    supportStrategy: 'minimal',

    // Multi-section wing defaults (single panel)
    ...MULTI_SECTION_DEFAULTS,
  };
}

function createScalePreset(): AircraftDesign {
  return {
    version: '0.1.0',
    id: generateId(),
    name: 'Untitled Aircraft',

    // Global / Fuselage
    fuselagePreset: 'Conventional',
    engineCount: 1,
    motorConfig: 'Tractor',
    wingSpan: 1400,
    wingChord: 190,
    wingMountType: 'Low-Wing',
    fuselageLength: 1100,
    tailType: 'Conventional',

    // Wing
    wingAirfoil: 'NACA-2412',
    wingSweep: 8,
    wingTipRootRatio: 0.55,
    wingDihedral: 5,
    wingSkinThickness: 1.2,
    wingIncidence: 2.0,
    wingTwist: -1.5,

    // Tail (Conventional) — scale-like proportions with proper tail arm
    hStabSpan: 380,
    hStabChord: 100,
    hStabIncidence: -1.5,
    vStabHeight: 160,
    vStabRootChord: 130,
    tailArm: 650,

    // V-tail defaults
    ...VTAIL_DEFAULTS,

    // Fuselage section transition points (F11/F12)
    // nose=275/1100=25%, nose+cabin=715/1100=65%
    noseCabinBreakPct: 25,
    cabinTailBreakPct: 65,

    // Fuselage wall
    wallThickness: 1.5,

    // Landing gear (belly land by default)
    ...LANDING_GEAR_DEFAULTS,

    // Print/Export
    ...PRINT_DEFAULTS,

    // Control surfaces — all disabled by default
    ...CONTROL_SURFACE_DEFAULTS,

    // Support strategy
    supportStrategy: 'minimal',

    // Multi-section wing defaults (single panel)
    ...MULTI_SECTION_DEFAULTS,
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export const PRESET_FACTORIES: Record<
  Exclude<PresetName, 'Custom'>,
  () => AircraftDesign
> = {
  Trainer: createTrainerPreset,
  Sport: createSportPreset,
  Aerobatic: createAerobaticPreset,
  Glider: createGliderPreset,
  FlyingWing: createFlyingWingPreset,
  Scale: createScalePreset,
};

export function createDesignFromPreset(
  name: Exclude<PresetName, 'Custom'>,
): AircraftDesign {
  return PRESET_FACTORIES[name]();
}

export const DEFAULT_PRESET: Exclude<PresetName, 'Custom'> = 'Trainer';
