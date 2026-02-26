// ============================================================================
// CHENG — useColdStart hook unit tests
// Issue #151: Cold start UX
// ============================================================================

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useColdStart } from '@/hooks/useColdStart';
import { useConnectionStore } from '@/store/connectionStore';
import { useDesignStore } from '@/store/designStore';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resetStores() {
  useConnectionStore.getState().setState('disconnected');
  useConnectionStore.getState().resetAttempts();
  useDesignStore.getState().newDesign();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useColdStart', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    resetStores();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ── Initial state ──────────────────────────────────────────────────────────

  it('starts with overlay not visible', () => {
    const { result } = renderHook(() => useColdStart());
    expect(result.current.visible).toBe(false);
    expect(result.current.phase).toBe('idle');
  });

  // ── Fast connect — no overlay ──────────────────────────────────────────────

  it('does not show overlay when connection is established within threshold', () => {
    const { result } = renderHook(() => useColdStart());

    // Start connecting
    act(() => {
      useConnectionStore.getState().setState('connecting');
    });

    // Connect before 1s threshold
    act(() => {
      vi.advanceTimersByTime(500);
    });
    act(() => {
      useConnectionStore.getState().setState('connected');
    });

    expect(result.current.visible).toBe(false);
    expect(result.current.phase).toBe('dismissed');
  });

  // ── Slow connect — overlay shown ───────────────────────────────────────────

  it('shows overlay when connection takes longer than 1 second', () => {
    const { result } = renderHook(() => useColdStart());

    // Start connecting
    act(() => {
      useConnectionStore.getState().setState('connecting');
    });

    // Advance past the threshold
    act(() => {
      vi.advanceTimersByTime(1100);
    });

    expect(result.current.visible).toBe(true);
    expect(result.current.phase).toBe('starting');
  });

  // ── Phase progression ──────────────────────────────────────────────────────

  it('advances from starting to loading after 3.5 seconds', () => {
    const { result } = renderHook(() => useColdStart());

    act(() => {
      useConnectionStore.getState().setState('connecting');
    });
    act(() => {
      vi.advanceTimersByTime(1100);
    });

    expect(result.current.phase).toBe('starting');

    act(() => {
      vi.advanceTimersByTime(3600);
    });

    expect(result.current.phase).toBe('loading');
  });

  it('advances from loading to initializing after 4 more seconds', () => {
    const { result } = renderHook(() => useColdStart());

    act(() => {
      useConnectionStore.getState().setState('connecting');
    });
    act(() => {
      vi.advanceTimersByTime(1100);
    });
    act(() => {
      vi.advanceTimersByTime(3600); // → loading
    });
    act(() => {
      vi.advanceTimersByTime(4100); // → initializing
    });

    expect(result.current.phase).toBe('initializing');
  });

  // ── Connected transitions to ready ────────────────────────────────────────

  it('transitions to ready phase when connection established (overlay was shown)', () => {
    const { result } = renderHook(() => useColdStart());

    act(() => {
      useConnectionStore.getState().setState('connecting');
    });
    act(() => {
      vi.advanceTimersByTime(1100);
    });

    expect(result.current.visible).toBe(true);

    act(() => {
      useConnectionStore.getState().setState('connected');
    });

    expect(result.current.phase).toBe('ready');
    // Overlay still visible until first mesh arrives
    expect(result.current.visible).toBe(true);
  });

  // ── Dismissed on first mesh ────────────────────────────────────────────────

  it('dismisses overlay after first mesh is received in ready phase', () => {
    const { result } = renderHook(() => useColdStart());

    act(() => {
      useConnectionStore.getState().setState('connecting');
    });
    act(() => {
      vi.advanceTimersByTime(1100);
    });
    act(() => {
      useConnectionStore.getState().setState('connected');
    });

    expect(result.current.phase).toBe('ready');

    // Simulate first mesh arriving
    act(() => {
      useDesignStore.getState().setMeshData({
        vertices: new Float32Array([0, 1, 2]),
        normals: new Float32Array([0, 0, 1]),
        faces: new Uint32Array([0]),
        vertexCount: 1,
        faceCount: 1,
        componentRanges: {},
      });
    });

    // Advance dismiss timer (600ms)
    act(() => {
      vi.advanceTimersByTime(700);
    });

    expect(result.current.phase).toBe('dismissed');
    expect(result.current.visible).toBe(false);
  });

  // ── No overlay for reconnects ──────────────────────────────────────────────

  it('does not show overlay when reconnecting (not initial load)', () => {
    const { result } = renderHook(() => useColdStart());

    // Simulate a fast initial connect (no overlay shown)
    act(() => {
      useConnectionStore.getState().setState('connecting');
    });
    act(() => {
      vi.advanceTimersByTime(200); // fast connect
    });
    act(() => {
      useConnectionStore.getState().setState('connected');
    });

    expect(result.current.phase).toBe('dismissed');

    // Now simulate a reconnect cycle
    act(() => {
      useConnectionStore.getState().setState('reconnecting');
    });
    act(() => {
      vi.advanceTimersByTime(2000); // well past threshold
    });

    // Phase should stay dismissed — no overlay for reconnects
    expect(result.current.visible).toBe(false);
    expect(result.current.phase).toBe('dismissed');
  });

  it('does not show overlay for reconnect even if connection is slow', () => {
    const { result } = renderHook(() => useColdStart());

    // Fast initial connect — hook deactivates
    act(() => {
      useConnectionStore.getState().setState('connecting');
    });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    act(() => {
      useConnectionStore.getState().setState('connected');
    });
    act(() => {
      useDesignStore.getState().setMeshData({
        vertices: new Float32Array([0]),
        normals: new Float32Array([0]),
        faces: new Uint32Array([0]),
        vertexCount: 1,
        faceCount: 1,
        componentRanges: {},
      });
    });
    act(() => {
      vi.advanceTimersByTime(700); // dismiss timer
    });

    expect(result.current.phase).toBe('dismissed');

    // Reconnect (simulating slow reconnect)
    act(() => {
      useConnectionStore.getState().setState('reconnecting');
    });
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    act(() => {
      useConnectionStore.getState().setState('connected');
    });

    // Should still be dismissed — overlay never shows for reconnects
    expect(result.current.visible).toBe(false);
  });

  // ── Threshold boundary ────────────────────────────────────────────────────

  it('does not show overlay at exactly the threshold boundary (999ms)', () => {
    const { result } = renderHook(() => useColdStart());

    act(() => {
      useConnectionStore.getState().setState('connecting');
    });
    act(() => {
      vi.advanceTimersByTime(999);
    });

    // Just before threshold — still idle
    expect(result.current.phase).toBe('idle');
    expect(result.current.visible).toBe(false);
  });

  it('shows overlay at just over threshold (1001ms)', () => {
    const { result } = renderHook(() => useColdStart());

    act(() => {
      useConnectionStore.getState().setState('connecting');
    });
    act(() => {
      vi.advanceTimersByTime(1001);
    });

    expect(result.current.phase).toBe('starting');
    expect(result.current.visible).toBe(true);
  });
});
