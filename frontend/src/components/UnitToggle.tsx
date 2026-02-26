// ============================================================================
// CHENG — UnitToggle: Toolbar button to switch between mm and inches
// Issue #153 (Unit toggle: mm / inches)
// ============================================================================

import React, { useCallback } from 'react';
import { useUnitStore } from '../store/unitStore';

/**
 * A compact pill button in the toolbar that toggles the display unit
 * system between millimeters (mm) and inches (in).
 *
 * The preference is persisted in localStorage via useUnitStore.
 * All mm-based parameter sliders and derived fields update automatically
 * by reading unitSystem from the store.
 */
export function UnitToggle(): React.JSX.Element {
  const unitSystem = useUnitStore((s) => s.unitSystem);
  const toggleUnit = useUnitStore((s) => s.toggleUnit);

  const handleClick = useCallback(() => {
    toggleUnit();
  }, [toggleUnit]);

  const isInches = unitSystem === 'in';

  return (
    <button
      onClick={handleClick}
      className={[
        'px-2 py-0.5 text-[10px] font-medium rounded-full border',
        'focus:outline-none focus:ring-1 focus:ring-blue-500',
        'transition-colors duration-150',
        'mr-1',
        isInches
          ? 'bg-blue-900 text-blue-300 border-blue-700'
          : 'bg-zinc-700 text-zinc-300 border-zinc-600',
      ].join(' ')}
      title={isInches ? 'Displaying in inches — click to switch to mm' : 'Displaying in mm — click to switch to inches'}
      aria-label={`Unit system: ${isInches ? 'inches' : 'millimeters'} — click to toggle`}
      aria-pressed={isInches}
    >
      {isInches ? 'in' : 'mm'}
    </button>
  );
}
