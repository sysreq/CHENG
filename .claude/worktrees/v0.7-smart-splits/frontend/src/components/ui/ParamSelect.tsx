// ============================================================================
// CHENG — Reusable Select Dropdown for Design Parameters
// ============================================================================

import React, { useCallback, useId } from 'react';

export interface ParamSelectProps<T extends string> {
  /** Display label */
  label: string;
  /** Current value */
  value: T;
  /** Available options */
  options: readonly T[];
  /** Called when value changes */
  onChange: (value: T) => void;
  /** Whether the field has an associated warning */
  hasWarning?: boolean;
  /** Optional tooltip/description */
  title?: string;
  /** Whether the control is disabled (e.g. when disconnected) */
  disabled?: boolean;
}

/**
 * Native <select> dropdown for enum/literal type parameters.
 * Uses immediate source since dropdowns change values instantly.
 */
export function ParamSelect<T extends string>({
  label,
  value,
  options,
  onChange,
  hasWarning = false,
  title,
  disabled = false,
}: ParamSelectProps<T>): React.JSX.Element {
  const id = useId();

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      onChange(e.target.value as T);
    },
    [onChange],
  );

  const warningRing = hasWarning ? 'ring-1 ring-amber-500/50' : '';

  return (
    <div className="mb-3" title={title}>
      <label htmlFor={id} className="block text-xs font-medium text-zinc-300 mb-1">
        {label}
        {hasWarning && <span className="ml-1 text-amber-400" aria-label="has warning">!</span>}
      </label>
      <select
        id={id}
        value={value}
        onChange={handleChange}
        disabled={disabled}
        className={`w-full px-2 py-1.5 text-xs text-zinc-100 bg-zinc-800
          border border-zinc-700 rounded cursor-pointer
          focus:outline-none focus:border-blue-500 ${warningRing}
          disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </div>
  );
}
