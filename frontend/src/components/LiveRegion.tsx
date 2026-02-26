// ============================================================================
// CHENG — LiveRegion: Global ARIA live region for screen reader announcements
// Issue #180 (Accessibility audit)
// ============================================================================

import { useEffect, useRef } from 'react';
import { useLiveRegionStore } from '@/store/liveRegionStore';

/**
 * Invisible ARIA live region that vocalises transient status messages.
 *
 * Usage: call `useLiveRegionStore.getState().announce(msg)` from anywhere.
 * The message is cleared after 5 s so it doesn't linger in the accessibility
 * tree.
 *
 * Two regions are maintained:
 *  - polite  — non-urgent (save confirmation, preset loaded, etc.)
 *  - assertive — urgent (connection errors, export failures)
 */
export function LiveRegion() {
  const politeMsg = useLiveRegionStore((s) => s.politeMessage);
  const assertiveMsg = useLiveRegionStore((s) => s.assertiveMessage);
  const clearPolite = useLiveRegionStore((s) => s.clearPolite);
  const clearAssertive = useLiveRegionStore((s) => s.clearAssertive);

  const politeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const assertiveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!politeMsg) return;
    if (politeTimer.current) clearTimeout(politeTimer.current);
    politeTimer.current = setTimeout(() => {
      clearPolite();
      politeTimer.current = null;
    }, 5000);
    return () => {
      if (politeTimer.current) clearTimeout(politeTimer.current);
    };
  }, [politeMsg, clearPolite]);

  useEffect(() => {
    if (!assertiveMsg) return;
    if (assertiveTimer.current) clearTimeout(assertiveTimer.current);
    assertiveTimer.current = setTimeout(() => {
      clearAssertive();
      assertiveTimer.current = null;
    }, 5000);
    return () => {
      if (assertiveTimer.current) clearTimeout(assertiveTimer.current);
    };
  }, [assertiveMsg, clearAssertive]);

  return (
    <>
      {/* Polite region — waits for the user to finish before announcing */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        style={{
          position: 'absolute',
          width: 1,
          height: 1,
          overflow: 'hidden',
          clip: 'rect(0 0 0 0)',
          whiteSpace: 'nowrap',
        }}
      >
        {politeMsg}
      </div>

      {/* Assertive region — interrupts immediately for urgent messages */}
      <div
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        style={{
          position: 'absolute',
          width: 1,
          height: 1,
          overflow: 'hidden',
          clip: 'rect(0 0 0 0)',
          whiteSpace: 'nowrap',
        }}
      >
        {assertiveMsg}
      </div>
    </>
  );
}
