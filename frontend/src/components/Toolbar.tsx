// ============================================================================
// CHENG — Toolbar (Stub)
// Track D: Frontend Panels will implement the full version.
// This stub provides a minimal bar so the App shell renders.
// ============================================================================

import { useDesignStore } from '@/store/designStore';

/**
 * Top toolbar with file operations, view controls, and undo/redo.
 * Stub implementation — Track D will provide the full version.
 */
export default function Toolbar() {
  const designName = useDesignStore((state) => state.designName);
  const activePreset = useDesignStore((state) => state.activePreset);

  return (
    <div
      style={{
        height: 'var(--toolbar-height)',
        backgroundColor: 'var(--color-bg-tertiary)',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 12px',
        gap: 12,
        fontSize: 13,
      }}
    >
      <span style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>
        CHENG
      </span>
      <span style={{ color: 'var(--color-text-muted)' }}>|</span>
      <span style={{ color: 'var(--color-text-secondary)' }}>
        {designName}
      </span>
      <span
        style={{
          fontSize: 11,
          color: 'var(--color-text-muted)',
          backgroundColor: 'var(--color-bg-elevated)',
          padding: '2px 8px',
          borderRadius: 3,
        }}
      >
        {activePreset}
      </span>
    </div>
  );
}
