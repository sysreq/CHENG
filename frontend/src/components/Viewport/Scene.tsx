// ============================================================================
// CHENG — 3D Viewport Scene
// R3F Canvas with lighting, grid, and dark background
// ============================================================================

import { Canvas } from '@react-three/fiber';
import AircraftMesh from './AircraftMesh';
import Controls from './Controls';
import Annotations from './Annotations';

/**
 * Main 3D viewport scene.
 *
 * Contains the R3F Canvas with:
 * - Ambient + directional lighting
 * - Ground plane grid
 * - Dark background (#2A2A2E)
 * - AircraftMesh (rendered from WebSocket binary data)
 * - OrbitControls for camera manipulation
 */
export default function Scene() {
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas
        gl={{ antialias: true }}
        camera={{
          position: [500, 300, 500],
          fov: 50,
          near: 1,
          far: 10000,
        }}
        style={{ background: '#2A2A2E' }}
      >
        {/* Lighting */}
        <ambientLight intensity={0.4} />
        <directionalLight
          position={[500, 500, 500]}
          intensity={0.8}
          castShadow={false}
        />
        <directionalLight
          position={[-300, 200, -200]}
          intensity={0.3}
          castShadow={false}
        />

        {/* Ground plane grid */}
        <gridHelper
          args={[2000, 40, '#555555', '#3a3a3a']}
          rotation={[0, 0, 0]}
        />

        {/* Axis helper (small, for orientation) */}
        <axesHelper args={[100]} />

        {/* Aircraft mesh from WebSocket binary data */}
        <AircraftMesh />

        {/* Orbit controls */}
        <Controls />
      </Canvas>

      {/* HTML overlay for dimension annotations */}
      <Annotations />
    </div>
  );
}
