// ============================================================================
// CHENG — Print Bed Preferences integration tests (Issue #155)
//
// Tests the interaction between printBedPrefs.ts and the designStore.
// ============================================================================

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useDesignStore } from '@/store/designStore';
import {
  savePrintBedPrefs,
  clearPrintBedPrefs,
  BED_DEFAULTS,
} from '@/lib/printBedPrefs';

// ---------------------------------------------------------------------------
// localStorage mock (same pattern as printBedPrefs.test.ts)
// ---------------------------------------------------------------------------

let _store: Record<string, string> = {};

const mockLocalStorage = {
  getItem: (key: string) => _store[key] ?? null,
  setItem: (key: string, value: string) => { _store[key] = value; },
  removeItem: (key: string) => { delete _store[key]; },
  clear: () => { _store = {}; },
};

// ---------------------------------------------------------------------------
// Reset helpers
// ---------------------------------------------------------------------------

function resetStore(): void {
  useDesignStore.getState().newDesign();
  useDesignStore.temporal.getState().clear();
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  _store = {};
  vi.stubGlobal('localStorage', mockLocalStorage);
  resetStore();
});

// ---------------------------------------------------------------------------
// applyBedPreferences
// ---------------------------------------------------------------------------

describe('designStore.applyBedPreferences', () => {
  it('does not change bed dims when no prefs are saved (default prefs)', () => {
    // No saved prefs — defaults should remain
    const before = useDesignStore.getState().design;
    useDesignStore.getState().applyBedPreferences();
    const after = useDesignStore.getState().design;

    expect(after.printBedX).toBe(before.printBedX);
    expect(after.printBedY).toBe(before.printBedY);
    expect(after.printBedZ).toBe(before.printBedZ);
  });

  it('applies non-default saved prefs to the active design', () => {
    // Save custom prefs
    savePrintBedPrefs({ printBedX: 300, printBedY: 310, printBedZ: 400 });

    useDesignStore.getState().applyBedPreferences();
    const { design } = useDesignStore.getState();

    expect(design.printBedX).toBe(300);
    expect(design.printBedY).toBe(310);
    expect(design.printBedZ).toBe(400);
  });

  it('does not mark design as dirty when applying prefs', () => {
    savePrintBedPrefs({ printBedX: 350, printBedY: 350, printBedZ: 350 });
    useDesignStore.getState().applyBedPreferences();

    // isDirty should NOT be set — bed prefs are not user design edits
    expect(useDesignStore.getState().isDirty).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// loadPreset + bed prefs
// ---------------------------------------------------------------------------

describe('designStore.loadPreset with saved bed prefs', () => {
  it('preserves saved custom bed dims when loading a preset', () => {
    // Save custom prefs
    savePrintBedPrefs({ printBedX: 350, printBedY: 350, printBedZ: 300 });

    // Load a different preset
    useDesignStore.getState().loadPreset('Sport');
    const { design } = useDesignStore.getState();

    // Bed dims should be the saved prefs, not the preset's defaults
    expect(design.printBedX).toBe(350);
    expect(design.printBedY).toBe(350);
    expect(design.printBedZ).toBe(300);
  });

  it('uses preset defaults when no custom prefs are saved', () => {
    // No saved prefs
    clearPrintBedPrefs();

    useDesignStore.getState().loadPreset('Aerobatic');
    const { design } = useDesignStore.getState();

    // Should use the preset's (factory) defaults
    expect(design.printBedX).toBe(BED_DEFAULTS.printBedX);
    expect(design.printBedY).toBe(BED_DEFAULTS.printBedY);
    expect(design.printBedZ).toBe(BED_DEFAULTS.printBedZ);
  });
});

// ---------------------------------------------------------------------------
// newDesign + bed prefs
// ---------------------------------------------------------------------------

describe('designStore.newDesign with saved bed prefs', () => {
  it('applies saved bed prefs to new designs', () => {
    savePrintBedPrefs({ printBedX: 400, printBedY: 400, printBedZ: 450 });

    useDesignStore.getState().newDesign();
    const { design } = useDesignStore.getState();

    expect(design.printBedX).toBe(400);
    expect(design.printBedY).toBe(400);
    expect(design.printBedZ).toBe(450);
  });

  it('uses factory defaults for new designs when no prefs are saved', () => {
    clearPrintBedPrefs();

    useDesignStore.getState().newDesign();
    const { design } = useDesignStore.getState();

    expect(design.printBedX).toBe(BED_DEFAULTS.printBedX);
    expect(design.printBedY).toBe(BED_DEFAULTS.printBedY);
    expect(design.printBedZ).toBe(BED_DEFAULTS.printBedZ);
  });
});
