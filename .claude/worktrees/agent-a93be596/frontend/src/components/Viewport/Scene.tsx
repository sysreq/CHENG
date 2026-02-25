// ============================================================================
// CHENG — 3D Viewport Scene
// ============================================================================

import { useState, useCallback, useEffect, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { Bounds, useBounds, Html } from '@react-three/drei';
import AircraftMesh from './AircraftMesh';
import Controls from './Controls';
import Annotations from './Annotations';
import DimensionLines from './DimensionLines';
import { useDesignStore } from '@/store/designStore';

function BoundsWatcher({ readyTick }: { readyTick: number }) {
  const bounds = useBounds();

  useEffect(() => {
    if (readyTick > 0) {
      // Force a re-calculation of the boundaries and fit the camera
      bounds.refresh().clip().fit();

      const timer = setTimeout(() => {
        bounds.refresh().clip().fit();
      }, 150);

      return () => clearTimeout(timer);
    }
  }, [readyTick, bounds]);

  return null;
}

/** Delayed loading overlay — only shows after 300ms to avoid flicker. */
function GeneratingOverlay() {
  const isGenerating = useDesignStore((s) => s.isGenerating);
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (isGenerating) {
      timerRef.current = setTimeout(() => setVisible(true), 300);
    } else {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = null;
      setVisible(false);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isGenerating]);

  if (!visible) return null;

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0, 0, 0, 0.35)',
        zIndex: 10,
        pointerEvents: 'none',
      }}
    >
      <div className="generating-spinner" />
    </div>
  );
}

const AXIS_LABEL_STYLE: React.CSSProperties = {
  fontSize: 10,
  fontFamily: 'monospace',
  fontWeight: 700,
  whiteSpace: 'nowrap' as const,
  pointerEvents: 'none' as const,
  userSelect: 'none' as const,
};

/** Text labels for axes helper endpoints (#173). */
function AxesLabels({ size }: { size: number }) {
  return (
    <>
      <Html position={[size + 8, 0, 0]} center style={{ pointerEvents: 'none' }}>
        <span style={{ ...AXIS_LABEL_STYLE, color: '#ff4444' }}>X</span>
      </Html>
      <Html position={[0, size + 8, 0]} center style={{ pointerEvents: 'none' }}>
        <span style={{ ...AXIS_LABEL_STYLE, color: '#44ff44' }}>Y</span>
      </Html>
      <Html position={[0, 0, size + 8]} center style={{ pointerEvents: 'none' }}>
        <span style={{ ...AXIS_LABEL_STYLE, color: '#4444ff' }}>Z</span>
      </Html>
    </>
  );
}

export default function Scene() {
  const [readyTick, setReadyTick] = useState(0);

  const handleMeshLoaded = useCallback(() => {
    setReadyTick((prev) => prev + 1);
  }, []);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas
        gl={{ antialias: true }}
        camera={{ position: [500, 300, 500], fov: 50, near: 1, far: 10000 }}
        style={{ background: '#2A2A2E' }}
      >
        <ambientLight intensity={0.4} />
        <directionalLight position={[500, 500, 500]} intensity={0.8} />
        <directionalLight position={[-300, 200, -200]} intensity={0.3} />

        <gridHelper args={[2000, 40, '#555555', '#3a3a3a']} />
        <axesHelper args={[100]} />
        <AxesLabels size={100} />

        <Bounds fit observe margin={1.5}>
          <AircraftMesh onLoaded={handleMeshLoaded} />
          <DimensionLines />
          {readyTick > 0 && <BoundsWatcher readyTick={readyTick} />}
        </Bounds>
        <Controls />
      </Canvas>

      <GeneratingOverlay />
      <Annotations onResetCamera={handleMeshLoaded} />
    </div>
  );
}