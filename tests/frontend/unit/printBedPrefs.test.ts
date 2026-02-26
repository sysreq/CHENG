// ============================================================================
// CHENG — Print Bed Preferences unit tests (Issue #155)
// ============================================================================

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  loadPrintBedPrefs,
  savePrintBedPrefs,
  clearPrintBedPrefs,
  isDefaultPrintBedPrefs,
  BED_DEFAULTS,
  type PrintBedPrefs,
} from '@/lib/printBedPrefs';

// ---------------------------------------------------------------------------
// localStorage mock helpers
// ---------------------------------------------------------------------------

/** Minimal synchronous localStorage mock for jsdom. */
let _store: Record<string, string> = {};

const mockLocalStorage = {
  getItem: (key: string) => _store[key] ?? null,
  setItem: (key: string, value: string) => { _store[key] = value; },
  removeItem: (key: string) => { delete _store[key]; },
  clear: () => { _store = {}; },
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  _store = {};
  vi.stubGlobal('localStorage', mockLocalStorage);
});

// ---------------------------------------------------------------------------
// BED_DEFAULTS
// ---------------------------------------------------------------------------

describe('BED_DEFAULTS', () => {
  it('has the expected factory values', () => {
    expect(BED_DEFAULTS.printBedX).toBe(220);
    expect(BED_DEFAULTS.printBedY).toBe(220);
    expect(BED_DEFAULTS.printBedZ).toBe(250);
  });
});

// ---------------------------------------------------------------------------
// loadPrintBedPrefs
// ---------------------------------------------------------------------------

describe('loadPrintBedPrefs', () => {
  it('returns defaults when nothing is stored', () => {
    const prefs = loadPrintBedPrefs();
    expect(prefs).toEqual(BED_DEFAULTS);
  });

  it('returns stored values when valid prefs are present', () => {
    const stored: PrintBedPrefs = { printBedX: 300, printBedY: 310, printBedZ: 350 };
    mockLocalStorage.setItem('cheng-print-bed-prefs', JSON.stringify(stored));

    const prefs = loadPrintBedPrefs();
    expect(prefs.printBedX).toBe(300);
    expect(prefs.printBedY).toBe(310);
    expect(prefs.printBedZ).toBe(350);
  });

  it('clamps out-of-range X value to default', () => {
    mockLocalStorage.setItem(
      'cheng-print-bed-prefs',
      JSON.stringify({ printBedX: 50, printBedY: 220, printBedZ: 250 }),
    );
    const prefs = loadPrintBedPrefs();
    // 50 < 100 (min) -> falls back to default
    expect(prefs.printBedX).toBe(220);
  });

  it('clamps out-of-range Y value to default', () => {
    mockLocalStorage.setItem(
      'cheng-print-bed-prefs',
      JSON.stringify({ printBedX: 220, printBedY: 9999, printBedZ: 250 }),
    );
    const prefs = loadPrintBedPrefs();
    // 9999 > 500 (max) -> falls back to default
    expect(prefs.printBedY).toBe(220);
  });

  it('clamps out-of-range Z value to default', () => {
    mockLocalStorage.setItem(
      'cheng-print-bed-prefs',
      JSON.stringify({ printBedX: 220, printBedY: 220, printBedZ: 10 }),
    );
    const prefs = loadPrintBedPrefs();
    // 10 < 50 (min) -> falls back to default
    expect(prefs.printBedZ).toBe(250);
  });

  it('falls back to defaults when JSON is malformed', () => {
    mockLocalStorage.setItem('cheng-print-bed-prefs', 'not valid json {');
    const prefs = loadPrintBedPrefs();
    expect(prefs).toEqual(BED_DEFAULTS);
  });

  it('falls back to defaults when stored value is null/missing fields', () => {
    mockLocalStorage.setItem('cheng-print-bed-prefs', JSON.stringify({}));
    const prefs = loadPrintBedPrefs();
    expect(prefs).toEqual(BED_DEFAULTS);
  });

  it('does not throw when localStorage throws', () => {
    const throwingStorage = {
      ...mockLocalStorage,
      getItem: () => { throw new Error('Storage blocked'); },
    };
    vi.stubGlobal('localStorage', throwingStorage);
    expect(() => loadPrintBedPrefs()).not.toThrow();
    expect(loadPrintBedPrefs()).toEqual(BED_DEFAULTS);
  });
});

// ---------------------------------------------------------------------------
// savePrintBedPrefs
// ---------------------------------------------------------------------------

describe('savePrintBedPrefs', () => {
  it('stores prefs in localStorage', () => {
    savePrintBedPrefs({ printBedX: 400, printBedY: 400, printBedZ: 400 });
    const raw = mockLocalStorage.getItem('cheng-print-bed-prefs');
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!) as PrintBedPrefs;
    expect(parsed.printBedX).toBe(400);
    expect(parsed.printBedY).toBe(400);
    expect(parsed.printBedZ).toBe(400);
  });

  it('overwrites previously stored prefs', () => {
    savePrintBedPrefs({ printBedX: 300, printBedY: 300, printBedZ: 300 });
    savePrintBedPrefs({ printBedX: 250, printBedY: 260, printBedZ: 270 });
    const prefs = loadPrintBedPrefs();
    expect(prefs.printBedX).toBe(250);
    expect(prefs.printBedY).toBe(260);
    expect(prefs.printBedZ).toBe(270);
  });

  it('does not throw when localStorage is unavailable', () => {
    const throwingStorage = {
      ...mockLocalStorage,
      setItem: () => { throw new Error('Storage blocked'); },
    };
    vi.stubGlobal('localStorage', throwingStorage);
    expect(() =>
      savePrintBedPrefs({ printBedX: 300, printBedY: 300, printBedZ: 300 }),
    ).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// clearPrintBedPrefs
// ---------------------------------------------------------------------------

describe('clearPrintBedPrefs', () => {
  it('removes stored prefs so next load returns defaults', () => {
    savePrintBedPrefs({ printBedX: 350, printBedY: 350, printBedZ: 350 });
    clearPrintBedPrefs();
    expect(loadPrintBedPrefs()).toEqual(BED_DEFAULTS);
  });

  it('does not throw when nothing is stored', () => {
    expect(() => clearPrintBedPrefs()).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// isDefaultPrintBedPrefs
// ---------------------------------------------------------------------------

describe('isDefaultPrintBedPrefs', () => {
  it('returns true for factory defaults', () => {
    expect(isDefaultPrintBedPrefs({ ...BED_DEFAULTS })).toBe(true);
  });

  it('returns false when any dimension differs', () => {
    expect(isDefaultPrintBedPrefs({ printBedX: 300, printBedY: 220, printBedZ: 250 })).toBe(false);
    expect(isDefaultPrintBedPrefs({ printBedX: 220, printBedY: 300, printBedZ: 250 })).toBe(false);
    expect(isDefaultPrintBedPrefs({ printBedX: 220, printBedY: 220, printBedZ: 300 })).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Round-trip: save then load
// ---------------------------------------------------------------------------

describe('round-trip', () => {
  it('save + load returns identical values', () => {
    const original: PrintBedPrefs = { printBedX: 180, printBedY: 220, printBedZ: 500 };
    savePrintBedPrefs(original);
    const loaded = loadPrintBedPrefs();
    expect(loaded).toEqual(original);
  });
});
