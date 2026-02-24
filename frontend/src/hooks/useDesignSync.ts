// ============================================================================
// CHENG — Design Sync Hook
// Spec: implementation_guide.md §6.2
// ============================================================================

import { useEffect, useRef } from 'react';
import { useDesignStore } from '@/store/designStore';
import { useConnectionStore } from '@/store/connectionStore';
import type { AircraftDesign, ChangeSource } from '@/types/design';

/** Throttle interval for slider changes (ms). */
const SLIDER_THROTTLE_MS = 100;

/** Debounce delay for text input changes (ms). */
const TEXT_DEBOUNCE_MS = 300;

/**
 * Watches designStore for parameter changes and sends updates via WebSocket.
 *
 * Applies debounce/throttle per spec Section 7.7:
 *   - Sliders: throttled at 100ms (sends at most once per interval)
 *   - Text inputs: debounced at 300ms (waits until typing stops)
 *   - Dropdowns/toggles: immediate (no delay)
 *
 * On reconnection (reconnecting -> connected), immediately resends the
 * current design state to synchronize the backend.
 *
 * Call exactly once at the App level.
 *
 * @param send - Function to send a design object via WebSocket
 */
export function useDesignSync(send: (design: AircraftDesign) => void): void {
  const sendRef = useRef(send);
  sendRef.current = send;

  // Track throttle/debounce timers
  const throttleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastThrottleSendRef = useRef<number>(0);

  // Track previous design reference for change detection
  const prevDesignRef = useRef<AircraftDesign>(useDesignStore.getState().design);

  // Subscribe to design store changes
  useEffect(() => {
    const unsubDesign = useDesignStore.subscribe((state) => {
      const design = state.design;
      const source: ChangeSource = state.lastChangeSource;

      // Only send if the design object reference actually changed
      if (design === prevDesignRef.current) return;
      prevDesignRef.current = design;

      if (source === 'immediate') {
        // Dropdowns, toggles, presets — send immediately
        sendRef.current(design);
      } else if (source === 'slider') {
        // Throttle: send at most once per SLIDER_THROTTLE_MS
        const now = Date.now();
        const elapsed = now - lastThrottleSendRef.current;

        if (elapsed >= SLIDER_THROTTLE_MS) {
          // Enough time has passed — send now
          lastThrottleSendRef.current = now;
          sendRef.current(design);
        } else {
          // Schedule a trailing send at the end of the throttle window
          if (throttleTimerRef.current !== null) {
            clearTimeout(throttleTimerRef.current);
          }
          throttleTimerRef.current = setTimeout(() => {
            throttleTimerRef.current = null;
            lastThrottleSendRef.current = Date.now();
            sendRef.current(useDesignStore.getState().design);
          }, SLIDER_THROTTLE_MS - elapsed);
        }
      } else if (source === 'text') {
        // Debounce: wait until typing stops for TEXT_DEBOUNCE_MS
        if (debounceTimerRef.current !== null) {
          clearTimeout(debounceTimerRef.current);
        }
        debounceTimerRef.current = setTimeout(() => {
          debounceTimerRef.current = null;
          sendRef.current(useDesignStore.getState().design);
        }, TEXT_DEBOUNCE_MS);
      }
    });

    return () => {
      unsubDesign();

      // Clean up pending timers
      if (throttleTimerRef.current !== null) {
        clearTimeout(throttleTimerRef.current);
        throttleTimerRef.current = null;
      }
      if (debounceTimerRef.current !== null) {
        clearTimeout(debounceTimerRef.current);
        debounceTimerRef.current = null;
      }
    };
  }, []);

  // On connection (initial or reconnection), send current design to sync backend
  useEffect(() => {
    let prevConnState = useConnectionStore.getState().state;

    const unsubConnection = useConnectionStore.subscribe((state) => {
      const curr = state.state;
      if (curr === 'connected' && prevConnState !== 'connected') {
        // Sync the backend with current design state on any connection
        const design = useDesignStore.getState().design;
        sendRef.current(design);
      }
      prevConnState = curr;
    });

    return () => {
      unsubConnection();
    };
  }, []);
}
