// ============================================================================
// CHENG — Viewport Annotations Overlay
// HUD info panel + camera reset button (outside Canvas).
// 3D dimension annotations are rendered inside Canvas via DimensionLines.
// ============================================================================

import { useDesignStore } from '@/store/designStore';

interface AnnotationsProps {
  onResetCamera?: () => void;
}

export default function Annotations({ onResetCamera }: AnnotationsProps) {
  const selectedComponent = useDesignStore((state) => state.selectedComponent);
  const derived = useDesignStore((state) => state.derived);

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, pointerEvents: 'none', zIndex: 10 }}>
      {/* HUD info overlay */}
      <div style={{ position: 'absolute', top: 8, left: 8, display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11, fontFamily: 'monospace', color: 'rgba(255,255,255,0.7)', backgroundColor: 'rgba(30, 30, 34, 0.75)', padding: '6px 10px', borderRadius: 4 }}>
        {derived && (
          <>
            <span>Wing Area: {derived.wingAreaCm2.toFixed(1)} cm2</span>
            <span>AR: {derived.aspectRatio.toFixed(2)}</span>
            <span>MAC: {derived.meanAeroChordMm.toFixed(1)} mm</span>
          </>
        )}
      </div>

      <div style={{ position: 'absolute', top: 8, right: 8, pointerEvents: 'auto' }}>
        <button
          onClick={onResetCamera}
          style={{ backgroundColor: '#444448', color: 'white', border: 'none', padding: '6px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 11, fontWeight: 600 }}
        >
          Center View
        </button>
      </div>

      {selectedComponent && (
        <div style={{ position: 'absolute', bottom: 8, left: 8, fontSize: 12, fontWeight: 600, color: 'white', backgroundColor: 'rgba(30, 30, 34, 0.85)', padding: '4px 10px', borderRadius: 4, textTransform: 'capitalize' }}>
          Selected: {selectedComponent}
        </div>
      )}
    </div>
  );
}
