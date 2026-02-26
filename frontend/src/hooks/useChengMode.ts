// ============================================================================
// CHENG — useChengMode (#150)
//
// Fetches /api/mode from the backend to determine whether we are running in
// 'cloud' or 'local' mode.  Returns the mode string and a loading flag.
//
// Caches the result only after a SUCCESSFUL fetch so that transient network
// failures do not permanently disable cloud-mode behaviour for the session.
// A failed fetch returns 'local' as a safe fallback and leaves the cache
// empty so the next render can retry.
// ============================================================================

import { useState, useEffect } from 'react';

export type ChengMode = 'local' | 'cloud';

interface ModeState {
  mode: ChengMode;
  loading: boolean;
  error: boolean;
}

let _cachedMode: ChengMode | null = null;

/**
 * Fetch and cache CHENG_MODE from the backend (/api/mode).
 *
 * - Caches on SUCCESS — subsequent renders skip the network call.
 * - Does NOT cache on failure — transient errors allow retry on remount.
 * - Returns 'local' as an in-flight/error fallback (backward-compatible).
 */
export function useChengMode(): Omit<ModeState, 'error'> & { error: boolean } {
  const [state, setState] = useState<ModeState>({
    mode: _cachedMode ?? 'local',
    loading: _cachedMode === null,
    error: false,
  });

  useEffect(() => {
    if (_cachedMode !== null) return; // already resolved — no network needed

    let cancelled = false;
    fetch('/api/mode')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: { mode?: string }) => {
        if (cancelled) return;
        const mode: ChengMode = data.mode === 'cloud' ? 'cloud' : 'local';
        // Only cache on success so transient failures allow retry
        _cachedMode = mode;
        setState({ mode, loading: false, error: false });
      })
      .catch(() => {
        if (cancelled) return;
        // Do NOT set _cachedMode — leaves it null so next mount can retry
        setState({ mode: 'local', loading: false, error: true });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
