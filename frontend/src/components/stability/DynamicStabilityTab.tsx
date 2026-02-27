// ============================================================================
// CHENG — Dynamic Stability Tab
// Displays DATCOM dynamic mode analysis results with quality classification.
// Issue #358
// ============================================================================

import React from 'react';
import { useDesignStore } from '../../store/designStore';
import {
  classifyShortPeriod,
  classifyPhugoid,
  classifyDutchRoll,
  classifyRollMode,
  classifySpiralMode,
  type ModeQuality,
} from '../../lib/dynamicStabilityAnalyzer';
import type { DynamicStabilityResult } from '../../types/design';

// ---------------------------------------------------------------------------
// Quality badge — color-coded chip
// ---------------------------------------------------------------------------

interface QualityBadgeProps {
  quality: ModeQuality;
}

function QualityBadge({ quality }: QualityBadgeProps): React.JSX.Element {
  const map: Record<ModeQuality, { label: string; cls: string }> = {
    good:       { label: 'Good',       cls: 'bg-green-900/40 text-green-400 border-green-700/40' },
    acceptable: { label: 'Acceptable', cls: 'bg-amber-900/30 text-amber-400 border-amber-700/40' },
    poor:       { label: 'Poor',       cls: 'bg-red-900/40 text-red-400 border-red-700/40' },
    unknown:    { label: 'Unknown',    cls: 'bg-zinc-800/40 text-zinc-500 border-zinc-700/40' },
  };
  const { label, cls } = map[quality];
  return (
    <span
      className={`text-[10px] px-1.5 py-0.5 rounded border font-medium shrink-0 ${cls}`}
      aria-label={`Quality: ${label}`}
    >
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Mode row — label + value + quality badge
// ---------------------------------------------------------------------------

interface ModeRowProps {
  label: string;
  value: string;
  quality: ModeQuality;
  title?: string;
}

function ModeRow({ label, value, quality, title }: ModeRowProps): React.JSX.Element {
  return (
    <div className="flex items-center justify-between py-0.5 gap-1" title={title}>
      <span className="text-xs text-zinc-400 shrink-0 min-w-0 flex-1">{label}</span>
      <span className="text-xs text-zinc-300 tabular-nums mx-1 shrink-0">{value}</span>
      <QualityBadge quality={quality} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Derivative row — compact label + value
// ---------------------------------------------------------------------------

interface DerivRowProps {
  label: string;
  value: number;
  title?: string;
}

function DerivRow({ label, value, title }: DerivRowProps): React.JSX.Element {
  const formatted = Number.isFinite(value)
    ? value.toFixed(3)
    : value > 0 ? '+\u221e' : '\u2212\u221e';

  return (
    <div className="flex items-center justify-between py-0.5" title={title}>
      <span className="text-xs text-zinc-500 font-mono">{label}</span>
      <span className="text-xs text-zinc-400 tabular-nums">{formatted}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section header
// ---------------------------------------------------------------------------

function SectionHeader({ children }: { children: React.ReactNode }): React.JSX.Element {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500 mt-3 mb-1 pb-0.5 border-b border-zinc-700/50">
      {children}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Formatted period/tau helpers
// ---------------------------------------------------------------------------

function formatPeriod(periodS: number): string {
  if (!Number.isFinite(periodS) || periodS <= 0) return 'aperiodic';
  return `${periodS.toFixed(2)} s`;
}

function formatT2(t2S: number): string {
  if (isNaN(t2S)) return '\u2014';
  if (t2S === Infinity || t2S < 0) return 'stable';
  return `${t2S.toFixed(1)} s`;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * Dynamic Stability Tab — shows DATCOM dynamic mode analysis results.
 * Displays quality classifications (per MIL-F-8785C) and stability derivatives.
 * Issue #358.
 */
export function DynamicStabilityTab(): React.JSX.Element {
  const derived = useDesignStore((s) => s.derived);
  const ds: DynamicStabilityResult | null | undefined = derived?.dynamicStability;

  // Loading / not-computed states
  if (!derived) {
    return (
      <div className="p-4 text-xs text-zinc-500 text-center py-8">
        Waiting for analysis data...
      </div>
    );
  }

  if (!ds) {
    return (
      <div className="p-4 space-y-2">
        <p className="text-xs text-zinc-500 text-center py-4">
          Dynamic stability analysis not yet available.
        </p>
        <p className="text-[11px] text-zinc-600 text-center">
          Results will appear here once the backend DATCOM pipeline is integrated.
        </p>
      </div>
    );
  }

  // Classify each mode using MIL-F-8785C boundaries
  const spQuality     = classifyShortPeriod(ds.spZeta, ds.spOmegaN);
  const phQuality     = classifyPhugoid(ds.phugoidZeta);
  const drQuality     = classifyDutchRoll(ds.drZeta, ds.drOmegaN);
  const rollQuality   = classifyRollMode(ds.rollTauS);
  const spiralQuality = classifySpiralMode(ds.spiralT2S);

  return (
    <section
      role="region"
      aria-label="Dynamic Stability Analysis"
      className="p-4 overflow-y-auto"
    >
      {/* Longitudinal modes */}
      <SectionHeader>Longitudinal Modes</SectionHeader>

      <ModeRow
        label="Short Period"
        value={`\u03b6=${ds.spZeta.toFixed(2)}, \u03c9n=${ds.spOmegaN.toFixed(2)} rad/s`}
        quality={spQuality}
        title={`Short-period oscillation. T=${formatPeriod(ds.spPeriodS)}. Level 1: 0.35\u2264\u03b6\u22641.30, \u03c9n>1.0 rad/s.`}
      />

      <ModeRow
        label="Phugoid"
        value={`\u03b6=${ds.phugoidZeta.toFixed(3)}, \u03c9n=${ds.phugoidOmegaN.toFixed(3)} rad/s`}
        quality={phQuality}
        title={`Slow speed/pitch oscillation. T=${formatPeriod(ds.phugoidPeriodS)}. Level 1: \u03b6\u22650.04.`}
      />

      {/* Lateral modes */}
      <SectionHeader>Lateral Modes</SectionHeader>

      <ModeRow
        label="Dutch Roll"
        value={`\u03b6=${ds.drZeta.toFixed(2)}, \u03c9n=${ds.drOmegaN.toFixed(2)} rad/s`}
        quality={drQuality}
        title={`Dutch roll oscillation. T=${formatPeriod(ds.drPeriodS)}. Level 1: \u03b6\u22650.08, \u03c9n\u22650.4 rad/s.`}
      />

      <ModeRow
        label="Roll Mode"
        value={`\u03c4=${ds.rollTauS.toFixed(2)} s`}
        quality={rollQuality}
        title="Roll mode time constant. Level 1: \u03c4\u22640.5 s. Level 2: \u03c4\u22641.0 s."
      />

      <ModeRow
        label="Spiral"
        value={`t\u2082=${formatT2(ds.spiralT2S)}`}
        quality={spiralQuality}
        title="Spiral divergence doubling time. Level 1: t2\u226520 s or stable. Level 2: t2\u22658 s."
      />

      {/* Stability derivatives (collapsible) */}
      <details className="group mt-2">
        <summary className="text-xs font-medium text-zinc-400 cursor-pointer hover:text-zinc-200 select-none py-1">
          Stability Derivatives
          {ds.derivativesEstimated && (
            <span className="ml-1.5 text-[10px] text-amber-500">(DATCOM estimate)</span>
          )}
        </summary>

        <div className="mt-1">
          <SectionHeader>Longitudinal</SectionHeader>
          <DerivRow label="CL\u03b1"     value={ds.clAlpha}    title="Lift-curve slope dCL/d\u03b1 (per rad)" />
          <DerivRow label="CD\u03b1"     value={ds.cdAlpha}    title="Drag-slope dCD/d\u03b1 (per rad)" />
          <DerivRow label="Cm\u03b1"     value={ds.cmAlpha}    title="Pitch stiffness dCm/d\u03b1 (negative = stable)" />
          <DerivRow label="CL\u1E51"     value={ds.clQ}        title="Lift due to pitch rate" />
          <DerivRow label="Cm\u1E51"     value={ds.cmQ}        title="Pitch damping dCm/d(qc/2V) (negative = damped)" />
          <DerivRow label="CL\u03b1\u0307" value={ds.clAlphadot} title="Lift due to \u03b1-dot" />
          <DerivRow label="Cm\u03b1\u0307" value={ds.cmAlphadot} title="Pitch due to \u03b1-dot" />

          <SectionHeader>Lateral</SectionHeader>
          <DerivRow label="CY\u03b2" value={ds.cyBeta} title="Side force due to sideslip" />
          <DerivRow label="Cl\u03b2" value={ds.clBeta} title="Roll due to sideslip (dihedral effect; negative = stable)" />
          <DerivRow label="Cn\u03b2" value={ds.cnBeta} title="Yaw due to sideslip (weathercock; positive = stable)" />
          <DerivRow label="CY\u1E55"  value={ds.cyP}   title="Side force due to roll rate" />
          <DerivRow label="Cl\u1E55"  value={ds.clP}   title="Roll damping (negative = damped)" />
          <DerivRow label="Cn\u1E55"  value={ds.cnP}   title="Adverse yaw due to roll rate" />
          <DerivRow label="CY\u0159"  value={ds.cyR}   title="Side force due to yaw rate" />
          <DerivRow label="Cl\u0159"  value={ds.clR}   title="Roll due to yaw rate" />
          <DerivRow label="Cn\u0159"  value={ds.cnR}   title="Yaw damping (negative = damped)" />
        </div>
      </details>
    </section>
  );
}
