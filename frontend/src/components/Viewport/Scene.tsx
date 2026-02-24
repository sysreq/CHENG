// ============================================================================
// CHENG — 3D Viewport Scene
// ============================================================================

import { useState, useCallback, useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { Bounds, useBounds } from '@react-three/drei';
import AircraftMesh from './AircraftMesh';
import Controls from './Controls';
import Annotations from './Annotations';

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

        <Bounds fit observe margin={1.2}>
          <AircraftMesh onLoaded={handleMeshLoaded} />
          {readyTick > 0 && <BoundsWatcher readyTick={readyTick} />}
        </Bounds>

        <Controls />
      </Canvas>

      <Annotations onResetCamera={handleMeshLoaded} />
    </div>
  );
}