// ============================================================================
// CHENG — Unit Conversion Utilities
// Issue #153 (Unit toggle: mm / inches)
// ============================================================================
//
// The backend always stores and processes values in mm.
// These utilities convert between mm and inches for UI display only.
//
// Conversion factor: 1 inch = 25.4 mm
// ============================================================================

import type { UnitSystem } from '../store/unitStore';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Exact conversion factor: millimeters per inch. */
export const MM_PER_INCH = 25.4;

// ---------------------------------------------------------------------------
// Core Conversion Functions
// ---------------------------------------------------------------------------

/** Convert millimeters to inches. */
export function mmToIn(mm: number): number {
  return mm / MM_PER_INCH;
}

/** Convert inches to millimeters. */
export function inToMm(inches: number): number {
  return inches * MM_PER_INCH;
}

// ---------------------------------------------------------------------------
// Display Helpers
// ---------------------------------------------------------------------------

/**
 * Convert a mm value for display in the given unit system.
 * Returns the value unchanged for non-mm units (deg, %, ratio, etc.)
 */
export function toDisplayUnit(valueMm: number, unitSystem: UnitSystem): number {
  if (unitSystem === 'in') {
    return mmToIn(valueMm);
  }
  return valueMm;
}

/**
 * Convert a display value back to mm for storage.
 * Returns the value unchanged for non-mm units.
 */
export function fromDisplayUnit(value: number, unitSystem: UnitSystem): number {
  if (unitSystem === 'in') {
    return inToMm(value);
  }
  return value;
}

/**
 * Get the display unit string for a given field's native unit.
 * Only mm fields are converted — deg, %, ratio etc. stay unchanged.
 */
export function getDisplayUnit(nativeUnit: string, unitSystem: UnitSystem): string {
  if (nativeUnit === 'mm' && unitSystem === 'in') {
    return 'in';
  }
  return nativeUnit;
}

// ---------------------------------------------------------------------------
// Slider Range Conversion
// ---------------------------------------------------------------------------

/**
 * Convert a slider min/max/step from mm to the display unit.
 * For non-mm fields returns values unchanged.
 *
 * Steps are rounded to reasonable precision for inches display:
 * - Steps < 1mm: keep as-is (already fine-grained)
 * - Steps >= 1mm: convert and round to 2 decimal places
 */
export function convertSliderRange(
  range: { min: number; max: number; step: number },
  nativeUnit: string,
  unitSystem: UnitSystem,
): { min: number; max: number; step: number } {
  if (nativeUnit !== 'mm' || unitSystem !== 'in') {
    return range;
  }

  const min = parseFloat(mmToIn(range.min).toFixed(4));
  const max = parseFloat(mmToIn(range.max).toFixed(4));
  // Convert step: round to 3 decimal places to keep slider usable
  const step = parseFloat(mmToIn(range.step).toFixed(3));

  return { min, max, step };
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

/**
 * Format a mm value for display in the given unit system with appropriate
 * decimal places.
 *
 * @param valueMm  The value in mm (as stored in AircraftDesign)
 * @param unitSystem  The current display unit system
 * @param decimalsMm  Decimal places when displaying in mm (default 1)
 * @param decimalsIn  Decimal places when displaying in inches (default 3)
 */
export function formatMmValue(
  valueMm: number,
  unitSystem: UnitSystem,
  decimalsMm = 1,
  decimalsIn = 3,
): string {
  if (unitSystem === 'in') {
    const inches = mmToIn(valueMm);
    return `${inches.toFixed(decimalsIn)} in`;
  }
  return `${valueMm.toFixed(decimalsMm)} mm`;
}
