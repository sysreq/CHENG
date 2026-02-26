// ============================================================================
// CHENG — Reusable Slider + Number Input for Design Parameters
// Issue #153 (Unit toggle: mm / inches)
// ============================================================================

import React, { useState, useCallback, useEffect, useId, useRef } from 'react';
import * as Tooltip from '@radix-ui/react-tooltip';
import { useDesignStore } from '../../store/designStore';
import { useUnitStore } from '../../store/unitStore';
import { toDisplayUnit, fromDisplayUnit, getDisplayUnit, convertSliderRange } from '../../lib/units';

export interface ParamSliderProps {
  /** Display label */
  label: string;
  /** Unit string (e.g. "mm", "deg"). "mm" fields will be converted when in inches mode. */
  unit?: string;
  /** Current value (always in native units — mm for mm fields) */
  value: number;
  /** Minimum allowed value (in native units) */
  min: number;
  /** Maximum allowed value (in native units) */
  max: number;
  /** Step increment (in native units) */
  step: number;
  /** Called when value changes from slider (value in native units) */
  onSliderChange: (value: number) => void;
  /** Called when value changes from number input (value in native units) */
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
 *
 * When unit is "mm" and the global unit system is set to "in", values are
 * automatically converted for display. The slider and input show inches;
 * onSliderChange/onInputChange still receive the value in mm (native units).
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
  const unitSystem = useUnitStore((s) => s.unitSystem);

  // Determine if this is an mm field that should be converted
  const isMmField = unit === 'mm';
  const displayUnit = unit ? getDisplayUnit(unit, unitSystem) : unit;

  // Convert native mm value/range to display units
  const displayValue = isMmField ? toDisplayUnit(value, unitSystem) : value;
  const displayRange = convertSliderRange({ min, max, step }, unit ?? '', unitSystem);

  // Track whether the slider is currently being dragged (for Zundo pause/resume)
  const isDragging = useRef(false);

  // Local string state for the number input — allows free typing
  // Use display value (may be in inches) for local state
  const [localValue, setLocalValue] = useState<string>(String(displayValue));
  const [isFocused, setIsFocused] = useState(false);

  // Sync local value from prop when not focused (e.g. slider or preset change)
  // Use displayValue so the local state reflects current unit system
  useEffect(() => {
    if (!isFocused) {
      setLocalValue(String(displayValue));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [displayValue, isFocused]);

  // Check if current local value is out of range (for red border)
  // Compare against display range (converted min/max)
  const parsed = parseFloat(localValue);
  const isOutOfRange =
    isFocused &&
    !Number.isNaN(parsed) &&
    (parsed < displayRange.min || parsed > displayRange.max);

  // Commit helper: resume Zundo and force a history snapshot of the current state.
  const commitDrag = useCallback(() => {
    if (isDragging.current) {
      isDragging.current = false;
      temporalStore.getState().resume();
      commitSliderChange();
    }
  }, [temporalStore, commitSliderChange]);

  // Pause Zundo history recording at the start of a slider drag.
  const handleSliderPointerDown = useCallback(() => {
    if (!isDragging.current) {
      isDragging.current = true;
      temporalStore.getState().pause();
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
      const displayVal = parseFloat(e.target.value);
      // Convert back to native mm before calling onSliderChange
      const nativeVal = isMmField ? fromDisplayUnit(displayVal, unitSystem) : displayVal;
      onSliderChange(nativeVal);
    },
    [onSliderChange, isMmField, unitSystem],
  );

  // On each keystroke: update local display only, no clamping or sending
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setLocalValue(e.target.value);
    },
    [],
  );

  // On blur or Enter: clamp (in display units) and send to backend (in native units)
  const commitValue = useCallback(() => {
    const val = parseFloat(localValue);
    if (Number.isNaN(val)) {
      // Revert to current display value
      setLocalValue(String(displayValue));
    } else {
      const clamped = Math.min(displayRange.max, Math.max(displayRange.min, val));
      setLocalValue(String(clamped));
      // Convert back to native mm before calling onInputChange
      const nativeVal = isMmField ? fromDisplayUnit(clamped, unitSystem) : clamped;
      onInputChange(nativeVal);
    }
    setIsFocused(false);
  }, [localValue, displayValue, displayRange.min, displayRange.max, onInputChange, isMmField, unitSystem]);

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
        <span className="text-xs text-zinc-500">{displayUnit}</span>
      </div>

      {/* Slider — operates in display units */}
      <input
        type="range"
        min={displayRange.min}
        max={displayRange.max}
        step={displayRange.step}
        value={displayValue}
        onChange={handleSliderChange}
        onPointerDown={handleSliderPointerDown}
        onPointerUp={handleSliderPointerUp}
        disabled={disabled}
        className={`w-full h-1.5 rounded-full appearance-none cursor-pointer
          bg-zinc-700 accent-blue-500 ${warningRing}
          disabled:opacity-50 disabled:cursor-not-allowed`}
        aria-label={`${label} slider`}
      />

      {/* Number input — displays in current unit system */}
      <input
        id={id}
        type="number"
        min={displayRange.min}
        max={displayRange.max}
        step={displayRange.step}
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
