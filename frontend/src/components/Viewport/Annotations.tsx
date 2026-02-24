// ============================================================================
// CHENG — Viewport Annotations Overlay
// HTML overlay showing dimensions and selected component
// ============================================================================

import { useDesignStore } from '@/store/designStore';

/**
 * HTML overlay on the viewport showing key dimensions and the
 * currently selected component label.
 *
 * This is an HTML overlay (not a 3D object) — positioned absolutely
 * over the Canvas. Reads design params and derived values from the store.
 */
export default function Annotations() {
  const wingSpan = useDesignStore((state) => state.design.wingSpan);
  const fuselageLength = useDesignStore((state) => state.design.fuselageLength);
  const selectedComponent = useDesignStore((state) => state.selectedComponent);
  const derived = useDesignStore((state) => state.derived);

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        pointerEvents: 'none',
        zIndex: 10,
      }}
    >
      {/* Top-left: Key dimensions */}
      <div
        style={{
          position: 'absolute',
          top: 8,
          left: 8,
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          fontSize: 11,
          fontFamily: 'monospace',
          color: 'var(--color-text-secondary)',
          backgroundColor: 'rgba(30, 30, 34, 0.75)',
          padding: '6px 10px',
          borderRadius: 4,
        }}
      >
        <span>Wingspan: {wingSpan} mm</span>
        <span>Length: {fuselageLength} mm</span>
        {derived && (
          <>
            <span>Wing Area: {derived.wingAreaCm2.toFixed(1)} cm{'\u00B2'}</span>
            <span>AR: {derived.aspectRatio.toFixed(2)}</span>
            <span>MAC: {derived.meanAeroChordMm.toFixed(1)} mm</span>
          </>
        )}
      </div>

      {/* Bottom-left: Selected component label */}
      {selectedComponent && (
        <div
          style={{
            position: 'absolute',
            bottom: 8,
            left: 8,
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            backgroundColor: 'rgba(30, 30, 34, 0.85)',
            padding: '4px 10px',
            borderRadius: 4,
            textTransform: 'capitalize',
          }}
        >
          Selected: {selectedComponent}
        </div>
      )}
    </div>
  );
}
