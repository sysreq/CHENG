// ============================================================================
// CHENG — Aircraft Mesh Component
// Renders per-component mesh groups with click-to-select highlighting.
// ============================================================================

import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import * as THREE from 'three';
import { ThreeEvent } from '@react-three/fiber';
import { useDesignStore } from '@/store/designStore';
import { createBufferGeometry } from '@/lib/meshParser';
import type { MeshFrame } from '@/lib/meshParser';
import type { ComponentSelection } from '@/types/design';

const SELECTED_COLOR = '#FFD60A';
const UNSELECTED_COLOR = '#6B6B70';

/** Default color per component when nothing is selected. */
const COMPONENT_COLORS: Record<string, string> = {
  wing: '#5c9ce6',
  fuselage: '#8b8b8b',
  tail: '#e6a65c',
};
const DEFAULT_COLOR = '#a0a0a8';

interface AircraftMeshProps {
  onLoaded?: () => void;
}

/** Create a sub-geometry from a face range of the full geometry. */
function createSubGeometry(
  fullGeom: THREE.BufferGeometry,
  startFace: number,
  endFace: number,
): THREE.BufferGeometry {
  const sub = new THREE.BufferGeometry();

  // Share the same vertex/normal buffer attributes
  const posAttr = fullGeom.getAttribute('position');
  const normAttr = fullGeom.getAttribute('normal');
  sub.setAttribute('position', posAttr);
  sub.setAttribute('normal', normAttr);

  // Slice the index buffer for this component's face range
  const fullIndex = fullGeom.getIndex();
  if (fullIndex) {
    const start = startFace * 3;
    const count = (endFace - startFace) * 3;
    sub.setIndex(new THREE.BufferAttribute(
      fullIndex.array.slice(start, start + count) as Uint32Array,
      1,
    ));
  }

  sub.computeBoundingBox();
  sub.computeBoundingSphere();
  return sub;
}

export default function AircraftMesh({ onLoaded }: AircraftMeshProps) {
  const groupRef = useRef<THREE.Group>(null);

  // Full merged geometry for centering + sub-geometry extraction
  const [fullGeometry, setFullGeometry] = useState<THREE.BufferGeometry | null>(null);

  // Guard to ensure we only AUTO-ZOOM on the very first load
  const hasInitialZoomed = useRef<boolean>(false);

  const meshData = useDesignStore((state) => state.meshData);
  const selectedComponent = useDesignStore((state) => state.selectedComponent);
  const setSelectedComponent = useDesignStore((state) => state.setSelectedComponent);

  // Build full geometry when meshData changes
  useEffect(() => {
    if (!meshData) {
      setFullGeometry((prev) => {
        if (prev) prev.dispose();
        return null;
      });
      return;
    }

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
      componentRanges: null,
    };

    const newGeometry = createBufferGeometry(frame);
    newGeometry.computeBoundingBox();

    if (newGeometry.boundingBox) {
      const bbox = newGeometry.boundingBox;
      const center = new THREE.Vector3();
      bbox.getCenter(center);
      newGeometry.translate(-center.x, -center.y, -bbox.min.z);
    }

    setFullGeometry((prev) => {
      if (prev) prev.dispose();
      return newGeometry;
    });

    // Trigger zoom only once on initial load
    if (!hasInitialZoomed.current && onLoaded) {
      const timer = setTimeout(() => {
        hasInitialZoomed.current = true;
        onLoaded();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [meshData, onLoaded]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      setFullGeometry((prev) => {
        if (prev) prev.dispose();
        return null;
      });
    };
  }, []);

  // Build sub-geometries per component from face ranges
  const componentGeometries = useMemo(() => {
    if (!fullGeometry || !meshData?.componentRanges) return null;

    const ranges = meshData.componentRanges;
    const result: Partial<Record<'fuselage' | 'wing' | 'tail', THREE.BufferGeometry>> = {};

    for (const key of ['fuselage', 'wing', 'tail'] as const) {
      const range = ranges[key];
      if (range) {
        result[key] = createSubGeometry(fullGeometry, range[0], range[1]);
      }
    }

    return result;
  }, [fullGeometry, meshData?.componentRanges]);

  const handleComponentClick = useCallback(
    (component: ComponentSelection) => (e: ThreeEvent<MouseEvent>) => {
      e.stopPropagation();
      setSelectedComponent(selectedComponent === component ? null : component);
    },
    [selectedComponent, setSelectedComponent],
  );

  const handleMissClick = useCallback(() => {
    setSelectedComponent(null);
  }, [setSelectedComponent]);

  if (!meshData) {
    return (
      <mesh>
        <boxGeometry args={[200, 50, 100]} />
        <meshStandardMaterial color="#555555" wireframe transparent opacity={0.3} />
      </mesh>
    );
  }

  // If we have per-component ranges, render separate meshes
  if (componentGeometries) {
    return (
      <group ref={groupRef} rotation={[-Math.PI / 2, 0, Math.PI / 2]} onPointerMissed={handleMissClick}>
        {(['fuselage', 'wing', 'tail'] as const).map((key) => {
          const geom = componentGeometries[key];
          if (!geom) return null;

          let color: string;
          if (selectedComponent === null) {
            // Nothing selected — show component-specific colors
            color = COMPONENT_COLORS[key] ?? DEFAULT_COLOR;
          } else if (selectedComponent === key) {
            color = SELECTED_COLOR;
          } else {
            color = UNSELECTED_COLOR;
          }

          return (
            <mesh
              key={key}
              geometry={geom}
              onClick={handleComponentClick(key)}
            >
              <meshStandardMaterial
                color={color}
                metalness={0.1}
                roughness={0.7}
                side={THREE.DoubleSide}
              />
            </mesh>
          );
        })}
      </group>
    );
  }

  // Fallback: single mesh when no component ranges available
  return (
    <mesh
      geometry={fullGeometry ?? undefined}
      rotation={[-Math.PI / 2, 0, Math.PI / 2]}
      onClick={handleMissClick}
    >
      <meshStandardMaterial
        color={DEFAULT_COLOR}
        metalness={0.1}
        roughness={0.7}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}
