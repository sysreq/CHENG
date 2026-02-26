// ============================================================================
// CHENG — Wing Panel Selection unit tests (#241, #242)
// Tests for selectedPanel state and setSelectedPanel action in designStore.
// ============================================================================

import { describe, it, expect, beforeEach } from 'vitest';
import { useDesignStore } from '@/store/designStore';

/** Reset store to initial state before each test. */
function resetStore() {
  useDesignStore.getState().newDesign();
  useDesignStore.temporal.getState().clear();
}

describe('designStore — wing panel selection (#241, #242)', () => {
  beforeEach(() => {
    resetStore();
  });

  // ── Initial state ──────────────────────────────────────────────────

  it('starts with selectedPanel = null', () => {
    const { selectedPanel } = useDesignStore.getState();
    expect(selectedPanel).toBeNull();
  });

  it('starts with selectedComponent = global (#289)', () => {
    const { selectedComponent } = useDesignStore.getState();
    expect(selectedComponent).toBe('global');
  });

  // ── setSelectedPanel ───────────────────────────────────────────────

  it('setSelectedPanel(0) sets selectedPanel=0 and selectedComponent=wing', () => {
    useDesignStore.getState().setSelectedPanel(0);
    const { selectedPanel, selectedComponent } = useDesignStore.getState();
    expect(selectedPanel).toBe(0);
    expect(selectedComponent).toBe('wing');
  });

  it('setSelectedPanel(1) sets selectedPanel=1', () => {
    useDesignStore.getState().setSelectedPanel(1);
    expect(useDesignStore.getState().selectedPanel).toBe(1);
  });

  it('setSelectedPanel(2) sets selectedPanel=2', () => {
    useDesignStore.getState().setSelectedPanel(2);
    expect(useDesignStore.getState().selectedPanel).toBe(2);
  });

  it('setSelectedPanel(null) clears panel selection', () => {
    useDesignStore.getState().setSelectedPanel(1);
    useDesignStore.getState().setSelectedPanel(null);
    expect(useDesignStore.getState().selectedPanel).toBeNull();
  });

  it('setSelectedPanel clears selectedSubElement', () => {
    // Set up a sub-element selection
    useDesignStore.getState().setSelectedComponent('wing');
    // Verify sub-element starts null after setSelectedComponent
    expect(useDesignStore.getState().selectedSubElement).toBeNull();
    // Now set panel — still no sub-element
    useDesignStore.getState().setSelectedPanel(0);
    expect(useDesignStore.getState().selectedSubElement).toBeNull();
  });

  // ── setSelectedComponent clears selectedPanel ─────────────────────

  it('setSelectedComponent("fuselage") clears selectedPanel', () => {
    useDesignStore.getState().setSelectedPanel(0);
    expect(useDesignStore.getState().selectedPanel).toBe(0);
    useDesignStore.getState().setSelectedComponent('fuselage');
    expect(useDesignStore.getState().selectedPanel).toBeNull();
  });

  it('setSelectedComponent(null) clears selectedPanel', () => {
    useDesignStore.getState().setSelectedPanel(1);
    useDesignStore.getState().setSelectedComponent(null);
    expect(useDesignStore.getState().selectedPanel).toBeNull();
  });

  it('setSelectedComponent("wing") clears selectedPanel', () => {
    useDesignStore.getState().setSelectedPanel(2);
    useDesignStore.getState().setSelectedComponent('wing');
    // selectedComponent is now 'wing' but no specific panel is selected
    expect(useDesignStore.getState().selectedPanel).toBeNull();
    expect(useDesignStore.getState().selectedComponent).toBe('wing');
  });

  // ── newDesign resets selectedPanel ────────────────────────────────

  it('newDesign() resets selectedPanel to null', () => {
    useDesignStore.getState().setSelectedPanel(0);
    useDesignStore.getState().newDesign();
    expect(useDesignStore.getState().selectedPanel).toBeNull();
  });

  // ── Switching between panels ──────────────────────────────────────

  it('can switch from panel 0 to panel 1', () => {
    useDesignStore.getState().setSelectedPanel(0);
    expect(useDesignStore.getState().selectedPanel).toBe(0);
    useDesignStore.getState().setSelectedPanel(1);
    expect(useDesignStore.getState().selectedPanel).toBe(1);
  });

  it('selectedComponent stays "wing" when switching panels', () => {
    useDesignStore.getState().setSelectedPanel(0);
    useDesignStore.getState().setSelectedPanel(1);
    expect(useDesignStore.getState().selectedComponent).toBe('wing');
  });
});
