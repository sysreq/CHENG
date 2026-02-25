// ============================================================================
// CHENG — Wing Panel: Wing geometry + airfoil selection + derived values
// Issue #26 | Multi-section wings #143
// ============================================================================

import React, { useCallback, useState } from 'react';
import { useDesignStore } from '../../store/designStore';
import { fieldHasWarning, getFieldWarnings, formatWarning } from '../../lib/validation';
import { ParamSlider, ParamSelect, DerivedField } from '../ui';
import { PrintSettingsSection } from './PrintSettingsSection';
import type { WingAirfoil } from '../../types/design';

// ---------------------------------------------------------------------------
// Option Constants
// ---------------------------------------------------------------------------

const WING_AIRFOIL_OPTIONS: readonly WingAirfoil[] = [
  'Flat-Plate',
  'NACA-0012',
  'NACA-2412',
  'NACA-4412',
  'NACA-6412',
  'Clark-Y',
  'Eppler-193',
  'Eppler-387',
  'Selig-1223',
  'AG-25',
] as const;

// ---------------------------------------------------------------------------
// WingPanelSection sub-component (for each panel break when wingSections > 1)
// ---------------------------------------------------------------------------

interface WingPanelSectionProps {
  index: number; // 0-based index into panelBreakPositions/panelDihedrals/panelSweeps
}

function WingPanelSection({ index }: WingPanelSectionProps): React.JSX.Element {
  const design = useDesignStore((s) => s.design);
  const setPanelBreak = useDesignStore((s) => s.setPanelBreak);
  const setPanelDihedral = useDesignStore((s) => s.setPanelDihedral);
  const setPanelSweep = useDesignStore((s) => s.setPanelSweep);

  // Open by default for index 0 (first outer panel), collapsed for higher
  const [open, setOpen] = useState(index === 0);

  const breakVal = design.panelBreakPositions[index] ?? 60;
  const dihedralVal = design.panelDihedrals[index] ?? 10;
  const sweepVal = design.panelSweeps[index] ?? 0;

  const setBreak = useCallback(
    (v: number) => setPanelBreak(index, v),
    [setPanelBreak, index],
  );

  const setDihedral = useCallback(
    (v: number) => setPanelDihedral(index, v),
    [setPanelDihedral, index],
  );

  const setSweep = useCallback(
    (v: number) => setPanelSweep(index, v),
    [setPanelSweep, index],
  );

  // Inline validation: break must be < next break (if it exists)
  const nextBreak = design.panelBreakPositions[index + 1];
  const breakIsInvalid =
    index < design.panelBreakPositions.length - 1 &&
    nextBreak !== undefined &&
    breakVal >= nextBreak;

  const panelLabel = `Panel ${index + 2}`;

  return (
    <div className="border border-zinc-700/50 rounded mb-2 overflow-hidden">
      {/* Collapsible header */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-3 py-2 text-left bg-zinc-800/50 hover:bg-zinc-700/50 transition-colors"
      >
        <span className="text-xs font-medium text-zinc-300">
          {panelLabel}
          <span className="ml-1 text-zinc-500 font-normal">
            (break at {breakVal.toFixed(0)}%)
          </span>
        </span>
        <span className="text-zinc-500 text-xs">{open ? '▲' : '▼'}</span>
      </button>

      {/* Panel content */}
      {open && (
        <div className="px-3 pt-2 pb-1 bg-zinc-900/30">
          {/* Break Position */}
          <ParamSlider
            label="Break Position"
            unit="%"
            value={breakVal}
            min={10}
            max={90}
            step={1}
            onSliderChange={setBreak}
            onInputChange={setBreak}
            title={`Spanwise position of panel break ${index + 1} as % of half-span`}
          />
          {breakIsInvalid && nextBreak !== undefined && (
            <p className="text-[10px] text-red-400 mt-0.5 mb-1">
              Break must be less than Panel {index + 3} break (
              {nextBreak.toFixed(0)}%)
            </p>
          )}

          {/* Outer Dihedral */}
          <ParamSlider
            label="Outer Dihedral"
            unit="deg"
            value={dihedralVal}
            min={-10}
            max={45}
            step={0.5}
            onSliderChange={setDihedral}
            onInputChange={setDihedral}
            title={`Dihedral of panel ${index + 2}, measured from horizontal`}
          />

          {/* Outer Sweep */}
          <ParamSlider
            label="Outer Sweep"
            unit="deg"
            value={sweepVal}
            min={-10}
            max={45}
            step={1}
            onSliderChange={setSweep}
            onInputChange={setSweep}
            title={`Leading-edge sweep of panel ${index + 2}. Defaults to global sweep when section is created.`}
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main WingPanel Component
// ---------------------------------------------------------------------------

export function WingPanel(): React.JSX.Element {
  const design = useDesignStore((s) => s.design);
  const derived = useDesignStore((s) => s.derived);
  const warnings = useDesignStore((s) => s.warnings);
  const setParam = useDesignStore((s) => s.setParam);

  // ── Dropdown (immediate) ────────────────────────────────────────────

  const setWingAirfoil = useCallback(
    (v: WingAirfoil) => setParam('wingAirfoil', v, 'immediate'),
    [setParam],
  );

  // ── Sliders ─────────────────────────────────────────────────────────

  const setSectionsSlider = useCallback(
    (v: number) => setParam('wingSections', Math.round(v), 'immediate'),
    [setParam],
  );
  const setSectionsInput = useCallback(
    (v: number) => setParam('wingSections', Math.round(v), 'immediate'),
    [setParam],
  );

  const setSweepSlider = useCallback(
    (v: number) => setParam('wingSweep', v, 'slider'),
    [setParam],
  );
  const setSweepInput = useCallback(
    (v: number) => setParam('wingSweep', v, 'text'),
    [setParam],
  );

  const setTipRootSlider = useCallback(
    (v: number) => setParam('wingTipRootRatio', v, 'slider'),
    [setParam],
  );
  const setTipRootInput = useCallback(
    (v: number) => setParam('wingTipRootRatio', v, 'text'),
    [setParam],
  );

  const setDihedralSlider = useCallback(
    (v: number) => setParam('wingDihedral', v, 'slider'),
    [setParam],
  );
  const setDihedralInput = useCallback(
    (v: number) => setParam('wingDihedral', v, 'text'),
    [setParam],
  );

  const setIncidenceSlider = useCallback(
    (v: number) => setParam('wingIncidence', v, 'slider'),
    [setParam],
  );
  const setIncidenceInput = useCallback(
    (v: number) => setParam('wingIncidence', v, 'text'),
    [setParam],
  );

  const setTwistSlider = useCallback(
    (v: number) => setParam('wingTwist', v, 'slider'),
    [setParam],
  );
  const setTwistInput = useCallback(
    (v: number) => setParam('wingTwist', v, 'text'),
    [setParam],
  );

  const setSkinSlider = useCallback(
    (v: number) => setParam('wingSkinThickness', v, 'slider'),
    [setParam],
  );
  const setSkinInput = useCallback(
    (v: number) => setParam('wingSkinThickness', v, 'text'),
    [setParam],
  );

  const warnText = (field: string) =>
    getFieldWarnings(warnings, field).map(formatWarning).join('\n') || undefined;

  return (
    <div className="p-3">
      <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
        Wing
      </h3>

      {/* W12 — Wing Airfoil */}
      <ParamSelect
        label="Airfoil"
        value={design.wingAirfoil}
        options={WING_AIRFOIL_OPTIONS}
        onChange={setWingAirfoil}
        hasWarning={fieldHasWarning(warnings, 'wingAirfoil')}
      />

      {/* W08 — Wing Sections (multi-section #143) */}
      <ParamSlider
        label="Wing Sections"
        value={design.wingSections}
        min={1}
        max={4}
        step={1}
        onSliderChange={setSectionsSlider}
        onInputChange={setSectionsInput}
        title="Number of spanwise wing panels per half. 1 = straight, 2–4 = polyhedral or cranked planform."
      />

      {/* W05 — Wing Sweep */}
      <ParamSlider
        label="Sweep Angle"
        unit="deg"
        value={design.wingSweep}
        min={-10}
        max={45}
        step={1}
        onSliderChange={setSweepSlider}
        onInputChange={setSweepInput}
        hasWarning={fieldHasWarning(warnings, 'wingSweep')}
        warningText={warnText('wingSweep')}
      />

      {/* W04 — Wing Tip/Root Ratio */}
      <ParamSlider
        label="Tip/Root Chord Ratio"
        unit="ratio"
        value={design.wingTipRootRatio}
        min={0.3}
        max={1.0}
        step={0.01}
        onSliderChange={setTipRootSlider}
        onInputChange={setTipRootInput}
        hasWarning={fieldHasWarning(warnings, 'wingTipRootRatio')}
        warningText={warnText('wingTipRootRatio')}
        title="1.0 = rectangular wing, lower values = more tapered toward the tip"
      />

      {/* W07 — Wing Dihedral (panel 1) */}
      <ParamSlider
        label={design.wingSections > 1 ? 'Panel 1 Dihedral' : 'Dihedral'}
        unit="deg"
        value={design.wingDihedral}
        min={-10}
        max={15}
        step={0.5}
        onSliderChange={setDihedralSlider}
        onInputChange={setDihedralInput}
        hasWarning={fieldHasWarning(warnings, 'wingDihedral')}
        warningText={warnText('wingDihedral')}
      />

      {/* W08 — Wing Incidence */}
      <ParamSlider
        label="Incidence"
        unit="deg"
        value={design.wingIncidence}
        min={-5}
        max={15}
        step={0.5}
        onSliderChange={setIncidenceSlider}
        onInputChange={setIncidenceInput}
        hasWarning={fieldHasWarning(warnings, 'wingIncidence')}
      />

      {/* W06 — Wing Twist (washout) */}
      <ParamSlider
        label="Twist (washout)"
        unit="deg"
        value={design.wingTwist}
        min={-5}
        max={5}
        step={0.5}
        onSliderChange={setTwistSlider}
        onInputChange={setTwistInput}
        hasWarning={fieldHasWarning(warnings, 'wingTwist')}
        title="Negative = washout (tip nose-down), positive = washin"
      />

      {/* W20 — Wing Skin Thickness */}
      <ParamSlider
        label="Skin Thickness"
        unit="mm"
        value={design.wingSkinThickness}
        min={0.8}
        max={3.0}
        step={0.1}
        onSliderChange={setSkinSlider}
        onInputChange={setSkinInput}
        hasWarning={fieldHasWarning(warnings, 'wingSkinThickness')}
        warningText={warnText('wingSkinThickness')}
      />

      {/* ── Wing Panel Breaks (conditional: wingSections > 1) (#143) ── */}
      {design.wingSections > 1 && (
        <div className="mt-3">
          <div className="border-t border-zinc-700/50 mb-3" />
          <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
            Wing Panel Breaks
          </h4>
          {Array.from({ length: design.wingSections - 1 }, (_, i) => (
            <WingPanelSection key={i} index={i} />
          ))}
        </div>
      )}

      {/* ── Derived Values ─────────────────────────────────────────── */}
      <div className="border-t border-zinc-700/50 mt-4 mb-3" />
      <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
        Computed Values
      </h4>

      <DerivedField
        label="Tip Chord"
        value={derived?.tipChordMm ?? null}
        unit="mm"
        decimals={1}
      />
      <DerivedField
        label="Wing Area"
        value={derived?.wingAreaCm2 ?? null}
        unit="cm&#178;"
        decimals={1}
      />
      <DerivedField
        label="Aspect Ratio"
        value={derived?.aspectRatio ?? null}
        decimals={2}
      />
      <DerivedField
        label="Mean Aero Chord"
        value={derived?.meanAeroChordMm ?? null}
        unit="mm"
        decimals={1}
      />
      <DerivedField
        label="Taper Ratio"
        value={derived?.taperRatio ?? null}
        decimals={3}
      />
      <DerivedField
        label="Estimated CG"
        value={derived?.estimatedCgMm ?? null}
        unit="mm"
        decimals={1}
        suffix="from wing LE"
      />

      {/* ── Per-Component Print Settings (#128) ────────────────────── */}
      <PrintSettingsSection component="wing" />
    </div>
  );
}
