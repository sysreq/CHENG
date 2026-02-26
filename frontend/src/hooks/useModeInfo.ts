// ============================================================================
// CHENG — useModeInfo: fetch deployment mode from /api/info
// Issue #152 (Mode badge)
// ============================================================================

import { useEffect, useState } from 'react';

export type DeploymentMode = 'local' | 'cloud';

export interface ModeInfo {
  mode: DeploymentMode;
  version: string;
}

/**
 * Fetches deployment mode from /api/info on mount.
 *
 * Falls back to "local" on any fetch or parse failure so the badge is
 * always displayed even if the endpoint is unavailable or not yet merged.
 *
 * @returns The parsed ModeInfo, or null while the fetch is in-flight.
 */
export function useModeInfo(): ModeInfo | null {
  const [info, setInfo] = useState<ModeInfo | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetch('/api/info')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<unknown>;
      })
      .then((data) => {
        if (cancelled) return;
        // Validate shape before trusting it
        const raw = data as Record<string, unknown> | null;
        const mode: DeploymentMode =
          raw?.['mode'] === 'cloud' ? 'cloud' : 'local';
        const version = String(raw?.['version'] ?? '0.1.0');
        setInfo({ mode, version });
      })
      .catch(() => {
        // Graceful degradation: fall back to "local" if endpoint is unreachable
        if (!cancelled) {
          setInfo({ mode: 'local', version: '0.1.0' });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return info;
}
