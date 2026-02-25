// ============================================================================
// CHENG — Motor toggle unit tests (#240)
// engine_count restricted to 0/1 — numeric input replaced with toggle
// ============================================================================

import { describe, it, expect, beforeEach } from 'vitest';
import { useDesignStore } from '@/store/designStore';
import { createDesignFromPreset } from '@/lib/presets';

/** Reset store to initial (Trainer) state before each test. */
function resetStore() {
  useDesignStore.getState().newDesign();
  useDesignStore.temporal.getState().clear();
}

// ============================================================================
// Engine count / motor toggle — store behaviour
// ============================================================================

describe('motor toggle: engineCount 0/1 (#240)', () => {
  beforeEach(() => {
    resetStore();
  });

  it('default design (Trainer) has engineCount=1 (motor on)', () => {
    const { design } = useDesignStore.getState();
    expect(design.engineCount).toBe(1);
  });

  it('setting engineCount to 0 turns the motor off', () => {
    useDesignStore.getState().setParam('engineCount', 0, 'immediate');
    const { design } = useDesignStore.getState();
    expect(design.engineCount).toBe(0);
  });

  it('setting engineCount to 1 turns the motor on', () => {
    useDesignStore.getState().setParam('engineCount', 0, 'immediate');
    useDesignStore.getState().setParam('engineCount', 1, 'immediate');
    const { design } = useDesignStore.getState();
    expect(design.engineCount).toBe(1);
  });

  it('toggling motor changes activePreset to Custom', () => {
    // Start on Trainer preset (engineCount=1)
    expect(useDesignStore.getState().activePreset).toBe('Trainer');
    useDesignStore.getState().setParam('engineCount', 0, 'immediate');
    expect(useDesignStore.getState().activePreset).toBe('Custom');
  });

  it('toggling motor is recorded in lastAction', () => {
    useDesignStore.getState().setParam('engineCount', 0, 'immediate');
    expect(useDesignStore.getState().lastAction).toContain('Engine Count');
  });

  it('Glider preset has engineCount=0 (unpowered glider)', () => {
    const d = createDesignFromPreset('Glider');
    expect(d.engineCount).toBe(0);
  });

  it('all powered presets have engineCount=1', () => {
    const poweredPresets = ['Trainer', 'Sport', 'Aerobatic', 'FlyingWing', 'Scale'] as const;
    for (const name of poweredPresets) {
      const d = createDesignFromPreset(name);
      expect(d.engineCount, `${name} should have engineCount=1`).toBe(1);
    }
  });

  it('engineCount only has values 0 or 1 in all presets', () => {
    const allPresets = ['Trainer', 'Sport', 'Aerobatic', 'Glider', 'FlyingWing', 'Scale'] as const;
    for (const name of allPresets) {
      const d = createDesignFromPreset(name);
      expect([0, 1], `${name}.engineCount must be 0 or 1`).toContain(d.engineCount);
    }
  });
});
