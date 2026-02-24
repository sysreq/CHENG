// ============================================================================
// CHENG — Aircraft Mesh Component
// ============================================================================

import { useState, useRef, useEffect, useCallback } from 'react';
import * as THREE from 'three';
import { useDesignStore } from '@/store/designStore';
import { createBufferGeometry } from '@/lib/meshParser';
import type { MeshFrame } from '@/lib/meshParser';
import type { ComponentSelection } from '@/types/design';

const COMPONENT_COLORS: Record<string, string> = {
  wing: '#5c9ce6',
  fuselage: '#8b8b8b',
  tail: '#e6a65c',
};

const DEFAULT_COLOR = '#a0a0a8';

interface AircraftMeshProps {
  onLoaded?: () => void;
}

export default function AircraftMesh({ onLoaded }: AircraftMeshProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  // Keep current geometry in state so React re-renders when it changes,
  // avoiding the race where the mesh renders a disposed ref.
  const [geometry, setGeometry] = useState<THREE.BufferGeometry | null>(null);

  // Guard to ensure we only AUTO-ZOOM on the very first load
  const hasInitialZoomed = useRef<boolean>(false);

  const meshData = useDesignStore((state) => state.meshData);
  const selectedComponent = useDesignStore((state) => state.selectedComponent);
  const setSelectedComponent = useDesignStore((state) => state.setSelectedComponent);

  useEffect(() => {
    // 1. If no data, cleanup and exit
    if (!meshData) {
      setGeometry((prev) => {
        if (prev) prev.dispose();
        return null;
      });
      return;
    }

    // 2. Build the geometry (This now runs on every wingspan/param change)
    const frame: MeshFrame = {
      type: 0x01,
      vertexCount: meshData.vertexCount,
      faceCount: meshData.faceCount,
      vertices: meshData.vertices,
      normals: meshData.normals,
      faces: meshData.faces,
      derived: {
        tipChordMm: 0, wingAreaCm2: 0, aspectRatio: 0,
        meanAeroChordMm: 0, taperRatio: 0, estimatedCgMm: 0,
        minFeatureThicknessMm: 0, wallThicknessMm: 0,
      },
      validation: [],
    };

    const newGeometry = createBufferGeometry(frame);
    newGeometry.computeBoundingBox();

    if (newGeometry.boundingBox) {
      const bbox = newGeometry.boundingBox;
      const center = new THREE.Vector3();
      bbox.getCenter(center);
      // Center the mesh internal data
      newGeometry.translate(-center.x, -center.y, -bbox.min.z);
    }

    // Atomically swap: set new geometry first, then dispose old
    setGeometry((prev) => {
      if (prev) prev.dispose();
      return newGeometry;
    });

    if (meshRef.current) {
      meshRef.current.geometry = newGeometry;
      meshRef.current.updateMatrixWorld();
    }

    // 3. Trigger the zoom only once on initial load.
    // Subsequent design changes update the mesh but DON'T move the camera.
    if (!hasInitialZoomed.current && onLoaded) {
      const timer = setTimeout(() => {
        hasInitialZoomed.current = true;
        onLoaded();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [meshData, onLoaded]);

  useEffect(() => {
    return () => {
      setGeometry((prev) => {
        if (prev) prev.dispose();
        return null;
      });
    };
  }, []);

  const handleClick = useCallback(() => {
    const components: ComponentSelection[] = ['fuselage', 'wing', 'tail', null];
    const currentIndex = components.indexOf(selectedComponent);
    const nextIndex = (currentIndex + 1) % components.length;
    const next = components[nextIndex];
    if (next !== undefined) {
      setSelectedComponent(next);
    }
  }, [selectedComponent, setSelectedComponent]);

  const color = selectedComponent
    ? (COMPONENT_COLORS[selectedComponent] ?? DEFAULT_COLOR)
    : DEFAULT_COLOR;

  if (!meshData) {
    return (
      <mesh>
        <boxGeometry args={[200, 50, 100]} />
        <meshStandardMaterial color="#555555" wireframe transparent opacity={0.3} />
      </mesh>
    );
  }

  return (
    <mesh
      ref={meshRef}
      onClick={handleClick}
      geometry={geometry ?? undefined}
      rotation={[-Math.PI / 2, 0, Math.PI / 2]}
    >
      <meshStandardMaterial
        color={color}
        metalness={0.1}
        roughness={0.7}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}