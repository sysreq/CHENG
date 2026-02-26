// ============================================================================
// CHENG — usePrintBedPreferences (Issue #155)
//
// Synchronises the active design's print bed dimensions with localStorage.
//
// Behaviour:
// 1. On mount: loads saved prefs from localStorage and, if they are non-default,
//    calls the store's applyBedPreferences() action to apply them to the active
//    design without marking it as dirty.
// 2. Returns { saveAsDefault, resetToDefaults } for the UI.
//    - saveAsDefault(): saves current design bed dims to localStorage.
//    - resetToDefaults(): clears saved prefs and restores factory defaults.
//
// The store's loadPreset() and newDesign() already call loadPrintBedPrefs()
// internally, so preset loads also honour user preferences automatically.
//
// Usage: call once at App root level.
// ============================================================================

import { useEffect, useRef, useCallback } from 'react';
import { useDesignStore } from '@/store/designStore';
import {
  loadPrintBedPrefs,
  savePrintBedPrefs,
  clearPrintBedPrefs,
  BED_DEFAULTS,
  isDefaultPrintBedPrefs,
} from '@/lib/printBedPrefs';

/**
 * Manages print bed preferences persistence.
 *
 * Returns helpers used by the ExportDialog's "Save as default" button.
 */
export function usePrintBedPreferences(): {
  /** Save current design bed dims as the new user default. */
  saveAsDefault: () => void;
  /** Reset saved prefs to factory defaults and apply to current design. */
  resetToDefaults: () => void;
} {
  const applyBedPreferences = useDesignStore((s) => s.applyBedPreferences);
  const setParam = useDesignStore((s) => s.setParam);
  const design = useDesignStore((s) => s.design);

  // Ref so callbacks always see latest design without re-creating handlers.
  const designRef = useRef(design);
  useEffect(() => {
    designRef.current = design;
  });

  // ── On mount: apply saved prefs to the initial design ──────────────────────
  useEffect(() => {
    // The store's applyBedPreferences() reads localStorage and applies saved
    // bed dims without dirtying the design (no isDirty flag set).
    applyBedPreferences();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run once on mount only

  // ── saveAsDefault: persist current bed dims ─────────────────────────────────
  const saveAsDefault = useCallback(() => {
    const { printBedX, printBedY, printBedZ } = designRef.current;
    savePrintBedPrefs({ printBedX, printBedY, printBedZ });
  }, []);

  // ── resetToDefaults: clear prefs and apply factory defaults ────────────────
  const resetToDefaults = useCallback(() => {
    clearPrintBedPrefs();
    // Apply factory defaults to the current design
    setParam('printBedX', BED_DEFAULTS.printBedX, 'immediate');
    setParam('printBedY', BED_DEFAULTS.printBedY, 'immediate');
    setParam('printBedZ', BED_DEFAULTS.printBedZ, 'immediate');
  }, [setParam]);

  return {
    saveAsDefault,
    resetToDefaults,
  };
}

// Explicitly re-export the type so it can be used by the ExportDialog without
// a separate import from printBedPrefs.
export { isDefaultPrintBedPrefs, loadPrintBedPrefs };
