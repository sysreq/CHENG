import { create } from 'zustand';

// ---------------------------------------------------------------------------
// Connection State Types
// ---------------------------------------------------------------------------

/**
 * WebSocket connection state machine.
 * - 'connecting': Initial connection attempt in progress.
 * - 'connected': Green dot. Full functionality.
 * - 'reconnecting': Yellow pulsing dot. Exponential backoff retry.
 * - 'disconnected': Red dot + banner. Max attempts reached or intentional close.
 * - 'error': Red dot + banner. Connection error occurred.
 */
export type ConnectionState =
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnected'
  | 'error';

export interface ConnectionStore {
  state: ConnectionState;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  lastError: string | null;
  setState: (state: ConnectionState) => void;
  setError: (error: string) => void;
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
  lastError: null,

  setState: (state) => set({ state }),

  setError: (error) => set({ state: 'error', lastError: error }),

  incrementAttempt: () =>
    set((s) => ({ reconnectAttempts: s.reconnectAttempts + 1 })),

  resetAttempts: () => set({ reconnectAttempts: 0, lastError: null }),
}));
