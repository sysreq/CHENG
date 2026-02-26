// ============================================================================
// CHENG — Disconnected Banner
// Shown at the top of the viewport when WebSocket is not connected.
// ============================================================================

import { useConnectionStore } from '@/store/connectionStore';

/**
 * A thin warning banner displayed when the WebSocket connection is lost.
 * Shown for 'disconnected', 'error', and 'reconnecting' states.
 * Hidden when 'connected' or 'connecting' (initial connect).
 */
export default function DisconnectedBanner() {
  const state = useConnectionStore((s) => s.state);
  const lastError = useConnectionStore((s) => s.lastError);

  if (state === 'connected' || state === 'connecting') {
    return null;
  }

  const messages: Record<string, string> = {
    reconnecting: 'Connection lost. Attempting to reconnect...',
    disconnected: 'Disconnected from server. Parameter changes are disabled.',
    error: lastError ?? 'Connection error. Parameter changes are disabled.',
  };

  const isWarning = state === 'reconnecting';

  return (
    <div
      role="alert"
      aria-live="assertive"
      style={{
        position: 'absolute',
        top: 'var(--toolbar-height, 36px)',
        left: 0,
        right: 0,
        zIndex: 20,
        padding: '6px 12px',
        fontSize: 11,
        fontWeight: 500,
        textAlign: 'center',
        backgroundColor: isWarning
          ? 'rgba(202, 138, 4, 0.9)'
          : 'rgba(220, 38, 38, 0.9)',
        color: '#fff',
      }}
    >
      {messages[state]}
    </div>
  );
}
