// ============================================================================
// CHENG — Validation Warning Utilities
// ============================================================================

import type { ValidationWarning } from '../types/design';

// ---------------------------------------------------------------------------
// Warning Severity Colors (Tailwind classes)
// ---------------------------------------------------------------------------

/** All MVP warnings are 'warn' level — mapped to amber/yellow. */
export const WARNING_COLORS = {
  warn: {
    bg: 'bg-amber-900/30',
    border: 'border-amber-500/50',
    text: 'text-amber-400',
    badge: 'bg-amber-600',
    icon: 'text-amber-400',
  },
} as const;

// ---------------------------------------------------------------------------
// Warning ID Descriptions
// ---------------------------------------------------------------------------

export const WARNING_DESCRIPTIONS: Record<string, string> = {
  V01: 'Wing aspect ratio too high — risk of flutter',
  V02: 'Wing loading exceeds recommendation',
  V03: 'CG position outside safe range',
  V04: 'Tail volume coefficient too low',
  V05: 'Control surface authority insufficient',
  V06: 'Structural stress margin low',
  V16: 'Part exceeds print bed — auto-section recommended',
  V17: 'Wall thickness below minimum printable',
  V18: 'Overhang angle exceeds printer capability',
  V20: 'Joint overlap too small for reliable bonding',
  V21: 'Trailing edge below min thickness',
  V22: 'Nozzle diameter incompatible with feature size',
  V23: 'Hollow sections may need internal supports',
};

// ---------------------------------------------------------------------------
// Structural vs Print Warning Classification
// ---------------------------------------------------------------------------

const STRUCTURAL_IDS: Set<string> = new Set(['V01', 'V02', 'V03', 'V04', 'V05', 'V06']);
const PRINT_IDS: Set<string> = new Set(['V16', 'V17', 'V18', 'V20', 'V21', 'V22', 'V23']);

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Format a validation warning for display.
 * Returns e.g. "[V01] Wing aspect ratio too high — risk of flutter"
 */
export function formatWarning(warning: ValidationWarning): string {
  return `[${warning.id}] ${warning.message}`;
}

/**
 * Get a human-readable badge string for warning count.
 * Returns e.g. "3 warnings", "1 warning", or "" for zero.
 */
export function getWarningCountBadge(warnings: ValidationWarning[]): string {
  const count = warnings.length;
  if (count === 0) return '';
  return count === 1 ? '1 warning' : `${count} warnings`;
}

/**
 * Group warnings into structural and print categories.
 */
export function groupWarningsByCategory(
  warnings: ValidationWarning[],
): { structural: ValidationWarning[]; print: ValidationWarning[] } {
  const structural: ValidationWarning[] = [];
  const print: ValidationWarning[] = [];

  for (const w of warnings) {
    if (STRUCTURAL_IDS.has(w.id)) {
      structural.push(w);
    } else if (PRINT_IDS.has(w.id)) {
      print.push(w);
    } else {
      // Unknown category — default to structural
      structural.push(w);
    }
  }

  return { structural, print };
}

/**
 * Check if a specific field has any associated warnings.
 */
export function fieldHasWarning(
  warnings: ValidationWarning[],
  fieldName: string,
): boolean {
  return warnings.some((w) => w.fields.includes(fieldName));
}

/**
 * Get all warnings associated with a specific field.
 */
export function getFieldWarnings(
  warnings: ValidationWarning[],
  fieldName: string,
): ValidationWarning[] {
  return warnings.filter((w) => w.fields.includes(fieldName));
}
