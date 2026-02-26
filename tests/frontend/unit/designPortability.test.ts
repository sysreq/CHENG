// ============================================================================
// CHENG — Design Portability unit tests (Issue #156)
// Tests exportDesignAsJson and importDesignFromJson store actions.
// ============================================================================

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { useDesignStore } from '@/store/designStore';

/** Reset store to initial state before each test. */
function resetStore() {
  useDesignStore.getState().newDesign();
  useDesignStore.temporal.getState().clear();
}

describe('designStore — design portability (Issue #156)', () => {
  beforeEach(() => {
    resetStore();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── exportDesignAsJson ─────────────────────────────────────────────

  describe('exportDesignAsJson', () => {
    it('triggers a file download with a .cheng extension', () => {
      // Spy on DOM element creation and URL API
      const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock');
      const revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
      const appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation((el) => el);
      const removeChildSpy = vi.spyOn(document.body, 'removeChild').mockImplementation((el) => el);

      // Capture the anchor element's attributes
      let capturedHref = '';
      let capturedDownload = '';
      const clickSpy = vi.fn();
      const originalCreate = document.createElement.bind(document);
      vi.spyOn(document, 'createElement').mockImplementation((tag) => {
        const el = originalCreate(tag);
        if (tag === 'a') {
          Object.defineProperty(el, 'href', {
            get: () => capturedHref,
            set: (v: string) => { capturedHref = v; },
          });
          Object.defineProperty(el, 'download', {
            get: () => capturedDownload,
            set: (v: string) => { capturedDownload = v; },
          });
          el.click = clickSpy;
        }
        return el;
      });

      useDesignStore.getState().exportDesignAsJson();

      expect(createObjectURLSpy).toHaveBeenCalledOnce();
      expect(clickSpy).toHaveBeenCalledOnce();
      expect(capturedDownload).toMatch(/\.cheng$/);
      expect(revokeObjectURLSpy).toHaveBeenCalledOnce();
      expect(appendChildSpy).toHaveBeenCalledOnce();
      expect(removeChildSpy).toHaveBeenCalledOnce();
    });

    it('filename is derived from the design name', () => {
      useDesignStore.getState().setParam('wingSpan', 1200); // make isDirty
      // Set a design name
      useDesignStore.getState().setDesignName('My Trainer V2');

      vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock');
      vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
      vi.spyOn(document.body, 'appendChild').mockImplementation((el) => el);
      vi.spyOn(document.body, 'removeChild').mockImplementation((el) => el);

      let capturedDownload = '';
      const originalCreate = document.createElement.bind(document);
      vi.spyOn(document, 'createElement').mockImplementation((tag) => {
        const el = originalCreate(tag);
        if (tag === 'a') {
          Object.defineProperty(el, 'download', {
            get: () => capturedDownload,
            set: (v: string) => { capturedDownload = v; },
          });
          el.click = vi.fn();
        }
        return el;
      });

      useDesignStore.getState().exportDesignAsJson();

      // Spaces should be replaced with underscores
      expect(capturedDownload).toBe('My_Trainer_V2.cheng');
    });

    it('exported JSON contains the current design data', () => {
      vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
      vi.spyOn(document.body, 'appendChild').mockImplementation((el) => el);
      vi.spyOn(document.body, 'removeChild').mockImplementation((el) => el);

      let capturedBlob: Blob | null = null;
      vi.spyOn(URL, 'createObjectURL').mockImplementation((blob) => {
        capturedBlob = blob as Blob;
        return 'blob:mock';
      });
      const originalCreate = document.createElement.bind(document);
      vi.spyOn(document, 'createElement').mockImplementation((tag) => {
        const el = originalCreate(tag);
        if (tag === 'a') {
          el.click = vi.fn();
        }
        return el;
      });

      useDesignStore.getState().setParam('wingSpan', 1337);
      useDesignStore.getState().exportDesignAsJson();

      expect(capturedBlob).not.toBeNull();
      // Read the blob content
      return capturedBlob!.text().then((text) => {
        const parsed = JSON.parse(text) as Record<string, unknown>;
        expect(parsed['wingSpan']).toBe(1337);
      });
    });
  });

  // ── importDesignFromJson (cloud mode) ─────────────────────────────

  describe('importDesignFromJson — cloud mode', () => {
    it('loads a valid design file directly into the store', async () => {
      const design = {
        version: '0.1.0',
        id: 'test-import-id',
        name: 'Imported Glider',
        wingSpan: 1800,
        // Include all other required fields by omission (Pydantic defaults)
      };
      const file = new File([JSON.stringify(design)], 'glider.cheng', {
        type: 'application/json',
      });

      await useDesignStore.getState().importDesignFromJson(file, true);

      const state = useDesignStore.getState();
      expect(state.design.wingSpan).toBe(1800);
      expect(state.designName).toBe('Imported Glider');
      expect(state.isLoading).toBe(false);
    });

    it('rejects and clears isLoading for non-JSON file content', async () => {
      const file = new File(['not valid json!'], 'bad.cheng', {
        type: 'application/json',
      });

      await expect(
        useDesignStore.getState().importDesignFromJson(file, true),
      ).rejects.toThrow('File is not valid JSON');

      const state = useDesignStore.getState();
      // fileError is NOT set by importDesignFromJson — it is reserved for save
      // errors. The Toolbar handles import error display via local importError state.
      expect(state.fileError).toBeNull();
      expect(state.isLoading).toBe(false);
    });

    it('rejects with descriptive error for non-object JSON', async () => {
      const file = new File(['"just a string"'], 'bad.cheng', {
        type: 'application/json',
      });

      await expect(
        useDesignStore.getState().importDesignFromJson(file, true),
      ).rejects.toThrow('not a JSON object');

      expect(useDesignStore.getState().fileError).toBeNull();
    });

    it('rejects when file lacks both version and wingSpan fields', async () => {
      const file = new File(
        [JSON.stringify({ someRandomField: 42 })],
        'not_a_design.cheng',
        { type: 'application/json' },
      );

      await expect(
        useDesignStore.getState().importDesignFromJson(file, true),
      ).rejects.toThrow(/missing required fields/);

      expect(useDesignStore.getState().fileError).toBeNull();
    });

    it('fills missing fields from defaults when importing partial design', async () => {
      // Only specify wingSpan — all other fields should default from Trainer preset
      const partial = { version: '0.1.0', wingSpan: 750, name: 'Partial Import' };
      const file = new File([JSON.stringify(partial)], 'partial.cheng', {
        type: 'application/json',
      });

      await useDesignStore.getState().importDesignFromJson(file, true);

      const state = useDesignStore.getState();
      expect(state.design.wingSpan).toBe(750);
      expect(state.design.name).toBe('Partial Import');
      // fuselagePreset should default to a known value (not undefined)
      expect(state.design.fuselagePreset).toBeTruthy();
    });

    it('marks design as dirty after cloud import', async () => {
      const design = { version: '0.1.0', id: '', name: 'Test', wingSpan: 900 };
      const file = new File([JSON.stringify(design)], 'test.cheng', {
        type: 'application/json',
      });

      await useDesignStore.getState().importDesignFromJson(file, true);

      expect(useDesignStore.getState().isDirty).toBe(true);
    });
  });

  // ── importDesignFromJson (local mode) ─────────────────────────────

  describe('importDesignFromJson — local mode', () => {
    it('uploads file to backend and loads the returned design', async () => {
      const uploadedDesign = {
        version: '0.1.0',
        id: 'server-assigned-uuid',
        name: 'Server Plane',
        wing_span: 1100,
        wingSpan: 1100,
      };

      // Mock the fetch calls
      const fetchMock = vi.spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce(
          // POST /api/designs/import
          new Response(JSON.stringify({ id: 'server-assigned-uuid' }), { status: 201 }),
        )
        .mockResolvedValueOnce(
          // GET /api/designs/{id}
          new Response(JSON.stringify(uploadedDesign), { status: 200 }),
        );

      const file = new File([JSON.stringify({ name: 'Server Plane', wing_span: 1100 })], 'plane.cheng', {
        type: 'application/json',
      });

      await useDesignStore.getState().importDesignFromJson(file, false);

      expect(fetchMock).toHaveBeenCalledTimes(2);
      const firstCall = fetchMock.mock.calls[0];
      expect(firstCall[0]).toBe('/api/designs/import');
      expect((firstCall[1] as RequestInit).method).toBe('POST');

      const state = useDesignStore.getState();
      expect(state.designId).toBe('server-assigned-uuid');
      expect(state.designName).toBe('Server Plane');
      expect(state.isDirty).toBe(false);
    });

    it('rejects with backend error detail when backend returns 400', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Invalid design file: bad schema' }), { status: 400 }),
      );

      const file = new File([JSON.stringify({ name: 'Bad Design' })], 'bad.cheng', {
        type: 'application/json',
      });

      await expect(
        useDesignStore.getState().importDesignFromJson(file, false),
      ).rejects.toThrow('Invalid design file: bad schema');

      const state = useDesignStore.getState();
      // fileError is NOT set on import errors — only on save errors.
      // The Toolbar handles import error display via local importError state.
      expect(state.fileError).toBeNull();
      expect(state.isLoading).toBe(false);
    });
  });
});
