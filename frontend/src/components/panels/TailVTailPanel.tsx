// ============================================================================
// CHENG — Tail V-Tail Panel: V-tail specific parameters
// Shown when tailType === 'V-Tail'
// Issue #27, #144 (control surfaces — ruddervators)
// Issue #154 — Parameter renaming for beginners
// ============================================================================

import React, { useCallback } from 'react';
import { useDesignStore } from '../../store/designStore';
import { fieldHasWarning, getFieldWarnings, formatWarning } from '../../lib/validation';
import { ParamSlider } from '../ui';
import { PrintSettingsSection } from './PrintSettingsSection';
import { ControlSurfaceSection } from './shared/ControlSurfaceSection';

export function TailVTailPanel(): React.JSX.Element {
  const design = useDesignStore((s) => s.design);
  const warnings = useDesignStore((s) => s.warnings);
  const setParam = useDesignStore((s) => s.setParam);

  // ── V-Tail handlers ────────────────────────────────────────────────

  const setVTailDihedralSlider = useCallback(
    (v: number) => setParam('vTailDihedral', v, 'slider'),
    [setParam],
  );
  const setVTailDihedralInput = useCallback(
    (v: number) => setParam('vTailDihedral', v, 'text'),
    [setParam],
  );

  const setVTailSpanSlider = useCallback(
    (v: number) => setParam('vTailSpan', v, 'slider'),
    [setParam],
  );
  const setVTailSpanInput = useCallback(
    (v: number) => setParam('vTailSpan', v, 'text'),
    [setParam],
  );

  const setVTailChordSlider = useCallback(
    (v: number) => setParam('vTailChord', v, 'slider'),
    [setParam],
  );
  const setVTailChordInput = useCallback(
    (v: number) => setParam('vTailChord', v, 'text'),
    [setParam],
  );

  const setVTailIncidenceSlider = useCallback(
    (v: number) => setParam('vTailIncidence', v, 'slider'),
    [setParam],
  );
  const setVTailIncidenceInput = useCallback(
    (v: number) => setParam('vTailIncidence', v, 'text'),
    [setParam],
  );

  const setVTailSweepSlider = useCallback(
    (v: number) => setParam('vTailSweep', v, 'slider'),
    [setParam],
  );
  const setVTailSweepInput = useCallback(
    (v: number) => setParam('vTailSweep', v, 'text'),
    [setParam],
  );

  // ── Ruddervator handlers ──────────────────────────────────────────

  const setRuddervatorEnable = useCallback(
    (v: boolean) => setParam('ruddervatorEnable', v, 'immediate'),
    [setParam],
  );
  const setRuddervatorChordSlider = useCallback(
    (v: number) => setParam('ruddervatorChordPercent', v, 'slider'),
    [setParam],
  );
  const setRuddervatorChordInput = useCallback(
    (v: number) => setParam('ruddervatorChordPercent', v, 'text'),
    [setParam],
  );
  const setRuddervatorSpanSlider = useCallback(
    (v: number) => setParam('ruddervatorSpanPercent', v, 'slider'),
    [setParam],
  );
  const setRuddervatorSpanInput = useCallback(
    (v: number) => setParam('ruddervatorSpanPercent', v, 'text'),
    [setParam],
  );

  // ── Tail Distance handler ─────────────────────────────────────────

  const setTailArmSlider = useCallback(
    (v: number) => setParam('tailArm', v, 'slider'),
    [setParam],
  );
  const setTailArmInput = useCallback(
    (v: number) => setParam('tailArm', v, 'text'),
    [setParam],
  );

  const warnText = (field: string) =>
    getFieldWarnings(warnings, field).map(formatWarning).join('\n') || undefined;

  return (
    <div className="p-3">
      <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
        Tail &mdash; V-Tail
      </h3>

      {/* T14 — V-Tail Tilt (formerly "V-Tail Dihedral") */}
      <ParamSlider
        label="V-Tail Tilt"
        unit="deg"
        value={design.vTailDihedral}
        min={20}
        max={60}
        step={1}
        onSliderChange={setVTailDihedralSlider}
        onInputChange={setVTailDihedralInput}
        hasWarning={fieldHasWarning(warnings, 'vTailDihedral')}
        title="How far the V-tail surfaces are tilted from horizontal. Higher values = more V-shaped."
      />

      {/* T16 — V-Tail Span */}
      <ParamSlider
        label="V-Tail Span"
        unit="mm"
        value={design.vTailSpan}
        min={80}
        max={600}
        step={10}
        onSliderChange={setVTailSpanSlider}
        onInputChange={setVTailSpanInput}
        hasWarning={fieldHasWarning(warnings, 'vTailSpan')}
        title="Total tip-to-tip span of the V-tail surfaces."
      />

      {/* T17 — V-Tail Chord */}
      <ParamSlider
        label="V-Tail Chord"
        unit="mm"
        value={design.vTailChord}
        min={30}
        max={200}
        step={5}
        onSliderChange={setVTailChordSlider}
        onInputChange={setVTailChordInput}
        hasWarning={fieldHasWarning(warnings, 'vTailChord')}
        title="Width of each V-tail surface from leading edge to trailing edge."
      />

      {/* T18 — V-Tail Angle (formerly "V-Tail Incidence") */}
      <ParamSlider
        label="V-Tail Angle"
        unit="deg"
        value={design.vTailIncidence}
        min={-3}
        max={3}
        step={0.5}
        onSliderChange={setVTailIncidenceSlider}
        onInputChange={setVTailIncidenceInput}
        hasWarning={fieldHasWarning(warnings, 'vTailIncidence')}
        title="Pitch angle of the V-tail surfaces relative to the fuselage. Usually left at 0."
      />

      {/* T15 — V-Tail Sweep */}
      <ParamSlider
        label="V-Tail Sweep"
        unit="deg"
        value={design.vTailSweep}
        min={-10}
        max={45}
        step={1}
        onSliderChange={setVTailSweepSlider}
        onInputChange={setVTailSweepInput}
        hasWarning={fieldHasWarning(warnings, 'vTailSweep')}
        title="How far the leading edge of the V-tail is swept back."
      />

      {/* ── Ruddervators (C18-C20) ─────────────────────────────────── */}
      <ControlSurfaceSection
        title="Ruddervators"
        tooltip="Ruddervators combine elevator and rudder function on V-tail surfaces."
      >
        <label className="flex items-center gap-2 text-xs text-zinc-300 mb-2 cursor-pointer">
          <input
            type="checkbox"
            checked={design.ruddervatorEnable}
            onChange={(e) => setRuddervatorEnable(e.target.checked)}
            className="w-3 h-3 rounded"
          />
          Enable Ruddervators
        </label>
        <ParamSlider
          label="Ruddervator Span %"
          unit="%"
          value={design.ruddervatorSpanPercent}
          min={60}
          max={100}
          step={1}
          onSliderChange={setRuddervatorSpanSlider}
          onInputChange={setRuddervatorSpanInput}
          disabled={!design.ruddervatorEnable}
          hasWarning={fieldHasWarning(warnings, 'ruddervatorSpanPercent')}
          title="Ruddervator span as % of total V-tail span."
        />
        <ParamSlider
          label="Ruddervator Chord %"
          unit="%"
          value={design.ruddervatorChordPercent}
          min={20}
          max={50}
          step={1}
          onSliderChange={setRuddervatorChordSlider}
          onInputChange={setRuddervatorChordInput}
          disabled={!design.ruddervatorEnable}
          hasWarning={fieldHasWarning(warnings, 'ruddervatorChordPercent')}
          warningText={warnText('ruddervatorChordPercent')}
          title="Ruddervator chord as % of V-tail chord. 35% is typical."
        />
      </ControlSurfaceSection>

      {/* ── Shared ─────────────────────────────────────────────────── */}
      <div className="border-t border-zinc-700/50 mt-3 mb-2" />

      {/* T22 — Tail Distance (formerly "Tail Arm") */}
      <ParamSlider
        label="Tail Distance"
        unit="mm"
        value={design.tailArm}
        min={80}
        max={1500}
        step={10}
        onSliderChange={setTailArmSlider}
        onInputChange={setTailArmInput}
        hasWarning={fieldHasWarning(warnings, 'tailArm')}
        warningText={warnText('tailArm')}
        title="Distance from the wing to the tail. Longer = more stable but heavier."
      />

      {/* ── Per-Component Print Settings (#128) ────────────────────── */}
      <PrintSettingsSection component="tail" />
    </div>
  );
}
