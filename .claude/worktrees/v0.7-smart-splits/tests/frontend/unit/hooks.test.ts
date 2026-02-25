// ============================================================================
// CHENG — Hooks unit tests
// ============================================================================

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDesignSync } from '@/hooks/useDesignSync';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDesignStore } from '@/store/designStore';
import { useConnectionStore } from '@/store/connectionStore';

// Mock WebSocket — track instances for test assertions
const wsInstances: MockWebSocket[] = [];

class MockWebSocket {
  url: string;
  readyState: number = 0; // CONNECTING
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((ev: any) => void) | null = null;
  onerror: (() => void) | null = null;
  binaryType: string = 'blob';

  static OPEN = 1;
  static CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    wsInstances.push(this);
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) this.onopen();
    }, 0);
  }

  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose();
  });
}

describe('Hooks', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    wsInstances.length = 0;
    vi.stubGlobal('WebSocket', MockWebSocket);
    // Reset stores
    useDesignStore.getState().newDesign();
    useConnectionStore.getState().resetAttempts();
    useConnectionStore.getState().setState('disconnected');
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  describe('useDesignSync', () => {
    it('throttles slider changes', async () => {
      const send = vi.fn();
      renderHook(() => useDesignSync(send));

      // 1. Slider change - immediate send
      act(() => {
        useDesignStore.getState().setParam('wingSpan', 1300, 'slider');
      });
      expect(send).toHaveBeenCalledTimes(1);

      // 2. Rapid slider changes - should be throttled
      act(() => {
        useDesignStore.getState().setParam('wingSpan', 1400, 'slider');
        useDesignStore.getState().setParam('wingSpan', 1500, 'slider');
      });
      // Still 1 (throttled)
      expect(send).toHaveBeenCalledTimes(1);

      // 3. Fast forward 100ms
      act(() => {
        vi.advanceTimersByTime(100);
      });
      // Trailing edge should have fired
      expect(send).toHaveBeenCalledTimes(2);
      expect(send).toHaveBeenLastCalledWith(expect.objectContaining({ wingSpan: 1500 }));
    });

    it('debounces text changes', async () => {
      const send = vi.fn();
      renderHook(() => useDesignSync(send));

      // 1. Text change - no immediate send
      act(() => {
        useDesignStore.getState().setParam('name', 'My Plane', 'text');
      });
      expect(send).not.toHaveBeenCalled();

      // 2. Advance partial time
      act(() => {
        vi.advanceTimersByTime(150);
      });
      expect(send).not.toHaveBeenCalled();

      // 3. Advance to 300ms
      act(() => {
        vi.advanceTimersByTime(150);
      });
      expect(send).toHaveBeenCalledTimes(1);
      expect(send).toHaveBeenLastCalledWith(expect.objectContaining({ name: 'My Plane' }));
    });

    it('sends immediate changes without delay', async () => {
      const send = vi.fn();
      renderHook(() => useDesignSync(send));

      act(() => {
        useDesignStore.getState().setParam('fuselagePreset', 'Pod', 'immediate');
      });
      expect(send).toHaveBeenCalledTimes(1);
    });
  });

  describe('useWebSocket', () => {
    it('transitions to connected state on open', async () => {
      const { result } = renderHook(() => useWebSocket());
      
      // Wait for MockWebSocket's simulated open
      await act(async () => {
        await vi.runOnlyPendingTimersAsync();
      });

      expect(useConnectionStore.getState().state).toBe('connected');
    });

    it('implements exponential backoff on reconnection', async () => {
      renderHook(() => useWebSocket());

      // 1. Connect
      await act(async () => {
        await vi.runOnlyPendingTimersAsync();
      });
      expect(useConnectionStore.getState().state).toBe('connected');

      // 2. Simulate unintended close
      const wsInstance = wsInstances[0];
      act(() => {
        if (wsInstance.onclose) wsInstance.onclose();
      });
      
      expect(useConnectionStore.getState().state).toBe('reconnecting');
      expect(useConnectionStore.getState().reconnectAttempts).toBe(1);

      // 3. Wait 1s (initial delay)
      await act(async () => {
        vi.advanceTimersByTime(1000);
        await vi.runOnlyPendingTimersAsync();
      });
      // Should have attempted second connection
      expect(wsInstances.length).toBe(2);
    });
  });
});
