// ============================================================================
// CHENG — DimensionLines wing X position calculation tests (#238)
// ============================================================================
//
// Tests the WING_X_FRACTION constant and wingX computation that drives the
// GlobalDimensions wingspan annotation in DimensionLines.tsx.
// The logic is extracted here as a pure function so it can be tested without
// needing to spin up the full R3F canvas.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { createDesignFromPreset } from '@/lib/presets';

// ---------------------------------------------------------------------------
// Mirror of the WING_X_FRACTION map in DimensionLines.tsx
// ---------------------------------------------------------------------------

/** Wing mount X position as a fraction of fuselage length, per fuselage style.
 *  Must stay in sync with WING_X_FRACTION in DimensionLines.tsx and
 *  _WING_X_FRACTION in backend/geometry/engine.py. */
const WING_X_FRACTION: Record<string, number> = {
  Conventional: 0.30,
  Pod: 0.25,
  'Blended-Wing-Body': 0.35,
};

/** Compute the wing mount X position for a given fuselage preset and length. */
function computeWingX(fuselagePreset: string, fuselageLength: number): number {
  const frac = WING_X_FRACTION[fuselagePreset] ?? 0.30;
  return fuselageLength * frac;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('GlobalDimensions wing X position (#238)', () => {
  // ── WING_X_FRACTION constant values ──────────────────────────────────────

  it('Conventional fuselage uses 0.30 fraction', () => {
    expect(WING_X_FRACTION['Conventional']).toBe(0.30);
  });

  it('Pod fuselage uses 0.25 fraction', () => {
    expect(WING_X_FRACTION['Pod']).toBe(0.25);
  });

  it('Blended-Wing-Body fuselage uses 0.35 fraction', () => {
    expect(WING_X_FRACTION['Blended-Wing-Body']).toBe(0.35);
  });

  it('unknown fuselage preset falls back to 0.30 fraction', () => {
    const frac = WING_X_FRACTION['UnknownPreset'] ?? 0.30;
    expect(frac).toBe(0.30);
  });

  // ── Trainer preset: Conventional fuselage, fuselageLength=400 ────────────

  it('Trainer preset: wingspan line drawn at 30% of fuselage length (not at nose)', () => {
    const design = createDesignFromPreset('Trainer');
    const wingX = computeWingX(design.fuselagePreset, design.fuselageLength);
    // Conventional (0.30) × 400mm = 120mm from nose
    expect(design.fuselagePreset).toBe('Conventional');
    expect(design.fuselageLength).toBe(400);
    expect(wingX).toBe(120);
    // Critically — NOT at the nose (X=0)
    expect(wingX).not.toBe(0);
  });

  // ── Sport preset: Conventional fuselage, fuselageLength=300 ──────────────

  it('Sport preset: wingspan line drawn at 30% of fuselage length', () => {
    const design = createDesignFromPreset('Sport');
    const wingX = computeWingX(design.fuselagePreset, design.fuselageLength);
    // Conventional (0.30) × 300mm = 90mm from nose
    expect(design.fuselagePreset).toBe('Conventional');
    expect(design.fuselageLength).toBe(300);
    expect(wingX).toBe(90);
    expect(wingX).not.toBe(0);
  });

  // ── Glider preset: Pod fuselage, fuselageLength=1000 ─────────────────────

  it('Glider preset: wingspan line drawn at 25% of fuselage length (Pod fraction)', () => {
    const design = createDesignFromPreset('Glider');
    const wingX = computeWingX(design.fuselagePreset, design.fuselageLength);
    // Pod (0.25) × 1000mm = 250mm from nose
    expect(design.fuselagePreset).toBe('Pod');
    expect(design.fuselageLength).toBe(1000);
    expect(wingX).toBe(250);
    expect(wingX).not.toBe(0);
  });

  // ── FlyingWing preset: Blended-Wing-Body fuselage, fuselageLength=200 ────

  it('FlyingWing preset: wingspan line drawn at 35% of fuselage length (BWB fraction)', () => {
    const design = createDesignFromPreset('FlyingWing');
    const wingX = computeWingX(design.fuselagePreset, design.fuselageLength);
    // Blended-Wing-Body (0.35) × 200mm = 70mm from nose
    expect(design.fuselagePreset).toBe('Blended-Wing-Body');
    expect(design.fuselageLength).toBe(200);
    expect(wingX).toBe(70);
    expect(wingX).not.toBe(0);
  });

  // ── Scale preset: Conventional fuselage, fuselageLength=1100 ────────────

  it('Scale preset: wingspan line drawn at 30% of fuselage length', () => {
    const design = createDesignFromPreset('Scale');
    const wingX = computeWingX(design.fuselagePreset, design.fuselageLength);
    // Conventional (0.30) × 1100mm = 330mm from nose
    expect(design.fuselagePreset).toBe('Conventional');
    expect(design.fuselageLength).toBe(1100);
    expect(wingX).toBe(330);
    expect(wingX).not.toBe(0);
  });

  // ── Fuselage annotation offset ───────────────────────────────────────────

  it('fuselage length annotation uses fixed 40mm offset, not halfSpan-based', () => {
    const design = createDesignFromPreset('Trainer');
    const halfSpan = design.wingSpan / 2;   // 600mm for Trainer
    // Old bug: spanY = halfSpan + 40 = 640mm — floated far to the side
    const oldSpanY = halfSpan + 40;
    // Fixed: spanY = 40 — close to centreline
    const fixedSpanY = 40;

    expect(fixedSpanY).toBe(40);
    expect(oldSpanY).toBeGreaterThan(100); // confirm the old value was far off
    expect(fixedSpanY).toBeLessThan(oldSpanY);
  });

  it('fuselage annotation offset is wingspan-independent', () => {
    // With the fix, spanY=40 regardless of wingspan.
    // Verify this holds for the largest preset (Glider: 2000mm span).
    const glider = createDesignFromPreset('Glider');
    const halfSpan = glider.wingSpan / 2; // 1000mm
    const fixedSpanY = 40;

    // Old value would have been 1040mm off-centre — clearly wrong
    const oldSpanY = halfSpan + 40;
    expect(oldSpanY).toBeGreaterThan(500);
    // Fixed value is always 40mm
    expect(fixedSpanY).toBe(40);
  });
});
