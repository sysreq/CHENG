// ============================================================================
// CHENG — Live Region Store
// Zustand store for ARIA live region announcements.
// Issue #180 (Accessibility audit)
// ============================================================================

import { create } from 'zustand';

interface LiveRegionState {
  /** Current message for aria-live="polite" */
  politeMessage: string;
  /** Current message for aria-live="assertive" */
  assertiveMessage: string;
  /** Announce a polite (non-interrupting) message */
  announce: (message: string) => void;
  /** Announce an assertive (interrupting) message */
  announceAssertive: (message: string) => void;
  /** Clear the polite message */
  clearPolite: () => void;
  /** Clear the assertive message */
  clearAssertive: () => void;
}

export const useLiveRegionStore = create<LiveRegionState>((set) => ({
  politeMessage: '',
  assertiveMessage: '',

  announce: (message: string) => set({ politeMessage: message }),

  announceAssertive: (message: string) => set({ assertiveMessage: message }),

  clearPolite: () => set({ politeMessage: '' }),

  clearAssertive: () => set({ assertiveMessage: '' }),
}));
