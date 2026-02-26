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
 * Screen reader behaviour:
 * - `role="status"` implicitly includes aria-live="polite" + aria-atomic="true",
 *   so status text changes are announced automatically by assistive technology.
 * - Crossing below 0% (becoming unstable) triggers an additional `announceAssertive`
 *   call because an unstable state warrants an interrupting warning that cannot
 *   be achieved with role="status" alone.
 *
 * Live region store is NOT used for the stable state — role="status" handles it.
 */
export function PitchStabilityIndicator({
  staticMarginPct,
}: PitchStabilityIndicatorProps): React.JSX.Element {
  const { announceAssertive } = useLiveRegionStore();

  const status = getStabilityStatus(staticMarginPct);
  const meta = getStatusMeta(status);

  // Track previous status to detect threshold crossings. Initialized to null
  // so we do NOT announce on the first render (no "crossing" has occurred yet).
  const prevStatusRef = useRef<StabilityStatus | null>(null);

  useEffect(() => {
    const prevStatus = prevStatusRef.current;

    if (prevStatus !== null && prevStatus !== status) {
      // Detect crossing into unstable (assertive — interrupts screen reader).
      // role="status" cannot produce assertive announcements, so we use the store.
      if (status === 'unstable') {
        announceAssertive(
          'Warning: aircraft is now pitch-unstable. CG must move forward.'
        );
      }
      // Note: other transitions (entering stable, over-stable, marginal) are
      // handled automatically by role="status" reading the updated DOM text.
    }

    prevStatusRef.current = status;
  }, [status, announceAssertive]);

  return (
    <div
      role="status"
      // aria-live="polite" omitted — implicit from role="status"
      // aria-label omitted — screen reader will read the child text naturally
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
