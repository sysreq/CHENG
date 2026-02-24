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
        <p className="text-xs text-zinc-500">
          Fuselage detail parameters coming soon.
          <br />
          Use the Global panel to set fuselage style and length.
        </p>
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
