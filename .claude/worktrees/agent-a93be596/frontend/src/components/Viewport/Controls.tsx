// ============================================================================
// CHENG — Orbit Controls
// Camera manipulation with preset positions
// ============================================================================

import { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { useDesignStore } from '@/store/designStore';

/** Camera preset positions for standard views. */
export const CAMERA_PRESETS = {
  perspective: { position: [500, 300, 500] as [number, number, number], target: [0, 0, 0] as [number, number, number] },
  front: { position: [0, 0, 600] as [number, number, number], target: [0, 0, 0] as [number, number, number] },
  side: { position: [600, 0, 0] as [number, number, number], target: [0, 0, 0] as [number, number, number] },
  top: { position: [0, 600, 0] as [number, number, number], target: [0, 0, 0] as [number, number, number] },
};

export type CameraPreset = keyof typeof CAMERA_PRESETS;

export default function Controls() {
  const controlsRef = useRef<React.ComponentRef<typeof OrbitControls>>(null);
  const { camera } = useThree();
  const cameraPresetTick = useDesignStore((s) => s.cameraPresetTick);

  useEffect(() => {
    if (cameraPresetTick.tick === 0) return;
    const preset = CAMERA_PRESETS[cameraPresetTick.preset];
    if (!preset) return;

    const [px, py, pz] = preset.position;
    const [tx, ty, tz] = preset.target;

    camera.position.set(px, py, pz);
    camera.lookAt(new THREE.Vector3(tx, ty, tz));
    camera.updateProjectionMatrix();

    if (controlsRef.current) {
      controlsRef.current.target.set(tx, ty, tz);
      controlsRef.current.update();
    }
  }, [cameraPresetTick, camera]);

  return (
    <OrbitControls
      ref={controlsRef}
      makeDefault
      enableDamping
      dampingFactor={0.05}
      minDistance={10}
      maxDistance={8000}
      enablePan
      panSpeed={0.8}
      rotateSpeed={0.8}
      zoomSpeed={1.0}
    />
  );
}