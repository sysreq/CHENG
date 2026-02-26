// ============================================================================
// CHENG — Connection Status Indicator
// Green/Yellow/Red dot with label + disconnection banner
// ============================================================================

import { useConnectionStore } from '@/store/connectionStore';
import type { ConnectionState } from '@/store/connectionStore';

/** Visual configuration for each connection state. */
const STATE_CONFIG: Record<
  ConnectionState,
  { color: string; label: string; pulse: boolean }
> = {
  connecting: {
    color: 'var(--color-warning)',
    label: 'Connecting...',
    pulse: true,
  },
  connected: {
    color: 'var(--color-success)',
    label: 'Connected',
    pulse: false,
  },
  reconnecting: {
    color: 'var(--color-warning)',
    label: 'Reconnecting...',
    pulse: true,
  },
  disconnected: {
    color: 'var(--color-error)',
    label: 'Disconnected',
    pulse: false,
  },
  error: {
    color: 'var(--color-error)',
    label: 'Connection Error',
    pulse: false,
  },
};

/**
 * Connection status indicator shown in the bottom-right corner of the status bar.
 *
 * Displays a colored dot and label:
 * - Yellow pulsing dot + "Connecting..." — initial connection
 * - Green dot + "Connected" — full functionality
 * - Yellow pulsing dot + "Reconnecting..." — retrying connection
 * - Red dot + "Disconnected" — no connection, max retries reached
 * - Red dot + "Connection Error" — WebSocket error
 */
export default function ConnectionStatus() {
  const state = useConnectionStore((s) => s.state);
  const reconnectAttempts = useConnectionStore((s) => s.reconnectAttempts);
  const maxReconnectAttempts = useConnectionStore((s) => s.maxReconnectAttempts);

  const config = STATE_CONFIG[state];

  const ariaLabel = state === 'reconnecting'
    ? `Connection status: ${config.label} (attempt ${reconnectAttempts} of ${maxReconnectAttempts})`
    : `Connection status: ${config.label}`;

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={ariaLabel}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 11,
        color: 'var(--color-text-secondary)',
      }}
    >
      {/* Status dot (decorative) */}
      <span
        aria-hidden="true"
        style={{
          display: 'inline-block',
          width: 8,
          height: 8,
          borderRadius: '50%',
          backgroundColor: config.color,
          animation: config.pulse ? 'pulse 1.5s ease-in-out infinite' : 'none',
          flexShrink: 0,
        }}
      />

      {/* Label — not hidden; aria-label on container provides the full description */}
      <span>{config.label}</span>

      {/* Show attempt count when reconnecting */}
      {state === 'reconnecting' && (
        <span style={{ color: 'var(--color-text-muted)' }}>
          ({reconnectAttempts}/{maxReconnectAttempts})
        </span>
      )}

      {/* Inline keyframes for pulse animation */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
