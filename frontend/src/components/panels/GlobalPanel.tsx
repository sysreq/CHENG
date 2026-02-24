// ============================================================================
// CHENG — Global Panel: Core aircraft parameters + preset selector
// Issue #25
// ============================================================================

import React, { useCallback } from 'react';
import { useDesignStore } from '../../store/designStore';
import { PRESET_DESCRIPTIONS } from '../../lib/presets';
import { fieldHasWarning } from '../../lib/validation';
import { ParamSlider, ParamSelect } from '../ui';
import type {
  PresetName,
  FuselagePreset,
  MotorConfig,
  WingMountType,
  TailType,
} from '../../types/design';

// ---------------------------------------------------------------------------
// Option Constants
// ---------------------------------------------------------------------------

const PRESET_OPTIONS: readonly (Exclude<PresetName, 'Custom'>)[] = [
  'Trainer',
  'Sport',
  'Aerobatic',
] as const;

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
  const activePreset = useDesignStore((s) => s.activePreset);
  const warnings = useDesignStore((s) => s.warnings);
  const setParam = useDesignStore((s) => s.setParam);
  const loadPreset = useDesignStore((s) => s.loadPreset);

  // ── Preset ──────────────────────────────────────────────────────────

  const handlePresetChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const value = e.target.value as PresetName;
      if (value !== 'Custom') {
        loadPreset(value);
      }
    },
    [loadPreset],
  );

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

  // ── Engine count (number input — text source) ───────────────────────

  const handleEngineCountChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseInt(e.target.value, 10);
      if (!Number.isNaN(val) && val >= 0 && val <= 4) {
        setParam('engineCount', val, 'text');
      }
    },
    [setParam],
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

  return (
    <div className="p-3">
      {/* ── Preset Selector ─────────────────────────────────────────── */}
      <div className="mb-4">
        <label className="block text-xs font-medium text-zinc-300 mb-1">Preset</label>
        <select
          value={activePreset}
          onChange={handlePresetChange}
          className="w-full px-2 py-1.5 text-xs text-zinc-100 bg-zinc-800
            border border-zinc-700 rounded cursor-pointer
            focus:outline-none focus:border-blue-500"
        >
          {PRESET_OPTIONS.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
          {activePreset === 'Custom' && (
            <option value="Custom" disabled>
              Custom
            </option>
          )}
        </select>
        {activePreset !== 'Custom' && (
          <p className="mt-1 text-[10px] text-zinc-500">
            {PRESET_DESCRIPTIONS[activePreset]}
          </p>
        )}
      </div>

      {/* ── Separator ───────────────────────────────────────────────── */}
      <div className="border-t border-zinc-700/50 mb-3" />

      <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
        Global Parameters
      </h3>

      {/* G01 — Fuselage Preset */}
      <ParamSelect
        label="Fuselage Style"
        value={design.fuselagePreset}
        options={FUSELAGE_PRESET_OPTIONS}
        onChange={setFuselagePreset}
        hasWarning={fieldHasWarning(warnings, 'fuselagePreset')}
      />

      {/* G02 — Engine Count */}
      <div className="mb-3">
        <label className="block text-xs font-medium text-zinc-300 mb-1">
          Engine Count
        </label>
        <input
          type="number"
          min={0}
          max={4}
          step={1}
          value={design.engineCount}
          onChange={handleEngineCountChange}
          className="w-full px-2 py-1 text-xs text-zinc-100 bg-zinc-800
            border border-zinc-700 rounded focus:outline-none focus:border-blue-500
            [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none
            [&::-webkit-inner-spin-button]:appearance-none"
        />
      </div>

      {/* P02 — Motor Config */}
      <ParamSelect
        label="Motor Position"
        value={design.motorConfig}
        options={MOTOR_CONFIG_OPTIONS}
        onChange={setMotorConfig}
        hasWarning={fieldHasWarning(warnings, 'motorConfig')}
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
      />

      {/* G05 — Wing Chord */}
      <ParamSlider
        label="Wing Chord"
        unit="mm"
        value={design.wingChord}
        min={50}
        max={500}
        step={5}
        onSliderChange={setWingChordSlider}
        onInputChange={setWingChordInput}
        hasWarning={fieldHasWarning(warnings, 'wingChord')}
      />

      {/* F13 — Wing Mount Type */}
      <ParamSelect
        label="Wing Mount"
        value={design.wingMountType}
        options={WING_MOUNT_OPTIONS}
        onChange={setWingMountType}
        hasWarning={fieldHasWarning(warnings, 'wingMountType')}
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
      />

      {/* G06 — Tail Type */}
      <ParamSelect
        label="Tail Type"
        value={design.tailType}
        options={TAIL_TYPE_OPTIONS}
        onChange={setTailType}
        hasWarning={fieldHasWarning(warnings, 'tailType')}
      />
    </div>
  );
}
