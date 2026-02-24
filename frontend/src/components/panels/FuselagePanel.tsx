// ============================================================================
// CHENG — Fuselage Panel: Fuselage geometry params + computed section lengths
// Issue #120
// ============================================================================

import React, { useCallback, useMemo } from 'react';
import { useDesignStore } from '../../store/designStore';
import { fieldHasWarning, getFieldWarnings, formatWarning } from '../../lib/validation';
import { ParamSlider, ParamSelect, DerivedField } from '../ui';
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
// Section Length Computation
// Mirrors backend/geometry/fuselage.py zone ratios per preset
// ---------------------------------------------------------------------------

interface SectionBreakdown {
  noseLength: number;
  cabinLength: number;
  tailConeLength: number;
}

function computeSectionBreakdown(
  fuselagePreset: FuselagePreset,
  fuselageLength: number,
): SectionBreakdown {
  switch (fuselagePreset) {
    case 'Conventional':
      // Nose 25%, Cabin 50%, Tail cone 25%
      return {
        noseLength: fuselageLength * 0.25,
        cabinLength: fuselageLength * 0.50,
        tailConeLength: fuselageLength * 0.25,
      };
    case 'Pod':
      // Nose 15%, Cabin 60%, Tail cone 25%
      return {
        noseLength: fuselageLength * 0.15,
        cabinLength: fuselageLength * 0.60,
        tailConeLength: fuselageLength * 0.25,
      };
    case 'Blended-Wing-Body':
      // BWB uses a single loft, approximate as 20/50/30
      return {
        noseLength: fuselageLength * 0.20,
        cabinLength: fuselageLength * 0.50,
        tailConeLength: fuselageLength * 0.30,
      };
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FuselagePanel(): React.JSX.Element {
  const design = useDesignStore((s) => s.design);
  const derived = useDesignStore((s) => s.derived);
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

  // ── Computed section breakdown ──────────────────────────────────────

  const sections = useMemo(
    () => computeSectionBreakdown(design.fuselagePreset, design.fuselageLength),
    [design.fuselagePreset, design.fuselageLength],
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

      {/* ── Computed Section Breakdown ──────────────────────────────── */}
      <div className="border-t border-zinc-700/50 mt-4 mb-3" />
      <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
        Section Breakdown
      </h4>

      <DerivedField
        label="Nose Length"
        value={sections.noseLength}
        unit="mm"
        decimals={1}
      />
      <DerivedField
        label="Cabin Length"
        value={sections.cabinLength}
        unit="mm"
        decimals={1}
      />
      <DerivedField
        label="Tail Cone Length"
        value={sections.tailConeLength}
        unit="mm"
        decimals={1}
      />

      {/* Wall thickness from backend derived values */}
      <DerivedField
        label="Wall Thickness"
        value={derived?.wallThicknessMm ?? null}
        unit="mm"
        decimals={1}
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
