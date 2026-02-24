import { create } from 'zustand';

// ---------------------------------------------------------------------------
// Connection State Types
// ---------------------------------------------------------------------------

/**
 * WebSocket connection state machine.
 * - 'connected': Green dot. Full functionality.
 * - 'reconnecting': Yellow pulsing dot. Retry every 3s, max 5 attempts.
 * - 'disconnected': Red dot + banner. Auto-retry every 30s.
 */
export type ConnectionState = 'connected' | 'reconnecting' | 'disconnected';

export interface ConnectionStore {
  state: ConnectionState;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  setState: (state: ConnectionState) => void;
  incrementAttempt: () => void;
  resetAttempts: () => void;
}

// ---------------------------------------------------------------------------
// Store Implementation
// ---------------------------------------------------------------------------

export const useConnectionStore = create<ConnectionStore>()((set) => ({
  state: 'disconnected',
  reconnectAttempts: 0,
  maxReconnectAttempts: 5,

  setState: (state) => set({ state }),

  incrementAttempt: () =>
    set((s) => ({ reconnectAttempts: s.reconnectAttempts + 1 })),

  resetAttempts: () => set({ reconnectAttempts: 0 }),
}));
