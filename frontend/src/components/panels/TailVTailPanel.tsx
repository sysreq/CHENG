// ============================================================================
// CHENG — Tail V-Tail Panel: V-tail specific parameters
// Shown when tailType === 'V-Tail'
// Issue #27
// ============================================================================

import React, { useCallback } from 'react';
import { useDesignStore } from '../../store/designStore';
import { fieldHasWarning, getFieldWarnings, formatWarning } from '../../lib/validation';
import { ParamSlider } from '../ui';
import { PrintSettingsSection } from './PrintSettingsSection';

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

  // ── Tail Arm handler ──────────────────────────────────────────────

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

      {/* T14 — V-Tail Dihedral */}
      <ParamSlider
        label="V-Tail Dihedral"
        unit="deg"
        value={design.vTailDihedral}
        min={20}
        max={60}
        step={1}
        onSliderChange={setVTailDihedralSlider}
        onInputChange={setVTailDihedralInput}
        hasWarning={fieldHasWarning(warnings, 'vTailDihedral')}
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
      />

      {/* T18 — V-Tail Incidence */}
      <ParamSlider
        label="V-Tail Incidence"
        unit="deg"
        value={design.vTailIncidence}
        min={-3}
        max={3}
        step={0.5}
        onSliderChange={setVTailIncidenceSlider}
        onInputChange={setVTailIncidenceInput}
        hasWarning={fieldHasWarning(warnings, 'vTailIncidence')}
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
      />

      {/* ── Shared ─────────────────────────────────────────────────── */}
      <div className="border-t border-zinc-700/50 mt-3 mb-2" />

      {/* T22 — Tail Arm */}
      <ParamSlider
        label="Tail Arm"
        unit="mm"
        value={design.tailArm}
        min={80}
        max={1500}
        step={10}
        onSliderChange={setTailArmSlider}
        onInputChange={setTailArmInput}
        hasWarning={fieldHasWarning(warnings, 'tailArm')}
        warningText={warnText('tailArm')}
      />

      {/* ── Per-Component Print Settings (#128) ────────────────────── */}
      <PrintSettingsSection component="tail" />
    </div>
  );
}
