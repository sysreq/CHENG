// ============================================================================
// CHENG — Wing Panel: Wing geometry + airfoil selection + derived values
// Issue #26
// ============================================================================

import React, { useCallback } from 'react';
import { useDesignStore } from '../../store/designStore';
import { fieldHasWarning } from '../../lib/validation';
import { ParamSlider, ParamSelect, DerivedField } from '../ui';
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
// Component
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

  const setSkinSlider = useCallback(
    (v: number) => setParam('wingSkinThickness', v, 'slider'),
    [setParam],
  );
  const setSkinInput = useCallback(
    (v: number) => setParam('wingSkinThickness', v, 'text'),
    [setParam],
  );

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
      />

      {/* W04 — Wing Tip/Root Ratio */}
      <ParamSlider
        label="Tip/Root Chord Ratio"
        value={design.wingTipRootRatio}
        min={0.3}
        max={1.0}
        step={0.01}
        onSliderChange={setTipRootSlider}
        onInputChange={setTipRootInput}
        hasWarning={fieldHasWarning(warnings, 'wingTipRootRatio')}
      />

      {/* W07 — Wing Dihedral */}
      <ParamSlider
        label="Dihedral"
        unit="deg"
        value={design.wingDihedral}
        min={-10}
        max={15}
        step={0.5}
        onSliderChange={setDihedralSlider}
        onInputChange={setDihedralInput}
        hasWarning={fieldHasWarning(warnings, 'wingDihedral')}
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
      />

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
    </div>
  );
}
