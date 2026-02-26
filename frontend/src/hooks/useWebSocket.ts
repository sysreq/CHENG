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
  send: (design: AircraftDesign) => boolean;
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

    // Check BEFORE incrementing so that attempt #maxReconnectAttempts is
    // actually executed (#268 — off-by-one: old code incremented first so
    // the 5th attempt was skipped because count was already at 5).
    const { reconnectAttempts, maxReconnectAttempts } =
      useConnectionStore.getState();

    if (reconnectAttempts >= maxReconnectAttempts) {
      // Max attempts reached — give up
      connStore.setState('disconnected');
      return;
    }

    connStore.incrementAttempt();

    // Exponential backoff: 1s, 2s, 4s, 8s, 16s (capped at MAX_RECONNECT_MS).
    // reconnectAttempts is the PRE-increment value (0-based), so:
    //   attempt 1: reconnectAttempts=0 → 2^0=1s
    //   attempt 2: reconnectAttempts=1 → 2^1=2s  ...etc.
    const delay = Math.min(
      BASE_RECONNECT_MS * Math.pow(2, reconnectAttempts),
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
          // Error frame — clear spinner and surface the error (#266)
          useDesignStore.getState().setIsGenerating(false);
          console.error(
            `[WS Error] ${frame.error}: ${frame.detail}` +
              (frame.field ? ` (field: ${frame.field})` : ''),
          );
        }
      } catch (err) {
        // Parse failure — clear spinner so the UI doesn't hang (#266)
        useDesignStore.getState().setIsGenerating(false);
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
   * Returns true if the message was sent, false if the socket was not OPEN.
   * Callers should only set isGenerating=true on a truthy return (#265).
   */
  const send = useCallback((design: AircraftDesign): boolean => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(serializeDesign(design)));
      return true;
    }
    return false;
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
    // Meta
    version: design.version,
    id: design.id,
    name: design.name,

    // Global / Fuselage
    fuselage_preset: design.fuselagePreset,
    engine_count: design.engineCount,
    motor_config: design.motorConfig,
    wing_span: design.wingSpan,
    wing_chord: design.wingChord,
    wing_mount_type: design.wingMountType,
    fuselage_length: design.fuselageLength,
    tail_type: design.tailType,

    // Wing
    wing_airfoil: design.wingAirfoil,
    wing_sweep: design.wingSweep,
    wing_tip_root_ratio: design.wingTipRootRatio,
    wing_dihedral: design.wingDihedral,
    wing_skin_thickness: design.wingSkinThickness,
    wing_incidence: design.wingIncidence,
    wing_twist: design.wingTwist,

    // Multi-section wing (#143, #245)
    wing_sections: design.wingSections,
    panel_break_positions: design.panelBreakPositions,
    panel_dihedrals: design.panelDihedrals,
    panel_sweeps: design.panelSweeps,
    panel_airfoils: design.panelAirfoils,

    // Tail (Conventional / T-Tail / Cruciform)
    h_stab_span: design.hStabSpan,
    h_stab_chord: design.hStabChord,
    h_stab_incidence: design.hStabIncidence,
    v_stab_height: design.vStabHeight,
    v_stab_root_chord: design.vStabRootChord,

    // Tail (V-Tail)
    v_tail_dihedral: design.vTailDihedral,
    v_tail_span: design.vTailSpan,
    v_tail_chord: design.vTailChord,
    v_tail_incidence: design.vTailIncidence,
    v_tail_sweep: design.vTailSweep,

    // Shared tail
    tail_airfoil: design.tailAirfoil,
    tail_arm: design.tailArm,

    // Fuselage section transition points (F11/F12) — #244
    nose_cabin_break_pct: design.noseCabinBreakPct,
    cabin_tail_break_pct: design.cabinTailBreakPct,

    // Fuselage wall thickness
    wall_thickness: design.wallThickness,

    // Control surfaces — Ailerons (#144)
    aileron_enable: design.aileronEnable,
    aileron_span_start: design.aileronSpanStart,
    aileron_span_end: design.aileronSpanEnd,
    aileron_chord_percent: design.aileronChordPercent,

    // Control surfaces — Elevator
    elevator_enable: design.elevatorEnable,
    elevator_span_percent: design.elevatorSpanPercent,
    elevator_chord_percent: design.elevatorChordPercent,

    // Control surfaces — Rudder
    rudder_enable: design.rudderEnable,
    rudder_height_percent: design.rudderHeightPercent,
    rudder_chord_percent: design.rudderChordPercent,

    // Control surfaces — Ruddervators
    ruddervator_enable: design.ruddervatorEnable,
    ruddervator_chord_percent: design.ruddervatorChordPercent,
    ruddervator_span_percent: design.ruddervatorSpanPercent,

    // Control surfaces — Elevons
    elevon_enable: design.elevonEnable,
    elevon_span_start: design.elevonSpanStart,
    elevon_span_end: design.elevonSpanEnd,
    elevon_chord_percent: design.elevonChordPercent,

    // Landing gear (#145)
    landing_gear_type: design.landingGearType,
    main_gear_position: design.mainGearPosition,
    main_gear_height: design.mainGearHeight,
    main_gear_track: design.mainGearTrack,
    main_wheel_diameter: design.mainWheelDiameter,
    nose_gear_height: design.noseGearHeight,
    nose_wheel_diameter: design.noseWheelDiameter,
    tail_wheel_diameter: design.tailWheelDiameter,
    tail_gear_position: design.tailGearPosition,

    // Export / Print
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
    support_strategy: design.supportStrategy,
  };
}
