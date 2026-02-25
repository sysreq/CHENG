// ============================================================================
// CHENG — Reusable Toggle/Checkbox for Boolean Parameters
// ============================================================================

import React, { useCallback, useId } from 'react';

export interface ParamToggleProps {
  /** Display label */
  label: string;
  /** Current checked state */
  checked: boolean;
  /** Called when toggled */
  onChange: (checked: boolean) => void;
  /** Whether the field has an associated warning */
  hasWarning?: boolean;
  /** Optional tooltip/description */
  title?: string;
  /** Whether the control is disabled (e.g. when disconnected) */
  disabled?: boolean;
}

/**
 * Toggle checkbox for boolean design parameters.
 * Uses immediate source since toggles change values instantly.
 */
export function ParamToggle({
  label,
  checked,
  onChange,
  hasWarning = false,
  title,
  disabled = false,
}: ParamToggleProps): React.JSX.Element {
  const id = useId();

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onChange(e.target.checked);
    },
    [onChange],
  );

  return (
    <div className="mb-3 flex items-center gap-2" title={title}>
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={handleChange}
        disabled={disabled}
        className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-blue-500
          focus:ring-blue-500 focus:ring-offset-0 cursor-pointer accent-blue-500
          disabled:opacity-50 disabled:cursor-not-allowed"
      />
      <label htmlFor={id} className="text-xs font-medium text-zinc-300 cursor-pointer">
        {label}
        {hasWarning && <span className="ml-1 text-amber-400" aria-label="has warning">!</span>}
      </label>
    </div>
  );
}
