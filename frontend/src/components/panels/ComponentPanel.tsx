// ============================================================================
// CHENG — Component Panel Router
// Routes to the appropriate detail panel based on selectedComponent + tailType
// Issue #27
// ============================================================================

import React from 'react';
import { useDesignStore } from '../../store/designStore';
import { WingPanel } from './WingPanel';
import { TailConventionalPanel } from './TailConventionalPanel';
import { TailVTailPanel } from './TailVTailPanel';

/**
 * Routes to the correct detail panel based on:
 * - selectedComponent: 'wing' | 'tail' | 'fuselage' | null
 * - design.tailType: determines which tail panel to show
 */
export function ComponentPanel(): React.JSX.Element {
  const selectedComponent = useDesignStore((s) => s.selectedComponent);
  const tailType = useDesignStore((s) => s.design.tailType);

  if (selectedComponent === null) {
    return (
      <div className="p-4 flex items-center justify-center h-full">
        <p className="text-xs text-zinc-500 text-center leading-relaxed">
          Click a component in the 3D viewport
          <br />
          to view and edit its parameters.
        </p>
      </div>
    );
  }

  if (selectedComponent === 'wing') {
    return <WingPanel />;
  }

  if (selectedComponent === 'tail') {
    if (tailType === 'V-Tail') {
      return <TailVTailPanel />;
    }
    // Conventional, T-Tail, Cruciform all use the same panel
    return <TailConventionalPanel />;
  }

  if (selectedComponent === 'fuselage') {
    return (
      <div className="p-4">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
          Fuselage
        </h3>
        <p className="text-xs text-zinc-500 mb-3">
          Fuselage geometry is controlled by the Global panel parameters:
          Fuselage Preset, Fuselage Length, Wing Chord (affects cross-section).
        </p>
        <button
          onClick={() => {
            // Scroll the sidebar to the Global Panel fuselage section
            const sidebar = document.querySelector('.app-sidebar');
            const fuselageSection = sidebar?.querySelector('[data-section="fuselage"]');
            if (fuselageSection) {
              fuselageSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
              // Brief highlight effect
              fuselageSection.classList.add('ring-1', 'ring-blue-500/50');
              setTimeout(() => fuselageSection.classList.remove('ring-1', 'ring-blue-500/50'), 2000);
            } else if (sidebar) {
              // Fallback: scroll sidebar to top where Global Panel starts
              sidebar.scrollTo({ top: 0, behavior: 'smooth' });
            }
          }}
          className="px-3 py-1.5 text-xs font-medium text-blue-200 bg-blue-600/20
            border border-blue-500/30 rounded hover:bg-blue-600/30
            focus:outline-none focus:ring-1 focus:ring-blue-500
            inline-flex items-center gap-1.5"
        >
          <span aria-hidden="true">&rarr;</span>
          Configure in Global Panel
        </button>
      </div>
    );
  }

  // Unreachable, but TypeScript exhaustiveness
  return (
    <div className="p-4">
      <p className="text-xs text-zinc-500">Unknown component selected.</p>
    </div>
  );
}
