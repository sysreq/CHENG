// ============================================================================
// CHENG — Tail Conventional Panel: H-stab + V-stab params
// Used for Conventional, T-Tail, and Cruciform tail types
// Issue #27, #144 (control surfaces)
// ============================================================================

import React, { useState, useCallback } from 'react';
import { useDesignStore } from '../../store/designStore';
import { fieldHasWarning, getFieldWarnings, formatWarning } from '../../lib/validation';
import { ParamSlider } from '../ui';
import { PrintSettingsSection } from './PrintSettingsSection';

// ---------------------------------------------------------------------------
// Collapsible control surface section — local panel-only component
// ---------------------------------------------------------------------------

function ControlSurfaceSection({
  title,
  tooltip,
  children,
}: {
  title: string;
  tooltip?: string;
  children: React.ReactNode;
}): React.JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div className="mt-3">
      <div className="border-t border-zinc-700/50 mb-2" />
      <button
        onClick={() => setIsOpen((v) => !v)}
        type="button"
        className="flex items-center justify-between w-full text-left
          focus:outline-none focus:ring-1 focus:ring-blue-500 rounded px-1 py-0.5"
        aria-expanded={isOpen}
        title={tooltip}
      >
        <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
          {title}
        </span>
        <span className="text-xs text-zinc-500">{isOpen ? '▲' : '▼'}</span>
      </button>
      {isOpen && <div className="mt-2 space-y-0">{children}</div>}
    </div>
  );
}

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

  // ── Elevator handlers ──────────────────────────────────────────────

  const setElevatorEnable = useCallback(
    (v: boolean) => setParam('elevatorEnable', v, 'immediate'),
    [setParam],
  );
  const setElevatorSpanSlider = useCallback(
    (v: number) => setParam('elevatorSpanPercent', v, 'slider'),
    [setParam],
  );
  const setElevatorSpanInput = useCallback(
    (v: number) => setParam('elevatorSpanPercent', v, 'text'),
    [setParam],
  );
  const setElevatorChordSlider = useCallback(
    (v: number) => setParam('elevatorChordPercent', v, 'slider'),
    [setParam],
  );
  const setElevatorChordInput = useCallback(
    (v: number) => setParam('elevatorChordPercent', v, 'text'),
    [setParam],
  );

  // ── Rudder handlers ──────────────────────────────────────────────

  const setRudderEnable = useCallback(
    (v: boolean) => setParam('rudderEnable', v, 'immediate'),
    [setParam],
  );
  const setRudderHeightSlider = useCallback(
    (v: number) => setParam('rudderHeightPercent', v, 'slider'),
    [setParam],
  );
  const setRudderHeightInput = useCallback(
    (v: number) => setParam('rudderHeightPercent', v, 'text'),
    [setParam],
  );
  const setRudderChordSlider = useCallback(
    (v: number) => setParam('rudderChordPercent', v, 'slider'),
    [setParam],
  );
  const setRudderChordInput = useCallback(
    (v: number) => setParam('rudderChordPercent', v, 'text'),
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

      {/* ── Elevator (C11-C13) ─────────────────────────────────────── */}
      <ControlSurfaceSection title="Elevator">
        <label className="flex items-center gap-2 text-xs text-zinc-300 mb-2 cursor-pointer">
          <input
            type="checkbox"
            checked={design.elevatorEnable}
            onChange={(e) => setElevatorEnable(e.target.checked)}
            className="w-3 h-3 rounded"
          />
          Enable Elevator
        </label>
        <ParamSlider
          label="Elevator Span %"
          unit="%"
          value={design.elevatorSpanPercent}
          min={50}
          max={100}
          step={1}
          onSliderChange={setElevatorSpanSlider}
          onInputChange={setElevatorSpanInput}
          disabled={!design.elevatorEnable}
          hasWarning={fieldHasWarning(warnings, 'elevatorSpanPercent')}
          title="Elevator span as % of total H-stab span."
        />
        <ParamSlider
          label="Elevator Chord %"
          unit="%"
          value={design.elevatorChordPercent}
          min={20}
          max={50}
          step={1}
          onSliderChange={setElevatorChordSlider}
          onInputChange={setElevatorChordInput}
          disabled={!design.elevatorEnable}
          hasWarning={fieldHasWarning(warnings, 'elevatorChordPercent')}
          warningText={warnText('elevatorChordPercent')}
          title="Elevator chord as % of H-stab chord. 35% is typical."
        />
      </ControlSurfaceSection>

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

      {/* ── Rudder (C15-C17) ───────────────────────────────────────── */}
      <ControlSurfaceSection title="Rudder">
        <label className="flex items-center gap-2 text-xs text-zinc-300 mb-2 cursor-pointer">
          <input
            type="checkbox"
            checked={design.rudderEnable}
            onChange={(e) => setRudderEnable(e.target.checked)}
            className="w-3 h-3 rounded"
          />
          Enable Rudder
        </label>
        <ParamSlider
          label="Rudder Height %"
          unit="%"
          value={design.rudderHeightPercent}
          min={50}
          max={100}
          step={1}
          onSliderChange={setRudderHeightSlider}
          onInputChange={setRudderHeightInput}
          disabled={!design.rudderEnable}
          hasWarning={fieldHasWarning(warnings, 'rudderHeightPercent')}
          title="Rudder height as % of V-stab height."
        />
        <ParamSlider
          label="Rudder Chord %"
          unit="%"
          value={design.rudderChordPercent}
          min={20}
          max={50}
          step={1}
          onSliderChange={setRudderChordSlider}
          onInputChange={setRudderChordInput}
          disabled={!design.rudderEnable}
          hasWarning={fieldHasWarning(warnings, 'rudderChordPercent')}
          warningText={warnText('rudderChordPercent')}
          title="Rudder chord as % of fin root chord."
        />
      </ControlSurfaceSection>

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
