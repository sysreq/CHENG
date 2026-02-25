// ============================================================================
// CHENG — Bidirectional Parameter Toggle
// Allows users to choose which of two related params to set directly,
// with the other becoming a computed/read-only derived value.
// Issue #121
// ============================================================================

import React, { useCallback, useId } from 'react';
import * as Tooltip from '@radix-ui/react-tooltip';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface BidirectionalParamProps {
  /** Label for param A (the "primary" when mode === 'a') */
  labelA: string;
  /** Label for param B (the "primary" when mode === 'b') */
  labelB: string;
  /** Current value of param A */
  valueA: number;
  /** Current value of param B */
  valueB: number;
  /** Unit for param A */
  unitA?: string;
  /** Unit for param B */
  unitB?: string;
  /** Min/max/step for param A slider */
  minA: number;
  maxA: number;
  stepA: number;
  /** Min/max/step for param B slider */
  minB: number;
  maxB: number;
  stepB: number;
  /** Which param is currently the "driver" — 'a' means A is editable, B is derived */
  mode: 'a' | 'b';
  /** Called to toggle between modes */
  onModeChange: (mode: 'a' | 'b') => void;
  /** Called when param A slider changes */
  onSliderChangeA: (value: number) => void;
  /** Called when param A input changes */
  onInputChangeA: (value: number) => void;
  /** Called when param B slider changes */
  onSliderChangeB: (value: number) => void;
  /** Called when param B input changes */
  onInputChangeB: (value: number) => void;
  /** Whether param A has a warning */
  hasWarningA?: boolean;
  /** Whether param B has a warning */
  hasWarningB?: boolean;
  /** Warning text for param A */
  warningTextA?: string;
  /** Warning text for param B */
  warningTextB?: string;
  /** Decimal places for the derived display */
  decimalsA?: number;
  decimalsB?: number;
  /** Whether the control is disabled (e.g. when disconnected) */
  disabled?: boolean;
}

// ---------------------------------------------------------------------------
// Internal: Inline mini slider+input (editable)
// ---------------------------------------------------------------------------

function InlineSliderInput({
  id,
  value,
  min,
  max,
  step,
  onSliderChange,
  onInputChange,
  hasWarning,
  warningText,
  disabled = false,
}: {
  id: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onSliderChange: (v: number) => void;
  onInputChange: (v: number) => void;
  hasWarning?: boolean;
  warningText?: string;
  disabled?: boolean;
}): React.JSX.Element {
  const [localValue, setLocalValue] = React.useState<string>(String(value));
  const [isFocused, setIsFocused] = React.useState(false);

  React.useEffect(() => {
    if (!isFocused) {
      setLocalValue(String(value));
    }
  }, [value, isFocused]);

  const parsed = parseFloat(localValue);
  const isOutOfRange =
    isFocused && !Number.isNaN(parsed) && (parsed < min || parsed > max);

  const handleSlider = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onSliderChange(parseFloat(e.target.value));
    },
    [onSliderChange],
  );

  const handleInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setLocalValue(e.target.value);
    },
    [],
  );

  const commitValue = useCallback(() => {
    const val = parseFloat(localValue);
    if (Number.isNaN(val)) {
      setLocalValue(String(value));
    } else {
      const clamped = Math.min(max, Math.max(min, val));
      setLocalValue(String(clamped));
      onInputChange(clamped);
    }
    setIsFocused(false);
  }, [localValue, value, min, max, onInputChange]);

  const handleFocus = useCallback(() => setIsFocused(true), []);
  const handleBlur = useCallback(() => commitValue(), [commitValue]);
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
  void warningText; // used for future tooltip enhancement

  return (
    <>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={handleSlider}
        disabled={disabled}
        className={`w-full h-1.5 rounded-full appearance-none cursor-pointer
          bg-zinc-700 accent-blue-500 ${warningRing}
          disabled:opacity-50 disabled:cursor-not-allowed`}
        aria-label={`${id} slider`}
      />
      <input
        id={id}
        type="number"
        min={min}
        max={max}
        step={step}
        value={localValue}
        onChange={handleInput}
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
    </>
  );
}

// ---------------------------------------------------------------------------
// Internal: Read-only derived display
// ---------------------------------------------------------------------------

function DerivedDisplay({
  value,
  unit,
  decimals = 1,
}: {
  value: number;
  unit?: string;
  decimals?: number;
}): React.JSX.Element {
  const formatted = `${value.toFixed(decimals)}${unit ? ` ${unit}` : ''}`;
  return (
    <div
      className="mt-1 w-full px-2 py-1 text-xs text-zinc-400 bg-zinc-800/50
        border border-zinc-700/50 rounded cursor-default italic"
      aria-readonly="true"
    >
      {formatted}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BidirectionalParam({
  labelA,
  labelB,
  valueA,
  valueB,
  unitA,
  unitB,
  minA,
  maxA,
  stepA,
  minB,
  maxB,
  stepB,
  mode,
  onModeChange,
  onSliderChangeA,
  onInputChangeA,
  onSliderChangeB,
  onInputChangeB,
  hasWarningA = false,
  hasWarningB = false,
  warningTextA,
  warningTextB,
  decimalsA = 1,
  decimalsB = 1,
  disabled = false,
}: BidirectionalParamProps): React.JSX.Element {
  const idA = useId();
  const idB = useId();

  const toggleMode = useCallback(() => {
    onModeChange(mode === 'a' ? 'b' : 'a');
  }, [mode, onModeChange]);

  const aIsEditable = mode === 'a';
  const bIsEditable = mode === 'b';

  return (
    <div className="mb-3">
      {/* ── Param A ──────────────────────────────────────────────────── */}
      <div className="mb-1">
        <div className="flex items-center justify-between mb-1">
          <label htmlFor={idA} className="text-xs font-medium text-zinc-300">
            {labelA}
            {aIsEditable && (
              <span className="ml-1 text-[9px] text-blue-400 font-normal">(editing)</span>
            )}
            {!aIsEditable && (
              <span className="ml-1 text-[9px] text-zinc-500 font-normal">(computed)</span>
            )}
            {hasWarningA && (
              <span className="ml-1" style={{ color: '#FFD60A' }} aria-label="has warning">
                {'\u26A0'}
              </span>
            )}
          </label>
          <span className="text-xs text-zinc-500">{unitA}</span>
        </div>

        {aIsEditable ? (
          <InlineSliderInput
            id={idA}
            value={valueA}
            min={minA}
            max={maxA}
            step={stepA}
            onSliderChange={onSliderChangeA}
            onInputChange={onInputChangeA}
            hasWarning={hasWarningA}
            warningText={warningTextA}
            disabled={disabled}
          />
        ) : (
          <DerivedDisplay value={valueA} unit={unitA} decimals={decimalsA} />
        )}
      </div>

      {/* ── Toggle Button ───────────────────────────────────────────── */}
      <div className="flex items-center justify-center my-1.5">
        <Tooltip.Provider delayDuration={300}>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button
                onClick={toggleMode}
                disabled={disabled}
                className="px-2 py-0.5 text-[10px] text-zinc-400 bg-zinc-800
                  border border-zinc-700 rounded hover:bg-zinc-700
                  hover:text-zinc-200 focus:outline-none focus:ring-1
                  focus:ring-blue-500 transition-colors
                  disabled:opacity-50 disabled:cursor-not-allowed"
                type="button"
                aria-label={`Switch to editing ${aIsEditable ? labelB : labelA}`}
              >
                {'\u21C5'} swap
              </button>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content
                className="z-50 px-2 py-1 text-[10px] text-zinc-200 bg-zinc-800
                  border border-zinc-700 rounded shadow-lg"
                side="right"
                sideOffset={4}
              >
                Switch to editing {aIsEditable ? labelB : labelA}
                <Tooltip.Arrow className="fill-zinc-800" />
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>
        </Tooltip.Provider>
      </div>

      {/* ── Param B ──────────────────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label htmlFor={idB} className="text-xs font-medium text-zinc-300">
            {labelB}
            {bIsEditable && (
              <span className="ml-1 text-[9px] text-blue-400 font-normal">(editing)</span>
            )}
            {!bIsEditable && (
              <span className="ml-1 text-[9px] text-zinc-500 font-normal">(computed)</span>
            )}
            {hasWarningB && (
              <span className="ml-1" style={{ color: '#FFD60A' }} aria-label="has warning">
                {'\u26A0'}
              </span>
            )}
          </label>
          <span className="text-xs text-zinc-500">{unitB}</span>
        </div>

        {bIsEditable ? (
          <InlineSliderInput
            id={idB}
            value={valueB}
            min={minB}
            max={maxB}
            step={stepB}
            onSliderChange={onSliderChangeB}
            onInputChange={onInputChangeB}
            hasWarning={hasWarningB}
            warningText={warningTextB}
            disabled={disabled}
          />
        ) : (
          <DerivedDisplay value={valueB} unit={unitB} decimals={decimalsB} />
        )}
      </div>
    </div>
  );
}
