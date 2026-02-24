// ============================================================================
// CHENG — Toolbar: File/Edit/View menus + Export button
// Issue #25
// ============================================================================

import React, { useCallback, useEffect } from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { useDesignStore } from '../store/designStore';
import { getWarningCountBadge } from '../lib/validation';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ToolbarProps {
  /** Callback to open the export dialog */
  onOpenExport: () => void;
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
// Component
// ---------------------------------------------------------------------------

export function Toolbar({ onOpenExport }: ToolbarProps): React.JSX.Element {
  const warnings = useDesignStore((s) => s.warnings);
  const isDirty = useDesignStore((s) => s.isDirty);
  const designName = useDesignStore((s) => s.designName);
  const newDesign = useDesignStore((s) => s.newDesign);
  const saveDesign = useDesignStore((s) => s.saveDesign);

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
    saveDesign().catch((err: unknown) => {
      console.error('Failed to save design:', err);
    });
  }, [saveDesign]);

  const handleLoad = useCallback(() => {
    // Placeholder — file picker will be wired in integration phase
    console.log('Load design: file picker placeholder');
  }, []);

  // ── Undo/Redo ──────────────────────────────────────────────────────

  const handleUndo = useCallback(() => {
    useDesignStore.temporal.getState().undo();
  }, []);

  const handleRedo = useCallback(() => {
    useDesignStore.temporal.getState().redo();
  }, []);

  // ── View Placeholders ──────────────────────────────────────────────

  const handleViewFront = useCallback(() => {
    console.log('Camera: Front view (placeholder — wired in Track C)');
  }, []);

  const handleViewSide = useCallback(() => {
    console.log('Camera: Side view (placeholder — wired in Track C)');
  }, []);

  const handleViewTop = useCallback(() => {
    console.log('Camera: Top view (placeholder — wired in Track C)');
  }, []);

  const handleViewPerspective = useCallback(() => {
    console.log('Camera: Perspective view (placeholder — wired in Track C)');
  }, []);

  // ── Keyboard Shortcuts ─────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isCtrl = e.ctrlKey || e.metaKey;
      if (!isCtrl) return;

      switch (e.key.toLowerCase()) {
        case 'z':
          e.preventDefault();
          if (e.shiftKey) {
            handleRedo();
          } else {
            handleUndo();
          }
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
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleNew, handleSave, handleUndo, handleRedo]);

  return (
    <div className="flex items-center h-10 px-2 bg-zinc-900 border-b border-zinc-800 gap-1">
      {/* ── File Menu ──────────────────────────────────────────────── */}
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

            <DropdownMenu.Item className={MENU_ITEM_CLASS} onSelect={handleSave}>
              Save
              <span className={MENU_SHORTCUT_CLASS}>Ctrl+S</span>
            </DropdownMenu.Item>

            <DropdownMenu.Item className={MENU_ITEM_CLASS} onSelect={handleLoad}>
              Load...
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      {/* ── Edit Menu ──────────────────────────────────────────────── */}
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
              <span className={MENU_SHORTCUT_CLASS}>Ctrl+Shift+Z</span>
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      {/* ── View Menu ──────────────────────────────────────────────── */}
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

      {/* ── Spacer ─────────────────────────────────────────────────── */}
      <div className="flex-1" />

      {/* ── Design Name ────────────────────────────────────────────── */}
      <span className="text-xs text-zinc-500 mr-2 truncate max-w-[200px]">
        {designName}
        {isDirty && <span className="text-zinc-600 ml-1">*</span>}
      </span>

      {/* ── Warning Badge ──────────────────────────────────────────── */}
      {warningBadge && (
        <span
          className="px-2 py-0.5 text-[10px] font-medium text-amber-100
            bg-amber-600 rounded-full mr-2"
        >
          {warningBadge}
        </span>
      )}

      {/* ── Export Button ──────────────────────────────────────────── */}
      <button
        onClick={onOpenExport}
        className="px-3 py-1 text-xs font-medium text-zinc-100 bg-blue-600
          rounded hover:bg-blue-500 focus:outline-none focus:ring-2
          focus:ring-blue-400 focus:ring-offset-1 focus:ring-offset-zinc-900"
      >
        Export STL
      </button>
    </div>
  );
}
