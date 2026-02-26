// ============================================================================
// CHENG -- ModeBadge + useModeInfo unit tests
// Issue #152 (Mode badge -- Local/Cloud indicator)
// ============================================================================

import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook, render, screen, waitFor } from '@testing-library/react';
import { useModeInfo } from '@/hooks/useModeInfo';
import { ModeBadge } from '@/components/ModeBadge';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetch(response: unknown, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 404,
    json: () => Promise.resolve(response),
  } as Response);
}

function mockFetchNetworkError() {
  return vi.fn().mockRejectedValue(new Error('Network error'));
}

// ---------------------------------------------------------------------------
// useModeInfo hook tests
// ---------------------------------------------------------------------------

describe('useModeInfo', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('returns null initially before fetch resolves', () => {
    // Never-resolving fetch
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));

    const { result } = renderHook(() => useModeInfo());
    expect(result.current).toBeNull();
  });

  it('returns "local" mode when API responds with mode=local', async () => {
    vi.stubGlobal('fetch', mockFetch({ mode: 'local', version: '0.1.0' }));

    const { result } = renderHook(() => useModeInfo());

    await waitFor(() => expect(result.current).not.toBeNull());

    expect(result.current?.mode).toBe('local');
    expect(result.current?.version).toBe('0.1.0');
  });

  it('returns "cloud" mode when API responds with mode=cloud', async () => {
    vi.stubGlobal('fetch', mockFetch({ mode: 'cloud', version: '0.1.0' }));

    const { result } = renderHook(() => useModeInfo());

    await waitFor(() => expect(result.current).not.toBeNull());

    expect(result.current?.mode).toBe('cloud');
  });

  it('falls back to "local" on network error', async () => {
    vi.stubGlobal('fetch', mockFetchNetworkError());

    const { result } = renderHook(() => useModeInfo());

    await waitFor(() => expect(result.current).not.toBeNull());

    expect(result.current?.mode).toBe('local');
  });

  it('falls back to "local" on non-OK HTTP response', async () => {
    vi.stubGlobal('fetch', mockFetch({ error: 'Not Found' }, false));

    const { result } = renderHook(() => useModeInfo());

    await waitFor(() => expect(result.current).not.toBeNull());

    expect(result.current?.mode).toBe('local');
  });

  it('falls back to "local" on unknown mode value', async () => {
    vi.stubGlobal('fetch', mockFetch({ mode: 'staging', version: '0.2.0' }));

    const { result } = renderHook(() => useModeInfo());

    await waitFor(() => expect(result.current).not.toBeNull());

    // Unknown mode defaults to "local"
    expect(result.current?.mode).toBe('local');
  });
});

// ---------------------------------------------------------------------------
// ModeBadge component tests
// ---------------------------------------------------------------------------

describe('ModeBadge', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('renders nothing initially (before fetch resolves)', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));

    const { container } = render(<ModeBadge />);
    expect(container.firstChild).toBeNull();
  });

  it('renders "Local" badge in local mode', async () => {
    vi.stubGlobal('fetch', mockFetch({ mode: 'local', version: '0.1.0' }));

    render(<ModeBadge />);

    await waitFor(() => expect(screen.getByText('Local')).toBeTruthy());

    const badge = screen.getByText('Local');
    expect(badge.getAttribute('title')).toBe('Running in local Docker mode');
    expect(badge.getAttribute('aria-label')).toBe('Deployment mode: Local');
  });

  it('renders "Cloud" badge in cloud mode', async () => {
    vi.stubGlobal('fetch', mockFetch({ mode: 'cloud', version: '0.1.0' }));

    render(<ModeBadge />);

    await waitFor(() => expect(screen.getByText('Cloud')).toBeTruthy());

    const badge = screen.getByText('Cloud');
    expect(badge.getAttribute('title')).toBe('Running in Cloud (Google Cloud Run) mode');
    expect(badge.getAttribute('aria-label')).toBe('Deployment mode: Cloud');
  });

  it('renders "Local" badge on fetch failure (graceful degradation)', async () => {
    vi.stubGlobal('fetch', mockFetchNetworkError());

    render(<ModeBadge />);

    await waitFor(() => expect(screen.getByText('Local')).toBeTruthy());
  });
});
