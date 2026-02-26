// ============================================================================
// CHENG — Read-Only Derived Value Display
// Issue #154 — Added title prop for hover tooltips
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
  /** Optional suffix text after unit (e.g. "from wing LE") */
  suffix?: string;
  /** Optional hover tooltip explaining what this value means */
  title?: string;
}

/**
 * Displays a backend-computed derived value in a read-only gray field.
 * Shows an em-dash when value is null (not yet computed).
 * Styled with cursor: default and no contentEditable to be truly read-only.
 */
export function DerivedField({
  label,
  value,
  unit,
  decimals = 1,
  suffix,
  title,
}: DerivedFieldProps): React.JSX.Element {
  let formatted: string;
  if (value == null) {
    formatted = '\u2014';
  } else {
    formatted = `${value.toFixed(decimals)}${unit ? ` ${unit}` : ''}`;
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
