// ============================================================================
// CHENG — Validation utility unit tests
// ============================================================================

import { describe, it, expect } from 'vitest';
import {
  formatWarning,
  getWarningCountBadge,
  groupWarningsByCategory,
  fieldHasWarning,
  getFieldWarnings,
  WARNING_DESCRIPTIONS,
} from '@/lib/validation';
import type { ValidationWarning } from '@/types/design';

const makeWarning = (id: string, fields: string[] = []): ValidationWarning => ({
  id: id as ValidationWarning['id'],
  level: 'warn',
  message: `Warning ${id}`,
  fields,
});

// All canonical warning IDs from backend/validation.py (V01-V13, V16-V23, V24-V32)
const ALL_WARNING_IDS = [
  // Structural / geometric (V01-V08)
  'V01', 'V02', 'V03', 'V04', 'V05', 'V06', 'V07', 'V08',
  // Aerodynamic / structural analysis (V09-V13)
  'V09', 'V10', 'V11', 'V12', 'V13',
  // 3D printing (V16-V23)
  'V16', 'V17', 'V18', 'V20', 'V21', 'V22', 'V23',
  // Printability analysis (V24-V28)
  'V24', 'V25', 'V26', 'V27', 'V28',
  // Advanced geometry warnings (V29-V32)
  'V29', 'V30', 'V31', 'V32',
] as const;

const AERO_IDS = ['V09', 'V10', 'V11', 'V12', 'V13'] as const;
const PRINT_IDS = ['V16', 'V17', 'V18', 'V20', 'V21', 'V22', 'V23', 'V24', 'V25', 'V26', 'V27', 'V28'] as const;
const STRUCTURAL_IDS = ['V01', 'V02', 'V03', 'V04', 'V05', 'V06', 'V07', 'V08', 'V29', 'V30', 'V31', 'V32'] as const;

describe('validation utilities', () => {
  it('formatWarning returns bracketed id with message', () => {
    const w = makeWarning('V01');
    expect(formatWarning(w)).toBe('[V01] Warning V01');
  });

  it('getWarningCountBadge returns correct strings', () => {
    expect(getWarningCountBadge([])).toBe('');
    expect(getWarningCountBadge([makeWarning('V01')])).toBe('1 warning');
    expect(getWarningCountBadge([makeWarning('V01'), makeWarning('V02')])).toBe('2 warnings');
  });

  it('groupWarningsByCategory separates structural and print', () => {
    const warnings = [
      makeWarning('V01'),
      makeWarning('V02'),
      makeWarning('V16'),
      makeWarning('V20'),
    ];
    const { structural, print } = groupWarningsByCategory(warnings);
    expect(structural).toHaveLength(2);
    expect(print).toHaveLength(2);
    expect(structural.map((w) => w.id)).toEqual(['V01', 'V02']);
    expect(print.map((w) => w.id)).toEqual(['V16', 'V20']);
  });

  it('fieldHasWarning checks field association', () => {
    const warnings = [makeWarning('V01', ['wingSpan', 'fuselageLength'])];
    expect(fieldHasWarning(warnings, 'wingSpan')).toBe(true);
    expect(fieldHasWarning(warnings, 'wingChord')).toBe(false);
  });

  it('getFieldWarnings returns matching warnings', () => {
    const warnings = [
      makeWarning('V01', ['wingSpan']),
      makeWarning('V02', ['wingTipRootRatio']),
      makeWarning('V05', ['wingSpan']),
    ];
    const result = getFieldWarnings(warnings, 'wingSpan');
    expect(result).toHaveLength(2);
    expect(result.map((w) => w.id)).toEqual(['V01', 'V05']);
  });
});

// ============================================================================
// Issue #273 — Complete warning ID coverage
// ============================================================================

describe('WARNING_DESCRIPTIONS completeness (Issue #273)', () => {
  it('has an entry for every canonical warning ID V01-V32', () => {
    for (const id of ALL_WARNING_IDS) {
      expect(
        WARNING_DESCRIPTIONS[id],
        `WARNING_DESCRIPTIONS is missing an entry for ${id}`,
      ).toBeDefined();
      expect(WARNING_DESCRIPTIONS[id].length).toBeGreaterThan(0);
    }
  });

  it('V07 and V08 have descriptions', () => {
    expect(WARNING_DESCRIPTIONS['V07']).toBeTruthy();
    expect(WARNING_DESCRIPTIONS['V08']).toBeTruthy();
  });

  it('V09-V13 (aero) have descriptions', () => {
    for (const id of AERO_IDS) {
      expect(WARNING_DESCRIPTIONS[id], `Missing description for aero warning ${id}`).toBeTruthy();
    }
  });

  it('V24-V28 (printability) have descriptions', () => {
    for (const id of ['V24', 'V25', 'V26', 'V27', 'V28'] as const) {
      expect(WARNING_DESCRIPTIONS[id], `Missing description for printability warning ${id}`).toBeTruthy();
    }
  });

  it('V29-V32 (advanced geometry) have descriptions', () => {
    for (const id of ['V29', 'V30', 'V31', 'V32'] as const) {
      expect(WARNING_DESCRIPTIONS[id], `Missing description for advanced warning ${id}`).toBeTruthy();
    }
  });
});

describe('groupWarningsByCategory — full ID coverage (Issue #273)', () => {
  it('routes V09-V13 to aero category', () => {
    const warnings = AERO_IDS.map((id) => makeWarning(id));
    const { structural, aero, print } = groupWarningsByCategory(warnings);
    expect(aero).toHaveLength(AERO_IDS.length);
    expect(structural).toHaveLength(0);
    expect(print).toHaveLength(0);
    expect(aero.map((w) => w.id)).toEqual([...AERO_IDS]);
  });

  it('routes V24-V28 (printability) to print category', () => {
    const printabilityIds = ['V24', 'V25', 'V26', 'V27', 'V28'] as const;
    const warnings = printabilityIds.map((id) => makeWarning(id));
    const { print, structural, aero } = groupWarningsByCategory(warnings);
    expect(print).toHaveLength(printabilityIds.length);
    expect(structural).toHaveLength(0);
    expect(aero).toHaveLength(0);
  });

  it('routes V16-V23 (3D printing) to print category', () => {
    const ids = ['V16', 'V17', 'V18', 'V20', 'V21', 'V22', 'V23'] as const;
    const warnings = ids.map((id) => makeWarning(id));
    const { print } = groupWarningsByCategory(warnings);
    expect(print).toHaveLength(ids.length);
  });

  it('routes V29 (multi-section wing) to structural category', () => {
    const { structural, aero, print } = groupWarningsByCategory([makeWarning('V29')]);
    expect(structural).toHaveLength(1);
    expect(structural[0].id).toBe('V29');
    expect(aero).toHaveLength(0);
    expect(print).toHaveLength(0);
  });

  it('routes V30 (control surfaces) to structural category', () => {
    const { structural } = groupWarningsByCategory([makeWarning('V30')]);
    expect(structural[0].id).toBe('V30');
  });

  it('routes V31 (landing gear) to structural category', () => {
    const { structural } = groupWarningsByCategory([makeWarning('V31')]);
    expect(structural[0].id).toBe('V31');
  });

  it('routes V32 (tail arm) to structural category', () => {
    const { structural } = groupWarningsByCategory([makeWarning('V32')]);
    expect(structural[0].id).toBe('V32');
  });

  it('correctly categorises all known IDs without dropping any', () => {
    const warnings = ALL_WARNING_IDS.map((id) => makeWarning(id));
    const { structural, aero, print } = groupWarningsByCategory(warnings);
    const total = structural.length + aero.length + print.length;
    expect(total).toBe(ALL_WARNING_IDS.length);
  });

  it('unknown IDs default to structural (never silently dropped)', () => {
    const { structural } = groupWarningsByCategory([makeWarning('V99')]);
    expect(structural).toHaveLength(1);
    expect(structural[0].id).toBe('V99');
  });

  it('V07 and V08 are in structural category', () => {
    const warnings = [makeWarning('V07'), makeWarning('V08')];
    const { structural, aero, print } = groupWarningsByCategory(warnings);
    expect(structural).toHaveLength(2);
    expect(aero).toHaveLength(0);
    expect(print).toHaveLength(0);
  });

  it('all structural IDs route correctly', () => {
    const warnings = STRUCTURAL_IDS.map((id) => makeWarning(id));
    const { structural, aero, print } = groupWarningsByCategory(warnings);
    expect(structural).toHaveLength(STRUCTURAL_IDS.length);
    expect(aero).toHaveLength(0);
    expect(print).toHaveLength(0);
  });

  it('all print IDs route correctly', () => {
    const warnings = PRINT_IDS.map((id) => makeWarning(id));
    const { structural, aero, print } = groupWarningsByCategory(warnings);
    expect(print).toHaveLength(PRINT_IDS.length);
    expect(structural).toHaveLength(0);
    expect(aero).toHaveLength(0);
  });
});
