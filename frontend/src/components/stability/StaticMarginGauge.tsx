// ============================================================================
// CHENG — Static Margin Gauge Component
// Color-coded horizontal bar showing static margin vs. stability zones.
// Issue #313
// ============================================================================

import React from 'react';
import {
  getStabilityStatus,
  getStatusMeta,
  getMarginColorClass,
} from '../../lib/stabilityAnalyzer';

// ─── Constants ────────────────────────────────────────────────────────────────

/** Bar spans from MIN_VALUE to MAX_VALUE % MAC. */
const MIN_VALUE = -5;
const MAX_VALUE = 25;
const TOTAL_RANGE = MAX_VALUE - MIN_VALUE; // 30

/** Zone boundaries as % MAC. */
const ZONES = [
  { label: 'Unstable', start: -5, end: 0, bgClass: 'bg-red-500' },
  { label: 'Marginal', start: 0, end: 2, bgClass: 'bg-yellow-500' },
  { label: 'Stable', start: 2, end: 15, bgClass: 'bg-green-500' },
  { label: 'Over-stable', start: 15, end: 25, bgClass: 'bg-blue-500' },
] as const;

/** Tick positions to label below the bar. */
const TICKS = [-5, 0, 2, 15, 25] as const;

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Convert a static margin value to a bar position percentage, clamped [0, 100]. */
function valueToBarPct(value: number): number {
  return Math.min(100, Math.max(0, ((value - MIN_VALUE) / TOTAL_RANGE) * 100));
}

// ─── Component ────────────────────────────────────────────────────────────────

interface StaticMarginGaugeProps {
  /** Static margin as % of MAC. Negative = unstable. */
  staticMarginPct: number;
}

/**
 * Horizontal segmented bar showing the static margin against four stability
 * zones: Unstable, Marginal, Stable, and Over-stable. A circle thumb indicator
 * follows the current value, colored by zone.
 */
export function StaticMarginGauge({
  staticMarginPct,
}: StaticMarginGaugeProps): React.JSX.Element {
  const status = getStabilityStatus(staticMarginPct);
  const meta = getStatusMeta(status);
  const thumbPct = valueToBarPct(staticMarginPct);
  const thumbBgClass = getMarginColorClass(staticMarginPct);
  const sign = staticMarginPct >= 0 ? '+' : '';

  return (
    <div className="mb-4">
      <h4 className="text-xs font-medium text-zinc-300 mb-2">Static Margin (% MAC)</h4>

      {/* Zone labels above bar */}
      <div className="flex text-[10px] text-zinc-500 mb-1" aria-hidden="true">
        {ZONES.map((zone) => (
          <div
            key={zone.label}
            className="text-center truncate"
            style={{ width: `${((zone.end - zone.start) / TOTAL_RANGE) * 100}%` }}
          >
            {zone.label}
          </div>
        ))}
      </div>

      {/* Bar + thumb container */}
      <div className="relative">
        {/* Zone segments */}
        <div
          role="progressbar"
          aria-valuemin={MIN_VALUE}
          aria-valuenow={staticMarginPct}
          aria-valuemax={MAX_VALUE}
          aria-label={`Static margin: ${sign}${staticMarginPct.toFixed(1)}% MAC — ${meta.label}`}
          className="relative h-4 rounded overflow-hidden flex"
        >
          {ZONES.map((zone) => (
            <div
              key={zone.label}
              className={zone.bgClass}
              style={{ width: `${((zone.end - zone.start) / TOTAL_RANGE) * 100}%` }}
              aria-hidden="true"
            />
          ))}
        </div>

        {/* Thumb indicator — positioned over the bar */}
        <div
          className={`absolute top-1/2 w-4 h-4 rounded-full ${thumbBgClass} ring-2 ring-zinc-900 pointer-events-none`}
          style={{
            left: `${thumbPct}%`,
            transform: 'translate(-50%, -50%)',
          }}
          aria-hidden="true"
        />
      </div>

      {/* Tick labels */}
      <div className="relative h-4 mt-0.5" aria-hidden="true">
        {TICKS.map((tick) => (
          <span
            key={tick}
            className="absolute text-[10px] text-zinc-500 -translate-x-1/2"
            style={{ left: `${valueToBarPct(tick)}%` }}
          >
            {tick}%
          </span>
        ))}
      </div>

      {/* Summary label */}
      <p className={`text-xs mt-2 ${meta.colorClass}`}>
        Static Margin:{' '}
        <span className="font-medium">
          {sign}{staticMarginPct.toFixed(1)}% MAC
        </span>
        {' — '}{meta.label}
      </p>
    </div>
  );
}
