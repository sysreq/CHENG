// ============================================================================
// CHENG — Fuselage Panel: Fuselage geometry params + computed section lengths
// Issue #120
// ============================================================================

import React, { useCallback } from 'react';
import { useDesignStore } from '../../store/designStore';
import { fieldHasWarning, getFieldWarnings, formatWarning } from '../../lib/validation';
import { ParamSlider, ParamSelect } from '../ui';
import { PrintSettingsSection } from './PrintSettingsSection';
import type { FuselagePreset, MotorConfig, WingMountType } from '../../types/design';

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

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FuselagePanel(): React.JSX.Element {
  const design = useDesignStore((s) => s.design);
  const warnings = useDesignStore((s) => s.warnings);
  const setParam = useDesignStore((s) => s.setParam);
  const setSelectedComponent = useDesignStore((s) => s.setSelectedComponent);

  // ── Dropdown (immediate) ────────────────────────────────────────────

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

  // ── Sliders ─────────────────────────────────────────────────────────

  const setLengthSlider = useCallback(
    (v: number) => setParam('fuselageLength', v, 'slider'),
    [setParam],
  );
  const setLengthInput = useCallback(
    (v: number) => setParam('fuselageLength', v, 'text'),
    [setParam],
  );

  // ── Section transition-point sliders (F11/F12) ──────────────────────
  // noseCabinBreakPct: where nose ends / cabin begins (% of fuselage length)
  // cabinTailBreakPct: where cabin ends / tail begins (% of fuselage length)
  // Constraint: noseCabinBreakPct < cabinTailBreakPct (enforced via dynamic min/max)

  const setNoseCabinBreakSlider = useCallback(
    (v: number) => setParam('noseCabinBreakPct', v, 'slider'),
    [setParam],
  );
  const setNoseCabinBreakInput = useCallback(
    (v: number) => setParam('noseCabinBreakPct', v, 'text'),
    [setParam],
  );

  const setCabinTailBreakSlider = useCallback(
    (v: number) => setParam('cabinTailBreakPct', v, 'slider'),
    [setParam],
  );
  const setCabinTailBreakInput = useCallback(
    (v: number) => setParam('cabinTailBreakPct', v, 'text'),
    [setParam],
  );

  // ── Wall thickness (F14) ──────────────────────────────────────────

  const setWallThicknessSlider = useCallback(
    (v: number) => setParam('wallThickness', v, 'slider'),
    [setParam],
  );
  const setWallThicknessInput = useCallback(
    (v: number) => setParam('wallThickness', v, 'text'),
    [setParam],
  );

  // ── Navigate to Global panel ────────────────────────────────────────

  const goToGlobal = useCallback(() => {
    setSelectedComponent(null);
  }, [setSelectedComponent]);

  const warnText = (field: string) =>
    getFieldWarnings(warnings, field).map(formatWarning).join('\n') || undefined;

  return (
    <div className="p-3">
      <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
        Fuselage
      </h3>

      {/* G01 — Fuselage Preset */}
      <ParamSelect
        label="Fuselage Style"
        value={design.fuselagePreset}
        options={FUSELAGE_PRESET_OPTIONS}
        onChange={setFuselagePreset}
        hasWarning={fieldHasWarning(warnings, 'fuselagePreset')}
      />

      {/* F01 — Fuselage Length */}
      <ParamSlider
        label="Fuselage Length"
        unit="mm"
        value={design.fuselageLength}
        min={150}
        max={2000}
        step={10}
        onSliderChange={setLengthSlider}
        onInputChange={setLengthInput}
        hasWarning={fieldHasWarning(warnings, 'fuselageLength')}
        warningText={warnText('fuselageLength')}
      />

      {/* P02 — Motor Config */}
      <ParamSelect
        label="Motor Position"
        value={design.motorConfig}
        options={MOTOR_CONFIG_OPTIONS}
        onChange={setMotorConfig}
        hasWarning={fieldHasWarning(warnings, 'motorConfig')}
      />

      {/* F13 — Wing Mount Type */}
      <ParamSelect
        label="Wing Mount"
        value={design.wingMountType}
        options={WING_MOUNT_OPTIONS}
        onChange={setWingMountType}
        hasWarning={fieldHasWarning(warnings, 'wingMountType')}
      />

      {/* ── Section Transition Points (F11/F12) ─────────────────────── */}
      <div className="border-t border-zinc-700/50 mt-4 mb-3" />
      <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
        Section Proportions
      </h4>

      <ParamSlider
        label="Nose/Cabin Break"
        unit="%"
        value={design.noseCabinBreakPct}
        min={10}
        max={design.cabinTailBreakPct - 5}
        step={1}
        onSliderChange={setNoseCabinBreakSlider}
        onInputChange={setNoseCabinBreakInput}
        hasWarning={fieldHasWarning(warnings, 'noseCabinBreakPct')}
        warningText={warnText('noseCabinBreakPct')}
      />
      <ParamSlider
        label="Cabin/Tail Break"
        unit="%"
        value={design.cabinTailBreakPct}
        min={design.noseCabinBreakPct + 5}
        max={90}
        step={1}
        onSliderChange={setCabinTailBreakSlider}
        onInputChange={setCabinTailBreakInput}
        hasWarning={fieldHasWarning(warnings, 'cabinTailBreakPct')}
        warningText={warnText('cabinTailBreakPct')}
      />

      {/* Computed section length summary */}
      {(() => {
        const L = design.fuselageLength;
        const noseMm = (design.noseCabinBreakPct / 100) * L;
        const cabinMm = ((design.cabinTailBreakPct - design.noseCabinBreakPct) / 100) * L;
        const tailMm = ((100 - design.cabinTailBreakPct) / 100) * L;
        return (
          <div className="text-xs text-zinc-500 mt-1 mb-2">
            Nose: {noseMm.toFixed(0)} mm | Cabin: {cabinMm.toFixed(0)} mm | Tail: {tailMm.toFixed(0)} mm
          </div>
        );
      })()}

      {/* F14 — Wall Thickness */}
      <ParamSlider
        label="Wall Thickness"
        unit="mm"
        value={design.wallThickness}
        min={0.8}
        max={4.0}
        step={0.1}
        onSliderChange={setWallThicknessSlider}
        onInputChange={setWallThicknessInput}
        hasWarning={fieldHasWarning(warnings, 'wallThickness')}
        warningText={warnText('wallThickness')}
      />

      {/* ── Per-Component Print Settings (#128) ────────────────────── */}
      <PrintSettingsSection component="fuselage" />

      {/* ── Link to Global Panel ───────────────────────────────────── */}
      <div className="border-t border-zinc-700/50 mt-4 mb-3" />
      <button
        onClick={goToGlobal}
        className="text-xs text-blue-400 hover:text-blue-300 underline
          focus:outline-none focus:ring-1 focus:ring-blue-500 rounded px-1"
        type="button"
      >
        Configure in Global Panel
      </button>
    </div>
  );
}
