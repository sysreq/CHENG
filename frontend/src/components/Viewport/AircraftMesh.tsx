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
  // Wing halves — left slightly lighter, right slightly darker for distinction (#228)
  wing_left: '#6db0f0',
  wing_right: '#4a88d4',
  fuselage: '#8b8b8b',
  tail: '#e6a65c',
  // Control surfaces — amber (#144)
  aileron_left: '#f59e0b',
  aileron_right: '#f59e0b',
  elevator_left: '#f59e0b',
  elevator_right: '#f59e0b',
  rudder: '#f59e0b',
  ruddervator_left: '#f59e0b',
  ruddervator_right: '#f59e0b',
  elevon_left: '#f59e0b',
  elevon_right: '#f59e0b',
  gear_main_left: '#22c55e',
  gear_main_right: '#22c55e',
  gear_nose: '#22c55e',
  gear_tail: '#22c55e',
};
const DEFAULT_COLOR = '#a0a0a8';

/** All primary structural components (selectable).
 *  Includes separate left/right wing halves for distinct shading (#228). */
const PRIMARY_COMPONENTS = ['fuselage', 'wing_left', 'wing_right', 'wing', 'tail'] as const;

/** Control surface component keys (rendered but not top-level selectable). */
const CONTROL_SURFACE_KEYS = [
  'aileron_left', 'aileron_right',
  'elevator_left', 'elevator_right',
  'rudder',
  'ruddervator_left', 'ruddervator_right',
  'elevon_left', 'elevon_right',
] as const;

type ControlSurfaceKey = typeof CONTROL_SURFACE_KEYS[number];

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
    const result: Partial<Record<
      'fuselage' | 'wing' | 'wing_left' | 'wing_right' | 'tail' | ControlSurfaceKey
      | 'gear_main_left' | 'gear_main_right' | 'gear_nose' | 'gear_tail',
      THREE.BufferGeometry
    >> = {};

    // Primary structural components — prefer separate wing_left/wing_right (#228)
    for (const key of PRIMARY_COMPONENTS) {
      const range = ranges[key];
      if (range) {
        result[key] = createSubGeometry(fullGeometry, range[0], range[1]);
      }
    }

    // Control surfaces
    for (const key of CONTROL_SURFACE_KEYS) {
      const range = ranges[key];
      if (range) {
        result[key] = createSubGeometry(fullGeometry, range[0], range[1]);
      }
    }

    // Landing gear
    for (const key of [
      'gear_main_left', 'gear_main_right', 'gear_nose', 'gear_tail',
    ] as const) {
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
      wing_left: 'Left Wing',
      wing_right: 'Right Wing',
      tail: 'Tail',
      aileron_left: 'Left Aileron',
      aileron_right: 'Right Aileron',
      elevator_left: 'Left Elevator',
      elevator_right: 'Right Elevator',
      rudder: 'Rudder',
      ruddervator_left: 'Left Ruddervator',
      ruddervator_right: 'Right Ruddervator',
      elevon_left: 'Left Elevon',
      elevon_right: 'Right Elevon',
      gear_main_left: 'Landing Gear (Main Left)',
      gear_main_right: 'Landing Gear (Main Right)',
      gear_nose: 'Landing Gear (Nose)',
      gear_tail: 'Landing Gear (Tail Wheel)',
    };

    // Map gear mesh keys to the 'landing_gear' ComponentSelection
    const GEAR_MESH_KEYS = new Set([
      'gear_main_left', 'gear_main_right', 'gear_nose', 'gear_tail',
    ] as const);

    // Map wing half keys to the 'wing' ComponentSelection so clicking either half selects the wing
    const WING_HALF_KEYS = new Set(['wing_left', 'wing_right'] as const);

    const getComponentSelection = (key: string): ComponentSelection => {
      if (GEAR_MESH_KEYS.has(key as 'gear_main_left')) return 'landing_gear';
      if (WING_HALF_KEYS.has(key as 'wing_left')) return 'wing';
      return key as ComponentSelection;
    };

    // Prefer separate wing_left/wing_right if available; fall back to combined 'wing' (#228)
    const hasWingHalves = Boolean(componentGeometries['wing_left'] || componentGeometries['wing_right']);

    const allKeys = [
      'fuselage',
      ...(hasWingHalves ? (['wing_left', 'wing_right'] as const) : (['wing'] as const)),
      'tail',
      'gear_main_left', 'gear_main_right', 'gear_nose', 'gear_tail',
    ] as const;

    return (
      <group ref={groupRef} rotation={[-Math.PI / 2, 0, Math.PI / 2]} onPointerMissed={handleMissClick}>
        {allKeys.map((key) => {
          const geom = componentGeometries[key as keyof typeof componentGeometries];
          if (!geom) return null;

          const componentSel = getComponentSelection(key);
          const isHovered = hoveredComponent === (key as ComponentSelection);
          const isSelected = selectedComponent === componentSel;
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
                onClick={handleComponentClick(componentSel)}
                onPointerEnter={handlePointerEnter(key as ComponentSelection)}
                onPointerLeave={handlePointerLeave(key as ComponentSelection)}
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

        {/* Control surfaces — amber, non-selectable (#144) */}
        {CONTROL_SURFACE_KEYS.map((key) => {
          const geom = componentGeometries[key];
          if (!geom) return null;

          const label = componentLabels[key] ?? key;
          const color = selectedComponent === null
            ? (COMPONENT_COLORS[key] ?? DEFAULT_COLOR)
            : UNSELECTED_COLOR;

          return (
            <group key={key}>
              <mesh geometry={geom}>
                <meshStandardMaterial
                  color={color}
                  emissive="#000000"
                  emissiveIntensity={0}
                  metalness={0.1}
                  roughness={0.6}
                  side={THREE.DoubleSide}
                />
              </mesh>
              {/* Invisible hit-test mesh for hover tooltip only */}
              <mesh
                geometry={geom}
                onPointerEnter={(e) => { e.stopPropagation(); setHoveredComponent(key as ComponentSelection); gl.domElement.style.cursor = 'default'; }}
                onPointerLeave={(e) => { e.stopPropagation(); setHoveredComponent(null); gl.domElement.style.cursor = 'auto'; }}
              >
                <meshBasicMaterial transparent opacity={0} depthWrite={false} />
              </mesh>
              {(hoveredComponent as string) === key && geom.boundingSphere && (
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
                    border: '1px solid rgba(255, 159, 0, 0.5)',
                  }}>
                    {label}
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
