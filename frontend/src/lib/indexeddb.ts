// ============================================================================
// CHENG — IndexedDB persistence layer for cloud mode (#150)
//
// In cloud mode (CHENG_MODE=cloud) the backend is stateless. The browser's
// IndexedDB becomes the canonical persistence layer for the active design.
//
// Design decisions:
// - Single database "cheng-db", single object store "designs".
// - One record per design, keyed by design.id.
// - A special key "__autosave__" holds the most-recently-active design so it
//   survives a page refresh.
// - All async operations return Promises so callers can await them cleanly.
// - The module uses a lazy-init singleton pattern: the DB connection is opened
//   once and reused for the lifetime of the page.
// ============================================================================

const DB_NAME = 'cheng-db';
const DB_VERSION = 1;
const STORE_NAME = 'designs';
const AUTOSAVE_KEY = '__autosave__';

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

let _db: IDBDatabase | null = null;

/** Open (or reuse) the IndexedDB connection. */
function openDb(): Promise<IDBDatabase> {
  if (_db) return Promise.resolve(_db);

  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);

    req.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };

    req.onsuccess = (event) => {
      _db = (event.target as IDBOpenDBRequest).result;
      resolve(_db);
    };

    req.onerror = (event) => {
      reject((event.target as IDBOpenDBRequest).error);
    };
  });
}

/** Run a single IDB request inside a transaction and resolve with its result. */
function idbRequest<T>(
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return openDb().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, mode);
        const store = tx.objectStore(STORE_NAME);
        const req = fn(store);
        req.onsuccess = () => resolve(req.result as T);
        req.onerror = () => reject(req.error);
      }),
  );
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Save a design to IndexedDB under its own id.
 * Also writes the autosave slot so the last-active design can be restored.
 *
 * Uses a single transaction for both writes to avoid the overhead of opening
 * two separate transactions when a design id is present.
 */
export async function idbSaveDesign(design: object): Promise<void> {
  const data = design as { id?: string };
  return openDb().then(
    (db) =>
      new Promise<void>((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);

        const store = tx.objectStore(STORE_NAME);
        if (data.id) {
          // Write under the design's own id key
          store.put(design, data.id);
        }
        // Always mirror into the autosave slot so the last-active design
        // survives a page refresh.  When there is no id this is the only write.
        store.put(design, AUTOSAVE_KEY);
      }),
  );
}

/**
 * Load the autosave design (last-active design on this device).
 * Returns null if nothing is stored.
 */
export async function idbLoadAutosave<T = object>(): Promise<T | null> {
  const result = await idbRequest<T | undefined>('readonly', (store) =>
    store.get(AUTOSAVE_KEY),
  );
  return result ?? null;
}

/**
 * Load a design by explicit id.
 * Returns null if not found.
 */
export async function idbLoadDesign<T = object>(id: string): Promise<T | null> {
  const result = await idbRequest<T | undefined>('readonly', (store) =>
    store.get(id),
  );
  return result ?? null;
}

/**
 * Delete a design by id.  Does nothing if the key does not exist.
 */
export async function idbDeleteDesign(id: string): Promise<void> {
  await idbRequest<undefined>('readwrite', (store) => store.delete(id));
}

/**
 * List all designs stored in IndexedDB (summaries only).
 * Returns records keyed by their IDB key. Excludes the autosave slot.
 */
export async function idbListDesigns<T = object>(): Promise<Array<{ key: string; data: T }>> {
  return openDb().then(
    (db) =>
      new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const results: Array<{ key: string; data: T }> = [];

        const cursorReq = store.openCursor();
        cursorReq.onsuccess = (event) => {
          const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result;
          if (cursor) {
            const key = cursor.key as string;
            if (key !== AUTOSAVE_KEY) {
              results.push({ key, data: cursor.value as T });
            }
            cursor.continue();
          } else {
            resolve(results);
          }
        };
        cursorReq.onerror = () => reject(cursorReq.error);
      }),
  );
}

/**
 * Estimate the total byte size of all data in the "designs" object store.
 *
 * Uses the StorageManager API (chrome/firefox) when available and falls back
 * to JSON-serialising each record.  Returns bytes.
 */
export async function idbEstimateUsageBytes(): Promise<number> {
  // Prefer the browser's own estimate (more accurate, includes overhead)
  if (typeof navigator !== 'undefined' && navigator.storage && navigator.storage.estimate) {
    try {
      const est = await navigator.storage.estimate();
      return est.usage ?? 0;
    } catch {
      // Fall through to manual estimation
    }
  }

  // Fallback: sum JSON size of all records (including autosave)
  return openDb().then(
    (db) =>
      new Promise<number>((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        let total = 0;

        const encoder = new TextEncoder();
        const cursorReq = store.openCursor();
        cursorReq.onsuccess = (event) => {
          const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result;
          if (cursor) {
            try {
              // Use TextEncoder for accurate UTF-8 byte count (not JS .length
              // which counts UTF-16 code units, not bytes)
              total += encoder.encode(JSON.stringify(cursor.value)).byteLength;
            } catch {
              /* ignore un-serialisable values */
            }
            cursor.continue();
          } else {
            resolve(total);
          }
        };
        cursorReq.onerror = () => reject(cursorReq.error);
      }),
  );
}

/**
 * Clear all records from the designs store (for testing / reset purposes).
 */
export async function idbClear(): Promise<void> {
  await idbRequest<undefined>('readwrite', (store) => store.clear());
}

// ---------------------------------------------------------------------------
// Debounce utility (avoids hammering IDB on every keystroke)
// ---------------------------------------------------------------------------

type AnyFn = (...args: never[]) => void;

export function debounce<T extends AnyFn>(fn: T, delayMs: number): T {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return ((...args: Parameters<T>) => {
    if (timer !== undefined) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delayMs);
  }) as T;
}

// ---------------------------------------------------------------------------
// Reset helper (for tests — clears the module-level DB singleton)
// ---------------------------------------------------------------------------

export function _resetDbForTesting(): void {
  _db = null;
}
