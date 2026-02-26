// ============================================================================
// CHENG — Stability Overlay
// Floating panel wrapper that positions StabilityPanel as a fixed card
// overlaying the 3D viewport. Toggled from the Toolbar.
// Issue #317
// ============================================================================

import React, { useRef, useEffect } from 'react';
import { StabilityPanel } from './panels/StabilityPanel';

// ─── Props ───────────────────────────────────────────────────────────────────

interface StabilityOverlayProps {
  /** Called when the user closes the overlay via the × button. */
  onClose: () => void;
  /** Ref to the toolbar's Toggle Plots button, so focus can be restored on close. */
  toggleButtonRef?: React.RefObject<HTMLButtonElement | null>;
}

// ─── Component ────────────────────────────────────────────────────────────────

/**
 * Floating panel overlay for the Stability Plots feature.
 *
 * Positioning: `fixed top-14 right-4` — just below the 40px toolbar with a
 * small gap. `z-40` sits above the 3D canvas but below modal dialogs (`z-50`).
 *
 * Width: `w-72` (288px) — readable gauges without obscuring the left sidebar.
 *
 * Scrollable: `max-h-[calc(100vh-8rem)]` prevents overflow below the viewport.
 *
 * Non-modal: `aria-modal="false"` allows the user to interact with the rest
 * of the app while this overlay is open (no focus trap).
 */
export function StabilityOverlay({
  onClose,
  toggleButtonRef,
}: StabilityOverlayProps): React.JSX.Element {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // When the overlay mounts, put focus on the close button so keyboard users
  // can immediately dismiss it without needing to tab through all content.
  useEffect(() => {
    closeButtonRef.current?.focus();
  }, []);

  const handleClose = () => {
    onClose();
    // Restore focus to the toolbar toggle button so keyboard users don't lose
    // their place after dismissing the overlay.
    toggleButtonRef?.current?.focus();
  };

  return (
    <div
      role="dialog"
      aria-label="Stability plots"
      aria-modal="false"
      className="fixed top-14 right-4 z-40 w-72 bg-zinc-900 border border-zinc-700
        rounded-lg shadow-2xl shadow-black/60 flex flex-col"
    >
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-2
        border-b border-zinc-800 flex-shrink-0">
        <span className="text-xs font-semibold text-zinc-300">
          Stability Plots
        </span>
        <button
          ref={closeButtonRef}
          onClick={handleClose}
          aria-label="Close stability plots"
          className="w-5 h-5 flex items-center justify-center text-zinc-500
            rounded hover:bg-zinc-700 hover:text-zinc-200
            focus:outline-none focus:ring-1 focus:ring-zinc-600 text-sm leading-none"
        >
          {/* × character — aria-label above provides accessible name */}
          <span aria-hidden="true">&times;</span>
        </button>
      </div>

      {/* Panel body — scrollable if content overflows viewport */}
      <div className="overflow-y-auto flex-1 min-h-0 max-h-[calc(100vh-8rem)]">
        <StabilityPanel />
      </div>
    </div>
  );
}
