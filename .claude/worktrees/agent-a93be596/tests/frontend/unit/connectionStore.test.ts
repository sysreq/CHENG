// ============================================================================
// CHENG — connectionStore unit tests
// ============================================================================

import { describe, it, expect, beforeEach } from 'vitest';
import { useConnectionStore } from '@/store/connectionStore';

function resetStore() {
  const store = useConnectionStore.getState();
  store.setState('disconnected');
  store.resetAttempts();
}

describe('connectionStore', () => {
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

  it('setState transitions state', () => {
    useConnectionStore.getState().setState('connecting');
    expect(useConnectionStore.getState().state).toBe('connecting');

    useConnectionStore.getState().setState('connected');
    expect(useConnectionStore.getState().state).toBe('connected');
  });

  it('setError sets state to error with message', () => {
    useConnectionStore.getState().setError('Connection refused');
    const { state, lastError } = useConnectionStore.getState();
    expect(state).toBe('error');
    expect(lastError).toBe('Connection refused');
  });

  it('incrementAttempt increases reconnectAttempts', () => {
    useConnectionStore.getState().incrementAttempt();
    expect(useConnectionStore.getState().reconnectAttempts).toBe(1);

    useConnectionStore.getState().incrementAttempt();
    expect(useConnectionStore.getState().reconnectAttempts).toBe(2);
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
