// ============================================================================
// CHENG — Aircraft Mesh Component
// Renders per-component mesh groups with click-to-select highlighting.
// Supports sub-element cycling within selected components (#138).
// ============================================================================

import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import * as THREE from 'three';
import { ThreeEvent, useThree } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import { useDesignStore } from '@/store/designStore';
import { createBufferGeometry } from '@/lib/meshParser';
import type { MeshFrame } from '@/lib/meshParser';
import type { ComponentSelection } from '@/types/design';

const SELECTED_COLOR = '#FFD60A';
const SUB_SELECTED_COLOR = '#FF6B35';
const UNSELECTED_COLOR = '#6B6B70';
const HOVER_EMISSIVE = '#222244';
const HOVER_EMISSIVE_INTENSITY = 0.3;

/** Default color per component when nothing is selected. */
const COMPONENT_COLORS: Record<string, string> = {
  wing: '#5c9ce6',
  fuselage: '#8b8b8b',
  tail: '#e6a65c',
};
const DEFAULT_COLOR = '#a0a0a8';

/** Human-readable labels for sub-elements. */
const SUB_ELEMENT_LABELS: Record<string, string> = {
  'left-panel': 'Left Panel',
  'right-panel': 'Right Panel',
  'h-stab': 'Horizontal Stabilizer',
  'v-stab': 'Vertical Stabilizer',
  'nose': 'Nose Section',
  'cabin': 'Cabin Section',
  'tail-cone': 'Tail Cone',
};

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

  // Use a subarray view of the index buffer for this component's face range (zero-copy)
  const fullIndex = fullGeom.getIndex();
  if (fullIndex) {
    const start = startFace * 3;
    const count = (endFace - startFace) * 3;
    const indexView = (fullIndex.array as Uint32Array).subarray(start, start + count);
    sub.setIndex(new THREE.Uint32BufferAttribute(indexView, 1));
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
  const selectedSubElement = useDesignStore((state) => state.selectedSubElement);
  const setSelectedComponent = useDesignStore((state) => state.setSelectedComponent);
  const cycleSubElement = useDesignStore((state) => state.cycleSubElement);
  const setMeshOffset = useDesignStore((state) => state.setMeshOffset);

  // Build full geometry when meshData changes
  useEffect(() => {
    if (!meshData) {
      setFullGeometry((prev) => {
        if (prev) prev.dispose();
        return null;
      });
      return;
    }

    // Clone typed arrays to avoid mutating Zustand store state when
    // translate() modifies vertex positions in-place (#192)
    const frame: MeshFrame = {
      type: 0x01,
      vertexCount: meshData.vertexCount,
      faceCount: meshData.faceCount,
      vertices: new Float32Array(meshData.vertices),
      normals: new Float32Array(meshData.normals),
      faces: new Uint32Array(meshData.faces),
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
      const offset: [number, number, number] = [-center.x, -center.y, -bbox.min.z];
      newGeometry.translate(offset[0], offset[1], offset[2]);
      setMeshOffset(offset);
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
  }, [meshData, onLoaded, setMeshOffset]);

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

  // Dispose component geometries when they change or on unmount (#91)
  useEffect(() => {
    return () => {
      if (componentGeometries) {
        Object.values(componentGeometries).forEach((geom) => {
          if (geom) geom.dispose();
        });
      }
    };
  }, [componentGeometries]);

  // Hover state for component highlighting (#168)
  const [hoveredComponent, setHoveredComponent] = useState<ComponentSelection>(null);
  const { gl } = useThree();

  const handleComponentClick = useCallback(
    (component: ComponentSelection) => (e: ThreeEvent<MouseEvent>) => {
      e.stopPropagation();
      if (selectedComponent === component) {
        // Already selected — cycle through sub-elements (#138)
        cycleSubElement();
      } else {
        setSelectedComponent(component);
      }
    },
    [selectedComponent, setSelectedComponent, cycleSubElement],
  );

  const handlePointerEnter = useCallback(
    (component: ComponentSelection) => (e: ThreeEvent<PointerEvent>) => {
      e.stopPropagation();
      setHoveredComponent(component);
      gl.domElement.style.cursor = 'pointer';
    },
    [gl],
  );

  const handlePointerLeave = useCallback(
    (_component: ComponentSelection) => (e: ThreeEvent<PointerEvent>) => {
      e.stopPropagation();
      setHoveredComponent(null);
      gl.domElement.style.cursor = 'auto';
    },
    [gl],
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
    /** Human-readable label for tooltip. */
    const componentLabels: Record<string, string> = {
      fuselage: 'Fuselage',
      wing: 'Wing',
      tail: 'Tail',
    };

    return (
      <group ref={groupRef} rotation={[-Math.PI / 2, 0, Math.PI / 2]} onPointerMissed={handleMissClick}>
        {(['fuselage', 'wing', 'tail'] as const).map((key) => {
          const geom = componentGeometries[key];
          if (!geom) return null;

          const isHovered = hoveredComponent === key;
          const isSelected = selectedComponent === key;
          const hasSubSelection = isSelected && selectedSubElement !== null;

          let color: string;
          if (selectedComponent === null) {
            color = COMPONENT_COLORS[key] ?? DEFAULT_COLOR;
          } else if (isSelected) {
            color = hasSubSelection ? SUB_SELECTED_COLOR : SELECTED_COLOR;
          } else {
            color = UNSELECTED_COLOR;
          }

          // Build tooltip text
          let tooltipText = componentLabels[key] ?? key;
          if (isSelected && selectedSubElement) {
            tooltipText += ` > ${SUB_ELEMENT_LABELS[selectedSubElement] ?? selectedSubElement}`;
          }

          return (
            <group key={key}>
              <mesh
                geometry={geom}
                onClick={handleComponentClick(key)}
                onPointerEnter={handlePointerEnter(key)}
                onPointerLeave={handlePointerLeave(key)}
              >
                <meshStandardMaterial
                  color={color}
                  emissive={isHovered ? HOVER_EMISSIVE : '#000000'}
                  emissiveIntensity={isHovered ? HOVER_EMISSIVE_INTENSITY : 0}
                  metalness={0.1}
                  roughness={0.7}
                  side={THREE.DoubleSide}
                />
              </mesh>
              {/* Sub-selection outline effect — wireframe overlay when sub-element is active */}
              <mesh geometry={geom} visible={hasSubSelection}>
                <meshBasicMaterial
                  color="#FF6B35"
                  wireframe
                  transparent
                  opacity={0.15}
                  side={THREE.DoubleSide}
                  depthWrite={false}
                />
              </mesh>
              {/* Tooltip on hover — rendered at component bounding sphere center */}
              {isHovered && geom.boundingSphere && (
                <Html
                  position={[
                    geom.boundingSphere.center.x,
                    geom.boundingSphere.center.y + geom.boundingSphere.radius * 0.8,
                    geom.boundingSphere.center.z,
                  ]}
                  center
                  style={{ pointerEvents: 'none' }}
                >
                  <div style={{
                    fontSize: 10,
                    fontFamily: 'monospace',
                    color: '#fff',
                    backgroundColor: 'rgba(30, 30, 34, 0.9)',
                    padding: '2px 8px',
                    borderRadius: 3,
                    whiteSpace: 'nowrap',
                    border: '1px solid rgba(255,255,255,0.15)',
                  }}>
                    {tooltipText}
                  </div>
                </Html>
              )}
            </group>
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
