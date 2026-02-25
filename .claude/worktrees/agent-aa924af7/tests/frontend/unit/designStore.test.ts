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
