// ============================================================================
// CHENG — Aircraft Mesh Component
// Renders BufferGeometry from WebSocket binary data
// ============================================================================

import { useRef, useEffect, useCallback } from 'react';
import * as THREE from 'three';
import { useDesignStore } from '@/store/designStore';
import { createBufferGeometry } from '@/lib/meshParser';
import type { MeshFrame } from '@/lib/meshParser';
import type { ComponentSelection } from '@/types/design';

/** Colors for component highlighting based on selection. */
const COMPONENT_COLORS: Record<string, string> = {
  wing: '#5c9ce6',
  fuselage: '#8b8b8b',
  tail: '#e6a65c',
};

const DEFAULT_COLOR = '#a0a0a8';

/**
 * Aircraft mesh rendered from WebSocket binary data.
 *
 * Reads meshData from the design store, creates BufferGeometry via
 * createBufferGeometry(), and renders with MeshStandardMaterial.
 *
 * Click to select a component (updates selectedComponent in store).
 * Properly disposes old geometry on update to prevent memory leaks.
 */
export default function AircraftMesh() {
  const meshRef = useRef<THREE.Mesh>(null);
  const geometryRef = useRef<THREE.BufferGeometry | null>(null);

  const meshData = useDesignStore((state) => state.meshData);
  const selectedComponent = useDesignStore((state) => state.selectedComponent);
  const setSelectedComponent = useDesignStore((state) => state.setSelectedComponent);

  // Build geometry from mesh data
  useEffect(() => {
    if (!meshData) {
      // No mesh data — dispose any existing geometry
      if (geometryRef.current) {
        geometryRef.current.dispose();
        geometryRef.current = null;
      }
      return;
    }

    // Create a MeshFrame-compatible object from the store's MeshData
    const frame: MeshFrame = {
      type: 0x01,
      vertexCount: meshData.vertexCount,
      faceCount: meshData.faceCount,
      vertices: meshData.vertices,
      normals: meshData.normals,
      faces: meshData.faces,
      // These are not needed for geometry creation, but required by the type
      derived: {
        tipChordMm: 0,
        wingAreaCm2: 0,
        aspectRatio: 0,
        meanAeroChordMm: 0,
        taperRatio: 0,
        estimatedCgMm: 0,
        minFeatureThicknessMm: 0,
        wallThicknessMm: 0,
      },
      validation: [],
    };

    // Dispose old geometry before creating new one
    if (geometryRef.current) {
      geometryRef.current.dispose();
    }

    const newGeometry = createBufferGeometry(frame);
    geometryRef.current = newGeometry;

    if (meshRef.current) {
      meshRef.current.geometry = newGeometry;
    }
  }, [meshData]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (geometryRef.current) {
        geometryRef.current.dispose();
        geometryRef.current = null;
      }
    };
  }, []);

  // Handle click to cycle through component selections
  const handleClick = useCallback(() => {
    const components: ComponentSelection[] = ['fuselage', 'wing', 'tail', null];
    const currentIndex = components.indexOf(selectedComponent);
    const nextIndex = (currentIndex + 1) % components.length;
    const next = components[nextIndex];
    if (next !== undefined) {
      setSelectedComponent(next);
    }
  }, [selectedComponent, setSelectedComponent]);

  // Determine material color based on selection
  const color = selectedComponent
    ? (COMPONENT_COLORS[selectedComponent] ?? DEFAULT_COLOR)
    : DEFAULT_COLOR;

  if (!meshData) {
    // Render a placeholder wireframe box when no mesh data is available
    return (
      <mesh>
        <boxGeometry args={[200, 50, 100]} />
        <meshStandardMaterial
          color="#555555"
          wireframe
          transparent
          opacity={0.3}
        />
      </mesh>
    );
  }

  return (
    <mesh
      ref={meshRef}
      onClick={handleClick}
      geometry={geometryRef.current ?? undefined}
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
