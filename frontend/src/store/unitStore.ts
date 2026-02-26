// ============================================================================
// CHENG — Unit System Store
// Issue #153 (Unit toggle: mm / inches)
// ============================================================================
//
// Manages the user's preferred unit system (mm or inches).
// Preference is persisted to localStorage so it survives page reloads.
//
// IMPORTANT: Backend always operates in mm. This store only affects display.
// Values are converted on the way OUT (for display) and converted back IN
// (when user types a value). The AircraftDesign store always stays in mm.
// ============================================================================

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type UnitSystem = 'mm' | 'in';

export interface UnitStore {
  /** Current unit system preference. */
  unitSystem: UnitSystem;
  /** Toggle between mm and inches. */
  toggleUnit: () => void;
  /** Set unit system explicitly. */
  setUnitSystem: (system: UnitSystem) => void;
}

// ---------------------------------------------------------------------------
// Store Implementation
// ---------------------------------------------------------------------------

export const useUnitStore = create<UnitStore>()(
  persist(
    (set) => ({
      unitSystem: 'mm',

      toggleUnit: () =>
        set((state) => ({
          unitSystem: state.unitSystem === 'mm' ? 'in' : 'mm',
        })),

      setUnitSystem: (system) => set({ unitSystem: system }),
    }),
    {
      name: 'cheng-unit-system',
      // Only persist the unitSystem field, not the action functions
      partialize: (state) => ({ unitSystem: state.unitSystem }),
    },
  ),
);
