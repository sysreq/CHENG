// ============================================================================
// CHENG — Reusable Slider + Number Input for Design Parameters
// ============================================================================

import React, { useState, useCallback, useEffect, useId } from 'react';

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
 *
 * The number input uses local state so users can type freely without
 * clamping on every keystroke. Clamping + send happens on blur or Enter.
 * Out-of-range values show a red border as visual feedback.
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

  // Local string state for the number input — allows free typing
  const [localValue, setLocalValue] = useState<string>(String(value));
  const [isFocused, setIsFocused] = useState(false);

  // Sync local value from prop when not focused (e.g. slider or preset change)
  useEffect(() => {
    if (!isFocused) {
      setLocalValue(String(value));
    }
  }, [value, isFocused]);

  // Check if current local value is out of range (for red border)
  const parsed = parseFloat(localValue);
  const isOutOfRange =
    isFocused && !Number.isNaN(parsed) && (parsed < min || parsed > max);

  const handleSliderChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onSliderChange(parseFloat(e.target.value));
    },
    [onSliderChange],
  );

  // On each keystroke: update local display only, no clamping or sending
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setLocalValue(e.target.value);
    },
    [],
  );

  // On blur or Enter: clamp and send to backend
  const commitValue = useCallback(() => {
    const val = parseFloat(localValue);
    if (Number.isNaN(val)) {
      // Revert to current prop value
      setLocalValue(String(value));
    } else {
      const clamped = Math.min(max, Math.max(min, val));
      setLocalValue(String(clamped));
      onInputChange(clamped);
    }
    setIsFocused(false);
  }, [localValue, value, min, max, onInputChange]);

  const handleFocus = useCallback(() => {
    setIsFocused(true);
  }, []);

  const handleBlur = useCallback(() => {
    commitValue();
  }, [commitValue]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        commitValue();
        (e.target as HTMLInputElement).blur();
      }
    },
    [commitValue],
  );

  const warningRing = hasWarning ? 'ring-1 ring-amber-500/50' : '';
  const outOfRangeBorder = isOutOfRange ? 'border-red-500' : 'border-zinc-700';

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
        value={localValue}
        onChange={handleInputChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        className={`mt-1 w-full px-2 py-1 text-xs text-zinc-100 bg-zinc-800
          border ${outOfRangeBorder} rounded focus:outline-none focus:border-blue-500
          [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none
          [&::-webkit-inner-spin-button]:appearance-none ${warningRing}`}
      />
    </div>
  );
}
