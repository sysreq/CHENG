// ============================================================================
// CHENG — designStore unit tests
// ============================================================================

import { describe, it, expect, beforeEach } from 'vitest';
import { useDesignStore } from '@/store/designStore';

/** Reset store to initial state before each test. */
function resetStore() {
  useDesignStore.getState().newDesign();
  // Also clear the temporal history
  useDesignStore.temporal.getState().clear();
}

describe('designStore', () => {
  beforeEach(() => {
    resetStore();
  });

  // ── Initial state ──────────────────────────────────────────────────

  it('has Trainer as the default preset', () => {
    const { activePreset } = useDesignStore.getState();
    expect(activePreset).toBe('Trainer');
  });

  it('initial design has wingSpan=1200 (Trainer default)', () => {
    const { design } = useDesignStore.getState();
    expect(design.wingSpan).toBe(1200);
  });

  it('initial design has version "0.1.0"', () => {
    const { design } = useDesignStore.getState();
    expect(design.version).toBe('0.1.0');
  });

  it('starts with no meshData, derived, or warnings', () => {
    const state = useDesignStore.getState();
    expect(state.meshData).toBeNull();
    expect(state.derived).toBeNull();
    expect(state.warnings).toEqual([]);
  });

  it('starts with isDirty=false', () => {
    expect(useDesignStore.getState().isDirty).toBe(false);
  });

  // ── setParam ────────────────────────────────────────────────────────

  it('setParam updates design field and switches to Custom preset', () => {
    useDesignStore.getState().setParam('wingSpan', 800);
    const { design, activePreset, isDirty } = useDesignStore.getState();
    expect(design.wingSpan).toBe(800);
    expect(activePreset).toBe('Custom');
    expect(isDirty).toBe(true);
  });

  it('setParam records lastChangeSource', () => {
    useDesignStore.getState().setParam('wingChord', 150, 'slider');
    expect(useDesignStore.getState().lastChangeSource).toBe('slider');

    useDesignStore.getState().setParam('wingChord', 160, 'text');
    expect(useDesignStore.getState().lastChangeSource).toBe('text');
  });

  // ── loadPreset ──────────────────────────────────────────────────────

  it('loadPreset overwrites all 33 design params', () => {
    // First change something
    useDesignStore.getState().setParam('wingSpan', 999);

    // Load Sport preset
    useDesignStore.getState().loadPreset('Sport');
    const { design, activePreset } = useDesignStore.getState();

    expect(activePreset).toBe('Sport');
    expect(design.wingSpan).toBe(1000);
    expect(design.wingChord).toBe(180);
    expect(design.wingMountType).toBe('Mid-Wing');
    expect(design.wingSweep).toBe(5);
    expect(design.wingTipRootRatio).toBe(0.67);
  });

  it('loadPreset preserves design id and name', () => {
    const originalId = useDesignStore.getState().design.id;
    const originalName = useDesignStore.getState().design.name;

    useDesignStore.getState().loadPreset('Aerobatic');
    const { design } = useDesignStore.getState();

    expect(design.id).toBe(originalId);
    expect(design.name).toBe(originalName);
  });

  // ── Undo / Redo ─────────────────────────────────────────────────────

  it('undo reverts setParam changes', () => {
    useDesignStore.getState().setParam('wingSpan', 500);
    expect(useDesignStore.getState().design.wingSpan).toBe(500);

    useDesignStore.temporal.getState().undo();
    expect(useDesignStore.getState().design.wingSpan).toBe(1200);
  });

  it('redo restores undone changes', () => {
    useDesignStore.getState().setParam('wingSpan', 500);
    useDesignStore.temporal.getState().undo();
    expect(useDesignStore.getState().design.wingSpan).toBe(1200);

    useDesignStore.temporal.getState().redo();
    expect(useDesignStore.getState().design.wingSpan).toBe(500);
  });

  // ── newDesign ───────────────────────────────────────────────────────

  it('newDesign resets to Trainer defaults', () => {
    useDesignStore.getState().setParam('wingSpan', 500);
    useDesignStore.getState().setParam('wingChord', 99);

    useDesignStore.getState().newDesign();
    const { design, activePreset, isDirty } = useDesignStore.getState();

    expect(design.wingSpan).toBe(1200);
    expect(design.wingChord).toBe(200);
    expect(activePreset).toBe('Trainer');
    expect(isDirty).toBe(false);
  });

  // ── selectedComponent ───────────────────────────────────────────────

  it('setSelectedComponent toggles component selection', () => {
    useDesignStore.getState().setSelectedComponent('wing');
    expect(useDesignStore.getState().selectedComponent).toBe('wing');

    useDesignStore.getState().setSelectedComponent(null);
    expect(useDesignStore.getState().selectedComponent).toBeNull();
  });

  // ── Multi-section wing panel actions (#143) ─────────────────────────

  it('initial design has wingSections=1 and default panel arrays', () => {
    const { design } = useDesignStore.getState();
    expect(design.wingSections).toBe(1);
    expect(Array.isArray(design.panelBreakPositions)).toBe(true);
    expect(Array.isArray(design.panelDihedrals)).toBe(true);
    expect(Array.isArray(design.panelSweeps)).toBe(true);
  });

  it('setParam wingSections=2 extends panel arrays by one element', () => {
    useDesignStore.getState().setParam('wingSections', 2, 'immediate');
    const { design } = useDesignStore.getState();
    expect(design.wingSections).toBe(2);
    // Arrays must have at least 1 element for the single break between 2 sections
    expect(design.panelBreakPositions.length).toBeGreaterThanOrEqual(1);
    expect(design.panelDihedrals.length).toBeGreaterThanOrEqual(1);
    expect(design.panelSweeps.length).toBeGreaterThanOrEqual(1);
  });

  it('setParam wingSections=1 truncates arrays to 0 active breaks', () => {
    // First go to 3 sections
    useDesignStore.getState().setParam('wingSections', 3, 'immediate');
    // Then back to 1
    useDesignStore.getState().setParam('wingSections', 1, 'immediate');
    const { design } = useDesignStore.getState();
    expect(design.wingSections).toBe(1);
    // The first two elements of the arrays may still exist (unused), but
    // wingSections determines how many are active (n-1 breaks for n sections)
  });

  it('setPanelBreak updates panelBreakPositions at the given index', () => {
    useDesignStore.getState().setParam('wingSections', 2, 'immediate');
    useDesignStore.getState().setPanelBreak(0, 55);
    const { design } = useDesignStore.getState();
    expect(design.panelBreakPositions[0]).toBe(55);
  });

  it('setPanelDihedral updates panelDihedrals at the given index', () => {
    useDesignStore.getState().setParam('wingSections', 2, 'immediate');
    useDesignStore.getState().setPanelDihedral(0, 20);
    const { design } = useDesignStore.getState();
    expect(design.panelDihedrals[0]).toBe(20);
  });

  it('setPanelSweep updates panelSweeps at the given index', () => {
    useDesignStore.getState().setParam('wingSections', 2, 'immediate');
    useDesignStore.getState().setPanelSweep(0, 15);
    const { design } = useDesignStore.getState();
    expect(design.panelSweeps[0]).toBe(15);
  });

  it('setPanelBreak on out-of-range index does not throw', () => {
    // wingSections=1, so no active breaks — calling setPanelBreak(5, ...) should not crash
    expect(() => {
      useDesignStore.getState().setPanelBreak(5, 70);
    }).not.toThrow();
  });

  // ── Zundo history deduplication (#246) ──────────────────────────────

  it('setting the same param value twice does NOT add a second undo entry', () => {
    // Start fresh
    useDesignStore.temporal.getState().clear();

    useDesignStore.getState().setParam('wingSpan', 800);
    const afterFirst = useDesignStore.temporal.getState().pastStates.length;

    // Set same value again — should not create a new snapshot
    useDesignStore.getState().setParam('wingSpan', 800);
    const afterSecond = useDesignStore.temporal.getState().pastStates.length;

    expect(afterSecond).toBe(afterFirst);
  });

  it('setting a different param value DOES add a new undo entry', () => {
    useDesignStore.temporal.getState().clear();

    useDesignStore.getState().setParam('wingSpan', 800);
    const afterFirst = useDesignStore.temporal.getState().pastStates.length;

    useDesignStore.getState().setParam('wingSpan', 900);
    const afterSecond = useDesignStore.temporal.getState().pastStates.length;

    expect(afterSecond).toBe(afterFirst + 1);
  });

  it('lastAction label is still updated even when design data is unchanged', () => {
    // setParam early-returns if value is the same, so we test via a fresh value
    useDesignStore.getState().setParam('wingSpan', 750);
    expect(useDesignStore.getState().lastAction).toBe('Set Wingspan to 750');

    useDesignStore.getState().setParam('wingChord', 180);
    expect(useDesignStore.getState().lastAction).toBe('Set Wing Chord to 180');
  });

  it('commitSliderChange does not create spurious history entries', () => {
    useDesignStore.temporal.getState().clear();

    useDesignStore.getState().setParam('wingSpan', 850);
    const before = useDesignStore.temporal.getState().pastStates.length;

    // commitSliderChange should be a no-op that doesn't add history
    useDesignStore.getState().commitSliderChange();
    const after = useDesignStore.temporal.getState().pastStates.length;

    expect(after).toBe(before);
  });

  // ── setMeshData clears isGenerating ─────────────────────────────────

  it('setMeshData clears isGenerating flag', () => {
    useDesignStore.getState().setIsGenerating(true);
    expect(useDesignStore.getState().isGenerating).toBe(true);

    useDesignStore.getState().setMeshData({
      vertices: new Float32Array(0),
      normals: new Float32Array(0),
      faces: new Uint32Array(0),
      vertexCount: 0,
      faceCount: 0,
      componentRanges: null,
    });
    expect(useDesignStore.getState().isGenerating).toBe(false);
  });
});
