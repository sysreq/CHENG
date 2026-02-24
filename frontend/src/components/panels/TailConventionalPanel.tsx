// ============================================================================
// CHENG — Tail Conventional Panel: H-stab + V-stab params
// Used for Conventional, T-Tail, and Cruciform tail types
// Issue #27
// ============================================================================

import React, { useCallback } from 'react';
import { useDesignStore } from '../../store/designStore';
import { fieldHasWarning, getFieldWarnings, formatWarning } from '../../lib/validation';
import { ParamSlider } from '../ui';
import { PrintSettingsSection } from './PrintSettingsSection';

export function TailConventionalPanel(): React.JSX.Element {
  const design = useDesignStore((s) => s.design);
  const warnings = useDesignStore((s) => s.warnings);
  const setParam = useDesignStore((s) => s.setParam);

  // ── Determine subtitle from tail type ───────────────────────────────

  const subtitle =
    design.tailType === 'T-Tail'
      ? 'T-Tail'
      : design.tailType === 'Cruciform'
        ? 'Cruciform'
        : 'Conventional';

  // ── H-Stab handlers ────────────────────────────────────────────────

  const setHStabSpanSlider = useCallback(
    (v: number) => setParam('hStabSpan', v, 'slider'),
    [setParam],
  );
  const setHStabSpanInput = useCallback(
    (v: number) => setParam('hStabSpan', v, 'text'),
    [setParam],
  );

  const setHStabChordSlider = useCallback(
    (v: number) => setParam('hStabChord', v, 'slider'),
    [setParam],
  );
  const setHStabChordInput = useCallback(
    (v: number) => setParam('hStabChord', v, 'text'),
    [setParam],
  );

  const setHStabIncidenceSlider = useCallback(
    (v: number) => setParam('hStabIncidence', v, 'slider'),
    [setParam],
  );
  const setHStabIncidenceInput = useCallback(
    (v: number) => setParam('hStabIncidence', v, 'text'),
    [setParam],
  );

  // ── V-Stab handlers ────────────────────────────────────────────────

  const setVStabHeightSlider = useCallback(
    (v: number) => setParam('vStabHeight', v, 'slider'),
    [setParam],
  );
  const setVStabHeightInput = useCallback(
    (v: number) => setParam('vStabHeight', v, 'text'),
    [setParam],
  );

  const setVStabRootChordSlider = useCallback(
    (v: number) => setParam('vStabRootChord', v, 'slider'),
    [setParam],
  );
  const setVStabRootChordInput = useCallback(
    (v: number) => setParam('vStabRootChord', v, 'text'),
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
        Tail &mdash; {subtitle}
      </h3>

      {/* ── Horizontal Stabilizer ──────────────────────────────────── */}
      <h4 className="text-[10px] font-medium text-zinc-500 uppercase mb-2">
        Horizontal Stabilizer
      </h4>

      {/* T02 — H-Stab Span */}
      <ParamSlider
        label="H-Stab Span"
        unit="mm"
        value={design.hStabSpan}
        min={100}
        max={1200}
        step={10}
        onSliderChange={setHStabSpanSlider}
        onInputChange={setHStabSpanInput}
        hasWarning={fieldHasWarning(warnings, 'hStabSpan')}
        warningText={warnText('hStabSpan')}
      />

      {/* T03 — H-Stab Chord */}
      <ParamSlider
        label="H-Stab Chord"
        unit="mm"
        value={design.hStabChord}
        min={30}
        max={250}
        step={5}
        onSliderChange={setHStabChordSlider}
        onInputChange={setHStabChordInput}
        hasWarning={fieldHasWarning(warnings, 'hStabChord')}
        warningText={warnText('hStabChord')}
      />

      {/* T06 — H-Stab Incidence */}
      <ParamSlider
        label="H-Stab Incidence"
        unit="deg"
        value={design.hStabIncidence}
        min={-5}
        max={5}
        step={0.5}
        onSliderChange={setHStabIncidenceSlider}
        onInputChange={setHStabIncidenceInput}
        hasWarning={fieldHasWarning(warnings, 'hStabIncidence')}
      />

      {/* ── Vertical Stabilizer ────────────────────────────────────── */}
      <div className="border-t border-zinc-700/50 mt-3 mb-2" />
      <h4 className="text-[10px] font-medium text-zinc-500 uppercase mb-2">
        Vertical Stabilizer
      </h4>

      {/* T09 — V-Stab Height */}
      <ParamSlider
        label="V-Stab Height"
        unit="mm"
        value={design.vStabHeight}
        min={30}
        max={400}
        step={5}
        onSliderChange={setVStabHeightSlider}
        onInputChange={setVStabHeightInput}
        hasWarning={fieldHasWarning(warnings, 'vStabHeight')}
      />

      {/* T10 — V-Stab Root Chord */}
      <ParamSlider
        label="V-Stab Root Chord"
        unit="mm"
        value={design.vStabRootChord}
        min={30}
        max={300}
        step={5}
        onSliderChange={setVStabRootChordSlider}
        onInputChange={setVStabRootChordInput}
        hasWarning={fieldHasWarning(warnings, 'vStabRootChord')}
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
