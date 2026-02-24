// ============================================================================
// CHENG — History Panel: Multi-level undo/redo with named entries (#136)
// Shows the undo/redo history stack with human-readable action descriptions.
// Clicking an entry jumps to that state.
// ============================================================================

import { useCallback, useMemo } from 'react';
import { useDesignStore, type UndoableState } from '../store/designStore';
import { useStoreWithEqualityFn } from 'zustand/traditional';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HistoryEntry {
  /** Index in the past states array (0 = oldest). -1 = current state. Positive = future. */
  index: number;
  /** Human-readable action description */
  action: string;
  /** Whether this is the current state */
  isCurrent: boolean;
  /** Zone: 'past' | 'current' | 'future' */
  zone: 'past' | 'current' | 'future';
}

// ---------------------------------------------------------------------------
// Hook: useHistoryEntries
// ---------------------------------------------------------------------------

function useHistoryEntries(): HistoryEntry[] {
  const temporalStore = useDesignStore.temporal;

  // Subscribe to temporal state changes
  const pastStates = useStoreWithEqualityFn(
    temporalStore,
    (s) => s.pastStates as UndoableState[],
    Object.is,
  );
  const futureStates = useStoreWithEqualityFn(
    temporalStore,
    (s) => s.futureStates as UndoableState[],
    Object.is,
  );
  const currentAction = useDesignStore((s) => s.lastAction);

  return useMemo(() => {
    const entries: HistoryEntry[] = [];

    // Future states: futureStates[0] = immediate redo, last = furthest future
    // Display furthest future at top, immediate redo closest to current
    for (let i = futureStates.length - 1; i >= 0; i--) {
      entries.push({
        index: i,
        action: futureStates[i]?.lastAction ?? 'Unknown action',
        isCurrent: false,
        zone: 'future',
      });
    }

    // Current state
    entries.push({
      index: -1,
      action: currentAction,
      isCurrent: true,
      zone: 'current',
    });

    // Past states (most recent first)
    for (let i = pastStates.length - 1; i >= 0; i--) {
      entries.push({
        index: i,
        action: pastStates[i]?.lastAction ?? 'Unknown action',
        isCurrent: false,
        zone: 'past',
      });
    }

    return entries;
  }, [pastStates, futureStates, currentAction]);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface HistoryPanelProps {
  /** Whether the panel is open */
  open: boolean;
  /** Toggle panel visibility */
  onClose: () => void;
}

export function HistoryPanel({ open, onClose }: HistoryPanelProps): React.JSX.Element | null {
  const entries = useHistoryEntries();
  const temporalStore = useDesignStore.temporal;

  const handleJumpTo = useCallback(
    (entry: HistoryEntry) => {
      if (entry.isCurrent) return;

      const temporal = temporalStore.getState();

      if (entry.zone === 'past') {
        // Jump back: undo (pastStates.length - entry.index) steps in one call
        const pastStates = temporal.pastStates as UndoableState[];
        const undoCount = pastStates.length - entry.index;
        temporal.undo(undoCount);
      } else if (entry.zone === 'future') {
        // Jump forward: redo (futureStates.length - entry.index) steps in one call
        const futureStates = temporal.futureStates as UndoableState[];
        const redoCount = futureStates.length - entry.index;
        temporal.redo(redoCount);
      }
    },
    [temporalStore],
  );

  if (!open) return null;

  return (
    <div className="absolute top-10 left-0 z-50 w-72 max-h-80 bg-zinc-900 border border-zinc-700 rounded-md shadow-xl shadow-black/50 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
        <span className="text-xs font-semibold text-zinc-300">History</span>
        <button
          onClick={onClose}
          className="text-xs text-zinc-500 hover:text-zinc-300 px-1"
          aria-label="Close history panel"
        >
          {'\u2715'}
        </button>
      </div>
      <div className="flex-1 overflow-y-auto min-h-0">
        {entries.length === 0 ? (
          <p className="text-xs text-zinc-500 py-4 text-center">No history yet.</p>
        ) : (
          <ul className="py-1">
            {entries.map((entry, i) => (
              <li key={`${entry.zone}-${entry.index}-${i}`}>
                <button
                  onClick={() => handleJumpTo(entry)}
                  disabled={entry.isCurrent}
                  className={`w-full text-left px-3 py-1.5 text-xs flex items-center gap-2
                    ${entry.isCurrent
                      ? 'bg-blue-900/30 text-blue-300 font-medium cursor-default'
                      : entry.zone === 'future'
                        ? 'text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 cursor-pointer'
                        : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 cursor-pointer'
                    }`}
                >
                  <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full" style={{
                    backgroundColor: entry.isCurrent ? '#3b82f6' : entry.zone === 'future' ? '#6b7280' : '#a1a1aa',
                  }} />
                  <span className="truncate">{entry.action}</span>
                  {entry.isCurrent && (
                    <span className="ml-auto text-[9px] text-blue-400 flex-shrink-0">current</span>
                  )}
                  {entry.zone === 'future' && (
                    <span className="ml-auto text-[9px] text-zinc-600 flex-shrink-0">redo</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
