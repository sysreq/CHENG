// ============================================================================
// CHENG — Preset configuration unit tests
// ============================================================================

import { describe, it, expect } from 'vitest';
import { createDesignFromPreset, PRESET_DESCRIPTIONS, PRESET_FACTORIES } from '@/lib/presets';
import type { AircraftDesign, PresetName } from '@/types/design';

/** All user-configurable param keys (excludes version, id, name). */
const ALL_PARAM_KEYS: (keyof AircraftDesign)[] = [
  'fuselagePreset', 'engineCount', 'motorConfig', 'wingSpan', 'wingChord',
  'wingMountType', 'fuselageLength', 'tailType', 'wingAirfoil', 'wingSweep',
  'wingTipRootRatio', 'wingDihedral', 'wingSkinThickness',
  'wingIncidence', 'wingTwist',
  // Multi-section wing params (#143)
  'wingSections', 'panelBreakPositions', 'panelDihedrals', 'panelSweeps',
  'hStabSpan', 'hStabChord', 'hStabIncidence', 'vStabHeight', 'vStabRootChord',
  'vTailDihedral', 'vTailSpan', 'vTailChord', 'vTailIncidence', 'vTailSweep',
  'tailArm',
  'fuselageNoseLength', 'fuselageCabinLength', 'fuselageTailLength',
  'wallThickness',
  'printBedX', 'printBedY', 'printBedZ', 'autoSection', 'sectionOverlap',
  'jointType', 'jointTolerance', 'nozzleDiameter', 'hollowParts', 'teMinThickness',
  'supportStrategy',
];

/** All non-Custom preset names. */
const ALL_PRESET_NAMES: Exclude<PresetName, 'Custom'>[] = [
  'Trainer', 'Sport', 'Aerobatic', 'Glider', 'FlyingWing', 'Scale',
];

describe('presets', () => {
  // ── Existing preset spot-checks ──────────────────────────────────────

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

  // ── Glider preset (#129) ─────────────────────────────────────────────

  it('Glider preset has high AR soaring config', () => {
    const d = createDesignFromPreset('Glider');
    expect(d.wingSpan).toBe(2000);
    expect(d.wingChord).toBe(130);
    expect(d.wingAirfoil).toBe('Eppler-387');
    expect(d.wingMountType).toBe('High-Wing');
    expect(d.tailType).toBe('V-Tail');
    expect(d.fuselagePreset).toBe('Pod');
    expect(d.engineCount).toBe(0);
    // Aspect ratio ~ 2000/130 ~ 15.4
    const ar = d.wingSpan / d.wingChord;
    expect(ar).toBeGreaterThan(14);
    expect(ar).toBeLessThan(17);
  });

  it('Glider preset has washout for tip stall prevention', () => {
    const d = createDesignFromPreset('Glider');
    expect(d.wingTwist).toBeLessThan(0); // negative = washout
    expect(d.wingIncidence).toBeGreaterThan(0); // positive root incidence
  });

  it('Glider preset V-tail params are reasonable', () => {
    const d = createDesignFromPreset('Glider');
    expect(d.vTailDihedral).toBe(40);
    expect(d.vTailSpan).toBe(450);
    expect(d.vTailChord).toBe(100);
    expect(d.vTailSweep).toBe(5);
    expect(d.tailArm).toBe(650);
    expect(d.fuselageLength).toBe(1000);
  });

  it('Glider fuselage sections sum to fuselage length', () => {
    const d = createDesignFromPreset('Glider');
    expect(d.fuselageNoseLength + d.fuselageCabinLength + d.fuselageTailLength)
      .toBe(d.fuselageLength);
  });

  // ── Flying Wing preset (#130) ────────────────────────────────────────

  it('Flying Wing preset has swept wing with washout', () => {
    const d = createDesignFromPreset('FlyingWing');
    expect(d.wingSpan).toBe(1100);
    expect(d.wingChord).toBe(250);
    expect(d.wingSweep).toBe(25);
    expect(d.wingTwist).toBe(-3.0); // strong washout for stability
    expect(d.wingIncidence).toBe(3.0);
    expect(d.wingAirfoil).toBe('NACA-0012'); // symmetrical avoids nose-down pitching moment
    expect(d.fuselagePreset).toBe('Blended-Wing-Body');
    expect(d.motorConfig).toBe('Pusher');
  });

  it('Flying Wing preset has minimal tail values', () => {
    const d = createDesignFromPreset('FlyingWing');
    expect(d.tailType).toBe('Conventional');
    expect(d.hStabSpan).toBeLessThanOrEqual(100);
    expect(d.hStabChord).toBeLessThanOrEqual(50);
    expect(d.tailArm).toBeLessThanOrEqual(100);
  });

  it('Flying Wing fuselage sections sum to fuselage length', () => {
    const d = createDesignFromPreset('FlyingWing');
    expect(d.fuselageNoseLength + d.fuselageCabinLength + d.fuselageTailLength)
      .toBe(d.fuselageLength);
  });

  // ── Scale preset (#131) ──────────────────────────────────────────────

  it('Scale preset has realistic proportions', () => {
    const d = createDesignFromPreset('Scale');
    expect(d.wingSpan).toBe(1400);
    expect(d.wingChord).toBe(190);
    expect(d.wingMountType).toBe('Low-Wing');
    expect(d.wingAirfoil).toBe('NACA-2412');
    expect(d.fuselagePreset).toBe('Conventional');
    expect(d.tailType).toBe('Conventional');
    expect(d.wingSweep).toBe(8);
    expect(d.wingTipRootRatio).toBe(0.55);
    // Fuselage length ~78% of wingspan — scale-like proportion
    expect(d.fuselageLength).toBe(1100);
    expect(d.tailArm).toBe(650);
  });

  it('Scale preset has moderate AR like scale models', () => {
    const d = createDesignFromPreset('Scale');
    const ar = d.wingSpan / d.wingChord;
    expect(ar).toBeGreaterThan(6);
    expect(ar).toBeLessThan(9);
  });

  it('Scale fuselage sections sum to fuselage length', () => {
    const d = createDesignFromPreset('Scale');
    expect(d.fuselageNoseLength + d.fuselageCabinLength + d.fuselageTailLength)
      .toBe(d.fuselageLength);
  });

  // ── Multi-section wing presets (#143) ───────────────────────────────

  it('Glider preset has wingSections=2 (polyhedral)', () => {
    const d = createDesignFromPreset('Glider');
    expect(d.wingSections).toBe(2);
    expect(d.panelBreakPositions).toHaveLength(3);
    expect(d.panelBreakPositions[0]).toBe(60.0);
    expect(d.panelDihedrals).toHaveLength(3);
    expect(d.panelSweeps).toHaveLength(3);
  });

  it('all non-Glider presets have wingSections=1 (single panel)', () => {
    for (const name of ['Trainer', 'Sport', 'Aerobatic', 'FlyingWing', 'Scale'] as const) {
      const d = createDesignFromPreset(name);
      expect(d.wingSections, `${name} should have wingSections=1`).toBe(1);
    }
  });

  it('all presets have panelBreakPositions, panelDihedrals, panelSweeps arrays', () => {
    for (const name of ALL_PRESET_NAMES) {
      const d = createDesignFromPreset(name);
      expect(Array.isArray(d.panelBreakPositions), `${name} panelBreakPositions should be array`).toBe(true);
      expect(Array.isArray(d.panelDihedrals), `${name} panelDihedrals should be array`).toBe(true);
      expect(Array.isArray(d.panelSweeps), `${name} panelSweeps should be array`).toBe(true);
    }
  });

  // ── Cross-cutting tests ──────────────────────────────────────────────

  it('all presets populate every design param (no undefined)', () => {
    for (const name of ALL_PRESET_NAMES) {
      const design = createDesignFromPreset(name);
      for (const key of ALL_PARAM_KEYS) {
        expect(design[key], `${name}.${key} should be defined`).not.toBeUndefined();
      }
    }
  });

  it('all presets have descriptions', () => {
    for (const name of ALL_PRESET_NAMES) {
      expect(PRESET_DESCRIPTIONS[name], `${name} should have a description`).toBeDefined();
    }
  });

  it('PRESET_FACTORIES has entries for all preset names', () => {
    for (const name of ALL_PRESET_NAMES) {
      expect(PRESET_FACTORIES[name], `${name} should have a factory`).toBeInstanceOf(Function);
    }
  });

  it('each call generates a unique id', () => {
    const a = createDesignFromPreset('Trainer');
    const b = createDesignFromPreset('Trainer');
    expect(a.id).not.toBe(b.id);
  });

  it('fuselage sections sum to fuselage length for all presets', () => {
    for (const name of ALL_PRESET_NAMES) {
      const d = createDesignFromPreset(name);
      expect(
        d.fuselageNoseLength + d.fuselageCabinLength + d.fuselageTailLength,
        `${name} fuselage sections should sum to fuselageLength`,
      ).toBe(d.fuselageLength);
    }
  });
});
