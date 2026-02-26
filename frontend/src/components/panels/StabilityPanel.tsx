// ============================================================================
// CHENG — Stability Panel
// Read-only tab panel showing static stability gauges and derived values.
// Issue #316
// ============================================================================

import React from 'react';
import { useDesignStore } from '../../store/designStore';
import { CgVsNpGauge } from '../stability/CgVsNpGauge';
import { StaticMarginGauge } from '../stability/StaticMarginGauge';
import { PitchStabilityIndicator } from '../stability/PitchStabilityIndicator';
import { DerivedField } from '../ui/DerivedField';

/**
 * Main container for the Stability tab. Reads derived values from the Zustand
 * store (populated live via WebSocket) and renders the three stability gauges
 * plus an expandable section of raw numeric values.
 *
 * The panel is strictly read-only — no sliders or inputs.
 */
export function StabilityPanel(): React.JSX.Element {
  const derived = useDesignStore((s) => s.derived);

  return (
    <section
      role="region"
      aria-label="Static Stability Analysis"
      className="p-4 space-y-4"
    >
      {/* Loading placeholder */}
      {!derived && (
        <p className="text-xs text-zinc-500 text-center py-8">
          Waiting for preview data...
        </p>
      )}

      {derived && (
        <>
          {/* Gauge 1 — CG vs. Neutral Point bar */}
          <CgVsNpGauge
            cgPctMac={derived.cgPctMac}
            npPctMac={derived.neutralPointPctMac}
            staticMarginPct={derived.staticMarginPct}
          />

          {/* Gauge 2 — Static Margin percentage bar */}
          <StaticMarginGauge staticMarginPct={derived.staticMarginPct} />

          {/* Gauge 3 — Pitch Stability status indicator */}
          <PitchStabilityIndicator staticMarginPct={derived.staticMarginPct} />

          {/* Expandable raw values section */}
          <details className="group">
            <summary className="text-xs font-medium text-zinc-400 cursor-pointer hover:text-zinc-200 select-none py-1">
              Raw Values
            </summary>
            <div className="mt-2 space-y-1">
              <DerivedField
                label="CG Position"
                value={derived.estimatedCgMm}
                unit="mm"
                title="Estimated center of gravity measured from nose datum"
              />
              <DerivedField
                label="Neutral Point"
                value={derived.neutralPointMm}
                unit="mm"
                title="Neutral point absolute position from nose datum. CG must be forward of this for stable flight."
              />
              <DerivedField
                label="Static Margin"
                value={derived.neutralPointMm - derived.estimatedCgMm}
                unit="mm"
                title="Distance between CG and neutral point (positive = stable). Equivalent to static margin in mm."
              />
              <DerivedField
                label="Tail Volume V_h"
                value={derived.tailVolumeH}
                decimals={3}
                title="Horizontal tail volume coefficient. Typical RC range: 0.30–0.80. Higher = more pitch damping."
              />
              <DerivedField
                label="Wing Loading"
                value={derived.wingLoadingGDm2}
                decimals={1}
                title="Total aircraft weight divided by wing area in g/dm². Higher = faster stall speed."
              />
              <DerivedField
                label="MAC"
                value={derived.meanAeroChordMm}
                unit="mm"
                title="Mean Aerodynamic Chord — the reference chord length used for stability calculations."
              />
            </div>
          </details>
        </>
      )}
    </section>
  );
}
