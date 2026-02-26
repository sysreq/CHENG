// ============================================================================
// CHENG — Print Bed Preferences (Issue #155)
//
// Persists the user's printer bed dimensions in localStorage so they survive
// across sessions and are not reset when loading presets or new designs.
//
// Design decisions:
// - Stored in localStorage (not IndexedDB) — preferences are machine-local
//   user data, not per-design. localStorage is synchronous and simpler.
// - Key: "cheng-print-bed-prefs"
// - Falls back to the CHENG defaults (220 / 220 / 250 mm) when nothing is
//   stored or the stored value is malformed.
// ============================================================================

const STORAGE_KEY = 'cheng-print-bed-prefs';

/** Default bed dimensions matching PRINT_DEFAULTS in presets.ts. */
export const BED_DEFAULTS = {
  printBedX: 220,
  printBedY: 220,
  printBedZ: 250,
} as const;

/** Minimum/maximum allowed bed dimensions (mirrors backend model constraints). */
export const BED_CONSTRAINTS = {
  printBedX: { min: 100, max: 500 },
  printBedY: { min: 100, max: 500 },
  printBedZ: { min: 50, max: 500 },
} as const;

/** Stored print bed preference values. */
export interface PrintBedPrefs {
  printBedX: number;
  printBedY: number;
  printBedZ: number;
}

/**
 * Load print bed preferences from localStorage.
 *
 * Returns the stored values if present and valid, or the defaults otherwise.
 * Never throws — storage errors are swallowed and the default is returned.
 */
export function loadPrintBedPrefs(): PrintBedPrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...BED_DEFAULTS };

    const parsed = JSON.parse(raw) as Partial<PrintBedPrefs>;

    // Validate each field; fall back to default on invalid value
    const x = _clampBed('printBedX', parsed.printBedX);
    const y = _clampBed('printBedY', parsed.printBedY);
    const z = _clampBed('printBedZ', parsed.printBedZ);

    return { printBedX: x, printBedY: y, printBedZ: z };
  } catch {
    return { ...BED_DEFAULTS };
  }
}

/**
 * Save print bed preferences to localStorage.
 *
 * Silently ignores storage errors (private browsing, quota exceeded, etc.).
 */
export function savePrintBedPrefs(prefs: PrintBedPrefs): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // Non-fatal — user can still use the app, prefs just won't persist.
  }
}

/**
 * Clear saved print bed preferences, resetting to defaults.
 *
 * Useful for tests and the "Reset to defaults" button.
 */
export function clearPrintBedPrefs(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Non-fatal
  }
}

/**
 * Return true when the given prefs match the built-in defaults exactly.
 */
export function isDefaultPrintBedPrefs(prefs: PrintBedPrefs): boolean {
  return (
    prefs.printBedX === BED_DEFAULTS.printBedX &&
    prefs.printBedY === BED_DEFAULTS.printBedY &&
    prefs.printBedZ === BED_DEFAULTS.printBedZ
  );
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function _clampBed(
  key: keyof typeof BED_CONSTRAINTS,
  value: unknown,
): number {
  const { min, max } = BED_CONSTRAINTS[key];
  const n = typeof value === 'number' ? value : NaN;
  if (Number.isNaN(n) || n < min || n > max) {
    return BED_DEFAULTS[key];
  }
  return n;
}
