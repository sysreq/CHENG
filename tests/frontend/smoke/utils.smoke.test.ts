// ============================================================================
// CHENG — Core utility smoke tests
// Tier 1: always run pre-commit (< 1s each)
//
// Covers: unit conversion, validation utilities, stability analyzer.
// Pure TypeScript — no DOM, no React, extremely fast.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { mmToIn, inToMm, MM_PER_INCH } from '@/lib/units';
import { formatWarning, fieldHasWarning } from '@/lib/validation';
import { getStabilityStatus, getStatusMeta } from '@/lib/stabilityAnalyzer';
import type { ValidationWarning } from '@/types/design';

// ---------------------------------------------------------------------------
// Unit conversion
// ---------------------------------------------------------------------------

describe('[smoke] unit conversion', () => {
  it('MM_PER_INCH is 25.4', () => {
    expect(MM_PER_INCH).toBe(25.4);
  });

  it('mmToIn converts correctly', () => {
    expect(mmToIn(25.4)).toBeCloseTo(1.0);
    expect(mmToIn(0)).toBe(0);
    expect(mmToIn(50.8)).toBeCloseTo(2.0);
  });

  it('inToMm converts correctly', () => {
    expect(inToMm(1)).toBeCloseTo(25.4);
    expect(inToMm(0)).toBe(0);
    expect(inToMm(2)).toBeCloseTo(50.8);
  });

  it('round-trip conversion is lossless', () => {
    const original = 1234.5;
    expect(inToMm(mmToIn(original))).toBeCloseTo(original);
  });
});

// ---------------------------------------------------------------------------
// Validation utilities
// ---------------------------------------------------------------------------

describe('[smoke] validation utilities', () => {
  const makeWarning = (id: string, fields: string[] = []): ValidationWarning => ({
    id: id as ValidationWarning['id'],
    level: 'warn',
    message: `Warning ${id}`,
    fields,
  });

  it('formatWarning returns bracketed id with message', () => {
    const w = makeWarning('V01');
    expect(formatWarning(w)).toBe('[V01] Warning V01');
  });

  it('fieldHasWarning returns true for matching field', () => {
    const warnings = [makeWarning('V01', ['wingSpan', 'fuselageLength'])];
    expect(fieldHasWarning(warnings, 'wingSpan')).toBe(true);
  });

  it('fieldHasWarning returns false for non-matching field', () => {
    const warnings = [makeWarning('V01', ['wingSpan'])];
    expect(fieldHasWarning(warnings, 'wingChord')).toBe(false);
  });

  it('fieldHasWarning returns false for empty warnings array', () => {
    expect(fieldHasWarning([], 'wingSpan')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Stability analyzer
// ---------------------------------------------------------------------------

describe('[smoke] stabilityAnalyzer', () => {
  it('classifies negative margin as unstable', () => {
    expect(getStabilityStatus(-1)).toBe('unstable');
    expect(getStabilityStatus(-5)).toBe('unstable');
  });

  it('classifies 0-2% as marginal', () => {
    expect(getStabilityStatus(0)).toBe('marginal');
    expect(getStabilityStatus(1)).toBe('marginal');
  });

  it('classifies 2-15% as stable', () => {
    expect(getStabilityStatus(2)).toBe('stable');
    expect(getStabilityStatus(10)).toBe('stable');
    expect(getStabilityStatus(15)).toBe('stable');
  });

  it('classifies > 15% as over-stable', () => {
    expect(getStabilityStatus(16)).toBe('over-stable');
    expect(getStabilityStatus(30)).toBe('over-stable');
  });

  it('getStatusMeta returns valid metadata for all statuses', () => {
    const statuses = ['unstable', 'marginal', 'stable', 'over-stable'] as const;
    for (const status of statuses) {
      const meta = getStatusMeta(status);
      expect(meta).toBeDefined();
      expect(meta.label).toBeTruthy();
      expect(meta.colorClass).toBeTruthy();
      expect(meta.description).toBeTruthy();
    }
  });
});
