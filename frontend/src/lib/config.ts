// ============================================================================
// CHENG — API Configuration Helpers
// ============================================================================

/**
 * Get the base URL for REST API calls.
 *
 * Uses VITE_API_URL env var if set, otherwise defaults to empty string
 * (same-origin). Empty default works with both Vite dev proxy and
 * production (FastAPI serves static at :8000).
 */
export function getApiUrl(): string {
  return import.meta.env.VITE_API_URL ?? '';
}

/**
 * Get the WebSocket URL for the preview channel.
 *
 * Uses VITE_WS_URL env var if set, otherwise computes from
 * window.location (ws:// for http, wss:// for https).
 */
export function getWebSocketUrl(): string {
  const envUrl = import.meta.env.VITE_WS_URL;
  if (envUrl) {
    return `${envUrl}/ws/preview`;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/preview`;
}
