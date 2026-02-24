// ============================================================================
// CHENG — Read-Only Derived Value Display
// ============================================================================

import React from 'react';

export interface DerivedFieldProps {
  /** Display label */
  label: string;
  /** Value to display, or null/undefined if not yet computed */
  value: number | null | undefined;
  /** Unit string (e.g. "mm", "cm2") */
  unit?: string;
  /** Decimal places for formatting */
  decimals?: number;
}

/**
 * Displays a backend-computed derived value in a read-only gray field.
 * Shows a dash when value is null (not yet computed).
 */
export function DerivedField({
  label,
  value,
  unit,
  decimals = 1,
}: DerivedFieldProps): React.JSX.Element {
  const formatted =
    value != null ? `${value.toFixed(decimals)}${unit ? ` ${unit}` : ''}` : '\u2014';

  return (
    <div className="mb-2">
      <span className="block text-xs font-medium text-zinc-400 mb-0.5">{label}</span>
      <div
        className="w-full px-2 py-1 text-xs text-zinc-300 bg-zinc-800/50
          border border-zinc-700/50 rounded select-text"
      >
        {formatted}
      </div>
    </div>
  );
}
