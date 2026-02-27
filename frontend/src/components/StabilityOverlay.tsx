// ============================================================================
// CHENG — Stability Analysis Overlay
// Floating panel wrapper with three tabs: Static Stability, Mass Properties,
// Dynamic Stability. Toggled from the Toolbar.
// Issue #355
// ============================================================================

import React, { useRef, useEffect, useCallback, useState } from 'react';
import { StabilityPanel } from './panels/StabilityPanel';
import { MassPropertiesTab } from './stability/MassPropertiesTab';
import { DynamicStabilityTab } from './stability/DynamicStabilityTab';

// ─── Tab type ─────────────────────────────────────────────────────────────────

export type StabilityTab = 'static' | 'mass' | 'dynamic';

// ─── Props ───────────────────────────────────────────────────────────────────

interface StabilityOverlayProps {
  /** Called when the user closes the overlay via the × button or Escape key. */
  onClose: () => void;
  /** Ref to the toolbar's Toggle Plots button, so focus can be restored on close. */
  toggleButtonRef?: React.RefObject<HTMLButtonElement | null>;
  /** Initial tab to show when the overlay opens (default: 'static'). */
  initialTab?: StabilityTab;
  /** Called when the active tab changes, so parent can track it. */
  onTabChange?: (tab: StabilityTab) => void;
}

// ─── Tab definitions ──────────────────────────────────────────────────────────

const TABS: { id: StabilityTab; label: string }[] = [
  { id: 'static',  label: 'Static' },
  { id: 'mass',    label: 'Mass' },
  { id: 'dynamic', label: 'Dynamic' },
];

// ─── Component ────────────────────────────────────────────────────────────────

/**
 * Floating panel overlay for the Stability Analysis feature.
 *
 * Positioning: `fixed top-14 right-4` — just below the 40px toolbar with a
 * visible gap. `z-40` sits above the 3D canvas but below modal dialogs (`z-50`).
 *
 * Width: `w-80` (320px) — readable gauges without obscuring the left sidebar.
 *
 * Scrollable: `max-h-[calc(100vh-8rem)]` prevents overflow below the viewport.
 *
 * Non-modal: `aria-modal="false"` allows the user to interact with the rest
 * of the app while this overlay is open (no focus trap).
 *
 * Keyboard: Escape key closes the overlay (standard dialog behaviour).
 */
export function StabilityOverlay({
  onClose,
  toggleButtonRef,
  initialTab = 'static',
  onTabChange,
}: StabilityOverlayProps): React.JSX.Element {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [activeTab, setActiveTab] = useState<StabilityTab>(initialTab);

  // Close handler: dismiss overlay and restore focus to the toolbar toggle button.
  const handleClose = useCallback(() => {
    onClose();
    // Restore focus to the toolbar toggle button so keyboard users don't lose
    // their place after dismissing the overlay.
    toggleButtonRef?.current?.focus();
  }, [onClose, toggleButtonRef]);

  // When the overlay mounts, put focus on the close button so keyboard users
  // can immediately dismiss it without needing to tab through all content.
  useEffect(() => {
    closeButtonRef.current?.focus();
  }, []);

  // Dismiss the overlay when the user presses Escape (standard dialog behaviour).
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [handleClose]);

  // Sync initialTab if parent changes it after mount (e.g. summary card click).
  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  const handleTabChange = (tab: StabilityTab) => {
    setActiveTab(tab);
    onTabChange?.(tab);
  };

  return (
    <div
      id="stability-overlay"
      role="dialog"
      aria-label="Stability analysis"
      aria-modal="false"
      className="fixed top-14 right-4 z-40 w-80 bg-zinc-900 border border-zinc-700
        rounded-lg shadow-2xl shadow-black/60 flex flex-col"
    >
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-2
        border-b border-zinc-800 flex-shrink-0">
        <span className="text-xs font-semibold text-zinc-300">
          Stability Analysis
        </span>
        <button
          ref={closeButtonRef}
          onClick={handleClose}
          aria-label="Close stability analysis"
          className="w-5 h-5 flex items-center justify-center text-zinc-500
            rounded hover:bg-zinc-700 hover:text-zinc-200
            focus:outline-none focus:ring-1 focus:ring-zinc-600 text-sm leading-none"
        >
          {/* × character — aria-label above provides accessible name */}
          <span aria-hidden="true">&times;</span>
        </button>
      </div>

      {/* Tab bar */}
      <div
        role="tablist"
        aria-label="Stability analysis tabs"
        className="flex border-b border-zinc-800 flex-shrink-0"
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls={`stability-tab-panel-${tab.id}`}
            id={`stability-tab-${tab.id}`}
            onClick={() => handleTabChange(tab.id)}
            className={[
              'flex-1 px-2 py-1.5 text-xs font-medium transition-colors',
              'focus:outline-none focus:ring-1 focus:ring-inset focus:ring-zinc-600',
              activeTab === tab.id
                ? 'text-sky-400 border-b-2 border-sky-500 bg-zinc-800/50'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/30',
            ].join(' ')}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Panel body — scrollable if content overflows viewport */}
      <div
        id={`stability-tab-panel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`stability-tab-${activeTab}`}
        className="overflow-y-auto flex-1 min-h-0 max-h-[calc(100vh-9rem)]"
      >
        {activeTab === 'static'  && <StabilityPanel />}
        {activeTab === 'mass'    && <MassPropertiesTab />}
        {activeTab === 'dynamic' && <DynamicStabilityTab />}
      </div>
    </div>
  );
}
