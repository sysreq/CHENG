// ============================================================================
// CHENG — useIndexedDbPersistence (#150)
//
// Auto-save the active design to IndexedDB (debounced, 1 s) and restore it
// on startup.  Only active in cloud mode; no-ops in local mode.
//
// Usage: call once at app root level (in App.tsx).
// ============================================================================

import { useEffect, useRef } from 'react';
import { useDesignStore } from '@/store/designStore';
import {
  idbSaveDesign,
  idbLoadAutosave,
  debounce,
} from '@/lib/indexeddb';
import type { AircraftDesign } from '@/types/design';

const AUTOSAVE_DEBOUNCE_MS = 1000;

/**
 * Enable IndexedDB persistence for the active design in cloud mode.
 *
 * - On mount: loads the autosave design from IndexedDB (if any) and
 *   populates the Zustand store.
 * - On every design change: debounces a save to IndexedDB.
 *
 * @param isCloudMode - true when CHENG_MODE=cloud (from /api/mode).
 */
export function useIndexedDbPersistence(isCloudMode: boolean): void {
  const design = useDesignStore((s) => s.design);
  const loadCustomPresetDesign = useDesignStore((s) => s.loadCustomPresetDesign);
  const restoredRef = useRef(false);

  // ── Restore on startup ───────────────────────────────────────────────────
  useEffect(() => {
    if (!isCloudMode || restoredRef.current) return;
    restoredRef.current = true;

    (async () => {
      try {
        const saved = await idbLoadAutosave<AircraftDesign>();
        if (saved && typeof saved === 'object' && 'wingSpan' in saved) {
          loadCustomPresetDesign(saved);
        }
      } catch (err) {
        // IndexedDB unavailable (private browsing, storage quota, etc.)
        console.warn('[CHENG] IndexedDB restore failed:', err);
      }
    })();
  }, [isCloudMode, loadCustomPresetDesign]);

  // ── Auto-save on design change ────────────────────────────────────────────
  const debouncedSaveRef = useRef<ReturnType<typeof debounce> | null>(null);

  useEffect(() => {
    debouncedSaveRef.current = debounce(
      (d: AircraftDesign) => {
        idbSaveDesign(d).catch((err) => {
          console.warn('[CHENG] IndexedDB auto-save failed:', err);
        });
      },
      AUTOSAVE_DEBOUNCE_MS,
    ) as ReturnType<typeof debounce>;
  }, []);

  useEffect(() => {
    if (!isCloudMode) return;
    debouncedSaveRef.current?.(design as never);
  }, [isCloudMode, design]);
}
