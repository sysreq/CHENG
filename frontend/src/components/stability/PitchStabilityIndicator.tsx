// ============================================================================
// CHENG — Pitch Stability Indicator Component
// Shows current pitch stability classification with live region announcements.
// Issue #315
// ============================================================================

import React, { useEffect, useRef } from 'react';
import { useLiveRegionStore } from '../../store/liveRegionStore';
import {
  getStabilityStatus,
  getStatusMeta,
  type StabilityStatus,
} from '../../lib/stabilityAnalyzer';

// ─── Props ───────────────────────────────────────────────────────────────────

interface PitchStabilityIndicatorProps {
  /** Static margin as % of MAC. Negative = unstable. */
  staticMarginPct: number;
}

// ─── Component ────────────────────────────────────────────────────────────────

/**
 * Displays the pitch stability classification (UNSTABLE / MARGINAL / STABLE /
 * OVER-STABLE) with the corresponding icon, color, and a one-sentence description.
 *
 * Announces threshold crossings to screen readers via useLiveRegionStore:
 * - Crossing below 0% (becoming unstable) → assertive announcement
 * - Entering 2–15% optimal zone (becoming stable) → polite announcement
 */
export function PitchStabilityIndicator({
  staticMarginPct,
}: PitchStabilityIndicatorProps): React.JSX.Element {
  const { announce, announceAssertive } = useLiveRegionStore();

  const status = getStabilityStatus(staticMarginPct);
  const meta = getStatusMeta(status);

  // Track previous status to detect threshold crossings. Initialized to null
  // so we do NOT announce on the first render (no "crossing" has occurred yet).
  const prevStatusRef = useRef<StabilityStatus | null>(null);

  useEffect(() => {
    const prevStatus = prevStatusRef.current;

    if (prevStatus !== null && prevStatus !== status) {
      // Detect crossing into unstable (assertive — interrupts screen reader)
      if (status === 'unstable') {
        announceAssertive(
          'Warning: aircraft is now pitch-unstable. CG must move forward.'
        );
      }
      // Detect crossing into stable optimal range (polite — non-interrupting)
      else if (status === 'stable') {
        announce('Pitch stability: aircraft is now in the stable range.');
      }
    }

    prevStatusRef.current = status;
  }, [status, announce, announceAssertive]);

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={`Pitch stability: ${meta.label}. ${meta.description}`}
      className="mb-4 p-3 rounded bg-zinc-800/30 border border-zinc-700/50"
    >
      {/* Status row: icon + label */}
      <div className="flex items-center gap-2">
        <span
          className={`text-lg font-bold leading-none ${meta.colorClass}`}
          aria-hidden="true"
        >
          {meta.icon}
        </span>
        <span className={`text-sm font-bold tracking-wide ${meta.colorClass}`}>
          {meta.label}
        </span>
      </div>

      {/* Description */}
      <p className="text-xs text-zinc-400 mt-1">{meta.description}</p>
    </div>
  );
}
