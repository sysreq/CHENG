// ============================================================================
// CHENG — Component Panel (Stub)
// Track D: Frontend Panels will implement the full version.
// This stub provides a minimal placeholder based on selected component.
// ============================================================================

import { useDesignStore } from '@/store/designStore';

/**
 * Component-specific parameter panel.
 * Routes to Wing/Tail panels based on the selected component.
 * Stub implementation — Track D will provide the full version.
 */
export default function ComponentPanel() {
  const selectedComponent = useDesignStore((state) => state.selectedComponent);

  if (!selectedComponent) {
    return (
      <div
        style={{
          padding: 12,
          fontSize: 12,
          color: 'var(--color-text-muted)',
          textAlign: 'center',
          marginTop: 16,
        }}
      >
        Click on the aircraft model to select a component
      </div>
    );
  }

  return (
    <div
      style={{
        padding: 12,
        borderBottom: '1px solid var(--color-border)',
      }}
    >
      <h3
        style={{
          fontSize: 12,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: 'var(--color-text-muted)',
          marginBottom: 8,
        }}
      >
        {selectedComponent} Parameters
      </h3>
      <div
        style={{
          fontSize: 11,
          color: 'var(--color-text-muted)',
          fontStyle: 'italic',
        }}
      >
        Full {selectedComponent} controls coming soon (Track D)
      </div>
    </div>
  );
}
