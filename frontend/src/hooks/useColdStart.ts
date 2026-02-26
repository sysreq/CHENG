// ============================================================================
// CHENG — Cold Start Detection Hook
// Spec: ux_design.md §1.3
// ============================================================================

import { useEffect, useRef, useState } from 'react';
import { useConnectionStore } from '@/store/connectionStore';
import { useDesignStore } from '@/store/designStore';

/**
 * Cold start phases — progress text sequences shown in the overlay.
 *
 * Phase 0 → "connecting" (delay not yet exceeded, no overlay shown)
 * Phase 1 → "starting"
 * Phase 2 → "loading"
 * Phase 3 → "initializing"
 * Phase 4 → "ready" (connected; overlay fading out)
 * Phase 5 → dismissed (overlay removed from DOM)
 */
export type ColdStartPhase = 'idle' | 'starting' | 'loading' | 'initializing' | 'ready' | 'dismissed';

export interface ColdStartState {
  /** Whether the cold start overlay should be rendered. */
  visible: boolean;
  /** Current progress phase for text/animation updates. */
  phase: ColdStartPhase;
}

/** Delay (ms) before showing the cold-start overlay on initial connect. */
const COLD_START_THRESHOLD_MS = 1_000;

/**
 * Detects a slow initial WebSocket connection (cold start) and manages
 * overlay visibility.
 *
 * Rules:
 * - Only activates on the FIRST connection attempt (not reconnects).
 * - Shows overlay after COLD_START_THRESHOLD_MS if still connecting.
 * - Advances text phases over time while waiting.
 * - Dismisses once the connection is established AND the first mesh is received.
 * - Never shows again after the initial load cycle.
 *
 * @returns ColdStartState — visibility flag and current phase.
 */
export function useColdStart(): ColdStartState {
  const connectionState = useConnectionStore((s) => s.state);
  const meshData = useDesignStore((s) => s.meshData);

  const [phase, setPhase] = useState<ColdStartPhase>('idle');

  // Track whether we are still in the initial connection window.
  // Once the first connection is fully established + mesh received,
  // or the threshold is never exceeded, this is permanently deactivated.
  const isInitialLoadRef = useRef(true);
  const thresholdTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const phaseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Phase advancement ──────────────────────────────────────────────────────
  // Once the overlay becomes visible (phase = 'starting'), auto-advance text
  // every few seconds to simulate perceived progress while waiting.
  useEffect(() => {
    if (phase === 'starting') {
      phaseTimerRef.current = setTimeout(() => {
        setPhase('loading');
      }, 3_500);
    } else if (phase === 'loading') {
      phaseTimerRef.current = setTimeout(() => {
        setPhase('initializing');
      }, 4_000);
    }

    return () => {
      if (phaseTimerRef.current !== null) {
        clearTimeout(phaseTimerRef.current);
        phaseTimerRef.current = null;
      }
    };
  }, [phase]);

  // ── Cold start detection ───────────────────────────────────────────────────
  // Monitor the connection state. On the initial 'connecting' state, start a
  // threshold timer. If still connecting after the threshold, show the overlay.
  useEffect(() => {
    if (!isInitialLoadRef.current) return;

    if (connectionState === 'connecting') {
      // Start the threshold timer — if we are still connecting after 1s,
      // the backend is cold-starting and we should show the overlay.
      if (thresholdTimerRef.current === null) {
        thresholdTimerRef.current = setTimeout(() => {
          thresholdTimerRef.current = null;
          // Still in the initial connecting window — show overlay
          if (isInitialLoadRef.current) {
            setPhase('starting');
          }
        }, COLD_START_THRESHOLD_MS);
      }
    } else if (connectionState === 'connected') {
      // Connection established — clear pending threshold timer
      if (thresholdTimerRef.current !== null) {
        clearTimeout(thresholdTimerRef.current);
        thresholdTimerRef.current = null;
      }

      // If the overlay was shown, transition to 'ready' phase.
      // If it was never shown (fast connect), mark dismissed immediately.
      setPhase((prev) => {
        if (prev === 'idle') {
          // Fast connect — deactivate without ever showing overlay.
          isInitialLoadRef.current = false;
          return 'dismissed';
        }
        // Overlay was shown — move to 'ready' (waiting for first mesh).
        return 'ready';
      });
    } else if (
      connectionState === 'reconnecting' ||
      connectionState === 'disconnected' ||
      connectionState === 'error'
    ) {
      // Non-initial connection states — clear threshold timer.
      // The overlay should NOT be shown for reconnections.
      if (thresholdTimerRef.current !== null) {
        clearTimeout(thresholdTimerRef.current);
        thresholdTimerRef.current = null;
      }

      // If we've already detected a reconnect (not first connect), permanently
      // deactivate this hook so the overlay never shows for reconnects.
      if (connectionState === 'reconnecting') {
        isInitialLoadRef.current = false;
        setPhase((prev) => {
          if (prev !== 'idle' && prev !== 'dismissed') {
            // Overlay was showing during initial connect — dismiss it.
            return 'dismissed';
          }
          return prev;
        });
      }
    }

    return () => {
      if (thresholdTimerRef.current !== null) {
        clearTimeout(thresholdTimerRef.current);
        thresholdTimerRef.current = null;
      }
    };
  }, [connectionState]);

  // ── Dismiss on first mesh received ────────────────────────────────────────
  // Once connected AND first mesh data arrives, dismiss the overlay.
  useEffect(() => {
    if (phase === 'ready' && meshData !== null) {
      // First mesh received — mark the initial load as complete.
      isInitialLoadRef.current = false;

      // Small delay so users can read "Ready!" before the overlay fades out.
      const dismissTimer = setTimeout(() => {
        setPhase('dismissed');
      }, 600);

      return () => clearTimeout(dismissTimer);
    }
  }, [phase, meshData]);

  const visible =
    phase === 'starting' ||
    phase === 'loading' ||
    phase === 'initializing' ||
    phase === 'ready';

  return { visible, phase };
}
