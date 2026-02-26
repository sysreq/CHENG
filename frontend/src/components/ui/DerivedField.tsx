// ============================================================================
// CHENG — Read-Only Derived Value Display
// Issue #153 (Unit toggle: mm / inches), #154 (title prop for tooltips)
// ============================================================================

import React from 'react';
import { useUnitStore } from '../../store/unitStore';
import { toDisplayUnit, getDisplayUnit } from '../../lib/units';

export interface DerivedFieldProps {
  /** Display label */
  label: string;
  /** Value to display, or null/undefined if not yet computed. Always in native units (mm for mm fields). */
  value: number | null | undefined;
  /** Unit string (e.g. "mm", "cm2"). "mm" fields will be converted when in inches mode. */
  unit?: string;
  /** Decimal places for formatting in mm mode */
  decimals?: number;
  /** Decimal places for formatting in inches mode (defaults to decimals + 2) */
  decimalsIn?: number;
  /** Optional suffix text after unit (e.g. "from wing LE") */
  suffix?: string;
  /** Optional hover tooltip explaining what this value means */
  title?: string;
}

/**
 * Displays a backend-computed derived value in a read-only gray field.
 * Shows an em-dash when value is null (not yet computed).
 * Styled with cursor: default and no contentEditable to be truly read-only.
 *
 * When unit is "mm" and the global unit system is "in", the value is
 * automatically converted to inches for display.
 */
export function DerivedField({
  label,
  value,
  unit,
  decimals = 1,
  decimalsIn,
  suffix,
  title,
}: DerivedFieldProps): React.JSX.Element {
  const unitSystem = useUnitStore((s) => s.unitSystem);

  let formatted: string;
  if (value == null) {
    formatted = '\u2014';
  } else {
    // Determine display unit and value
    const isMmField = unit === 'mm';
    const displayUnit = unit ? getDisplayUnit(unit, unitSystem) : unit;
    const displayValue = isMmField ? toDisplayUnit(value, unitSystem) : value;
    const displayDecimals = isMmField && unitSystem === 'in'
      ? (decimalsIn ?? decimals + 2)
      : decimals;

    formatted = `${displayValue.toFixed(displayDecimals)}${displayUnit ? ` ${displayUnit}` : ''}`;
    if (suffix) formatted += ` ${suffix}`;
  }

  return (
    <div className="mb-2" title={title}>
      <span className="block text-xs font-medium text-zinc-400 mb-0.5">{label}</span>
      <div
        className="w-full px-2 py-1 text-xs text-zinc-300 bg-zinc-800/50
          border border-zinc-700/50 rounded cursor-default"
        aria-readonly="true"
      >
        {formatted}
      </div>
    </div>
  );
}
