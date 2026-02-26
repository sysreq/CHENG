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
 *   0–2%    → 'marginal'
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
  /** One-sentence plain-English explanation for the pilot. */
  description: string;
}

/**
 * Classify a static margin percentage into a stability status.
 *
 * @param staticMarginPct - Static margin in % of MAC. Positive = CG ahead of NP (stable).
 * @returns StabilityStatus classification.
 */
export function getStabilityStatus(staticMarginPct: number): StabilityStatus {
  if (staticMarginPct < 0) return 'unstable';
  if (staticMarginPct < 2) return 'marginal';
  if (staticMarginPct <= 15) return 'stable';
  return 'over-stable';
}

/**
 * Returns display metadata for a given stability status.
 *
 * Icon characters:
 *   ✗ → unstable
 *   ⚠ → marginal or over-stable
 *   ✓ → stable
 *
 * Color classes use Tailwind CSS 4 text-* utilities for the dark theme.
 *
 * @param status - StabilityStatus value from getStabilityStatus().
 * @returns StabilityStatusMeta with icon, label, colorClass, description.
 */
export function getStatusMeta(status: StabilityStatus): StabilityStatusMeta {
  switch (status) {
    case 'unstable':
      return {
        icon: '✗',
        label: 'UNSTABLE',
        colorClass: 'text-red-500',
        description: 'CG is behind neutral point — aircraft will diverge in pitch.',
      };
    case 'marginal':
      return {
        icon: '⚠',
        label: 'MARGINAL',
        colorClass: 'text-yellow-500',
        description: 'Pitch authority is minimal; oscillations likely. Move CG forward.',
      };
    case 'stable':
      return {
        icon: '✓',
        label: 'STABLE',
        colorClass: 'text-green-500',
        description: 'Natural pitch stability is present. Aircraft returns to trim.',
      };
    case 'over-stable':
      return {
        icon: '⚠',
        label: 'OVER-STABLE',
        colorClass: 'text-blue-500',
        description: 'Pitch inputs feel sluggish. Consider moving CG aft.',
      };
  }
}

/**
 * Determine the Tailwind background color class for a static margin percentage.
 * Used by the StaticMarginGauge to color-code zones on the bar.
 *
 * Zones (per STABILITY_FEATURE.md §4.3):
 *   < 0%   → red
 *   0–2%   → yellow
 *   2–15%  → green
 *   > 15%  → blue
 *
 * @param staticMarginPct - Static margin value in % of MAC.
 * @returns Tailwind bg-* color class string.
 */
export function getMarginColorClass(staticMarginPct: number): string {
  if (staticMarginPct < 0) return 'bg-red-500';
  if (staticMarginPct < 2) return 'bg-yellow-500';
  if (staticMarginPct <= 15) return 'bg-green-500';
  return 'bg-blue-500';
}

/**
 * Determine the Tailwind text color class for a static margin percentage.
 * Used inline with numeric labels on the gauge.
 *
 * @param staticMarginPct - Static margin value in % of MAC.
 * @returns Tailwind text-* color class string.
 */
export function getMarginTextColorClass(staticMarginPct: number): string {
  if (staticMarginPct < 0) return 'text-red-500';
  if (staticMarginPct < 2) return 'text-yellow-500';
  if (staticMarginPct <= 15) return 'text-green-500';
  return 'text-blue-500';
}
