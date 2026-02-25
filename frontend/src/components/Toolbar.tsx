// ============================================================================
// CHENG — Toolbar: File/Edit/View menus + Export button
// Issue #25, #93 (Load dialog), #94 (Camera presets)
// ============================================================================

import React, { useCallback, useEffect, useState, useRef } from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import * as Dialog from '@radix-ui/react-dialog';
import { useStore } from 'zustand';
import { useDesignStore } from '../store/designStore';
import { getWarningCountBadge } from '../lib/validation';
import { useConnectionStore } from '../store/connectionStore';
import { HistoryPanel } from './HistoryPanel';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ToolbarProps {
  /** Callback to open the export dialog */
  onOpenExport: () => void;
}

interface DesignSummary {
  id: string;
  name: string;
  modifiedAt: string;
}

// ---------------------------------------------------------------------------
// Menu Item Styling Constants
// ---------------------------------------------------------------------------

const MENU_CONTENT_CLASS = `min-w-[180px] bg-zinc-800 border border-zinc-700 rounded-md
  p-1 shadow-xl shadow-black/50 z-50`;

const MENU_ITEM_CLASS = `flex items-center justify-between px-3 py-1.5 text-xs text-zinc-200
  rounded cursor-pointer outline-none
  data-[highlighted]:bg-zinc-700 data-[highlighted]:text-zinc-100`;

const MENU_SEPARATOR_CLASS = 'h-px bg-zinc-700 my-1';

const MENU_SHORTCUT_CLASS = 'ml-4 text-[10px] text-zinc-500';

// ---------------------------------------------------------------------------
// Load Design Dialog
// ---------------------------------------------------------------------------

function LoadDesignDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [designs, setDesigns] = useState<DesignSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadDesign = useDesignStore((s) => s.loadDesign);
  const isDirty = useDesignStore((s) => s.isDirty);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    fetch('/api/designs')
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to fetch designs: ${res.status}`);
        return res.json() as Promise<DesignSummary[]>;
      })
      .then(setDesigns)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to fetch designs');
      })
      .finally(() => setLoading(false));
  }, [open]);

  const handleSelect = useCallback(
    (id: string) => {
      if (isDirty) {
        const confirmed = window.confirm(
          'You have unsaved changes. Load a different design anyway?',
        );
        if (!confirmed) return;
      }
      loadDesign(id)
        .then(() => onOpenChange(false))
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : 'Failed to load design');
        });
    },
    [isDirty, loadDesign, onOpenChange],
  );

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] max-h-[70vh] bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl z-50 flex flex-col">
          <Dialog.Title className="px-4 pt-4 pb-2 text-sm font-semibold text-zinc-200">
            Load Design
          </Dialog.Title>

          <div className="flex-1 overflow-y-auto px-4 pb-4 min-h-0">
            {loading && (
              <p className="text-xs text-zinc-500 py-4 text-center">Loading...</p>
            )}
            {error && (
              <p className="text-xs text-red-400 py-4 text-center">{error}</p>
            )}
            {!loading && !error && designs.length === 0 && (
              <p className="text-xs text-zinc-500 py-4 text-center">
                No saved designs found.
              </p>
            )}
            {!loading && !error && designs.length > 0 && (
              <ul className="space-y-1">
                {designs.map((d) => (
                  <li key={d.id}>
                    <button
                      onClick={() => handleSelect(d.id)}
                      className="w-full text-left px-3 py-2 rounded text-xs text-zinc-200 hover:bg-zinc-800 focus:outline-none focus:ring-1 focus:ring-zinc-600 flex items-center justify-between"
                    >
                      <span className="truncate mr-2">{d.name}</span>
                      <span className="text-zinc-500 text-[10px] whitespace-nowrap">
                        {formatDate(d.modifiedAt)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="px-4 py-3 border-t border-zinc-800 flex justify-end">
            <Dialog.Close asChild>
              <button className="px-3 py-1 text-xs text-zinc-400 rounded hover:bg-zinc-800">
                Cancel
              </button>
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function Toolbar({ onOpenExport }: ToolbarProps): React.JSX.Element {
  const warnings = useDesignStore((s) => s.warnings);
  const isDirty = useDesignStore((s) => s.isDirty);
  const designName = useDesignStore((s) => s.designName);
  const setDesignName = useDesignStore((s) => s.setDesignName);
  const newDesign = useDesignStore((s) => s.newDesign);
  const saveDesign = useDesignStore((s) => s.saveDesign);
  const isSaving = useDesignStore((s) => s.isSaving);
  const fileError = useDesignStore((s) => s.fileError);
  const clearFileError = useDesignStore((s) => s.clearFileError);
  const setCameraPreset = useDesignStore((s) => s.setCameraPreset);
  const isConnected = useConnectionStore((s) => s.state === 'connected');

  const [loadDialogOpen, setLoadDialogOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [isEditingName, setIsEditingName] = useState(false);
  const [editNameValue, setEditNameValue] = useState(designName);
  const [saveFlash, setSaveFlash] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);

  const warningBadge = getWarningCountBadge(warnings);

  // ── File Operations ────────────────────────────────────────────────

  const handleNew = useCallback(() => {
    if (isDirty) {
      const confirmed = window.confirm(
        'You have unsaved changes. Create a new design anyway?',
      );
      if (!confirmed) return;
    }
    newDesign();
  }, [isDirty, newDesign]);

  const handleSave = useCallback(() => {
    saveDesign()
      .then(() => {
        setSaveFlash(true);
        setTimeout(() => setSaveFlash(false), 2000);
      })
      .catch((err: unknown) => {
        console.error('Failed to save design:', err);
      });
  }, [saveDesign]);

  const handleLoad = useCallback(() => {
    setLoadDialogOpen(true);
  }, []);

  // ── Undo/Redo ──────────────────────────────────────────────────────

  const handleUndo = useCallback(() => {
    useDesignStore.temporal.getState().undo();
  }, []);

  const handleRedo = useCallback(() => {
    useDesignStore.temporal.getState().redo();
  }, []);

  // ── View — Camera Presets (#94) ────────────────────────────────────

  const handleViewFront = useCallback(() => {
    setCameraPreset('front');
  }, [setCameraPreset]);

  const handleViewSide = useCallback(() => {
    setCameraPreset('side');
  }, [setCameraPreset]);

  const handleViewTop = useCallback(() => {
    setCameraPreset('top');
  }, [setCameraPreset]);

  const handleViewPerspective = useCallback(() => {
    setCameraPreset('perspective');
  }, [setCameraPreset]);

  // ── Keyboard Shortcuts ─────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Skip if user is typing in an input, textarea, or contenteditable
      const tag = (e.target as HTMLElement).tagName;
      const isEditable =
        tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable;

      const isCtrl = e.ctrlKey || e.metaKey;

      // Ctrl+key shortcuts
      if (isCtrl) {
        switch (e.key.toLowerCase()) {
          case 'z':
            e.preventDefault();
            if (e.shiftKey) {
              handleRedo();
            } else {
              handleUndo();
            }
            break;
          case 'y':
            e.preventDefault();
            handleRedo();
            break;
          case 'n':
            e.preventDefault();
            handleNew();
            break;
          case 's':
            e.preventDefault();
            handleSave();
            break;
        }
        return;
      }

      // Single-key camera shortcuts — number keys following Blender/CAD conventions (#202)
      // (only when no input is focused and no modifiers)
      if (!isEditable && !e.altKey && !e.shiftKey) {
        switch (e.key) {
          case '1':
            e.preventDefault();
            handleViewFront();
            break;
          case '2':
            e.preventDefault();
            handleViewSide();
            break;
          case '3':
            e.preventDefault();
            handleViewTop();
            break;
          case '4':
            e.preventDefault();
            handleViewPerspective();
            break;
        }
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleNew, handleSave, handleUndo, handleRedo, handleViewFront, handleViewSide, handleViewTop, handleViewPerspective]);

  // ── Undo/Redo button disabled state ─────────────────────────────
  const canUndo = useStore(
    useDesignStore.temporal,
    (s) => s.pastStates.length > 0,
  );
  const canRedo = useStore(
    useDesignStore.temporal,
    (s) => s.futureStates.length > 0,
  );

  return (
    <>
      <div className="flex items-center h-10 px-2 bg-zinc-900 border-b border-zinc-800 gap-1">
        {/* ════════════════════════════════════════════════════════════
            LEFT SECTION: File / Edit / View dropdown menus
            ════════════════════════════════════════════════════════════ */}
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              className="px-3 py-1 text-xs text-zinc-300 rounded hover:bg-zinc-800
                focus:outline-none focus:ring-1 focus:ring-zinc-600"
            >
              File
            </button>
          </DropdownMenu.Trigger>

          <DropdownMenu.Portal>
            <DropdownMenu.Content className={MENU_CONTENT_CLASS} sideOffset={4}>
              <DropdownMenu.Item className={MENU_ITEM_CLASS} onSelect={handleNew}>
                New Design
                <span className={MENU_SHORTCUT_CLASS}>Ctrl+N</span>
              </DropdownMenu.Item>

              <DropdownMenu.Item className={MENU_ITEM_CLASS} onSelect={handleSave} disabled={isSaving}>
                {isSaving ? 'Saving...' : 'Save'}
                <span className={MENU_SHORTCUT_CLASS}>Ctrl+S</span>
              </DropdownMenu.Item>

              <DropdownMenu.Item className={MENU_ITEM_CLASS} onSelect={handleLoad}>
                Load...
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              className="px-3 py-1 text-xs text-zinc-300 rounded hover:bg-zinc-800
                focus:outline-none focus:ring-1 focus:ring-zinc-600"
            >
              Edit
            </button>
          </DropdownMenu.Trigger>

          <DropdownMenu.Portal>
            <DropdownMenu.Content className={MENU_CONTENT_CLASS} sideOffset={4}>
              <DropdownMenu.Item className={MENU_ITEM_CLASS} onSelect={handleUndo}>
                Undo
                <span className={MENU_SHORTCUT_CLASS}>Ctrl+Z</span>
              </DropdownMenu.Item>

              <DropdownMenu.Item className={MENU_ITEM_CLASS} onSelect={handleRedo}>
                Redo
                <span className={MENU_SHORTCUT_CLASS}>Ctrl+Y</span>
              </DropdownMenu.Item>

              <DropdownMenu.Separator className={MENU_SEPARATOR_CLASS} />

              <DropdownMenu.Item
                className={MENU_ITEM_CLASS}
                onSelect={() => setHistoryOpen((v) => !v)}
              >
                {historyOpen ? 'Hide History' : 'Show History'}
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              className="px-3 py-1 text-xs text-zinc-300 rounded hover:bg-zinc-800
                focus:outline-none focus:ring-1 focus:ring-zinc-600"
            >
              View
            </button>
          </DropdownMenu.Trigger>

          <DropdownMenu.Portal>
            <DropdownMenu.Content className={MENU_CONTENT_CLASS} sideOffset={4}>
              <DropdownMenu.Item className={MENU_ITEM_CLASS} onSelect={handleViewFront}>
                Front
              </DropdownMenu.Item>

              <DropdownMenu.Item className={MENU_ITEM_CLASS} onSelect={handleViewSide}>
                Side
              </DropdownMenu.Item>

              <DropdownMenu.Item className={MENU_ITEM_CLASS} onSelect={handleViewTop}>
                Top
              </DropdownMenu.Item>

              <DropdownMenu.Separator className={MENU_SEPARATOR_CLASS} />

              <DropdownMenu.Item className={MENU_ITEM_CLASS} onSelect={handleViewPerspective}>
                Perspective (default)
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        {/* ════════════════════════════════════════════════════════════
            CENTER SECTION: View presets + Undo/Redo icon buttons
            ════════════════════════════════════════════════════════════ */}
        <div className="h-5 w-px bg-zinc-700 mx-1" aria-hidden="true" />

        {/* Camera view presets (#133) */}
        <div className="flex items-center gap-0.5" role="group" aria-label="Camera view presets">
          <button
            onClick={handleViewFront}
            className="w-7 h-7 flex items-center justify-center text-[10px] font-bold text-zinc-400 rounded hover:bg-zinc-800 hover:text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            title="Front view (1)"
            aria-label="Front view"
          >
            F
          </button>
          <button
            onClick={handleViewSide}
            className="w-7 h-7 flex items-center justify-center text-[10px] font-bold text-zinc-400 rounded hover:bg-zinc-800 hover:text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            title="Side view (2)"
            aria-label="Side view"
          >
            S
          </button>
          <button
            onClick={handleViewTop}
            className="w-7 h-7 flex items-center justify-center text-[10px] font-bold text-zinc-400 rounded hover:bg-zinc-800 hover:text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            title="Top view (3)"
            aria-label="Top view"
          >
            T
          </button>
          <button
            onClick={handleViewPerspective}
            className="w-7 h-7 flex items-center justify-center text-[10px] font-bold text-zinc-400 rounded hover:bg-zinc-800 hover:text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            title="3D perspective view (4)"
            aria-label="3D perspective view"
          >
            3D
          </button>
        </div>

        <div className="h-5 w-px bg-zinc-700 mx-1" aria-hidden="true" />

        {/* Undo/Redo icon buttons (#137) */}
        <div className="flex items-center gap-0.5" role="group" aria-label="Undo and redo">
          <button
            onClick={handleUndo}
            disabled={!canUndo}
            className="w-7 h-7 flex items-center justify-center text-sm rounded
              text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100
              focus:outline-none focus:ring-1 focus:ring-zinc-600
              disabled:text-zinc-600 disabled:bg-transparent disabled:cursor-not-allowed"
            title="Undo (Ctrl+Z)"
            aria-label="Undo"
          >
            <span aria-hidden="true">{'\u21A9'}</span>
          </button>
          <button
            onClick={handleRedo}
            disabled={!canRedo}
            className="w-7 h-7 flex items-center justify-center text-sm rounded
              text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100
              focus:outline-none focus:ring-1 focus:ring-zinc-600
              disabled:text-zinc-600 disabled:bg-transparent disabled:cursor-not-allowed"
            title="Redo (Ctrl+Y)"
            aria-label="Redo"
          >
            <span aria-hidden="true">{'\u21AA'}</span>
          </button>
        </div>

        {/* ════════════════════════════════════════════════════════════
            SPACER
            ════════════════════════════════════════════════════════════ */}
        <div className="flex-1" />

        {/* ════════════════════════════════════════════════════════════
            RIGHT SECTION: Design name, warnings, export
            ════════════════════════════════════════════════════════════ */}

        {/* Design Name (click to edit) */}
        {isEditingName ? (
          <input
            ref={nameInputRef}
            className="text-xs text-zinc-200 bg-zinc-800 border border-zinc-600 rounded px-1.5 py-0.5 mr-2 max-w-[200px] focus:outline-none focus:border-blue-500"
            value={editNameValue}
            onChange={(e) => setEditNameValue(e.target.value)}
            onBlur={() => {
              const trimmed = editNameValue.trim();
              if (trimmed && trimmed !== designName) {
                setDesignName(trimmed);
              }
              setIsEditingName(false);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                (e.target as HTMLInputElement).blur();
              } else if (e.key === 'Escape') {
                setEditNameValue(designName);
                setIsEditingName(false);
              }
            }}
            autoFocus
          />
        ) : (
          <button
            className="text-xs text-zinc-500 mr-2 truncate max-w-[200px] hover:text-zinc-300 cursor-text bg-transparent border-none p-0"
            onClick={() => {
              setEditNameValue(designName);
              setIsEditingName(true);
            }}
            title="Click to rename"
          >
            {designName}
            {isDirty && <span className="text-zinc-600 ml-1">*</span>}
          </button>
        )}

        {/* Save Feedback */}
        {saveFlash && (
          <span className="text-[10px] text-green-400 mr-2 animate-pulse">Saved!</span>
        )}
        {fileError && (
          <span
            className="text-[10px] text-red-400 mr-2 cursor-pointer truncate max-w-[160px]"
            title={fileError}
            onClick={clearFileError}
          >
            Save failed
          </span>
        )}

        {/* Warning Badge */}
        {warningBadge && (
          <span
            className="px-2 py-0.5 text-[10px] font-medium text-amber-100
              bg-amber-600 rounded-full mr-2"
          >
            {warningBadge}
          </span>
        )}

        {/* Export Button */}
        <button
          onClick={onOpenExport}
          disabled={!isConnected}
          className="px-3 py-1 text-xs font-medium text-zinc-100 bg-blue-600
            rounded hover:bg-blue-500 focus:outline-none focus:ring-2
            focus:ring-blue-400 focus:ring-offset-1 focus:ring-offset-zinc-900
            disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Export...
        </button>
      </div>

      {/* History Panel (#136) — only rendered when open to avoid subscription overhead */}
      {historyOpen && (
        <div style={{ position: 'relative' }}>
          <HistoryPanel open onClose={() => setHistoryOpen(false)} />
        </div>
      )}

      {/* Load Design Dialog (#93) */}
      <LoadDesignDialog open={loadDialogOpen} onOpenChange={setLoadDialogOpen} />
    </>
  );
}
