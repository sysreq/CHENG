// ============================================================================
// CHENG — Client-Side Validation Helpers (Stub)
// Track D: Frontend Panels will implement the full version.
// ============================================================================

import type { ValidationWarning, WarningId } from '@/types/design';

/**
 * Get warnings affecting a specific field.
 * Used by parameter panels to show warning icons next to fields.
 */
export function getWarningsForField(
  warnings: ValidationWarning[],
  fieldName: string,
): ValidationWarning[] {
  return warnings.filter((w) => w.fields.includes(fieldName));
}

/**
 * Check if a specific warning ID is present in the warnings list.
 */
export function hasWarning(
  warnings: ValidationWarning[],
  id: WarningId,
): boolean {
  return warnings.some((w) => w.id === id);
}

/**
 * Clamp a numeric value to the specified range.
 * Used by parameter inputs to enforce min/max constraints.
 */
export function clampValue(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
