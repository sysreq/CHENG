// ============================================================================
// CHENG — IndexedDB persistence layer unit tests (#150)
//
// Uses fake-indexeddb to test the IDB helpers without a real browser.
// ============================================================================

import { describe, it, expect, beforeEach, vi } from 'vitest';

// Polyfill IndexedDB with fake-indexeddb before importing the module under test.
// The 'auto' entry point patches the global scope (globalThis.indexedDB etc.)
import 'fake-indexeddb/auto';

import {
  idbSaveDesign,
  idbLoadAutosave,
  idbLoadDesign,
  idbDeleteDesign,
  idbListDesigns,
  idbEstimateUsageBytes,
  idbClear,
  debounce,
  _resetDbForTesting,
} from '@/lib/indexeddb';

// ── Helper: sample design ────────────────────────────────────────────────────

function makeDesign(id: string, name = 'Test Design') {
  return { id, name, wingSpan: 1200, version: '0.1.0' };
}

// ── Reset IDB between tests ──────────────────────────────────────────────────

beforeEach(async () => {
  _resetDbForTesting();
  await idbClear();
});

// ---------------------------------------------------------------------------
// idbSaveDesign + idbLoadDesign
// ---------------------------------------------------------------------------

describe('idbSaveDesign / idbLoadDesign', () => {
  it('saves and loads a design by id', async () => {
    const design = makeDesign('d1');
    await idbSaveDesign(design);
    const loaded = await idbLoadDesign('d1');
    expect(loaded).toEqual(design);
  });

  it('overwrites an existing design', async () => {
    await idbSaveDesign(makeDesign('d1', 'Original'));
    await idbSaveDesign(makeDesign('d1', 'Updated'));
    const loaded = await idbLoadDesign('d1');
    expect((loaded as { name: string }).name).toBe('Updated');
  });

  it('returns null for a missing design id', async () => {
    const result = await idbLoadDesign('nonexistent');
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// idbLoadAutosave
// ---------------------------------------------------------------------------

describe('idbLoadAutosave', () => {
  it('returns null when nothing has been saved', async () => {
    const result = await idbLoadAutosave();
    expect(result).toBeNull();
  });

  it('returns the last-saved design', async () => {
    const design = makeDesign('auto-1');
    await idbSaveDesign(design);
    const loaded = await idbLoadAutosave();
    expect(loaded).toEqual(design);
  });

  it('returns the most recently saved design when multiple saved', async () => {
    await idbSaveDesign(makeDesign('a', 'First'));
    await idbSaveDesign(makeDesign('b', 'Second'));
    const loaded = await idbLoadAutosave<{ name: string }>();
    // Autosave always mirrors the last save call
    expect(loaded?.name).toBe('Second');
  });
});

// ---------------------------------------------------------------------------
// idbDeleteDesign
// ---------------------------------------------------------------------------

describe('idbDeleteDesign', () => {
  it('deletes an existing design', async () => {
    await idbSaveDesign(makeDesign('del-1'));
    await idbDeleteDesign('del-1');
    const loaded = await idbLoadDesign('del-1');
    expect(loaded).toBeNull();
  });

  it('does not throw when deleting a non-existent key', async () => {
    await expect(idbDeleteDesign('ghost')).resolves.toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// idbListDesigns
// ---------------------------------------------------------------------------

describe('idbListDesigns', () => {
  it('returns an empty array when no designs are stored', async () => {
    const list = await idbListDesigns();
    expect(list).toEqual([]);
  });

  it('lists all stored designs (excluding autosave slot)', async () => {
    await idbSaveDesign(makeDesign('x'));
    await idbSaveDesign(makeDesign('y'));
    const list = await idbListDesigns<{ id: string }>();
    const keys = list.map((e) => e.key);
    expect(keys).toContain('x');
    expect(keys).toContain('y');
    expect(keys).not.toContain('__autosave__');
  });

  it('data field matches the original design', async () => {
    const design = makeDesign('list-d1', 'Listed');
    await idbSaveDesign(design);
    const list = await idbListDesigns<typeof design>();
    expect(list[0].data).toEqual(design);
  });
});

// ---------------------------------------------------------------------------
// idbEstimateUsageBytes
// ---------------------------------------------------------------------------

describe('idbEstimateUsageBytes', () => {
  it('returns a non-negative number', async () => {
    const bytes = await idbEstimateUsageBytes();
    expect(typeof bytes).toBe('number');
    expect(bytes).toBeGreaterThanOrEqual(0);
  });

  it('returns a non-negative number after saving data', async () => {
    await idbSaveDesign(makeDesign('size-test'));
    const bytes = await idbEstimateUsageBytes();
    expect(bytes).toBeGreaterThanOrEqual(0);
  });
});

// ---------------------------------------------------------------------------
// idbClear
// ---------------------------------------------------------------------------

describe('idbClear', () => {
  it('removes all records', async () => {
    await idbSaveDesign(makeDesign('c1'));
    await idbSaveDesign(makeDesign('c2'));
    await idbClear();
    expect(await idbListDesigns()).toEqual([]);
    expect(await idbLoadAutosave()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// debounce utility
// ---------------------------------------------------------------------------

describe('debounce', () => {
  it('calls the function after the delay', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 200);
    debounced();
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(200);
    expect(fn).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it('only calls once for rapid successive calls', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 300);
    debounced();
    debounced();
    debounced();
    vi.advanceTimersByTime(300);
    expect(fn).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});
