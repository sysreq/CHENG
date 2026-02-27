// ============================================================================
// CHENG — Dynamic Stability Summary Card
// Compact in-viewport card showing at-a-glance quality dots for 3 key modes.
// Fixed bottom-left of viewport. Clicking opens the Stability Overlay on the
// Dynamic Stability tab. Hidden when overlay is open or dynamicStability is null.
// Issue #359
// ============================================================================

import React from 'react';
import { useDesignStore } from '../store/designStore';
import {
  classifyShortPeriod,
  classifyPhugoid,
  classifyDutchRoll,
  type ModeQuality,
} from '../lib/dynamicStabilityAnalyzer';

// ---------------------------------------------------------------------------
// Quality dot — colored circle
// ---------------------------------------------------------------------------

interface QualityDotProps {
  quality: ModeQuality;
}

function QualityDot({ quality }: QualityDotProps): React.JSX.Element {
  const colorMap: Record<ModeQuality, string> = {
    good:       'bg-green-400',
    acceptable: 'bg-amber-400',
    poor:       'bg-red-400',
    unknown:    'bg-zinc-500',
  };
  return (
    <span
      className={`w-2 h-2 rounded-full shrink-0 ${colorMap[quality]}`}
      aria-hidden="true"
    />
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DynamicStabilitySummaryCardProps {
  /** Whether the stability overlay is currently open (card hides itself). */
  overlayOpen: boolean;
  /** Called when the user clicks the card — parent should open overlay. */
  onOpen: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Compact summary card displayed at the bottom-left of the 3D viewport.
 *
 * Shows three rows: Short-Period, Phugoid, Dutch Roll — each with a
 * colored quality dot (green/amber/red) derived from the DATCOM results.
 *
 * Hidden when:
 * - dynamicStability is null/undefined (no DATCOM results yet)
 * - The stability overlay is open (avoids visual redundancy)
 *
 * Clicking the card triggers onOpen() which should open the stability overlay
 * and switch to the Dynamic Stability tab.
 */
export function DynamicStabilitySummaryCard({
  overlayOpen,
  onOpen,
}: DynamicStabilitySummaryCardProps): React.JSX.Element | null {
  const derived = useDesignStore((s) => s.derived);
  const ds = derived?.dynamicStability;

  // Hide when no data or overlay already open
  if (!ds || overlayOpen) {
    return null;
  }

  const spQuality  = classifyShortPeriod(ds.spZeta, ds.spOmegaN);
  const phQuality  = classifyPhugoid(ds.phugoidZeta);
  const drQuality  = classifyDutchRoll(ds.drZeta, ds.drOmegaN);

  // Overall quality: worst of the three
  const qualityRank: Record<ModeQuality, number> = { good: 0, acceptable: 1, poor: 2, unknown: 3 };
  const overallRank = Math.max(qualityRank[spQuality], qualityRank[phQuality], qualityRank[drQuality]);
  const overallLabels = ['Good', 'Acceptable', 'Poor', 'Unknown'];
  const overallLabel = overallLabels[overallRank] ?? 'Unknown';

  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`Dynamic stability summary: ${overallLabel}. Click to open stability analysis.`}
      className={[
        'fixed bottom-4 left-4 z-40',
        'bg-zinc-900/95 border border-zinc-700/80 rounded-lg shadow-lg shadow-black/40',
        'px-3 py-2 text-left',
        'hover:border-zinc-500 hover:bg-zinc-800/95',
        'focus:outline-none focus:ring-1 focus:ring-sky-500',
        'transition-colors cursor-pointer',
        'select-none',
      ].join(' ')}
    >
      {/* Header */}
      <div className="text-[9px] font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">
        Stability
      </div>

      {/* Mode rows */}
      <div className="flex flex-col gap-1">
        <ModeRow label="Short-Period" quality={spQuality} />
        <ModeRow label="Phugoid"      quality={phQuality} />
        <ModeRow label="Dutch Roll"   quality={drQuality} />
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Mode row helper
// ---------------------------------------------------------------------------

interface ModeRowProps {
  label: string;
  quality: ModeQuality;
}

function ModeRow({ label, quality }: ModeRowProps): React.JSX.Element {
  const qualityLabels: Record<ModeQuality, string> = {
    good:       'Good',
    acceptable: 'OK',
    poor:       'Poor',
    unknown:    '—',
  };
  return (
    <div className="flex items-center gap-2">
      <QualityDot quality={quality} />
      <span className="text-[10px] text-zinc-400 flex-1 leading-none">{label}</span>
      <span
        className={[
          'text-[10px] font-medium leading-none',
          quality === 'good'       ? 'text-green-400' :
          quality === 'acceptable' ? 'text-amber-400' :
          quality === 'poor'       ? 'text-red-400'   :
          'text-zinc-500',
        ].join(' ')}
      >
        {qualityLabels[quality]}
      </span>
    </div>
  );
}
