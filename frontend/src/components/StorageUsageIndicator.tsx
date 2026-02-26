// ============================================================================
// CHENG — StorageUsageIndicator (#150)
//
// Shows how much browser storage is used by the IndexedDB persistence layer.
// Only rendered in cloud mode.  Displayed in the status bar next to the
// connection status.
//
// Refreshes every 30 seconds so the display stays current without hammering
// the storage API on every render.
// ============================================================================

import { useState, useEffect } from 'react';
import { idbEstimateUsageBytes } from '@/lib/indexeddb';

const MAX_BYTES = 50 * 1024 * 1024; // 50 MB advertised capacity
const REFRESH_INTERVAL_MS = 30_000;

/** Format bytes to a human-readable string (KB or MB). */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

interface StorageUsageIndicatorProps {
  /** Only show this indicator when true. */
  visible: boolean;
}

/**
 * A compact storage-usage badge rendered in the status bar footer.
 *
 * Example: "Storage: 12.3 KB / 50 MB"
 *
 * The display refreshes every 30 s.  On the first render it fetches the
 * usage immediately.
 */
export default function StorageUsageIndicator({ visible }: StorageUsageIndicatorProps) {
  const [usedBytes, setUsedBytes] = useState<number | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!visible) return;

    let cancelled = false;

    const refresh = () => {
      idbEstimateUsageBytes()
        .then((bytes) => {
          if (!cancelled) {
            setUsedBytes(bytes);
            setError(false);
          }
        })
        .catch(() => {
          if (!cancelled) setError(true);
        });
    };

    refresh();
    const timer = setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [visible]);

  if (!visible) return null;
  if (error) return null; // silently hide if storage API is unavailable

  const usedStr = usedBytes !== null ? formatBytes(usedBytes) : '...';
  const maxStr = formatBytes(MAX_BYTES);
  const pct = usedBytes !== null ? Math.min(100, (usedBytes / MAX_BYTES) * 100) : 0;

  return (
    <div
      title={`Browser storage used by CHENG designs: ${usedStr} of ${maxStr}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 11,
        color: 'var(--color-text-secondary)',
        marginRight: 12,
      }}
    >
      {/* Small progress bar */}
      <div
        style={{
          width: 40,
          height: 4,
          borderRadius: 2,
          backgroundColor: 'var(--color-border)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            borderRadius: 2,
            backgroundColor:
              pct > 80
                ? 'var(--color-error)'
                : pct > 60
                  ? 'var(--color-warning)'
                  : 'var(--color-success)',
            transition: 'width 0.4s ease',
          }}
        />
      </div>
      <span>
        {usedStr} / {maxStr}
      </span>
    </div>
  );
}
