// ============================================================================
// CHENG — Global Panel (Stub)
// Track D: Frontend Panels will implement the full version.
// This stub provides a minimal placeholder.
// ============================================================================

import { useDesignStore } from '@/store/designStore';

/**
 * Global parameters panel with 8 fields + preset dropdown.
 * Stub implementation — Track D will provide the full version.
 */
export default function GlobalPanel() {
  const activePreset = useDesignStore((state) => state.activePreset);
  const wingSpan = useDesignStore((state) => state.design.wingSpan);
  const fuselageLength = useDesignStore((state) => state.design.fuselageLength);

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
        Global Parameters
      </h3>
      <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.8 }}>
        <div>Preset: {activePreset}</div>
        <div>Wingspan: {wingSpan} mm</div>
        <div>Fuselage: {fuselageLength} mm</div>
        <div
          style={{
            marginTop: 8,
            fontSize: 11,
            color: 'var(--color-text-muted)',
            fontStyle: 'italic',
          }}
        >
          Full parameter controls coming soon (Track D)
        </div>
      </div>
    </div>
  );
}
