// ============================================================================
// CHENG — CG vs. Neutral Point Gauge Component
// Horizontal bar showing CG and NP positions as % of MAC with safe zone band.
// Issue #312
// ============================================================================

import React from 'react';

// ─── Props ───────────────────────────────────────────────────────────────────

interface CgVsNpGaugeProps {
  /** CG position as % of MAC from wing leading edge. */
  cgPctMac: number;
  /** Neutral point as % of MAC from wing leading edge. */
  npPctMac: number;
  /** Static margin as % of MAC. Used to determine CG indicator color. */
  staticMarginPct: number;
}

// ─── Constants ────────────────────────────────────────────────────────────────

/** The bar spans 0–40% MAC. Positions are expressed as % of this range. */
const BAR_RANGE_MAX = 40;
/** Safe zone start: 20% MAC → 20/40 = 50% of bar. */
const SAFE_ZONE_START_PCT = 50;
/** Safe zone end: 30% MAC → 30/40 = 75% of bar. */
const SAFE_ZONE_END_PCT = 75;

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Convert a MAC percentage value to a bar position, clamped to [0, 100]. */
function macPctToBarPct(macPct: number): number {
  return Math.min(100, Math.max(0, (macPct / BAR_RANGE_MAX) * 100));
}

/** Return the stability category label for the static margin. */
function getMarginCategory(staticMarginPct: number): string {
  if (staticMarginPct < 0) return 'Unstable';
  if (staticMarginPct < 2) return 'Marginal';
  if (staticMarginPct <= 15) return 'Optimal';
  return 'Over-stable';
}

// ─── Component ────────────────────────────────────────────────────────────────

/**
 * Horizontal bar gauge showing CG and Neutral Point positions relative to the
 * wing Mean Aerodynamic Chord. Safe zone (20–30% MAC) is highlighted with a
 * semi-transparent green band. CG indicator is green when stable, red when not.
 */
export function CgVsNpGauge({
  cgPctMac,
  npPctMac,
  staticMarginPct,
}: CgVsNpGaugeProps): React.JSX.Element {
  const cgBarPct = macPctToBarPct(cgPctMac);
  const npBarPct = macPctToBarPct(npPctMac);
  const isStable = staticMarginPct >= 0;
  const cgColor = isStable ? 'bg-green-500' : 'bg-red-500';
  const margin = staticMarginPct >= 0 ? `+${staticMarginPct.toFixed(1)}` : staticMarginPct.toFixed(1);

  return (
    <div className="mb-4">
      <h4 className="text-xs font-medium text-zinc-300 mb-2">CG vs. Neutral Point</h4>

      {/* Bar track */}
      <div
        role="img"
        aria-label={`CG at ${cgPctMac.toFixed(1)}% MAC, neutral point at ${npPctMac.toFixed(1)}% MAC, static margin ${staticMarginPct.toFixed(1)}%`}
        title="Horizontal bar showing CG and Neutral Point positions relative to Mean Aerodynamic Chord. CG should be forward of (lower % than) the Neutral Point for stable flight."
        className="relative h-8 w-full rounded bg-zinc-800/30 overflow-hidden"
      >
        {/* Safe zone band: 20%–30% MAC = 50%–75% of bar */}
        <div
          className="absolute top-0 bottom-0 bg-green-500/20"
          style={{
            left: `${SAFE_ZONE_START_PCT}%`,
            width: `${SAFE_ZONE_END_PCT - SAFE_ZONE_START_PCT}%`,
          }}
          aria-hidden="true"
        />

        {/* CG indicator — filled pill, centered via Tailwind transform */}
        <div
          className={`absolute top-1/2 w-3 h-3 -translate-x-1/2 -translate-y-1/2 rounded-full ${cgColor} border-2 border-zinc-900`}
          style={{ left: `${cgBarPct}%` }}
          aria-hidden="true"
        />

        {/* NP indicator — open circle with blue stroke */}
        <div
          className="absolute top-1/2 w-3 h-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-blue-400 bg-transparent"
          style={{ left: `${npBarPct}%` }}
          aria-hidden="true"
        />
      </div>

      {/* Tick labels — aria-hidden since bar has descriptive aria-label */}
      <div className="flex justify-between text-xs text-zinc-500 mt-0.5 px-0" aria-hidden="true">
        <span>0%</span>
        <span>10%</span>
        <span>20%</span>
        <span>30%</span>
        <span>40%</span>
      </div>

      {/* Value rows */}
      <div className="mt-2 space-y-0.5 text-xs text-zinc-400">
        <div className="flex items-center gap-1">
          <span className={`font-medium ${isStable ? 'text-green-400' : 'text-red-400'}`}>
            CG Position:
          </span>
          <span>{cgPctMac.toFixed(1)}% MAC from LE</span>
          <span>{isStable ? '✓' : '✗'}</span>
        </div>
        <div>
          <span className="font-medium text-blue-400">Neutral Point:</span>
          {' '}{npPctMac.toFixed(1)}% MAC from LE
        </div>
        <div>
          <span className="font-medium text-zinc-300">Static Margin:</span>
          {' '}{margin}% MAC ({getMarginCategory(staticMarginPct)})
        </div>
      </div>
    </div>
  );
}
