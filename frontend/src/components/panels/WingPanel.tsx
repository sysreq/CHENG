// ============================================================================
// CHENG — Wing Panel: Wing geometry + airfoil selection + derived values
// Issue #26 | Multi-section wings #143 | Control surfaces #144
// Issue #154 — Parameter renaming for beginners
// ============================================================================

import React, { useState, useCallback } from 'react';
import { useDesignStore } from '../../store/designStore';
import { fieldHasWarning, getFieldWarnings, formatWarning } from '../../lib/validation';
import { ParamSlider, ParamSelect, DerivedField } from '../ui';
import { PrintSettingsSection } from './PrintSettingsSection';
import { ControlSurfaceSection } from './shared/ControlSurfaceSection';
import type { WingAirfoil } from '../../types/design';

// (Re-exported so WingPanelSection can use without prop-drilling)
const WING_AIRFOIL_OPTIONS_LIST: readonly WingAirfoil[] = [
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
// Option Constants
// ---------------------------------------------------------------------------

const WING_AIRFOIL_OPTIONS: readonly WingAirfoil[] = WING_AIRFOIL_OPTIONS_LIST;

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
  const setPanelAirfoil = useDesignStore((s) => s.setPanelAirfoil);

  // Open by default for index 0 (first outer panel), collapsed for higher
  const [open, setOpen] = useState(index === 0);

  const breakVal = design.panelBreakPositions[index] ?? 60;
  const dihedralVal = design.panelDihedrals[index] ?? 10;
  const sweepVal = design.panelSweeps[index] ?? 0;
  const airfoilVal = design.panelAirfoils[index] ?? null;

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

  const setAirfoil = useCallback(
    (v: WingAirfoil | null) => setPanelAirfoil(index, v),
    [setPanelAirfoil, index],
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
            title={`How much panel ${index + 2} tilts upward from horizontal. Positive = tips up.`}
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

          {/* W12 — Airfoil override for this panel */}
          <div className="flex items-center justify-between py-1">
            <span
              className="text-xs text-zinc-400"
              title={`Airfoil profile for panel ${index + 2}. "(inherit)" uses the root airfoil.`}
            >
              Airfoil
            </span>
            <select
              value={airfoilVal ?? ''}
              onChange={(e) => {
                const v = e.target.value;
                setAirfoil(v === '' ? null : (v as WingAirfoil));
              }}
              className="text-xs bg-zinc-800 border border-zinc-700 rounded px-1.5 py-0.5 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
              title={`Airfoil for panel ${index + 2}. Leave blank to inherit the root airfoil (${design.wingAirfoil}).`}
            >
              <option value="">(inherit {design.wingAirfoil})</option>
              {WING_AIRFOIL_OPTIONS_LIST.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
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

  // ── Wing Panels stepper (#243) ───────────────────────────────────────
  const wingSections = design.wingSections;
  const decrementSections = useCallback(
    () => setParam('wingSections', Math.max(1, wingSections - 1), 'immediate'),
    [setParam, wingSections],
  );
  const incrementSections = useCallback(
    () => setParam('wingSections', Math.min(4, wingSections + 1), 'immediate'),
    [setParam, wingSections],
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

  // ── Aileron handlers ────────────────────────────────────────────────
  const setAileronEnable = useCallback(
    (v: boolean) => setParam('aileronEnable', v, 'immediate'),
    [setParam],
  );
  const setAileronSpanStartSlider = useCallback(
    (v: number) => setParam('aileronSpanStart', v, 'slider'),
    [setParam],
  );
  const setAileronSpanStartInput = useCallback(
    (v: number) => setParam('aileronSpanStart', v, 'text'),
    [setParam],
  );
  const setAileronSpanEndSlider = useCallback(
    (v: number) => setParam('aileronSpanEnd', v, 'slider'),
    [setParam],
  );
  const setAileronSpanEndInput = useCallback(
    (v: number) => setParam('aileronSpanEnd', v, 'text'),
    [setParam],
  );
  const setAileronChordSlider = useCallback(
    (v: number) => setParam('aileronChordPercent', v, 'slider'),
    [setParam],
  );
  const setAileronChordInput = useCallback(
    (v: number) => setParam('aileronChordPercent', v, 'text'),
    [setParam],
  );

  // ── Elevon handlers ─────────────────────────────────────────────────
  const setElevonEnable = useCallback(
    (v: boolean) => setParam('elevonEnable', v, 'immediate'),
    [setParam],
  );
  const setElevonSpanStartSlider = useCallback(
    (v: number) => setParam('elevonSpanStart', v, 'slider'),
    [setParam],
  );
  const setElevonSpanStartInput = useCallback(
    (v: number) => setParam('elevonSpanStart', v, 'text'),
    [setParam],
  );
  const setElevonSpanEndSlider = useCallback(
    (v: number) => setParam('elevonSpanEnd', v, 'slider'),
    [setParam],
  );
  const setElevonSpanEndInput = useCallback(
    (v: number) => setParam('elevonSpanEnd', v, 'text'),
    [setParam],
  );
  const setElevonChordSlider = useCallback(
    (v: number) => setParam('elevonChordPercent', v, 'slider'),
    [setParam],
  );
  const setElevonChordInput = useCallback(
    (v: number) => setParam('elevonChordPercent', v, 'text'),
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

      {/* W08 — Wing Panels stepper (#243, renamed from Wing Sections in #154) */}
      <div
        className="flex items-center justify-between mb-2"
        title="Number of spanwise panels per half-wing. 1 = straight wing, 2–4 = polyhedral or cranked planform."
      >
        <span className="text-xs text-zinc-300">Wing Panels</span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={decrementSections}
            disabled={wingSections <= 1}
            className="w-6 h-6 flex items-center justify-center rounded
              bg-zinc-700 hover:bg-zinc-600 disabled:opacity-40 disabled:cursor-not-allowed
              text-zinc-200 text-sm font-bold transition-colors focus:outline-none focus:ring-1 focus:ring-blue-500"
            aria-label="Decrease wing panels"
          >
            −
          </button>
          <span className="w-6 text-center text-sm font-mono text-zinc-100 select-none">
            {wingSections}
          </span>
          <button
            type="button"
            onClick={incrementSections}
            disabled={wingSections >= 4}
            className="w-6 h-6 flex items-center justify-center rounded
              bg-zinc-700 hover:bg-zinc-600 disabled:opacity-40 disabled:cursor-not-allowed
              text-zinc-200 text-sm font-bold transition-colors focus:outline-none focus:ring-1 focus:ring-blue-500"
            aria-label="Increase wing panels"
          >
            +
          </button>
        </div>
      </div>

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
        title="How far the wing is swept back. 0 = straight, positive = swept back (like a jet)."
      />

      {/* W04 — Wing Taper (Tip/Root Ratio) */}
      <ParamSlider
        label="Taper (Tip/Root)"
        unit="ratio"
        value={design.wingTipRootRatio}
        min={0.3}
        max={1.0}
        step={0.01}
        onSliderChange={setTipRootSlider}
        onInputChange={setTipRootInput}
        hasWarning={fieldHasWarning(warnings, 'wingTipRootRatio')}
        warningText={warnText('wingTipRootRatio')}
        title="How much the wing narrows from root to tip. 1.0 = rectangular (same width tip to root), lower = more tapered."
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
        title="How much the wings angle upward from root to tip. Positive = tips up. Improves stability."
      />

      {/* W06 — Wing Angle (incidence) */}
      <ParamSlider
        label="Wing Angle"
        unit="deg"
        value={design.wingIncidence}
        min={-5}
        max={15}
        step={0.5}
        onSliderChange={setIncidenceSlider}
        onInputChange={setIncidenceInput}
        hasWarning={fieldHasWarning(warnings, 'wingIncidence')}
        title="Tilts the wing up or down relative to the fuselage. Positive = front of wing tilts up. Most planes use 1–3 degrees."
      />

      {/* W16 — Tip Twist (washout) */}
      <ParamSlider
        label="Tip Twist"
        unit="deg"
        value={design.wingTwist}
        min={-5}
        max={5}
        step={0.5}
        onSliderChange={setTwistSlider}
        onInputChange={setTwistInput}
        hasWarning={fieldHasWarning(warnings, 'wingTwist')}
        title="Twists the wing tip compared to the root. Negative = tip nose-down (washout), which prevents tip stalls. Positive = washin."
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
        title="Thickness of the printed wing shell. Thicker = stronger but heavier."
      />

      {/* ── Control Surfaces (Issue #144) ─────────────────────────── */}
      {design.fuselagePreset === 'Blended-Wing-Body' ? (
        /* Elevons for flying-wing */
        <ControlSurfaceSection
          title="Elevons"
          tooltip="For flying-wing/delta configurations. Elevons combine aileron and elevator function."
        >
          <label className="flex items-center gap-2 text-xs text-zinc-300 mb-2 cursor-pointer">
            <input
              type="checkbox"
              checked={design.elevonEnable}
              onChange={(e) => setElevonEnable(e.target.checked)}
              className="w-3 h-3 rounded"
            />
            Enable Elevons
          </label>
          <ParamSlider
            label="Elevon Inboard"
            unit="%"
            value={design.elevonSpanStart}
            min={10}
            max={40}
            step={1}
            onSliderChange={setElevonSpanStartSlider}
            onInputChange={setElevonSpanStartInput}
            disabled={!design.elevonEnable}
            hasWarning={fieldHasWarning(warnings, 'elevonSpanStart')}
            title="Inner edge of the elevon surface as % of half-span from root."
          />
          <ParamSlider
            label="Elevon Outboard"
            unit="%"
            value={design.elevonSpanEnd}
            min={60}
            max={98}
            step={1}
            onSliderChange={setElevonSpanEndSlider}
            onInputChange={setElevonSpanEndInput}
            disabled={!design.elevonEnable}
            hasWarning={fieldHasWarning(warnings, 'elevonSpanEnd')}
            title="Outer edge of the elevon surface as % of half-span."
          />
          <ParamSlider
            label="Elevon Chord %"
            unit="%"
            value={design.elevonChordPercent}
            min={15}
            max={35}
            step={1}
            onSliderChange={setElevonChordSlider}
            onInputChange={setElevonChordInput}
            disabled={!design.elevonEnable}
            hasWarning={fieldHasWarning(warnings, 'elevonChordPercent')}
            warningText={warnText('elevonChordPercent')}
          />
        </ControlSurfaceSection>
      ) : (
        /* Ailerons for conventional/tailed aircraft */
        <ControlSurfaceSection title="Ailerons">
          <label className="flex items-center gap-2 text-xs text-zinc-300 mb-2 cursor-pointer">
            <input
              type="checkbox"
              checked={design.aileronEnable}
              onChange={(e) => setAileronEnable(e.target.checked)}
              className="w-3 h-3 rounded"
            />
            Enable Ailerons
          </label>
          <ParamSlider
            label="Aileron Inboard"
            unit="%"
            value={design.aileronSpanStart}
            min={30}
            max={70}
            step={1}
            onSliderChange={setAileronSpanStartSlider}
            onInputChange={setAileronSpanStartInput}
            disabled={!design.aileronEnable}
            hasWarning={fieldHasWarning(warnings, 'aileronSpanStart')}
            title="Inboard edge of aileron as % of half-span from root. Must be less than outboard edge."
          />
          <ParamSlider
            label="Aileron Outboard"
            unit="%"
            value={design.aileronSpanEnd}
            min={70}
            max={98}
            step={1}
            onSliderChange={setAileronSpanEndSlider}
            onInputChange={setAileronSpanEndInput}
            disabled={!design.aileronEnable}
            hasWarning={fieldHasWarning(warnings, 'aileronSpanEnd')}
            title="Outboard edge of aileron as % of half-span. 95% leaves a small wingtip gap."
          />
          <ParamSlider
            label="Aileron Chord %"
            unit="%"
            value={design.aileronChordPercent}
            min={15}
            max={40}
            step={1}
            onSliderChange={setAileronChordSlider}
            onInputChange={setAileronChordInput}
            disabled={!design.aileronEnable}
            hasWarning={fieldHasWarning(warnings, 'aileronChordPercent')}
            warningText={warnText('aileronChordPercent')}
            title="Aileron chord as % of the local wing chord at that spanwise station."
          />
        </ControlSurfaceSection>
      )}

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
        title="Calculated wing width at the tip, based on root chord and taper ratio."
      />
      <DerivedField
        label="Wing Area"
        value={derived?.wingAreaCm2 ?? null}
        unit="cm&#178;"
        decimals={1}
        title="Total planform area of both wings combined."
      />
      <DerivedField
        label="Aspect Ratio"
        value={derived?.aspectRatio ?? null}
        decimals={2}
        title="How long and narrow the wing is. Higher = more efficient glide, lower = more agile. Wingspan divided by average chord."
      />
      <DerivedField
        label="Avg. Wing Width (MAC)"
        value={derived?.meanAeroChordMm ?? null}
        unit="mm"
        decimals={1}
        title="Mean Aerodynamic Chord — the average width of the wing, used to calculate CG position."
      />
      <DerivedField
        label="Taper Ratio"
        value={derived?.taperRatio ?? null}
        decimals={3}
        title="Tip chord divided by root chord. Same as the Taper (Tip/Root) setting above."
      />
      <DerivedField
        label="Estimated CG"
        value={derived?.estimatedCgMm ?? null}
        unit="mm"
        decimals={1}
        suffix="from wing LE"
        title="Estimated balance point (center of gravity) measured from the wing leading edge."
      />

      {/* ── Per-Component Print Settings (#128) ────────────────────── */}
      <PrintSettingsSection component="wing" />
    </div>
  );
}
