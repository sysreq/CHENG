// ============================================================================
// CHENG — Viewport Annotations Overlay
// HUD info panel + camera reset button (outside Canvas).
// ============================================================================

import { useDesignStore } from '@/store/designStore';

interface AnnotationsProps {
  onResetCamera?: () => void;
}

/** Sub-element label mapping. */
const SUB_ELEMENT_LABELS: Record<string, string> = {
  'left-panel': 'Left Panel',
  'right-panel': 'Right Panel',
  'h-stab': 'H-Stab',
  'v-stab': 'V-Stab',
  'nose': 'Nose',
  'cabin': 'Cabin',
  'tail-cone': 'Tail Cone',
};

/** Badge showing currently selected component and sub-element. */
function SelectedComponentBadge() {
  const selectedComponent = useDesignStore((state) => state.selectedComponent);
  const selectedSubElement = useDesignStore((state) => state.selectedSubElement);

  // 'global' is the default tab state — no component-specific badge needed (#289)
  if (!selectedComponent || selectedComponent === 'global') return null;

  const subLabel = selectedSubElement ? SUB_ELEMENT_LABELS[selectedSubElement] ?? selectedSubElement : null;

  return (
    <div style={{ position: 'absolute', bottom: 8, left: 8, fontSize: 12, fontWeight: 600, color: 'white', backgroundColor: 'rgba(30, 30, 34, 0.85)', padding: '4px 10px', borderRadius: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ textTransform: 'capitalize' }}>{selectedComponent}</span>
      {subLabel && (
        <>
          <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 10 }}>{'\u203A'}</span>
          <span style={{ color: '#FF6B35', fontSize: 11 }}>{subLabel}</span>
        </>
      )}
      <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 9, marginLeft: 4 }}>
        {selectedSubElement ? 'click to cycle' : 'click again to sub-select'}
      </span>
    </div>
  );
}

export default function Annotations({ onResetCamera }: AnnotationsProps) {
  return (
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, pointerEvents: 'none', zIndex: 10 }}>
      <div style={{ position: 'absolute', top: 8, right: 8, pointerEvents: 'auto' }}>
        <button
          onClick={onResetCamera}
          style={{ backgroundColor: '#444448', color: 'white', border: 'none', padding: '6px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 11, fontWeight: 600 }}
        >
          Center View
        </button>
      </div>

      <SelectedComponentBadge />
    </div>
  );
}
