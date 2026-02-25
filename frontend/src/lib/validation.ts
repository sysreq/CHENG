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
  // Structural / geometric (V01-V08) — spec §9.2
  V01: 'Very high aspect ratio relative to fuselage',
  V02: 'Aggressive taper — tip stall risk',
  V03: 'Fuselage shorter than wing chord',
  V04: 'Short tail arm — may lack pitch stability',
  V05: 'Extremely small tip chord',
  V06: 'Tail arm exceeds fuselage — tail extends past the body',
  V07: 'Nose/cabin break too close to cabin/tail break — cabin section too short',
  V08: 'Fuselage wall too thin for solid perimeters',
  // Aerodynamic / structural analysis (V09-V13) — v0.6
  V09: 'High wing bending load — consider thicker skin or shorter span',
  V10: 'Tail volume coefficient out of range — pitch or directional stability concern',
  V11: 'High aspect ratio — flutter risk for 3D-printed wings',
  V12: 'Wing loading out of typical range',
  V13: 'Stall speed too high — difficult landings',
  // 3D printing (V16-V23) — spec §9.3
  V16: 'Wall too thin for solid perimeters',
  V17: 'Wall not clean multiple of nozzle diameter',
  V18: 'Wing skin too thin for reliable FDM',
  V20: 'Enable auto-sectioning or reduce dimensions',
  V21: 'Joint overlap too short for this span',
  V22: 'Parts may be loose',
  V23: 'Parts may not fit',
  // Printability analysis (V24-V28) — v0.6
  V24: 'Wing or tail dihedral creates print overhang — may need support material',
  V25: 'Trailing edge too thin to print reliably',
  V26: 'Joint tolerance too tight for nozzle diameter or wall thickness',
  V27: 'Component exceeds bed height — cannot print upright for best finish',
  V28: 'Wing skin or fuselage wall below minimum for reliable layer adhesion',
  // Multi-section wing (V29) — v0.7
  V29: 'Multi-section wing configuration issue — check panel break positions or dihedral angles',
  // Control surfaces (V30) — v0.7
  V30: 'Control surface sizing or geometry issue',
  // Landing gear (V31) — v0.7
  V31: 'Landing gear configuration issue — check gear position, height, or track width',
  // Tail arm clamping (V32) — v0.7.x
  V32: 'Tail arm places tail surfaces beyond fuselage end — increase fuselage length or reduce tail arm',
};

// ---------------------------------------------------------------------------
// Structural vs Print Warning Classification
// ---------------------------------------------------------------------------

const STRUCTURAL_IDS: Set<string> = new Set([
  // Geometric / structural (V01-V08)
  'V01', 'V02', 'V03', 'V04', 'V05', 'V06', 'V07', 'V08',
  // Multi-section wing (V29)
  'V29',
  // Control surfaces (V30)
  'V30',
  // Landing gear (V31)
  'V31',
  // Tail arm clamping (V32)
  'V32',
]);

const AERO_IDS: Set<string> = new Set([
  // Aerodynamic / structural analysis (V09-V13)
  'V09', 'V10', 'V11', 'V12', 'V13',
]);

const PRINT_IDS: Set<string> = new Set([
  // 3D printing (V16-V23)
  'V16', 'V17', 'V18', 'V20', 'V21', 'V22', 'V23',
  // Printability analysis (V24-V28)
  'V24', 'V25', 'V26', 'V27', 'V28',
]);

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
 * Group warnings into structural, aero, and print categories.
 *
 * structural: V01-V08 geometric/structural + V29 multi-section wing
 *             + V30 control surfaces + V31 landing gear + V32 tail arm
 * aero:       V09-V13 aerodynamic / structural analysis
 * print:      V16-V23 3D printing + V24-V28 printability analysis
 *
 * Warnings with unrecognised IDs default to the structural bucket so they
 * are never silently dropped from the UI.
 */
export function groupWarningsByCategory(
  warnings: ValidationWarning[],
): { structural: ValidationWarning[]; aero: ValidationWarning[]; print: ValidationWarning[] } {
  const structural: ValidationWarning[] = [];
  const aero: ValidationWarning[] = [];
  const print: ValidationWarning[] = [];

  for (const w of warnings) {
    if (STRUCTURAL_IDS.has(w.id)) {
      structural.push(w);
    } else if (AERO_IDS.has(w.id)) {
      aero.push(w);
    } else if (PRINT_IDS.has(w.id)) {
      print.push(w);
    } else {
      // Unknown category — default to structural so warnings are never dropped
      structural.push(w);
    }
  }

  return { structural, aero, print };
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
