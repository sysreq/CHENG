// ============================================================================
// CHENG — Reusable Slider + Number Input for Design Parameters
// ============================================================================

import React, { useState, useCallback, useEffect, useId, useRef } from 'react';
import * as Tooltip from '@radix-ui/react-tooltip';
import { useDesignStore } from '../../store/designStore';

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
  /** Warning tooltip text (shown on click of warning icon) */
  warningText?: string;
  /** Optional tooltip/description */
  title?: string;
  /** Whether the control is disabled (e.g. when disconnected) */
  disabled?: boolean;
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
  warningText,
  title,
  disabled = false,
}: ParamSliderProps): React.JSX.Element {
  const id = useId();
  const temporalStore = useDesignStore.temporal;
  const commitSliderChange = useDesignStore((s) => s.commitSliderChange);

  // Track whether the slider is currently being dragged (for Zundo pause/resume)
  const isDragging = useRef(false);

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

  // Commit helper: resume Zundo and force a history snapshot of the current state.
  // Called when slider drag ends (either via slider element or global safety net).
  const commitDrag = useCallback(() => {
    if (isDragging.current) {
      isDragging.current = false;
      // Resume Zundo tracking first, then commit the current state as a history entry.
      // commitSliderChange() triggers a no-op setState that Zundo intercepts to
      // record the current (post-drag) state as a history snapshot.
      temporalStore.getState().resume();
      commitSliderChange();
    }
  }, [temporalStore, commitSliderChange]);

  // Pause Zundo history recording at the start of a slider drag.
  // This prevents intermediate drag values from flooding the history stack.
  const handleSliderPointerDown = useCallback(() => {
    if (!isDragging.current) {
      isDragging.current = true;
      temporalStore.getState().pause();
      // Global safety net: if the pointer is released outside the slider element
      // (e.g. mouse moves off slider), still resume Zundo and commit history.
      const cleanup = () => {
        commitDrag();
        document.removeEventListener('pointerup', cleanup);
        document.removeEventListener('pointercancel', cleanup);
      };
      document.addEventListener('pointerup', cleanup, { once: true });
      document.addEventListener('pointercancel', cleanup, { once: true });
    }
  }, [temporalStore, commitDrag]);

  // Resume Zundo on pointer up and commit one history entry.
  const handleSliderPointerUp = useCallback(() => {
    commitDrag();
  }, [commitDrag]);

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
          {hasWarning && (
            <Tooltip.Provider delayDuration={200}>
              <Tooltip.Root>
                <Tooltip.Trigger asChild>
                  <span
                    className="inline-block ml-1 cursor-help"
                    style={{ color: '#FFD60A' }}
                    aria-label="has warning"
                  >
                    {'\u26A0'}
                  </span>
                </Tooltip.Trigger>
                {warningText && (
                  <Tooltip.Portal>
                    <Tooltip.Content
                      className="z-50 px-2 py-1.5 text-xs text-zinc-100 bg-zinc-800 border border-amber-500/50 rounded shadow-lg max-w-[250px] whitespace-normal"
                      side="bottom"
                      align="start"
                      sideOffset={4}
                    >
                      {warningText}
                      <Tooltip.Arrow className="fill-zinc-800" />
                    </Tooltip.Content>
                  </Tooltip.Portal>
                )}
              </Tooltip.Root>
            </Tooltip.Provider>
          )}
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
        onPointerDown={handleSliderPointerDown}
        onPointerUp={handleSliderPointerUp}
        disabled={disabled}
        className={`w-full h-1.5 rounded-full appearance-none cursor-pointer
          bg-zinc-700 accent-blue-500 ${warningRing}
          disabled:opacity-50 disabled:cursor-not-allowed`}
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
        disabled={disabled}
        className={`mt-1 w-full px-2 py-1 text-xs text-zinc-100 bg-zinc-800
          border ${outOfRangeBorder} rounded focus:outline-none focus:border-blue-500
          [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none
          [&::-webkit-inner-spin-button]:appearance-none ${warningRing}
          disabled:opacity-50 disabled:cursor-not-allowed`}
      />
    </div>
  );
}
