// ============================================================================
// CHENG — Reusable Slider + Number Input for Design Parameters
// ============================================================================

import React, { useCallback, useId } from 'react';

export interface ParamSliderProps {
  /** Display label */
  label: string;
  /** Unit string (e.g. "mm", "deg") */
  unit?: string;
  /** Current value */
  value: number;
  /** Minimum allowed value */
  min: number;
  /** Maximum allowed value */
  max: number;
  /** Step increment */
  step: number;
  /** Called when value changes from slider */
  onSliderChange: (value: number) => void;
  /** Called when value changes from number input */
  onInputChange: (value: number) => void;
  /** Whether the field has an associated warning */
  hasWarning?: boolean;
  /** Optional tooltip/description */
  title?: string;
}

/**
 * Combined slider + number input control for a design parameter.
 * Slider on top, number input below, label and unit displayed.
 */
export function ParamSlider({
  label,
  unit,
  value,
  min,
  max,
  step,
  onSliderChange,
  onInputChange,
  hasWarning = false,
  title,
}: ParamSliderProps): React.JSX.Element {
  const id = useId();

  const handleSliderChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onSliderChange(parseFloat(e.target.value));
    },
    [onSliderChange],
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value;
      const parsed = parseFloat(raw);
      if (!Number.isNaN(parsed)) {
        // Clamp to range
        const clamped = Math.min(max, Math.max(min, parsed));
        onInputChange(clamped);
      }
    },
    [onInputChange, min, max],
  );

  const warningRing = hasWarning ? 'ring-1 ring-amber-500/50' : '';

  return (
    <div className="mb-3" title={title}>
      <div className="flex items-center justify-between mb-1">
        <label htmlFor={id} className="text-xs font-medium text-zinc-300">
          {label}
          {hasWarning && <span className="ml-1 text-amber-400" aria-label="has warning">!</span>}
        </label>
        <span className="text-xs text-zinc-500">{unit}</span>
      </div>

      {/* Slider */}
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={handleSliderChange}
        className={`w-full h-1.5 rounded-full appearance-none cursor-pointer
          bg-zinc-700 accent-blue-500 ${warningRing}`}
        aria-label={`${label} slider`}
      />

      {/* Number input */}
      <input
        id={id}
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={handleInputChange}
        className={`mt-1 w-full px-2 py-1 text-xs text-zinc-100 bg-zinc-800
          border border-zinc-700 rounded focus:outline-none focus:border-blue-500
          [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none
          [&::-webkit-inner-spin-button]:appearance-none ${warningRing}`}
      />
    </div>
  );
}
