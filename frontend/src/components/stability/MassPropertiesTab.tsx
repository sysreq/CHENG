// ============================================================================
// CHENG — Mass Properties Tab
// Displays mass/CG/inertia state and provides MP01-MP07 override inputs.
// Issue #357
// ============================================================================

import React, { useId } from 'react';
import { useDesignStore } from '../../store/designStore';
import type { AircraftDesign } from '../../types/design';

// ---------------------------------------------------------------------------
// Helper: small numeric override input
// ---------------------------------------------------------------------------

interface OverrideInputProps {
  label: string;
  unit: string;
  value: number | null | undefined;
  min: number;
  max: number;
  step: number;
  decimals?: number;
  placeholder: string;
  title?: string;
  onChange: (value: number | null) => void;
}

function OverrideInput({
  label,
  unit,
  value,
  min,
  max,
  step,
  decimals = 2,
  placeholder,
  title,
  onChange,
}: OverrideInputProps): React.JSX.Element {
  const labelId = useId();
  const inputId = useId();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.trim();
    if (raw === '') {
      onChange(null);
    } else {
      const parsed = parseFloat(raw);
      if (!isNaN(parsed)) onChange(parsed);
    }
  };

  const displayValue = value != null ? value.toFixed(decimals) : '';

  return (
    <div className="mb-2" title={title}>
      <label
        id={labelId}
        htmlFor={inputId}
        className="block text-xs font-medium text-zinc-400 mb-0.5"
      >
        {label}
        <span className="ml-1 text-zinc-500 font-normal">({unit})</span>
      </label>
      <input
        id={inputId}
        type="number"
        min={min}
        max={max}
        step={step}
        value={displayValue}
        placeholder={placeholder}
        aria-labelledby={labelId}
        onChange={handleChange}
        className="w-full px-2 py-1 text-xs text-zinc-200 bg-zinc-800
          border border-zinc-700 rounded focus:outline-none
          focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30
          placeholder:text-zinc-600"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper: read-only value row with "Estimated" / "Measured" badge
// ---------------------------------------------------------------------------

interface ReadonlyRowProps {
  label: string;
  value: string;
  badge: 'estimated' | 'measured' | 'default';
  title?: string;
}

function ReadonlyRow({ label, value, badge, title }: ReadonlyRowProps): React.JSX.Element {
  const badgeClass =
    badge === 'measured'
      ? 'bg-green-900/40 text-green-400 border-green-700/40'
      : badge === 'estimated'
      ? 'bg-amber-900/30 text-amber-400 border-amber-700/40'
      : 'bg-zinc-800/40 text-zinc-500 border-zinc-700/40';

  const badgeLabel =
    badge === 'measured' ? 'Measured' : badge === 'estimated' ? 'Estimated' : 'Default';

  return (
    <div className="flex items-center justify-between py-0.5" title={title}>
      <span className="text-xs text-zinc-400 shrink-0 mr-2">{label}</span>
      <div className="flex items-center gap-1.5 min-w-0">
        <span className="text-xs text-zinc-300 tabular-nums">{value}</span>
        <span
          className={`text-[10px] px-1 py-0.5 rounded border font-medium shrink-0 ${badgeClass}`}
        >
          {badgeLabel}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section divider
// ---------------------------------------------------------------------------

function SectionHeader({ children }: { children: React.ReactNode }): React.JSX.Element {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500 mt-3 mb-1 pb-0.5 border-b border-zinc-700/50">
      {children}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * Mass Properties Tab — shows resolved mass, CG, and inertia state,
 * and provides numeric override inputs for MP01-MP07.
 */
export function MassPropertiesTab(): React.JSX.Element {
  const design = useDesignStore((s) => s.design);
  const derived = useDesignStore((s) => s.derived);
  const setParam = useDesignStore((s) => s.setParam);

  // Resolved display values
  // We show design.massTotalOverrideG if set, else note it's estimated from geometry
  const massBadge: 'measured' | 'estimated' =
    design.massTotalOverrideG != null ? 'measured' : 'estimated';
  const massDisplay =
    design.massTotalOverrideG != null
      ? `${design.massTotalOverrideG.toFixed(0)} g`
      : 'geometric estimate';

  const cgXBadge: 'measured' | 'estimated' =
    design.cgOverrideXMm != null ? 'measured' : 'estimated';
  const cgXDisplay =
    design.cgOverrideXMm != null
      ? `${design.cgOverrideXMm.toFixed(1)} mm`
      : derived
      ? `${derived.estimatedCgMm.toFixed(1)} mm`
      : '—';

  const cgZBadge: 'measured' | 'default' =
    design.cgOverrideZMm != null ? 'measured' : 'default';
  const cgZDisplay =
    design.cgOverrideZMm != null ? `${design.cgOverrideZMm.toFixed(1)} mm` : '0.0 mm';

  const cgYBadge: 'measured' | 'default' =
    design.cgOverrideYMm != null ? 'measured' : 'default';
  const cgYDisplay =
    design.cgOverrideYMm != null ? `${design.cgOverrideYMm.toFixed(1)} mm` : '0.0 mm';

  const ixxBadge: 'measured' | 'estimated' =
    design.ixxOverrideKgM2 != null ? 'measured' : 'estimated';
  const ixxDisplay =
    design.ixxOverrideKgM2 != null ? `${design.ixxOverrideKgM2.toFixed(4)} kg·m²` : 'geometric estimate';

  const iyyBadge: 'measured' | 'estimated' =
    design.iyyOverrideKgM2 != null ? 'measured' : 'estimated';
  const iyyDisplay =
    design.iyyOverrideKgM2 != null ? `${design.iyyOverrideKgM2.toFixed(4)} kg·m²` : 'geometric estimate';

  const izzBadge: 'measured' | 'estimated' =
    design.izzOverrideKgM2 != null ? 'measured' : 'estimated';
  const izzDisplay =
    design.izzOverrideKgM2 != null ? `${design.izzOverrideKgM2.toFixed(4)} kg·m²` : 'geometric estimate';

  function setMpParam<K extends keyof AircraftDesign>(key: K, val: AircraftDesign[K]) {
    setParam(key, val, 'text');
  }

  return (
    <section
      role="region"
      aria-label="Mass Properties"
      className="p-4 space-y-0.5 overflow-y-auto"
    >
      {/* Current resolved values */}
      <SectionHeader>Resolved Values</SectionHeader>

      <ReadonlyRow
        label="Total Mass"
        value={massDisplay}
        badge={massBadge}
        title="MP01: Total aircraft mass. Set an override below, or leave blank to use the geometric estimate."
      />
      <ReadonlyRow
        label="CG (longitudinal)"
        value={cgXDisplay}
        badge={cgXBadge}
        title="MP02: CG position along fuselage from nose. Set an override below, or leave blank to use 25% MAC estimate."
      />
      <ReadonlyRow
        label="CG (vertical)"
        value={cgZDisplay}
        badge={cgZBadge}
        title="MP03: CG vertical offset. Positive = above wing plane. Default = 0."
      />
      <ReadonlyRow
        label="CG (lateral)"
        value={cgYDisplay}
        badge={cgYBadge}
        title="MP04: CG lateral offset. Positive = starboard. Should be 0 for symmetric designs."
      />
      <ReadonlyRow
        label="Ixx (roll)"
        value={ixxDisplay}
        badge={ixxBadge}
        title="MP05: Roll moment of inertia. Estimated from wing span and mass distribution if not measured."
      />
      <ReadonlyRow
        label="Iyy (pitch)"
        value={iyyDisplay}
        badge={iyyBadge}
        title="MP06: Pitch moment of inertia. Typically larger than Ixx for conventional layouts."
      />
      <ReadonlyRow
        label="Izz (yaw)"
        value={izzDisplay}
        badge={izzBadge}
        title="MP07: Yaw moment of inertia. Typically largest for conventional layouts."
      />

      {/* Override inputs */}
      <SectionHeader>Measured Overrides</SectionHeader>

      <p className="text-[11px] text-zinc-500 mb-2">
        Enter measured values to replace geometric estimates. Leave blank to use estimates.
      </p>

      <OverrideInput
        label="MP01 — Total Mass"
        unit="g"
        value={design.massTotalOverrideG ?? null}
        min={50}
        max={10000}
        step={1}
        decimals={0}
        placeholder="e.g. 850"
        title="Measured total aircraft all-up weight in grams"
        onChange={(v) => setMpParam('massTotalOverrideG', v as AircraftDesign['massTotalOverrideG'])}
      />

      <OverrideInput
        label="MP02 — CG Longitudinal"
        unit="mm from nose"
        value={design.cgOverrideXMm ?? null}
        min={0}
        max={2000}
        step={0.5}
        decimals={1}
        placeholder="e.g. 340"
        title="Measured CG position along fuselage axis from nose datum"
        onChange={(v) => setMpParam('cgOverrideXMm', v as AircraftDesign['cgOverrideXMm'])}
      />

      <OverrideInput
        label="MP03 — CG Vertical"
        unit="mm (+ = up)"
        value={design.cgOverrideZMm ?? null}
        min={-50}
        max={100}
        step={0.5}
        decimals={1}
        placeholder="e.g. 0"
        title="Measured CG vertical offset above/below wing plane"
        onChange={(v) => setMpParam('cgOverrideZMm', v as AircraftDesign['cgOverrideZMm'])}
      />

      <OverrideInput
        label="MP04 — CG Lateral"
        unit="mm (+ = starboard)"
        value={design.cgOverrideYMm ?? null}
        min={-100}
        max={100}
        step={0.5}
        decimals={1}
        placeholder="e.g. 0"
        title="Measured CG lateral offset. Should be ~0 for symmetric designs."
        onChange={(v) => setMpParam('cgOverrideYMm', v as AircraftDesign['cgOverrideYMm'])}
      />

      <OverrideInput
        label="MP05 — Ixx (roll)"
        unit="kg·m²"
        value={design.ixxOverrideKgM2 ?? null}
        min={0.0001}
        max={10}
        step={0.0001}
        decimals={4}
        placeholder="e.g. 0.0150"
        title="Measured roll moment of inertia. Use a bifilar pendulum or swing test."
        onChange={(v) => setMpParam('ixxOverrideKgM2', v as AircraftDesign['ixxOverrideKgM2'])}
      />

      <OverrideInput
        label="MP06 — Iyy (pitch)"
        unit="kg·m²"
        value={design.iyyOverrideKgM2 ?? null}
        min={0.0001}
        max={10}
        step={0.0001}
        decimals={4}
        placeholder="e.g. 0.0320"
        title="Measured pitch moment of inertia."
        onChange={(v) => setMpParam('iyyOverrideKgM2', v as AircraftDesign['iyyOverrideKgM2'])}
      />

      <OverrideInput
        label="MP07 — Izz (yaw)"
        unit="kg·m²"
        value={design.izzOverrideKgM2 ?? null}
        min={0.0001}
        max={10}
        step={0.0001}
        decimals={4}
        placeholder="e.g. 0.0460"
        title="Measured yaw moment of inertia."
        onChange={(v) => setMpParam('izzOverrideKgM2', v as AircraftDesign['izzOverrideKgM2'])}
      />

      {/* Flight Condition */}
      <SectionHeader>Flight Condition</SectionHeader>

      <p className="text-[11px] text-zinc-500 mb-2">
        Used by the DATCOM dynamic stability analysis.
      </p>

      <OverrideInput
        label="FC01 — Cruise Speed"
        unit="m/s"
        value={design.flightSpeedMs ?? 50}
        min={10}
        max={100}
        step={0.5}
        decimals={1}
        placeholder="50"
        title="FC01: Cruise airspeed for dynamic stability analysis"
        onChange={(v) => setMpParam('flightSpeedMs', (v ?? 50) as AircraftDesign['flightSpeedMs'])}
      />

      <OverrideInput
        label="FC02 — Altitude"
        unit="m MSL"
        value={design.flightAltitudeM ?? 0}
        min={0}
        max={3000}
        step={10}
        decimals={0}
        placeholder="0"
        title="FC02: Flight altitude for ISA atmosphere model"
        onChange={(v) => setMpParam('flightAltitudeM', (v ?? 0) as AircraftDesign['flightAltitudeM'])}
      />
    </section>
  );
}
