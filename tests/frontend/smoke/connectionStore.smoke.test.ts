// ============================================================================
// CHENG — Connection Store smoke tests
// Tier 1: always run pre-commit (< 1s each)
//
// Covers: WebSocket connection state machine initialization.
// These are the fastest, most critical tests in the frontend suite.
// ============================================================================

import { describe, it, expect, beforeEach } from 'vitest';
import { useConnectionStore } from '@/store/connectionStore';

function resetStore() {
  const store = useConnectionStore.getState();
  store.setState('disconnected');
  store.resetAttempts();
}

describe('[smoke] connectionStore — initialization', () => {
  beforeEach(() => {
    resetStore();
  });

  it('starts in disconnected state', () => {
    const { state, reconnectAttempts, lastError } = useConnectionStore.getState();
    expect(state).toBe('disconnected');
    expect(reconnectAttempts).toBe(0);
    expect(lastError).toBeNull();
  });

  it('maxReconnectAttempts defaults to 5', () => {
    expect(useConnectionStore.getState().maxReconnectAttempts).toBe(5);
  });

  it('setState transitions correctly', () => {
    useConnectionStore.getState().setState('connecting');
    expect(useConnectionStore.getState().state).toBe('connecting');

    useConnectionStore.getState().setState('connected');
    expect(useConnectionStore.getState().state).toBe('connected');
  });

  it('resetAttempts clears attempts and lastError', () => {
    useConnectionStore.getState().incrementAttempt();
    useConnectionStore.getState().incrementAttempt();
    useConnectionStore.getState().setError('some error');

    useConnectionStore.getState().resetAttempts();
    const { reconnectAttempts, lastError } = useConnectionStore.getState();
    expect(reconnectAttempts).toBe(0);
    expect(lastError).toBeNull();
  });
});
