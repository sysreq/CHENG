// ============================================================================
// CHENG — Global Panel: Core aircraft parameters
// Issue #25 | #289 (preset section moved to Presets menu in Toolbar)
// Issue #154 — Parameter renaming for beginners (tooltips added)
// ============================================================================

import React, { useCallback, useMemo, useState } from 'react';
import { useDesignStore } from '../../store/designStore';
import { fieldHasWarning, getFieldWarnings, formatWarning } from '../../lib/validation';
import { ParamSlider, ParamSelect, BidirectionalParam } from '../ui';
import type {
  FuselagePreset,
  MotorConfig,
  WingMountType,
  TailType,
} from '../../types/design';

// ---------------------------------------------------------------------------
// Option Constants
// ---------------------------------------------------------------------------

const FUSELAGE_PRESET_OPTIONS: readonly FuselagePreset[] = [
  'Pod',
  'Conventional',
  'Blended-Wing-Body',
] as const;

const MOTOR_CONFIG_OPTIONS: readonly MotorConfig[] = [
  'Tractor',
  'Pusher',
] as const;

const WING_MOUNT_OPTIONS: readonly WingMountType[] = [
  'High-Wing',
  'Mid-Wing',
  'Low-Wing',
  'Shoulder-Wing',
] as const;

const TAIL_TYPE_OPTIONS: readonly TailType[] = [
  'Conventional',
  'T-Tail',
  'V-Tail',
  'Cruciform',
] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GlobalPanel(): React.JSX.Element {
  const design = useDesignStore((s) => s.design);
  const warnings = useDesignStore((s) => s.warnings);
  const setParam = useDesignStore((s) => s.setParam);

  // ── Param Setters (dropdowns — immediate source) ────────────────────

  const setFuselagePreset = useCallback(
    (v: FuselagePreset) => setParam('fuselagePreset', v, 'immediate'),
    [setParam],
  );
  const setMotorConfig = useCallback(
    (v: MotorConfig) => setParam('motorConfig', v, 'immediate'),
    [setParam],
  );
  const setWingMountType = useCallback(
    (v: WingMountType) => setParam('wingMountType', v, 'immediate'),
    [setParam],
  );
  const setTailType = useCallback(
    (v: TailType) => setParam('tailType', v, 'immediate'),
    [setParam],
  );

  // ── Motor toggle (boolean: 0 = no motor, 1 = single motor) ─────────
  // engine_count is restricted to 0/1 in v0.7.1 (#240).

  const handleMotorToggle = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setParam('engineCount', e.target.checked ? 1 : 0, 'immediate');
    },
    [setParam],
  );

  // ── Chord / Aspect Ratio bidirectional mode ────────────────────────
  // 'a' = chord is editable, aspect ratio is derived
  // 'b' = aspect ratio is editable, chord is derived from wingspan / AR
  const [chordArMode, setChordArMode] = useState<'a' | 'b'>('a');

  // Compute aspect ratio from current wingspan and chord (simple rectangular approx)
  const computedAspectRatio = useMemo(
    () => (design.wingChord > 0 ? design.wingSpan / design.wingChord : 0),
    [design.wingSpan, design.wingChord],
  );

  // When user changes aspect ratio, compute chord = wingspan / AR and send it
  const handleArSliderChange = useCallback(
    (ar: number) => {
      if (ar > 0) {
        const newChord = Math.round(design.wingSpan / ar / 5) * 5; // snap to step=5
        const clamped = Math.min(500, Math.max(50, newChord));
        setParam('wingChord', clamped, 'slider');
      }
    },
    [design.wingSpan, setParam],
  );
  const handleArInputChange = useCallback(
    (ar: number) => {
      if (ar > 0) {
        const newChord = Math.round(design.wingSpan / ar / 5) * 5;
        const clamped = Math.min(500, Math.max(50, newChord));
        setParam('wingChord', clamped, 'text');
      }
    },
    [design.wingSpan, setParam],
  );

  // ── Slider handlers ─────────────────────────────────────────────────

  const setWingSpanSlider = useCallback(
    (v: number) => setParam('wingSpan', v, 'slider'),
    [setParam],
  );
  const setWingSpanInput = useCallback(
    (v: number) => setParam('wingSpan', v, 'text'),
    [setParam],
  );
  const setWingChordSlider = useCallback(
    (v: number) => setParam('wingChord', v, 'slider'),
    [setParam],
  );
  const setWingChordInput = useCallback(
    (v: number) => setParam('wingChord', v, 'text'),
    [setParam],
  );
  const setFuselageLengthSlider = useCallback(
    (v: number) => setParam('fuselageLength', v, 'slider'),
    [setParam],
  );
  const setFuselageLengthInput = useCallback(
    (v: number) => setParam('fuselageLength', v, 'text'),
    [setParam],
  );

  const warnText = (field: string) =>
    getFieldWarnings(warnings, field).map(formatWarning).join('\n') || undefined;

  return (
    <div className="p-3">
      <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
        Global Parameters
      </h3>

      {/* G01 — Fuselage Preset */}
      <div data-section="fuselage" />
      <ParamSelect
        label="Fuselage Style"
        value={design.fuselagePreset}
        options={FUSELAGE_PRESET_OPTIONS}
        onChange={setFuselagePreset}
        hasWarning={fieldHasWarning(warnings, 'fuselagePreset')}
        title="Overall body shape. Pod = simple tube, Conventional = tapered body, Blended-Wing-Body = flying wing."
      />

      {/* G02 — Motor (toggle: engineCount 0 = no motor, 1 = single motor) */}
      <div className="mb-3 flex items-center justify-between" title="Enable or disable the motor mount. Turn off for gliders.">
        <label
          htmlFor="motor-toggle"
          className="text-xs font-medium text-zinc-300 cursor-pointer"
        >
          Motor
        </label>
        <button
          id="motor-toggle"
          role="switch"
          aria-checked={design.engineCount === 1}
          onClick={() => handleMotorToggle({
            target: { checked: design.engineCount === 0 },
          } as React.ChangeEvent<HTMLInputElement>)}
          className={[
            'relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full',
            'border-2 border-transparent transition-colors duration-200',
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-zinc-900',
            design.engineCount === 1
              ? 'bg-blue-600'
              : 'bg-zinc-600',
          ].join(' ')}
        >
          <span
            aria-hidden="true"
            className={[
              'pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow',
              'transform transition duration-200',
              design.engineCount === 1 ? 'translate-x-4' : 'translate-x-0',
            ].join(' ')}
          />
        </button>
      </div>

      {/* P02 — Motor Config */}
      <ParamSelect
        label="Motor Position"
        value={design.motorConfig}
        options={MOTOR_CONFIG_OPTIONS}
        onChange={setMotorConfig}
        hasWarning={fieldHasWarning(warnings, 'motorConfig')}
        title="Tractor = motor at the front pulling the plane. Pusher = motor at the back pushing the plane."
      />

      {/* G03 — Wing Span */}
      <ParamSlider
        label="Wingspan"
        unit="mm"
        value={design.wingSpan}
        min={300}
        max={3000}
        step={10}
        onSliderChange={setWingSpanSlider}
        onInputChange={setWingSpanInput}
        hasWarning={fieldHasWarning(warnings, 'wingSpan')}
        warningText={warnText('wingSpan')}
        title="Total tip-to-tip wingspan. Most RC trainers are 900–1500 mm."
      />

      {/* G05 — Wing Chord / Aspect Ratio (bidirectional) */}
      <BidirectionalParam
        labelA="Wing Chord"
        labelB="Aspect Ratio"
        valueA={design.wingChord}
        valueB={Math.round(computedAspectRatio * 100) / 100}
        unitA="mm"
        minA={50}
        maxA={500}
        stepA={5}
        minB={2}
        maxB={30}
        stepB={0.5}
        mode={chordArMode}
        onModeChange={setChordArMode}
        onSliderChangeA={setWingChordSlider}
        onInputChangeA={setWingChordInput}
        onSliderChangeB={handleArSliderChange}
        onInputChangeB={handleArInputChange}
        hasWarningA={fieldHasWarning(warnings, 'wingChord')}
        warningTextA={warnText('wingChord')}
        decimalsA={0}
        decimalsB={2}
      />

      {/* F13 — Wing Placement */}
      <ParamSelect
        label="Wing Placement"
        value={design.wingMountType}
        options={WING_MOUNT_OPTIONS}
        onChange={setWingMountType}
        hasWarning={fieldHasWarning(warnings, 'wingMountType')}
        title="Where the wing attaches to the fuselage. High-wing is easiest to build and most stable for beginners."
      />

      {/* F01 — Fuselage Length */}
      <ParamSlider
        label="Fuselage Length"
        unit="mm"
        value={design.fuselageLength}
        min={150}
        max={2000}
        step={10}
        onSliderChange={setFuselageLengthSlider}
        onInputChange={setFuselageLengthInput}
        hasWarning={fieldHasWarning(warnings, 'fuselageLength')}
        warningText={warnText('fuselageLength')}
        title="Length of the main body from nose to tail. Does not include spinner or tail overhang."
      />

      {/* G06 — Tail Type */}
      <ParamSelect
        label="Tail Type"
        value={design.tailType}
        options={TAIL_TYPE_OPTIONS}
        onChange={setTailType}
        hasWarning={fieldHasWarning(warnings, 'tailType')}
        title="Tail configuration. Conventional = horizontal + vertical stabilizers. V-Tail = two angled surfaces instead of separate H and V stabilizers."
      />
    </div>
  );
}
