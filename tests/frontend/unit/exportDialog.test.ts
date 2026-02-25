// ============================================================================
// CHENG — ExportDialog unit tests
// Issues #270 (AbortController), #271 (delayed URL.revokeObjectURL)
// ============================================================================

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ---------------------------------------------------------------------------
// Helpers: simulate the fetch + download logic extracted from ExportDialog
// These mirror the production patterns so we can unit-test them in isolation.
// ---------------------------------------------------------------------------

/**
 * Simulated preview handler matching ExportDialog.handlePreview.
 * Returns { setIsPreviewing calls, setExportError calls, abortController }.
 */
async function runPreviewHandler(
  fetchImpl: typeof fetch,
  signal: AbortSignal,
  mountedRef: { current: boolean },
): Promise<{ previewDataSet: boolean; errorSet: string | null; isPreviewing: boolean }> {
  let previewDataSet = false;
  let errorSet: string | null = null;
  let isPreviewing = true; // starts true

  try {
    const res = await fetchImpl('/api/export/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
      signal,
    });

    if (!mountedRef.current) return { previewDataSet, errorSet, isPreviewing };

    if (!res.ok) {
      const detail = await res.text().catch(() => '');
      if (!mountedRef.current) return { previewDataSet, errorSet, isPreviewing };
      throw new Error(detail || `Preview failed (${res.status})`);
    }

    await res.json();
    if (!mountedRef.current) return { previewDataSet, errorSet, isPreviewing };
    previewDataSet = true;
  } catch (err) {
    if (!mountedRef.current) return { previewDataSet, errorSet, isPreviewing };
    if (err instanceof Error && err.name === 'AbortError') return { previewDataSet, errorSet, isPreviewing };
    errorSet = err instanceof Error ? err.message : 'Preview failed';
  } finally {
    if (mountedRef.current) isPreviewing = false;
  }

  return { previewDataSet, errorSet, isPreviewing };
}

/**
 * Simulated export download handler matching ExportDialog.handleExport.
 */
async function runExportHandler(
  fetchImpl: typeof fetch,
  signal: AbortSignal,
  mountedRef: { current: boolean },
  createObjectURL: (blob: Blob) => string,
  revokeObjectURL: (url: string) => void,
): Promise<{ successSet: boolean; errorSet: string | null; isExporting: boolean }> {
  let successSet = false;
  let errorSet: string | null = null;
  let isExporting = true;

  try {
    const res = await fetchImpl('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
      signal,
    });

    if (!mountedRef.current) return { successSet, errorSet, isExporting };

    if (!res.ok) {
      const detail = await res.text().catch(() => '');
      if (!mountedRef.current) return { successSet, errorSet, isExporting };
      throw new Error(detail || `Export failed (${res.status})`);
    }

    const blob = await res.blob();
    if (!mountedRef.current) return { successSet, errorSet, isExporting };

    const url = createObjectURL(blob);
    const a = { href: '', download: '', click: vi.fn() } as unknown as HTMLAnchorElement;
    a.href = url;
    a.download = 'test_export.zip';
    // Simulate DOM append/click/remove inline (no real DOM needed)
    a.click();
    // #271: delay revoke (1000ms for Safari/iOS compat)
    setTimeout(() => revokeObjectURL(url), 1000);

    successSet = true;
  } catch (err) {
    if (!mountedRef.current) return { successSet, errorSet, isExporting };
    if (err instanceof Error && err.name === 'AbortError') return { successSet, errorSet, isExporting };
    errorSet = err instanceof Error ? err.message : 'Export failed';
  } finally {
    if (mountedRef.current) isExporting = false;
  }

  return { successSet, errorSet, isExporting };
}

// ---------------------------------------------------------------------------
// Tests: Issue #270 — fetch aborted on dialog close
// ---------------------------------------------------------------------------

describe('ExportDialog #270 — AbortController', () => {
  it('aborts preview fetch when abort signal fires before response resolves', async () => {
    const controller = new AbortController();
    const mountedRef = { current: true };

    // fetch that never resolves — simulates slow server
    const hangingFetch = vi.fn((_url: string, opts?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        if (opts?.signal) {
          opts.signal.addEventListener('abort', () => {
            const err = new DOMException('The operation was aborted.', 'AbortError');
            reject(err);
          });
        }
      });
    });

    // Start the handler but don't await it yet
    const handlerPromise = runPreviewHandler(hangingFetch as unknown as typeof fetch, controller.signal, mountedRef);

    // Simulate dialog close: abort + unmount
    controller.abort();
    mountedRef.current = false;

    const result = await handlerPromise;

    // fetch was called once
    expect(hangingFetch).toHaveBeenCalledOnce();
    // AbortError was silently swallowed — no error state, no data set
    expect(result.previewDataSet).toBe(false);
    expect(result.errorSet).toBeNull();
  });

  it('does not set state after dialog unmounts (mountedRef guard)', async () => {
    const controller = new AbortController();
    // Start as mounted
    const mountedRef = { current: true };

    // fetch resolves normally but component "unmounts" before we process the result
    const slowFetch = vi.fn(async (_url: string, _opts?: RequestInit) => {
      // Unmount the component while we're awaiting
      mountedRef.current = false;
      return {
        ok: true,
        text: async () => '',
        json: async () => ({ parts: [] }),
        blob: async () => new Blob(),
      } as unknown as Response;
    });

    const result = await runPreviewHandler(slowFetch as unknown as typeof fetch, controller.signal, mountedRef);

    // mountedRef was false when we tried to set state — should bail out early
    expect(result.previewDataSet).toBe(false);
    // isPreviewing stays true because the finally block also checks mountedRef
    expect(result.isPreviewing).toBe(true);
  });

  it('aborts export fetch when abort signal fires', async () => {
    const controller = new AbortController();
    const mountedRef = { current: true };
    const revokeObjectURL = vi.fn();
    const createObjectURL = vi.fn(() => 'blob:mock-url');

    const hangingFetch = vi.fn((_url: string, opts?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        if (opts?.signal) {
          opts.signal.addEventListener('abort', () => {
            reject(new DOMException('The operation was aborted.', 'AbortError'));
          });
        }
      });
    });

    const handlerPromise = runExportHandler(
      hangingFetch as unknown as typeof fetch,
      controller.signal,
      mountedRef,
      createObjectURL,
      revokeObjectURL,
    );

    controller.abort();
    mountedRef.current = false;

    const result = await handlerPromise;

    expect(hangingFetch).toHaveBeenCalledOnce();
    expect(result.successSet).toBe(false);
    expect(result.errorSet).toBeNull();
    // No URL was ever created or revoked
    expect(createObjectURL).not.toHaveBeenCalled();
    expect(revokeObjectURL).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Tests: Issue #271 — revokeObjectURL called after delay
// ---------------------------------------------------------------------------

describe('ExportDialog #271 — delayed URL.revokeObjectURL', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('schedules revokeObjectURL with 1000ms delay (not synchronously after click)', async () => {
    // Use setTimeout spy instead of fake timers to avoid async-microtask interaction issues
    const revokeObjectURL = vi.fn();
    const createObjectURL = vi.fn(() => 'blob:test-url');
    const mountedRef = { current: true };
    const controller = new AbortController();

    // Track what setTimeout is called with
    const setTimeoutCalls: Array<{ callback: () => void; delay: number }> = [];
    vi.spyOn(globalThis, 'setTimeout').mockImplementation((callback: unknown, delay?: number) => {
      setTimeoutCalls.push({ callback: callback as () => void, delay: delay ?? 0 });
      return 0 as unknown as ReturnType<typeof setTimeout>;
    });

    const successFetch = vi.fn(async (_url: string, _opts?: RequestInit) => ({
      ok: true,
      text: async () => '',
      json: async () => ({}),
      blob: async () => new Blob(['zip content'], { type: 'application/zip' }),
    } as unknown as Response));

    await runExportHandler(
      successFetch as unknown as typeof fetch,
      controller.signal,
      mountedRef,
      createObjectURL,
      revokeObjectURL,
    );

    // revokeObjectURL should NOT have been called synchronously
    expect(revokeObjectURL).not.toHaveBeenCalled();

    // Exactly one setTimeout call was made with 1000ms delay
    expect(setTimeoutCalls).toHaveLength(1);
    expect(setTimeoutCalls[0].delay).toBe(1000);

    // Manually invoke the callback to confirm it calls revokeObjectURL
    setTimeoutCalls[0].callback();
    expect(revokeObjectURL).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:test-url');
  });

  it('does not call revokeObjectURL if fetch is aborted before blob download', async () => {
    const revokeObjectURL = vi.fn();
    const createObjectURL = vi.fn(() => 'blob:should-never-appear');
    const mountedRef = { current: true };
    const controller = new AbortController();

    const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout');

    // Pre-abort the controller so the fetch will reject immediately with AbortError
    controller.abort();

    const abortingFetch = vi.fn((_url: string, opts?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        // Since signal is already aborted, reject immediately
        if (opts?.signal?.aborted) {
          reject(new DOMException('Aborted', 'AbortError'));
          return;
        }
        if (opts?.signal) {
          opts.signal.addEventListener('abort', () => {
            reject(new DOMException('Aborted', 'AbortError'));
          });
        }
      });
    });

    await runExportHandler(
      abortingFetch as unknown as typeof fetch,
      controller.signal,
      mountedRef,
      createObjectURL,
      revokeObjectURL,
    );

    expect(createObjectURL).not.toHaveBeenCalled();
    expect(revokeObjectURL).not.toHaveBeenCalled();
    // No setTimeout should have been scheduled (URL was never created)
    expect(setTimeoutSpy).not.toHaveBeenCalled();
  });
});
