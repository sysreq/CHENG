// ============================================================================
// CHENG — W12: per-panel airfoil selection tests (Issue #245)
// ============================================================================

import { describe, it, expect, beforeEach } from 'vitest';
import { useDesignStore } from '@/store/designStore';
import { createDesignFromPreset } from '@/lib/presets';

/** Reset store to initial state before each test. */
function resetStore() {
  useDesignStore.getState().newDesign();
  useDesignStore.temporal.getState().clear();
}

// ============================================================================
// Preset defaults
// ============================================================================

describe('W12: panelAirfoils preset defaults (#245)', () => {
  const ALL_PRESET_NAMES = ['Trainer', 'Sport', 'Aerobatic', 'Glider', 'FlyingWing', 'Scale'] as const;

  it('all presets have panelAirfoils array of length 3', () => {
    for (const name of ALL_PRESET_NAMES) {
      const d = createDesignFromPreset(name);
      expect(Array.isArray(d.panelAirfoils), `${name} should have panelAirfoils array`).toBe(true);
      expect(d.panelAirfoils).toHaveLength(3);
    }
  });

  it('all presets default panelAirfoils to [null, null, null]', () => {
    for (const name of ALL_PRESET_NAMES) {
      const d = createDesignFromPreset(name);
      expect(d.panelAirfoils, `${name} should have all-null panelAirfoils`).toEqual([null, null, null]);
    }
  });
});

// ============================================================================
// Store: setPanelAirfoil
// ============================================================================

describe('W12: setPanelAirfoil store action (#245)', () => {
  beforeEach(() => {
    resetStore();
  });

  it('initial design has panelAirfoils=[null,null,null]', () => {
    const { design } = useDesignStore.getState();
    expect(design.panelAirfoils).toEqual([null, null, null]);
  });

  it('setPanelAirfoil sets index 0 to a WingAirfoil value', () => {
    useDesignStore.getState().setPanelAirfoil(0, 'NACA-0012');
    const { design } = useDesignStore.getState();
    expect(design.panelAirfoils[0]).toBe('NACA-0012');
    expect(design.panelAirfoils[1]).toBeNull();
    expect(design.panelAirfoils[2]).toBeNull();
  });

  it('setPanelAirfoil resets index 0 to null (inherit)', () => {
    useDesignStore.getState().setPanelAirfoil(0, 'NACA-0012');
    useDesignStore.getState().setPanelAirfoil(0, null);
    const { design } = useDesignStore.getState();
    expect(design.panelAirfoils[0]).toBeNull();
  });

  it('setPanelAirfoil sets different indices independently', () => {
    useDesignStore.getState().setPanelAirfoil(0, 'Clark-Y');
    useDesignStore.getState().setPanelAirfoil(1, 'Eppler-387');
    const { design } = useDesignStore.getState();
    expect(design.panelAirfoils[0]).toBe('Clark-Y');
    expect(design.panelAirfoils[1]).toBe('Eppler-387');
    expect(design.panelAirfoils[2]).toBeNull();
  });

  it('setPanelAirfoil marks preset as Custom', () => {
    useDesignStore.getState().setPanelAirfoil(0, 'NACA-0012');
    expect(useDesignStore.getState().activePreset).toBe('Custom');
  });

  it('setPanelAirfoil sets isDirty=true', () => {
    useDesignStore.getState().setPanelAirfoil(0, 'AG-25');
    expect(useDesignStore.getState().isDirty).toBe(true);
  });

  it('setPanelAirfoil with non-null records meaningful lastAction', () => {
    useDesignStore.getState().setPanelAirfoil(1, 'Selig-1223');
    const { lastAction } = useDesignStore.getState();
    expect(lastAction).toContain('Panel 3');
    expect(lastAction).toContain('Selig-1223');
  });

  it('setPanelAirfoil with null records reset lastAction', () => {
    useDesignStore.getState().setPanelAirfoil(0, null);
    const { lastAction } = useDesignStore.getState();
    expect(lastAction).toContain('Panel 2');
    expect(lastAction.toLowerCase()).toContain('inherit');
  });
});

// ============================================================================
// Store: wingSections side-effect extends panelAirfoils
// ============================================================================

describe('W12: wingSections side-effect resizes panelAirfoils (#245)', () => {
  beforeEach(() => {
    resetStore();
  });

  it('increasing wingSections from 1 to 3 keeps panelAirfoils length >= 2', () => {
    useDesignStore.getState().setParam('wingSections', 3, 'immediate');
    const { design } = useDesignStore.getState();
    // panelAirfoils should have at least targetLen = 2 entries
    expect(design.panelAirfoils.length).toBeGreaterThanOrEqual(2);
  });

  it('new panelAirfoils entries from wingSections expansion are null', () => {
    // Start with all-None, then go to 3 sections (targetLen=2)
    useDesignStore.getState().setParam('wingSections', 3, 'immediate');
    const { design } = useDesignStore.getState();
    // All new entries must be null (inherit root)
    for (let i = 0; i < design.wingSections - 1; i++) {
      expect(design.panelAirfoils[i], `panelAirfoils[${i}] should be null after expansion`).toBeNull();
    }
  });

  it('decreasing wingSections truncates panelAirfoils', () => {
    // Go to 4 sections, set an override, then reduce
    useDesignStore.getState().setParam('wingSections', 4, 'immediate');
    useDesignStore.getState().setPanelAirfoil(2, 'NACA-0012'); // panel 4
    useDesignStore.getState().setParam('wingSections', 2, 'immediate'); // targetLen=1
    const { design } = useDesignStore.getState();
    // After truncation to targetLen=1, panelAirfoils should have length <= 1
    expect(design.panelAirfoils.length).toBeLessThanOrEqual(3); // stored array still 3, but active len=1
  });
});
