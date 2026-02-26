// ============================================================================
// CHENG — Component Panel Router
// Routes to the appropriate detail panel based on selectedComponent + tailType
// Issue #27 | Landing Gear UI access #230 | Global inline #289
// ============================================================================

import React, { useCallback } from 'react';
import { useDesignStore } from '../../store/designStore';
import { GlobalPanel } from './GlobalPanel';
import { WingPanel } from './WingPanel';
import { TailConventionalPanel } from './TailConventionalPanel';
import { TailVTailPanel } from './TailVTailPanel';
import { FuselagePanel } from './FuselagePanel';
import { LandingGearPanel } from './LandingGearPanel';
import type { ComponentSelection } from '../../types/design';

// ---------------------------------------------------------------------------
// Component selector tab strip
// ---------------------------------------------------------------------------

const COMPONENT_TABS: readonly { key: Exclude<ComponentSelection, null>; label: string }[] = [
  { key: 'global', label: 'Global' },
  { key: 'wing', label: 'Wing' },
  { key: 'tail', label: 'Tail' },
  { key: 'fuselage', label: 'Fuselage' },
  { key: 'landing_gear', label: 'Landing Gear' },
] as const;

interface ComponentTabsProps {
  selected: ComponentSelection;
  onSelect: (component: ComponentSelection) => void;
}

function ComponentTabs({ selected, onSelect }: ComponentTabsProps): React.JSX.Element {
  return (
    <div className="flex border-b border-zinc-700/50 bg-zinc-900/60">
      {COMPONENT_TABS.map(({ key, label }) => {
        const isActive = selected === key;
        // 'global' tab cannot be toggled off (clicking it while active keeps it selected)
        const handleClick = () => onSelect(isActive && key !== 'global' ? null : key);
        return (
          <button
            key={key}
            type="button"
            onClick={handleClick}
            className={`flex-1 px-2 py-1.5 text-[10px] font-medium truncate transition-colors
              focus:outline-none focus:ring-1 focus:ring-inset focus:ring-blue-500
              ${isActive
                ? 'text-blue-300 bg-blue-900/30 border-b-2 border-blue-400'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 border-b-2 border-transparent'
              }`}
            aria-pressed={isActive}
            title={label}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main ComponentPanel router
// ---------------------------------------------------------------------------

/**
 * Routes to the correct detail panel based on:
 * - selectedComponent: 'wing' | 'tail' | 'fuselage' | 'landing_gear' | null
 * - design.tailType: determines which tail panel to show
 *
 * Includes a tab strip for direct navigation to each component panel (#230).
 */
export function ComponentPanel(): React.JSX.Element {
  const selectedComponent = useDesignStore((s) => s.selectedComponent);
  const setSelectedComponent = useDesignStore((s) => s.setSelectedComponent);
  const tailType = useDesignStore((s) => s.design.tailType);

  const handleTabSelect = useCallback(
    (component: ComponentSelection) => {
      setSelectedComponent(component);
    },
    [setSelectedComponent],
  );

  const renderPanel = (): React.JSX.Element => {
    if (selectedComponent === null) {
      return (
        <div className="p-4 flex items-center justify-center h-full">
          <p className="text-xs text-zinc-500 text-center leading-relaxed">
            Select a component tab above
            <br />
            or click a part in the 3D viewport.
          </p>
        </div>
      );
    }

    if (selectedComponent === 'global') {
      return <GlobalPanel />;
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
      return <FuselagePanel />;
    }

    if (selectedComponent === 'landing_gear') {
      return <LandingGearPanel />;
    }

    // Unreachable, but TypeScript exhaustiveness
    return (
      <div className="p-4">
        <p className="text-xs text-zinc-500">Unknown component selected.</p>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full">
      <ComponentTabs selected={selectedComponent} onSelect={handleTabSelect} />
      {renderPanel()}
    </div>
  );
}
