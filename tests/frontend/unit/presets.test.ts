// ============================================================================
// CHENG — Preset configuration unit tests
// ============================================================================

import { describe, it, expect } from 'vitest';
import { createDesignFromPreset, PRESET_DESCRIPTIONS } from '@/lib/presets';
import type { AircraftDesign } from '@/types/design';

/** All 33 user-configurable param keys (excludes version, id, name). */
const ALL_PARAM_KEYS: (keyof AircraftDesign)[] = [
  'fuselagePreset', 'engineCount', 'motorConfig', 'wingSpan', 'wingChord',
  'wingMountType', 'fuselageLength', 'tailType', 'wingAirfoil', 'wingSweep',
  'wingTipRootRatio', 'wingDihedral', 'wingSkinThickness', 'hStabSpan',
  'hStabChord', 'hStabIncidence', 'vStabHeight', 'vStabRootChord',
  'vTailDihedral', 'vTailSpan', 'vTailChord', 'vTailIncidence', 'tailArm',
  'printBedX', 'printBedY', 'printBedZ', 'autoSection', 'sectionOverlap',
  'jointType', 'jointTolerance', 'nozzleDiameter', 'hollowParts', 'teMinThickness',
];

describe('presets', () => {
  it('Trainer preset has wingSpan=1200', () => {
    const design = createDesignFromPreset('Trainer');
    expect(design.wingSpan).toBe(1200);
  });

  it('Sport preset has wingSpan=1000', () => {
    const design = createDesignFromPreset('Sport');
    expect(design.wingSpan).toBe(1000);
  });

  it('Aerobatic preset has wingSpan=900', () => {
    const design = createDesignFromPreset('Aerobatic');
    expect(design.wingSpan).toBe(900);
  });

  it('Trainer preset has expected key values', () => {
    const d = createDesignFromPreset('Trainer');
    expect(d.wingChord).toBe(200);
    expect(d.wingMountType).toBe('High-Wing');
    expect(d.wingAirfoil).toBe('Clark-Y');
    expect(d.wingTipRootRatio).toBe(1.0);
    expect(d.fuselageLength).toBe(400);
  });

  it('Sport preset has correct sweep and taper', () => {
    const d = createDesignFromPreset('Sport');
    expect(d.wingSweep).toBe(5);
    expect(d.wingTipRootRatio).toBe(0.67);
    expect(d.wingMountType).toBe('Mid-Wing');
  });

  it('Aerobatic preset has symmetric airfoil and zero dihedral', () => {
    const d = createDesignFromPreset('Aerobatic');
    expect(d.wingAirfoil).toBe('NACA-0012');
    expect(d.wingDihedral).toBe(0);
    expect(d.wingTipRootRatio).toBe(1.0);
  });

  it('all presets populate every design param (no undefined)', () => {
    for (const name of ['Trainer', 'Sport', 'Aerobatic'] as const) {
      const design = createDesignFromPreset(name);
      for (const key of ALL_PARAM_KEYS) {
        expect(design[key], `${name}.${key} should be defined`).not.toBeUndefined();
      }
    }
  });

  it('all presets have descriptions', () => {
    expect(PRESET_DESCRIPTIONS.Trainer).toBeDefined();
    expect(PRESET_DESCRIPTIONS.Sport).toBeDefined();
    expect(PRESET_DESCRIPTIONS.Aerobatic).toBeDefined();
  });

  it('each call generates a unique id', () => {
    const a = createDesignFromPreset('Trainer');
    const b = createDesignFromPreset('Trainer');
    expect(a.id).not.toBe(b.id);
  });
});
