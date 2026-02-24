// ============================================================================
// CHENG — Orbit Controls
// Camera manipulation with preset positions
// ============================================================================

import { OrbitControls } from '@react-three/drei';

/** Camera preset positions for standard views. */
export const CAMERA_PRESETS = {
  isometric: { position: [500, 300, 500] as const, target: [0, 0, 0] as const },
  front: { position: [0, 0, 600] as const, target: [0, 0, 0] as const },
  side: { position: [600, 0, 0] as const, target: [0, 0, 0] as const },
  top: { position: [0, 600, 0] as const, target: [0, 0, 0] as const },
} as const;

export type CameraPreset = keyof typeof CAMERA_PRESETS;

export default function Controls() {
  return (
    <OrbitControls
      makeDefault
      enableDamping
      dampingFactor={0.05} // Lower value = smoother, more stable transition
      minDistance={10}     // Reduced to allow close-up inspection of parts
      maxDistance={8000}   // Increased to prevent clipping on huge models
      enablePan
      panSpeed={0.8}
      rotateSpeed={0.8}
      zoomSpeed={1.0}
    />
  );
}