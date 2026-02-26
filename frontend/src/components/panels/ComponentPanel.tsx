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
  const handleKeyDown = (e: React.KeyboardEvent, _key: Exclude<ComponentSelection, null>, index: number) => {
    const tabs = COMPONENT_TABS;
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      const next = tabs[(index + 1) % tabs.length];
      if (next) onSelect(next.key);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      const prev = tabs[(index - 1 + tabs.length) % tabs.length];
      if (prev) onSelect(prev.key);
    } else if (e.key === 'Home') {
      e.preventDefault();
      if (tabs[0]) onSelect(tabs[0].key);
    } else if (e.key === 'End') {
      e.preventDefault();
      const last = tabs[tabs.length - 1];
      if (last) onSelect(last.key);
    }
  };

  return (
    <div
      role="tablist"
      aria-label="Aircraft component selector"
      className="flex border-b border-zinc-700/50 bg-zinc-900/60"
    >
      {COMPONENT_TABS.map(({ key, label }, index) => {
        const isActive = selected === key;
        // 'global' tab cannot be toggled off. Other tabs toggle off to 'global' (not null).
        const handleClick = () => onSelect(isActive && key !== 'global' ? 'global' : key);
        return (
          <button
            key={key}
            type="button"
            role="tab"
            id={`tab-${key}`}
            aria-controls={`tabpanel-${key}`}
            aria-selected={isActive}
            onClick={handleClick}
            onKeyDown={(e) => handleKeyDown(e, key as Exclude<ComponentSelection, null>, index)}
            tabIndex={isActive ? 0 : -1}
            className={`flex-1 px-2 py-1.5 text-[10px] font-medium truncate transition-colors
              focus:outline-none focus:ring-1 focus:ring-inset focus:ring-blue-500
              ${isActive
                ? 'text-blue-300 bg-blue-900/30 border-b-2 border-blue-400'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 border-b-2 border-transparent'
              }`}
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
 * - selectedComponent: 'global' | 'wing' | 'tail' | 'fuselage' | 'landing_gear' | null
 * - design.tailType: determines which tail panel to show
 *
 * Includes a tab strip for direct navigation (#230). 'Global' is always the first tab
 * and shows the core aircraft parameters that were previously in the right sidebar (#289).
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

  const activeKey = selectedComponent ?? 'global';

  return (
    <div className="flex flex-col h-full">
      <ComponentTabs selected={selectedComponent} onSelect={handleTabSelect} />
      <div
        role="tabpanel"
        id={`tabpanel-${activeKey}`}
        aria-labelledby={`tab-${activeKey}`}
        tabIndex={0}
        className="flex-1 overflow-auto focus:outline-none"
      >
        {renderPanel()}
      </div>
    </div>
  );
}
