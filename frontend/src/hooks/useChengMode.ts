// ============================================================================
// CHENG — useChengMode (#150)
//
// Fetches /api/mode from the backend to determine whether we are running in
// 'cloud' or 'local' mode.  Returns the mode string and a loading flag.
//
// Caches the result after the first successful fetch so subsequent renders
// do not make additional network requests.
// ============================================================================

import { useState, useEffect } from 'react';

export type ChengMode = 'local' | 'cloud';

interface ModeState {
  mode: ChengMode;
  loading: boolean;
}

let _cachedMode: ChengMode | null = null;

/**
 * Fetch and cache CHENG_MODE from the backend (/api/mode).
 * Defaults to 'local' if the request fails (backward-compatible).
 */
export function useChengMode(): ModeState {
  const [state, setState] = useState<ModeState>({
    mode: _cachedMode ?? 'local',
    loading: _cachedMode === null,
  });

  useEffect(() => {
    if (_cachedMode !== null) return; // already resolved

    let cancelled = false;
    fetch('/api/mode')
      .then((r) => r.json())
      .then((data: { mode?: string }) => {
        if (cancelled) return;
        const mode: ChengMode = data.mode === 'cloud' ? 'cloud' : 'local';
        _cachedMode = mode;
        setState({ mode, loading: false });
      })
      .catch(() => {
        if (cancelled) return;
        // Default to local on error (safe fallback)
        _cachedMode = 'local';
        setState({ mode: 'local', loading: false });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
