import type { AircraftDesign, PresetName } from '../types/design';

// ---------------------------------------------------------------------------
// Preset Descriptions
// ---------------------------------------------------------------------------

export const PRESET_DESCRIPTIONS: Record<Exclude<PresetName, 'Custom'>, string> = {
  Trainer: 'Stable, forgiving high-wing trainer for beginners',
  Sport: 'Versatile mid-wing sport plane for intermediate pilots',
  Aerobatic: 'Symmetrical-airfoil aerobatic plane for advanced pilots',
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

    // Fuselage sections (sum = 400 = fuselageLength)
    fuselageNoseLength: 100,
    fuselageCabinLength: 200,
    fuselageTailLength: 100,

    // Fuselage wall
    wallThickness: 1.6,

    // Print/Export
    ...PRINT_DEFAULTS,

    // Support strategy
    supportStrategy: 'minimal',
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

    // Fuselage sections (sum = 300 = fuselageLength)
    fuselageNoseLength: 75,
    fuselageCabinLength: 150,
    fuselageTailLength: 75,

    // Fuselage wall
    wallThickness: 1.5,

    // Print/Export
    ...PRINT_DEFAULTS,

    // Support strategy
    supportStrategy: 'minimal',
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

    // Fuselage sections (sum = 280 = fuselageLength)
    fuselageNoseLength: 70,
    fuselageCabinLength: 140,
    fuselageTailLength: 70,

    // Fuselage wall
    wallThickness: 1.5,

    // Print/Export
    ...PRINT_DEFAULTS,

    // Support strategy
    supportStrategy: 'none',
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
};

export function createDesignFromPreset(
  name: Exclude<PresetName, 'Custom'>,
): AircraftDesign {
  return PRESET_FACTORIES[name]();
}

export const DEFAULT_PRESET: Exclude<PresetName, 'Custom'> = 'Trainer';
