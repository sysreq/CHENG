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
} from '@/lib/validation';
import type { ValidationWarning } from '@/types/design';

const makeWarning = (id: string, fields: string[] = []): ValidationWarning => ({
  id: id as ValidationWarning['id'],
  level: 'warn',
  message: `Warning ${id}`,
  fields,
});

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
