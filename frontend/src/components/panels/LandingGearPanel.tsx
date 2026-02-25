// ============================================================================
// CHENG — Landing Gear Panel: Gear type selection + conditional parameters
// Issue #145
// ============================================================================

import React, { useCallback } from 'react';
import { useDesignStore } from '../../store/designStore';
import { fieldHasWarning, getFieldWarnings, formatWarning } from '../../lib/validation';
import { ParamSlider, ParamSelect } from '../ui';
import { PrintSettingsSection } from './PrintSettingsSection';
import type { LandingGearType } from '../../types/design';

// ---------------------------------------------------------------------------
// Option Constants
// ---------------------------------------------------------------------------

const GEAR_TYPE_OPTIONS: readonly LandingGearType[] = [
  'None',
  'Tricycle',
  'Taildragger',
] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LandingGearPanel(): React.JSX.Element {
  const design = useDesignStore((s) => s.design);
  const warnings = useDesignStore((s) => s.warnings);
  const setParam = useDesignStore((s) => s.setParam);

  // ── Gear Type (immediate — triggers full rebuild) ──────────────────
  const setGearType = useCallback(
    (v: LandingGearType) => setParam('landingGearType', v, 'immediate'),
    [setParam],
  );

  // ── Main Gear sliders ─────────────────────────────────────────────
  const setMainGearPositionSlider = useCallback(
    (v: number) => setParam('mainGearPosition', v, 'slider'),
    [setParam],
  );
  const setMainGearPositionInput = useCallback(
    (v: number) => setParam('mainGearPosition', v, 'text'),
    [setParam],
  );

  const setMainGearHeightSlider = useCallback(
    (v: number) => setParam('mainGearHeight', v, 'slider'),
    [setParam],
  );
  const setMainGearHeightInput = useCallback(
    (v: number) => setParam('mainGearHeight', v, 'text'),
    [setParam],
  );

  const setMainGearTrackSlider = useCallback(
    (v: number) => setParam('mainGearTrack', v, 'slider'),
    [setParam],
  );
  const setMainGearTrackInput = useCallback(
    (v: number) => setParam('mainGearTrack', v, 'text'),
    [setParam],
  );

  const setMainWheelDiameterSlider = useCallback(
    (v: number) => setParam('mainWheelDiameter', v, 'slider'),
    [setParam],
  );
  const setMainWheelDiameterInput = useCallback(
    (v: number) => setParam('mainWheelDiameter', v, 'text'),
    [setParam],
  );

  // ── Nose Gear sliders (Tricycle only) ─────────────────────────────
  const setNoseGearHeightSlider = useCallback(
    (v: number) => setParam('noseGearHeight', v, 'slider'),
    [setParam],
  );
  const setNoseGearHeightInput = useCallback(
    (v: number) => setParam('noseGearHeight', v, 'text'),
    [setParam],
  );

  const setNoseWheelDiameterSlider = useCallback(
    (v: number) => setParam('noseWheelDiameter', v, 'slider'),
    [setParam],
  );
  const setNoseWheelDiameterInput = useCallback(
    (v: number) => setParam('noseWheelDiameter', v, 'text'),
    [setParam],
  );

  // ── Tail Wheel sliders (Taildragger only) ─────────────────────────
  const setTailWheelDiameterSlider = useCallback(
    (v: number) => setParam('tailWheelDiameter', v, 'slider'),
    [setParam],
  );
  const setTailWheelDiameterInput = useCallback(
    (v: number) => setParam('tailWheelDiameter', v, 'text'),
    [setParam],
  );

  const setTailGearPositionSlider = useCallback(
    (v: number) => setParam('tailGearPosition', v, 'slider'),
    [setParam],
  );
  const setTailGearPositionInput = useCallback(
    (v: number) => setParam('tailGearPosition', v, 'text'),
    [setParam],
  );

  // ── Derived booleans for conditional rendering ─────────────────────
  const hasSomeGear = design.landingGearType !== 'None';
  const isTricycle = design.landingGearType === 'Tricycle';
  const isTaildragger = design.landingGearType === 'Taildragger';

  const warnText = (field: string) =>
    getFieldWarnings(warnings, field).map(formatWarning).join('\n') || undefined;

  return (
    <div className="p-3">
      <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
        Landing Gear
      </h3>

      {/* L01 — Gear Type */}
      <ParamSelect
        label="Gear Type"
        value={design.landingGearType}
        options={GEAR_TYPE_OPTIONS}
        onChange={setGearType}
        hasWarning={fieldHasWarning(warnings, 'landingGearType')}
        title="None = belly landing. Tricycle = nose wheel + two mains. Taildragger = two mains + rear tail wheel."
      />

      {/* None — info message */}
      {!hasSomeGear && (
        <p className="text-[10px] text-zinc-500 leading-relaxed mb-3">
          No landing gear will be generated. The plane belly-lands. Select Tricycle or
          Taildragger to add printed gear struts.
        </p>
      )}

      {/* ── Main Gear — shown for Tricycle and Taildragger ──────────── */}
      {hasSomeGear && (
        <>
          <div className="border-t border-zinc-700/50 mt-3 mb-2" />
          <h4 className="text-[10px] font-medium text-zinc-500 uppercase mb-2">
            Main Gear
          </h4>

          {/* L03 — Main Gear Position */}
          <ParamSlider
            label="Position"
            unit="%"
            value={design.mainGearPosition}
            min={25}
            max={55}
            step={1}
            onSliderChange={setMainGearPositionSlider}
            onInputChange={setMainGearPositionInput}
            hasWarning={fieldHasWarning(warnings, 'mainGearPosition')}
            warningText={warnText('mainGearPosition')}
            title="Longitudinal position of main gear axle as % of fuselage length from nose. Should be behind the CG for tricycle, at/near CG for taildragger."
          />

          {/* L04 — Main Gear Height */}
          <ParamSlider
            label="Strut Height"
            unit="mm"
            value={design.mainGearHeight}
            min={15}
            max={150}
            step={1}
            onSliderChange={setMainGearHeightSlider}
            onInputChange={setMainGearHeightInput}
            hasWarning={fieldHasWarning(warnings, 'mainGearHeight')}
            warningText={warnText('mainGearHeight')}
            title="Height of the main gear strut. Determines ground clearance for the propeller and fuselage."
          />

          {/* L05 — Main Gear Track */}
          <ParamSlider
            label="Track Width"
            unit="mm"
            value={design.mainGearTrack}
            min={30}
            max={400}
            step={5}
            onSliderChange={setMainGearTrackSlider}
            onInputChange={setMainGearTrackInput}
            hasWarning={fieldHasWarning(warnings, 'mainGearTrack')}
            warningText={warnText('mainGearTrack')}
            title="Lateral distance between left and right main wheel axles."
          />

          {/* L06 — Main Wheel Diameter */}
          <ParamSlider
            label="Wheel Diameter"
            unit="mm"
            value={design.mainWheelDiameter}
            min={10}
            max={80}
            step={1}
            onSliderChange={setMainWheelDiameterSlider}
            onInputChange={setMainWheelDiameterInput}
            hasWarning={fieldHasWarning(warnings, 'mainWheelDiameter')}
            title="Main wheel diameter. Match to your purchased wheels or print custom wheels."
          />
        </>
      )}

      {/* ── Nose Gear — Tricycle only ─────────────────────────────── */}
      {isTricycle && (
        <>
          <div className="border-t border-zinc-700/50 mt-3 mb-2" />
          <h4 className="text-[10px] font-medium text-zinc-500 uppercase mb-2">
            Nose Gear
          </h4>

          {/* L08 — Nose Gear Height */}
          <ParamSlider
            label="Strut Height"
            unit="mm"
            value={design.noseGearHeight}
            min={15}
            max={150}
            step={1}
            onSliderChange={setNoseGearHeightSlider}
            onInputChange={setNoseGearHeightInput}
            hasWarning={fieldHasWarning(warnings, 'noseGearHeight')}
            title="Nose gear strut height. Should be similar to or slightly shorter than the main gear height for level ground stance."
          />

          {/* L09 — Nose Wheel Diameter */}
          <ParamSlider
            label="Wheel Diameter"
            unit="mm"
            value={design.noseWheelDiameter}
            min={8}
            max={60}
            step={1}
            onSliderChange={setNoseWheelDiameterSlider}
            onInputChange={setNoseWheelDiameterInput}
            hasWarning={fieldHasWarning(warnings, 'noseWheelDiameter')}
            title="Nose wheel diameter. Usually smaller than main wheels."
          />
        </>
      )}

      {/* ── Tail Wheel — Taildragger only ─────────────────────────── */}
      {isTaildragger && (
        <>
          <div className="border-t border-zinc-700/50 mt-3 mb-2" />
          <h4 className="text-[10px] font-medium text-zinc-500 uppercase mb-2">
            Tail Wheel
          </h4>

          {/* L10 — Tail Wheel Diameter */}
          <ParamSlider
            label="Wheel Diameter"
            unit="mm"
            value={design.tailWheelDiameter}
            min={5}
            max={40}
            step={1}
            onSliderChange={setTailWheelDiameterSlider}
            onInputChange={setTailWheelDiameterInput}
            hasWarning={fieldHasWarning(warnings, 'tailWheelDiameter')}
            title="Tail wheel diameter. Usually much smaller than main wheels (e.g. 12 mm vs 30 mm mains)."
          />

          {/* L11 — Tail Gear Position */}
          <ParamSlider
            label="Position"
            unit="%"
            value={design.tailGearPosition}
            min={85}
            max={98}
            step={1}
            onSliderChange={setTailGearPositionSlider}
            onInputChange={setTailGearPositionInput}
            hasWarning={fieldHasWarning(warnings, 'tailGearPosition')}
            title="Longitudinal position of tail wheel as % of fuselage length from nose. Typically near the very tail of the fuselage."
          />
        </>
      )}

      {/* ── Material note for printed gear ────────────────────────── */}
      {hasSomeGear && (
        <div className="mt-3 px-2 py-2 text-[10px] text-amber-200 bg-amber-900/20
          border border-amber-700/30 rounded leading-relaxed">
          Note: Printed PLA gear struts can be fragile. Consider PETG or Nylon for
          struts, or use bent music wire in printed guide brackets.
        </div>
      )}

      {/* ── V31 gear warnings ─────────────────────────────────────── */}
      {hasSomeGear && fieldHasWarning(warnings, 'mainGearPosition') && (
        <div className="mt-2 px-2 py-1 text-[10px] text-yellow-200 bg-yellow-900/20
          border border-yellow-700/30 rounded leading-relaxed">
          {warnText('mainGearPosition')}
        </div>
      )}

      {/* ── Per-Component Print Settings ──────────────────────────── */}
      <PrintSettingsSection component="landing_gear" />
    </div>
  );
}
