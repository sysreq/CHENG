// ============================================================================
// CHENG — WebSocket Connection Hook
// Spec: implementation_guide.md §6.1
// ============================================================================

import { useEffect, useRef, useCallback } from 'react';
import { getWebSocketUrl } from '@/lib/config';
import { parseMeshFrame } from '@/lib/meshParser';
import { useDesignStore } from '@/store/designStore';
import { useConnectionStore } from '@/store/connectionStore';
import type { AircraftDesign } from '@/types/design';

/** Base reconnection interval in milliseconds. */
const BASE_RECONNECT_MS = 1_000;

/** Maximum reconnection interval (cap for exponential backoff). */
const MAX_RECONNECT_MS = 30_000;

/**
 * Manages the WebSocket connection to /ws/preview.
 *
 * Opens on mount, closes on unmount. Call exactly once at the App level.
 *
 * - Parses binary frames via parseMeshFrame()
 * - Updates designStore (meshData, derived, warnings) on MeshFrame
 * - Updates connectionStore on open/close/error
 * - Implements reconnection with exponential backoff: 1s, 2s, 4s, 8s, 16s
 *   then gives up after maxReconnectAttempts (5).
 *
 * @returns send function to transmit design JSON, and disconnect to close.
 */
export function useWebSocket(): {
  send: (design: AircraftDesign) => void;
  disconnect: () => void;
} {
  const wsRef = useRef<WebSocket | null>(null);
  const intentionalCloseRef = useRef(false);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Use a ref for connect so startReconnect can reference it without circular deps
  const connectRef = useRef<() => void>(() => {});

  // Stable references to store actions (these don't change between renders)
  const storeActionsRef = useRef({
    setMeshData: useDesignStore.getState().setMeshData,
    setDerived: useDesignStore.getState().setDerived,
    setWarnings: useDesignStore.getState().setWarnings,
  });

  const startReconnect = useCallback(() => {
    const connStore = useConnectionStore.getState();
    connStore.setState('reconnecting');
    connStore.incrementAttempt();

    const { reconnectAttempts, maxReconnectAttempts } =
      useConnectionStore.getState();

    if (reconnectAttempts >= maxReconnectAttempts) {
      // Max attempts reached — give up
      connStore.setState('disconnected');
      return;
    }

    // Exponential backoff: 1s, 2s, 4s, 8s, 16s (capped at MAX_RECONNECT_MS)
    const delay = Math.min(
      BASE_RECONNECT_MS * Math.pow(2, reconnectAttempts - 1),
      MAX_RECONNECT_MS,
    );

    // Schedule next reconnection attempt
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      connectRef.current();
    }, delay);
  }, []);

  const connect = useCallback(() => {
    // Clean up any existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const connStore = useConnectionStore.getState();
    // Set to 'connecting' on initial connect, keep 'reconnecting' on retries
    if (connStore.state !== 'reconnecting') {
      connStore.setState('connecting');
    }

    const url = getWebSocketUrl();
    const ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen = () => {
      const store = useConnectionStore.getState();
      store.setState('connected');
      store.resetAttempts();
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!(event.data instanceof ArrayBuffer)) {
        console.warn('Received non-binary WebSocket message, ignoring');
        return;
      }

      try {
        const frame = parseMeshFrame(event.data);
        const actions = storeActionsRef.current;

        if (frame.type === 0x01) {
          // Mesh update — push to designStore
          actions.setMeshData({
            vertices: frame.vertices,
            normals: frame.normals,
            faces: frame.faces,
            vertexCount: frame.vertexCount,
            faceCount: frame.faceCount,
            componentRanges: frame.componentRanges,
          });
          actions.setDerived(frame.derived);
          actions.setWarnings(frame.validation);
        } else if (frame.type === 0x02) {
          // Error frame — log for debugging
          console.error(
            `[WS Error] ${frame.error}: ${frame.detail}` +
              (frame.field ? ` (field: ${frame.field})` : ''),
          );
        }
      } catch (err) {
        console.error('[WS] Failed to parse binary frame:', err);
      }
    };

    ws.onerror = () => {
      // onerror fires before onclose — set error state with message
      useConnectionStore.getState().setError('WebSocket connection error');
    };

    ws.onclose = () => {
      wsRef.current = null;

      if (intentionalCloseRef.current) {
        // Intentional close (unmount or disconnect call) — no reconnect
        useConnectionStore.getState().setState('disconnected');
        return;
      }

      // If onerror already set 'error' state, preserve it briefly before
      // starting reconnection so the UI can display the error (#193).
      // Use reconnectTimerRef so the timeout is cleared on unmount/disconnect.
      const currentState = useConnectionStore.getState().state;
      if (currentState === 'error') {
        reconnectTimerRef.current = setTimeout(() => {
          reconnectTimerRef.current = null;
          startReconnect();
        }, 1500);
        return;
      }

      // Unintentional close — start reconnection
      startReconnect();
    };
  }, [startReconnect]);

  // Keep the ref in sync
  connectRef.current = connect;

  /**
   * Send a design object as JSON to the backend via WebSocket.
   * Silently drops if not connected.
   */
  const send = useCallback((design: AircraftDesign) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(serializeDesign(design)));
    }
  }, []);

  /**
   * Intentionally close the WebSocket connection.
   */
  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;

    // Clear any pending reconnect timer
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    useConnectionStore.getState().setState('disconnected');
  }, []);

  // Connect on mount, close on unmount
  useEffect(() => {
    intentionalCloseRef.current = false;
    connect();

    return () => {
      intentionalCloseRef.current = true;

      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { send, disconnect };
}

// ---------------------------------------------------------------------------
// Serialization: camelCase -> snake_case
// ---------------------------------------------------------------------------

/**
 * Convert camelCase AircraftDesign to snake_case for the Python backend.
 * Explicit mapping (not algorithmic) to catch mismatches at compile time.
 * Field mapping from implementation_guide.md Appendix A.
 */
function serializeDesign(design: AircraftDesign): Record<string, unknown> {
  return {
    version: design.version,
    id: design.id,
    name: design.name,
    fuselage_preset: design.fuselagePreset,
    engine_count: design.engineCount,
    motor_config: design.motorConfig,
    wing_span: design.wingSpan,
    wing_chord: design.wingChord,
    wing_mount_type: design.wingMountType,
    fuselage_length: design.fuselageLength,
    tail_type: design.tailType,
    wing_airfoil: design.wingAirfoil,
    wing_sweep: design.wingSweep,
    wing_tip_root_ratio: design.wingTipRootRatio,
    wing_dihedral: design.wingDihedral,
    wing_skin_thickness: design.wingSkinThickness,
    h_stab_span: design.hStabSpan,
    h_stab_chord: design.hStabChord,
    h_stab_incidence: design.hStabIncidence,
    v_stab_height: design.vStabHeight,
    v_stab_root_chord: design.vStabRootChord,
    v_tail_dihedral: design.vTailDihedral,
    v_tail_span: design.vTailSpan,
    v_tail_chord: design.vTailChord,
    v_tail_incidence: design.vTailIncidence,
    tail_arm: design.tailArm,
    print_bed_x: design.printBedX,
    print_bed_y: design.printBedY,
    print_bed_z: design.printBedZ,
    auto_section: design.autoSection,
    section_overlap: design.sectionOverlap,
    joint_type: design.jointType,
    joint_tolerance: design.jointTolerance,
    nozzle_diameter: design.nozzleDiameter,
    hollow_parts: design.hollowParts,
    te_min_thickness: design.teMinThickness,
  };
}
