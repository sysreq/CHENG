// ============================================================================
// CHENG — Shared ControlSurfaceSection component
// Extracted from WingPanel and TailConventionalPanel (Issue #272)
// ============================================================================

import React, { useState } from 'react';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ControlSurfaceSectionProps {
  /** Section heading displayed in the collapsible button. */
  title: string;
  /** Optional tooltip text for the button. */
  tooltip?: string;
  /** Content to render when the section is expanded. */
  children: React.ReactNode;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Collapsible accordion section used to group control surface parameters
 * (ailerons, elevons, elevator, rudder, etc.) inside parameter panels.
 *
 * Initially collapsed; toggled by clicking the header button.
 */
export function ControlSurfaceSection({
  title,
  tooltip,
  children,
}: ControlSurfaceSectionProps): React.JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div className="mt-3">
      <div className="border-t border-zinc-700/50 mb-2" />
      <button
        onClick={() => setIsOpen((v) => !v)}
        type="button"
        className="flex items-center justify-between w-full text-left
          focus:outline-none focus:ring-1 focus:ring-blue-500 rounded px-1 py-0.5"
        aria-expanded={isOpen}
        title={tooltip}
      >
        <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
          {title}
        </span>
        <span className="text-xs text-zinc-500">{isOpen ? '▲' : '▼'}</span>
      </button>
      {isOpen && <div className="mt-2 space-y-0">{children}</div>}
    </div>
  );
}
