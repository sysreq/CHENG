// ============================================================================
// CHENG — Toolbar: File/Edit/Presets menus + Export button
// Issue #25, #93 (Load dialog), #94 (Camera presets), #152 (Mode badge),
//        #156 (Design import/export), #221 (Remove View menu), #289 (Presets menu)
// ============================================================================

import React, { useCallback, useEffect, useRef, useState } from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import * as Dialog from '@radix-ui/react-dialog';
import * as AlertDialog from '@radix-ui/react-alert-dialog';
import { useStore } from 'zustand';
import { useDesignStore } from '../store/designStore';
import { getWarningCountBadge } from '../lib/validation';
import { useConnectionStore } from '../store/connectionStore';
import { HistoryPanel } from './HistoryPanel';
import { ModeBadge } from './ModeBadge';
import { useModeInfo } from '../hooks/useModeInfo';
import { UnitToggle } from './UnitToggle';
import { PRESET_DESCRIPTIONS } from '../lib/presets';
import {
  listCustomPresets,
  loadCustomPreset,
  saveCustomPreset,
  deleteCustomPreset,
} from '../lib/presetApi';
import type { PresetName, CustomPresetSummary } from '../types/design';
import { useLiveRegionStore } from '../store/liveRegionStore';

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
        <Dialog.Content
          className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] max-h-[70vh] bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl z-50 flex flex-col"
          aria-describedby="load-dialog-description"
        >
          <Dialog.Title className="px-4 pt-4 pb-2 text-sm font-semibold text-zinc-200">
            Load Design
          </Dialog.Title>
          <p id="load-dialog-description" className="sr-only">
            Select a saved design to load. This will replace the current design.
          </p>

          <div className="flex-1 overflow-y-auto px-4 pb-4 min-h-0">
            {loading && (
              <p className="text-xs text-zinc-500 py-4 text-center" aria-live="polite">Loading designs...</p>
            )}
            {error && (
              <p className="text-xs text-red-400 py-4 text-center" role="alert">{error}</p>
            )}
            {!loading && !error && designs.length === 0 && (
              <p className="text-xs text-zinc-500 py-4 text-center">
                No saved designs found.
              </p>
            )}
            {!loading && !error && designs.length > 0 && (
              <ul
                className="space-y-1"
                role="listbox"
                aria-label={`${designs.length} saved design${designs.length === 1 ? '' : 's'}`}
              >
                {designs.map((d) => (
                  <li key={d.id} role="option" aria-selected={false}>
                    <button
                      onClick={() => handleSelect(d.id)}
                      aria-label={`Load design: ${d.name}, last modified ${formatDate(d.modifiedAt)}`}
                      className="w-full text-left px-3 py-2 rounded text-xs text-zinc-200 hover:bg-zinc-800 focus:outline-none focus:ring-1 focus:ring-zinc-600 flex items-center justify-between"
                    >
                      <span className="truncate mr-2">{d.name}</span>
                      <span className="text-zinc-500 text-[10px] whitespace-nowrap" aria-hidden="true">
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
              <button className="px-3 py-1 text-xs text-zinc-400 rounded hover:bg-zinc-800 focus:outline-none focus:ring-1 focus:ring-zinc-600">
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
// Presets Menu constants
// ---------------------------------------------------------------------------

const PRESET_OPTIONS: readonly (Exclude<PresetName, 'Custom'>)[] = [
  'Trainer',
  'Sport',
  'Aerobatic',
  'Glider',
  'FlyingWing',
  'Scale',
] as const;

const PRESET_DISPLAY_LABELS: Record<Exclude<PresetName, 'Custom'>, string> = {
  Trainer: 'Trainer',
  Sport: 'Sport',
  Aerobatic: 'Aerobatic',
  Glider: 'Glider',
  FlyingWing: 'Flying Wing',
  Scale: 'Scale',
};

// ---------------------------------------------------------------------------
// PresetsMenu — Presets dropdown in the top menu bar (#289)
// ---------------------------------------------------------------------------

function PresetsMenu(): React.JSX.Element {
  const activePreset = useDesignStore((s) => s.activePreset);
  const loadPreset = useDesignStore((s) => s.loadPreset);
  const loadCustomPresetDesign = useDesignStore((s) => s.loadCustomPresetDesign);
  const design = useDesignStore((s) => s.design);
  const announce = useLiveRegionStore((s) => s.announce);

  // ── Built-in preset confirmation ──────────────────────────────────
  const [pendingPreset, setPendingPreset] = useState<Exclude<PresetName, 'Custom'> | null>(null);

  const confirmPreset = useCallback(() => {
    if (pendingPreset) {
      loadPreset(pendingPreset);
      announce(`Preset "${PRESET_DISPLAY_LABELS[pendingPreset]}" loaded`);
      setPendingPreset(null);
    }
  }, [pendingPreset, loadPreset, announce]);

  const cancelPreset = useCallback(() => {
    setPendingPreset(null);
  }, []);

  // ── Custom presets ────────────────────────────────────────────────
  const [customPresets, setCustomPresets] = useState<CustomPresetSummary[]>([]);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [savePresetName, setSavePresetName] = useState('');
  const [presetError, setPresetError] = useState<string | null>(null);
  const [isSavingPreset, setIsSavingPreset] = useState(false);
  const [isLoadingPreset, setIsLoadingPreset] = useState(false);
  const [pendingDeletePreset, setPendingDeletePreset] = useState<CustomPresetSummary | null>(null);

  const refreshPresets = useCallback(async () => {
    try {
      const presets = await listCustomPresets();
      setCustomPresets(presets);
    } catch (err) {
      console.error('Failed to fetch custom presets:', err);
    }
  }, []);

  useEffect(() => {
    refreshPresets();
  }, [refreshPresets]);

  const handleSavePreset = useCallback(async () => {
    if (!savePresetName.trim()) return;
    setIsSavingPreset(true);
    setPresetError(null);
    try {
      await saveCustomPreset(savePresetName.trim(), design);
      announce(`Preset "${savePresetName.trim()}" saved`);
      setShowSaveDialog(false);
      setSavePresetName('');
      await refreshPresets();
    } catch (err) {
      setPresetError(err instanceof Error ? err.message : 'Failed to save preset');
    } finally {
      setIsSavingPreset(false);
    }
  }, [savePresetName, design, refreshPresets, announce]);

  const handleLoadCustomPreset = useCallback(
    async (id: string) => {
      setIsLoadingPreset(true);
      setPresetError(null);
      try {
        const presetData = await loadCustomPreset(id);
        loadCustomPresetDesign(presetData);
      } catch (err) {
        setPresetError(err instanceof Error ? err.message : 'Failed to load preset');
      } finally {
        setIsLoadingPreset(false);
      }
    },
    [loadCustomPresetDesign],
  );

  const handleConfirmDeletePreset = useCallback(async () => {
    if (!pendingDeletePreset) return;
    setPresetError(null);
    try {
      await deleteCustomPreset(pendingDeletePreset.id);
      await refreshPresets();
    } catch (err) {
      setPresetError(err instanceof Error ? err.message : 'Failed to delete preset');
    } finally {
      setPendingDeletePreset(null);
    }
  }, [pendingDeletePreset, refreshPresets]);

  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            className="px-3 py-1 text-xs text-zinc-300 rounded hover:bg-zinc-800
              focus:outline-none focus:ring-1 focus:ring-zinc-600"
          >
            Presets
            {activePreset !== 'Custom' && (
              <span className="ml-1 text-[10px] text-zinc-500">({activePreset === 'FlyingWing' ? 'Flying Wing' : activePreset})</span>
            )}
          </button>
        </DropdownMenu.Trigger>

        <DropdownMenu.Portal>
          <DropdownMenu.Content className={MENU_CONTENT_CLASS} sideOffset={4}>
            <div className="px-3 py-1 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
              Built-in Presets
            </div>
            {PRESET_OPTIONS.map((name) => (
              <DropdownMenu.Item
                key={name}
                className={`${MENU_ITEM_CLASS} ${activePreset === name ? 'text-blue-300' : ''}`}
                onSelect={() => setPendingPreset(name)}
              >
                <span>{PRESET_DISPLAY_LABELS[name]}</span>
                {activePreset === name && <span className="ml-2 text-blue-400 text-[10px]">active</span>}
              </DropdownMenu.Item>
            ))}

            <DropdownMenu.Separator className={MENU_SEPARATOR_CLASS} />

            <DropdownMenu.Item
              className={MENU_ITEM_CLASS}
              onSelect={() => { setShowSaveDialog(true); setSavePresetName(''); setPresetError(null); }}
            >
              Save Current as Preset...
            </DropdownMenu.Item>

            {customPresets.length > 0 && (
              <>
                <DropdownMenu.Separator className={MENU_SEPARATOR_CLASS} />
                <div className="px-3 py-1 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
                  Saved Presets
                </div>
                {customPresets.map((p) => (
                  // Two sibling items per preset: Load + Delete
                  // Avoids nested interactive elements inside DropdownMenu.Item (ARIA violation)
                  <div key={p.id} className="flex items-center">
                    <DropdownMenu.Item
                      className={`${MENU_ITEM_CLASS} flex-1 min-w-0`}
                      onSelect={() => handleLoadCustomPreset(p.id)}
                      disabled={isLoadingPreset}
                    >
                      <span className="truncate" title={p.name}>{p.name}</span>
                    </DropdownMenu.Item>
                    <DropdownMenu.Item
                      className="flex-shrink-0 px-2 py-1.5 text-[10px] text-zinc-500 rounded cursor-pointer outline-none data-[highlighted]:text-red-400 data-[highlighted]:bg-zinc-700"
                      onSelect={() => setPendingDeletePreset(p)}
                      title={`Delete "${p.name}"`}
                    >
                      Del
                    </DropdownMenu.Item>
                  </div>
                ))}
              </>
            )}

            {presetError && (
              <div className="px-3 py-1 text-[10px] text-red-400">{presetError}</div>
            )}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      {/* Built-in preset confirmation dialog */}
      <AlertDialog.Root open={pendingPreset !== null} onOpenChange={(open) => { if (!open) cancelPreset(); }}>
        <AlertDialog.Portal>
          <AlertDialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
          <AlertDialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[340px] bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl z-50 p-5">
            <AlertDialog.Title className="text-sm font-semibold text-zinc-200 mb-2">
              Load Preset
            </AlertDialog.Title>
            <AlertDialog.Description className="text-xs text-zinc-400 mb-4">
              Load <span className="text-zinc-200 font-medium">{pendingPreset ? PRESET_DISPLAY_LABELS[pendingPreset] : ''}</span> preset?
              {' '}{pendingPreset ? PRESET_DESCRIPTIONS[pendingPreset] : ''}
              <br /><br />
              This will replace all current parameters.
            </AlertDialog.Description>
            <div className="flex justify-end gap-2">
              <AlertDialog.Cancel asChild>
                <button
                  className="px-3 py-1.5 text-xs text-zinc-400 bg-zinc-800 border border-zinc-700 rounded hover:bg-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-600"
                  onClick={cancelPreset}
                >
                  Cancel
                </button>
              </AlertDialog.Cancel>
              <AlertDialog.Action asChild>
                <button
                  className="px-3 py-1.5 text-xs font-medium text-zinc-100 bg-blue-600 rounded hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-400"
                  onClick={confirmPreset}
                >
                  Apply
                </button>
              </AlertDialog.Action>
            </div>
          </AlertDialog.Content>
        </AlertDialog.Portal>
      </AlertDialog.Root>

      {/* Save custom preset dialog */}
      <AlertDialog.Root open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <AlertDialog.Portal>
          <AlertDialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
          <AlertDialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[340px] bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl z-50 p-5">
            <AlertDialog.Title className="text-sm font-semibold text-zinc-200 mb-2">
              Save Custom Preset
            </AlertDialog.Title>
            <AlertDialog.Description className="text-xs text-zinc-400 mb-3">
              Save the current parameter configuration as a named preset.
            </AlertDialog.Description>
            <input
              type="text"
              placeholder="Preset name..."
              value={savePresetName}
              onChange={(e) => setSavePresetName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSavePreset(); }}
              className="w-full px-2 py-1.5 mb-3 text-xs text-zinc-100 bg-zinc-800
                border border-zinc-700 rounded
                focus:outline-none focus:border-blue-500
                placeholder:text-zinc-600"
              autoFocus
            />
            {presetError && (
              <p className="text-[10px] text-red-400 mb-2">{presetError}</p>
            )}
            <div className="flex justify-end gap-2">
              <AlertDialog.Cancel asChild>
                <button className="px-3 py-1.5 text-xs text-zinc-400 bg-zinc-800 border border-zinc-700 rounded hover:bg-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-600">
                  Cancel
                </button>
              </AlertDialog.Cancel>
              <AlertDialog.Action asChild>
                <button
                  disabled={!savePresetName.trim() || isSavingPreset}
                  onClick={(e) => { e.preventDefault(); handleSavePreset(); }}
                  className="px-3 py-1.5 text-xs font-medium text-zinc-100 bg-blue-600 rounded
                    hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-400
                    disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSavingPreset ? 'Saving...' : 'Save'}
                </button>
              </AlertDialog.Action>
            </div>
          </AlertDialog.Content>
        </AlertDialog.Portal>
      </AlertDialog.Root>

      {/* Delete custom preset confirmation */}
      <AlertDialog.Root open={pendingDeletePreset !== null} onOpenChange={(open) => { if (!open) setPendingDeletePreset(null); }}>
        <AlertDialog.Portal>
          <AlertDialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
          <AlertDialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[340px] bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl z-50 p-5">
            <AlertDialog.Title className="text-sm font-semibold text-zinc-200 mb-2">
              Delete Preset
            </AlertDialog.Title>
            <AlertDialog.Description className="text-xs text-zinc-400 mb-4">
              Delete preset <span className="text-zinc-200 font-medium">{pendingDeletePreset?.name}</span>? This cannot be undone.
            </AlertDialog.Description>
            <div className="flex justify-end gap-2">
              <AlertDialog.Cancel asChild>
                <button className="px-3 py-1.5 text-xs text-zinc-400 bg-zinc-800 border border-zinc-700 rounded hover:bg-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-600">
                  Cancel
                </button>
              </AlertDialog.Cancel>
              <AlertDialog.Action asChild>
                <button
                  onClick={handleConfirmDeletePreset}
                  className="px-3 py-1.5 text-xs font-medium text-zinc-100 bg-red-600 rounded hover:bg-red-500 focus:outline-none focus:ring-2 focus:ring-red-400"
                >
                  Delete
                </button>
              </AlertDialog.Action>
            </div>
          </AlertDialog.Content>
        </AlertDialog.Portal>
      </AlertDialog.Root>
    </>
  );
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
  const exportDesignAsJson = useDesignStore((s) => s.exportDesignAsJson);
  const importDesignFromJson = useDesignStore((s) => s.importDesignFromJson);
  const isSaving = useDesignStore((s) => s.isSaving);
  const fileError = useDesignStore((s) => s.fileError);
  const clearFileError = useDesignStore((s) => s.clearFileError);
  const setCameraPreset = useDesignStore((s) => s.setCameraPreset);
  const isConnected = useConnectionStore((s) => s.state === 'connected');

  // Detect deployment mode for import behaviour (Issue #156)
  const modeInfo = useModeInfo();
  const isCloudMode = modeInfo?.mode === 'cloud';

  const [loadDialogOpen, setLoadDialogOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [isEditingName, setIsEditingName] = useState(false);
  const [editNameValue, setEditNameValue] = useState(designName);
  const [saveFlash, setSaveFlash] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const importInputRef = useRef<HTMLInputElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const announce = useLiveRegionStore((s) => s.announce);

  const warningBadge = getWarningCountBadge(warnings);

  // Announce warning count changes to screen readers
  const prevWarningCount = useRef<number | null>(null);
  useEffect(() => {
    const count = warnings.length;
    if (prevWarningCount.current !== null && prevWarningCount.current !== count) {
      if (count === 0) {
        announce('All validation warnings cleared');
      } else if (count > (prevWarningCount.current ?? 0)) {
        announce(`${count} validation ${count === 1 ? 'warning' : 'warnings'}`);
      }
    }
    prevWarningCount.current = count;
  }, [warnings.length, announce]);

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
        announce('Design saved successfully');
        setTimeout(() => setSaveFlash(false), 2000);
      })
      .catch((err: unknown) => {
        console.error('Failed to save design:', err);
        announce('Failed to save design');
      });
  }, [saveDesign, announce]);

  const handleLoad = useCallback(() => {
    setLoadDialogOpen(true);
  }, []);

  const handleExportJson = useCallback(() => {
    exportDesignAsJson();
  }, [exportDesignAsJson]);

  const handleImportJsonClick = useCallback(() => {
    setImportError(null);
    importInputRef.current?.click();
  }, []);

  const handleImportJsonFile = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      // Reset the input so the same file can be re-selected if needed
      e.target.value = '';
      setImportError(null);
      importDesignFromJson(file, isCloudMode).catch((err: unknown) => {
        setImportError(err instanceof Error ? err.message : 'Import failed');
      });
    },
    [importDesignFromJson, isCloudMode],
  );

  // ── Undo/Redo ──────────────────────────────────────────────────────

  const handleUndo = useCallback(() => {
    useDesignStore.temporal.getState().undo();
  }, []);

  const handleRedo = useCallback(() => {
    useDesignStore.temporal.getState().redo();
  }, []);

  // ── Camera View Presets (#94) ──────────────────────────────────────
  // Note: View dropdown removed in #221 — F/S/T/3D toolbar buttons are the
  // sole camera-view controls. Keyboard shortcuts 1/2/3/4 also apply.

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
      <div
        role="toolbar"
        aria-label="Main toolbar"
        className="flex items-center h-10 px-2 bg-zinc-900 border-b border-zinc-800 gap-1 overflow-hidden"
      >
        {/* ════════════════════════════════════════════════════════════
            LEFT SECTION: File / Edit / Presets dropdown menus
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

              <DropdownMenu.Separator className={MENU_SEPARATOR_CLASS} />

              <DropdownMenu.Item className={MENU_ITEM_CLASS} onSelect={handleExportJson}>
                Export Design as JSON...
              </DropdownMenu.Item>

              <DropdownMenu.Item
                className={MENU_ITEM_CLASS}
                onSelect={handleImportJsonClick}
                disabled={modeInfo === null}
              >
                Import Design from JSON...{modeInfo === null ? ' (loading…)' : ''}
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

        <PresetsMenu />

        {/* ════════════════════════════════════════════════════════════
            CENTER SECTION: Camera view buttons + Undo/Redo icon buttons
            F/S/T/3D buttons are the canonical camera-view controls (#221).
            Keyboard shortcuts 1/2/3/4 mirror each button.
            ════════════════════════════════════════════════════════════ */}
        <div className="h-5 w-px bg-zinc-700 mx-1" aria-hidden="true" />

        {/* Camera view presets (#133, #221) */}
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

        {/* Design Name (click to edit) — hidden below 1400px to save horizontal space (#157) */}
        {isEditingName ? (
          <input
            ref={nameInputRef}
            className="toolbar-design-name text-xs text-zinc-200 bg-zinc-800 border border-zinc-600 rounded px-1.5 py-0.5 mr-2 max-w-[160px] focus:outline-none focus:border-blue-500"
            value={editNameValue}
            aria-label="Design name"
            onChange={(e) => setEditNameValue(e.target.value)}
            onBlur={() => {
              const trimmed = editNameValue.trim();
              if (trimmed && trimmed !== designName) {
                setDesignName(trimmed);
                announce(`Design renamed to ${trimmed}`);
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
            className="toolbar-design-name text-xs text-zinc-500 mr-2 truncate max-w-[160px] hover:text-zinc-300 cursor-text bg-transparent border-none p-0 focus:outline-none focus:ring-1 focus:ring-zinc-500 focus:rounded"
            onClick={() => {
              setEditNameValue(designName);
              setIsEditingName(true);
            }}
            aria-label={`Design name: ${designName}${isDirty ? ' (unsaved changes)' : ''}. Click to rename.`}
            title="Click to rename"
          >
            {designName}
            {isDirty && <span className="text-zinc-600 ml-1" aria-hidden="true">*</span>}
          </button>
        )}

        {/* Save Feedback — hidden below 1400px (#157); visual only — SR uses LiveRegion */}
        {saveFlash && (
          <span className="toolbar-design-name text-[10px] text-green-400 mr-2 animate-pulse" aria-hidden="true">Saved!</span>
        )}
        {/* Save error — only set by saveDesign(), never by importDesignFromJson() (#156) */}
        {fileError && (
          <button
            className="toolbar-design-name text-[10px] text-red-400 mr-2 cursor-pointer truncate max-w-[160px] bg-transparent border-none p-0 focus:outline-none focus:ring-1 focus:ring-red-400 focus:rounded"
            title={fileError}
            aria-label={`Save failed: ${fileError}. Click to dismiss.`}
            onClick={clearFileError}
          >
            Save failed
          </button>
        )}
        {/* Import error — managed by local importError state, not fileError (#156) */}
        {importError && (
          <span
            className="text-[10px] text-red-400 mr-2 cursor-pointer truncate max-w-[160px]"
            title={importError}
            onClick={() => setImportError(null)}
          >
            Import failed
          </span>
        )}

        {/* Warning Badge */}
        {warningBadge && (
          <span
            className="px-2 py-0.5 text-[10px] font-medium text-amber-100
              bg-amber-600 rounded-full mr-2"
            role="status"
            aria-label={`${warningBadge} — validation warnings active`}
            title={`${warningBadge} — validation warnings active`}
          >
            {warningBadge}
          </span>
        )}

        {/* Unit Toggle (#153) */}
        <UnitToggle />

        {/* Mode Badge (#152) */}
        <ModeBadge />

        {/* Export Button */}
        <button
          onClick={onOpenExport}
          disabled={!isConnected}
          aria-label={isConnected ? 'Export design (open export dialog)' : 'Export design (unavailable: not connected)'}
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

      {/* Hidden file input for JSON import (#156) */}
      <input
        ref={importInputRef}
        type="file"
        accept=".cheng,application/json"
        className="hidden"
        aria-hidden="true"
        onChange={handleImportJsonFile}
      />
    </>
  );
}
