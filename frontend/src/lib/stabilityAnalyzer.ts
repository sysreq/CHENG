// ============================================================================
// CHENG — Stability Interpretation Utility
// Pure TypeScript, no React dependencies.
// Translates numeric stability values into display-ready status objects.
// ============================================================================

/**
 * Stability classification for a static margin value.
 *
 * Thresholds (per STABILITY_FEATURE.md §2.3):
 *   < 0%    → 'unstable'
 *   0–2%    → 'marginal'   (exclusive: 2% is the start of 'stable')
 *   2–15%   → 'stable'
 *   > 15%   → 'over-stable'
 */
export type StabilityStatus = 'unstable' | 'marginal' | 'stable' | 'over-stable';

/**
 * Display metadata for a stability status.
 */
export interface StabilityStatusMeta {
  /** Text character used as visual indicator. */
  icon: string;
  /** Uppercase status label. */
  label: string;
  /** Tailwind text-color class. */
  colorClass: string;
  /** Tailwind bg-color class (for gauge fill). */
  bgColorClass: string;
  /** One-sentence plain-English explanation for the pilot. */
  description: string;
}

/** Lookup table keyed by StabilityStatus — defined once, referenced by all helpers. */
const STATUS_META: Record<StabilityStatus, StabilityStatusMeta> = {
  unstable: {
    icon: '✗',
    label: 'UNSTABLE',
    colorClass: 'text-red-500',
    bgColorClass: 'bg-red-500',
    description: 'CG is behind neutral point — aircraft will diverge in pitch.',
  },
  marginal: {
    icon: '⚠',
    label: 'MARGINAL',
    colorClass: 'text-yellow-500',
    bgColorClass: 'bg-yellow-500',
    description: 'Pitch authority is minimal; oscillations likely. Move CG forward.',
  },
  stable: {
    icon: '✓',
    label: 'STABLE',
    colorClass: 'text-green-500',
    bgColorClass: 'bg-green-500',
    description: 'Natural pitch stability is present. Aircraft returns to trim.',
  },
  'over-stable': {
    icon: '⚠',
    label: 'OVER-STABLE',
    colorClass: 'text-blue-500',
    bgColorClass: 'bg-blue-500',
    description: 'Pitch inputs feel sluggish. Consider moving CG aft.',
  },
};

/**
 * Classify a static margin percentage into a stability status.
 *
 * Non-finite values (NaN, ±Infinity) from degenerate geometry are classified
 * as 'unstable' so the UI shows an error state rather than a false-positive.
 *
 * @param staticMarginPct - Static margin in % of MAC. Positive = CG ahead of NP (stable).
 * @returns StabilityStatus classification.
 */
export function getStabilityStatus(staticMarginPct: number): StabilityStatus {
  if (!isFinite(staticMarginPct)) return 'unstable';
  if (staticMarginPct < 0) return 'unstable';
  if (staticMarginPct < 2) return 'marginal';
  if (staticMarginPct <= 15) return 'stable';
  return 'over-stable';
}

/**
 * Returns display metadata for a given stability status.
 *
 * @param status - StabilityStatus value from getStabilityStatus().
 * @returns StabilityStatusMeta with icon, label, colorClass, bgColorClass, description.
 */
export function getStatusMeta(status: StabilityStatus): StabilityStatusMeta {
  return STATUS_META[status];
}

/**
 * Determine the Tailwind background color class for a static margin percentage.
 * Used by StaticMarginGauge to color-code zones on the bar.
 *
 * Delegates classification to getStabilityStatus() to keep thresholds DRY.
 *
 * @param staticMarginPct - Static margin value in % of MAC.
 * @returns Tailwind bg-* color class string.
 */
export function getMarginColorClass(staticMarginPct: number): string {
  return STATUS_META[getStabilityStatus(staticMarginPct)].bgColorClass;
}

/**
 * Determine the Tailwind text color class for a static margin percentage.
 * Used inline with numeric labels on the gauge.
 *
 * Delegates classification to getStabilityStatus() to keep thresholds DRY.
 *
 * @param staticMarginPct - Static margin value in % of MAC.
 * @returns Tailwind text-* color class string.
 */
export function getMarginTextColorClass(staticMarginPct: number): string {
  return STATUS_META[getStabilityStatus(staticMarginPct)].colorClass;
}
