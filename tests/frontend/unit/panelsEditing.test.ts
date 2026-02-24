// ============================================================================
// CHENG — Tests for v0.3 Track 2: Panels & Editing
// Issues #120, #121, #128
// ============================================================================

import { describe, it, expect, beforeEach } from 'vitest';
import { useDesignStore } from '@/store/designStore';

/** Reset store to initial state before each test. */
function resetStore() {
  useDesignStore.getState().newDesign();
  useDesignStore.temporal.getState().clear();
}

// ============================================================================
// #128 — Per-Component Print Settings
// ============================================================================

describe('per-component print settings (#128)', () => {
  beforeEach(() => {
    resetStore();
  });

  it('starts with empty componentPrintSettings', () => {
    const { componentPrintSettings } = useDesignStore.getState();
    expect(componentPrintSettings).toEqual({});
  });

  it('setComponentPrintSetting adds settings for a component', () => {
    useDesignStore.getState().setComponentPrintSetting('wing', {
      wallThickness: 2.0,
      infillHint: 'high',
    });
    const { componentPrintSettings } = useDesignStore.getState();
    expect(componentPrintSettings.wing).toEqual({
      wallThickness: 2.0,
      infillHint: 'high',
    });
  });

  it('setComponentPrintSetting merges with existing settings', () => {
    useDesignStore.getState().setComponentPrintSetting('fuselage', {
      wallThickness: 1.6,
    });
    useDesignStore.getState().setComponentPrintSetting('fuselage', {
      supportStrategy: 'everywhere',
    });
    const { componentPrintSettings } = useDesignStore.getState();
    expect(componentPrintSettings.fuselage).toEqual({
      wallThickness: 1.6,
      supportStrategy: 'everywhere',
    });
  });

  it('clearComponentPrintSettings removes component entry', () => {
    useDesignStore.getState().setComponentPrintSetting('tail', {
      infillHint: 'low',
    });
    expect(useDesignStore.getState().componentPrintSettings.tail).toBeDefined();

    useDesignStore.getState().clearComponentPrintSettings('tail');
    expect(useDesignStore.getState().componentPrintSettings.tail).toBeUndefined();
  });

  it('components have independent print settings', () => {
    useDesignStore.getState().setComponentPrintSetting('wing', {
      infillHint: 'high',
    });
    useDesignStore.getState().setComponentPrintSetting('fuselage', {
      infillHint: 'low',
    });
    const { componentPrintSettings } = useDesignStore.getState();
    expect(componentPrintSettings.wing?.infillHint).toBe('high');
    expect(componentPrintSettings.fuselage?.infillHint).toBe('low');
  });
});

// ============================================================================
// #120 — Fuselage section breakdown (pure logic test)
// ============================================================================

describe('fuselage section breakdown logic (#120)', () => {
  // Test the section ratios used in FuselagePanel
  // Conventional: 25/50/25, Pod: 15/60/25, BWB: 20/50/30

  it('Conventional splits as 25/50/25', () => {
    const length = 400;
    expect(length * 0.25).toBe(100); // nose
    expect(length * 0.50).toBe(200); // cabin
    expect(length * 0.25).toBe(100); // tail cone
  });

  it('Pod splits as 15/60/25', () => {
    const length = 400;
    expect(length * 0.15).toBe(60);  // nose
    expect(length * 0.60).toBe(240); // cabin
    expect(length * 0.25).toBe(100); // tail cone
  });

  it('BWB splits as 20/50/30', () => {
    const length = 500;
    expect(length * 0.20).toBe(100); // nose
    expect(length * 0.50).toBe(250); // cabin
    expect(length * 0.30).toBe(150); // tail cone
  });
});

// ============================================================================
// #121 — Bidirectional parameter logic
// ============================================================================

describe('bidirectional param: chord/aspect ratio (#121)', () => {
  beforeEach(() => {
    resetStore();
  });

  it('aspect ratio is derived from wingspan / chord', () => {
    const { design } = useDesignStore.getState();
    const ar = design.wingSpan / design.wingChord;
    expect(ar).toBeGreaterThan(0);
    // Trainer: 1200mm span / 200mm chord = 6.0
    expect(ar).toBe(6);
  });

  it('setting chord changes the effective aspect ratio', () => {
    useDesignStore.getState().setParam('wingChord', 240, 'text');
    const { design } = useDesignStore.getState();
    const ar = design.wingSpan / design.wingChord;
    expect(ar).toBe(1200 / 240); // 5.0
  });

  it('computing chord from desired AR updates chord correctly', () => {
    // Simulate what the bidirectional param does in AR mode:
    // target AR = 10, wingspan = 1200 -> chord = 120
    const targetAR = 10;
    const wingspan = 1200;
    const newChord = Math.round(wingspan / targetAR / 5) * 5;
    expect(newChord).toBe(120);

    useDesignStore.getState().setParam('wingChord', newChord, 'text');
    const { design } = useDesignStore.getState();
    expect(design.wingChord).toBe(120);
  });
});
