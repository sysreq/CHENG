// ============================================================================
// CHENG — 3D Dimension Annotations (inside R3F Canvas)
// Leader lines for: Wingspan, Overall Length, Sweep Angle
// ============================================================================

import { useMemo } from 'react';
import { Html, Line } from '@react-three/drei';
import { useDesignStore } from '@/store/designStore';

const LABEL_STYLE: React.CSSProperties = {
  fontSize: 10,
  fontFamily: 'monospace',
  color: '#CCC',
  whiteSpace: 'nowrap',
  pointerEvents: 'none',
  userSelect: 'none',
};

const LINE_COLOR = '#CCCCCC';

/**
 * 3D dimension annotations rendered inside the R3F canvas.
 * Uses R3F coordinate system: after rotation, X=span, Y=length, Z=up.
 * But the mesh is rotated [-PI/2, 0, PI/2], so we work in CadQuery coords
 * (X=length, Y=span) and let the group rotation handle it.
 */
export default function DimensionLines() {
  const wingSpan = useDesignStore((s) => s.design.wingSpan);
  const fuselageLength = useDesignStore((s) => s.design.fuselageLength);
  const wingSweep = useDesignStore((s) => s.design.wingSweep);
  const meshData = useDesignStore((s) => s.meshData);

  // Offset outside the aircraft bounding box for leader lines
  const offset = useMemo(() => {
    const halfSpan = wingSpan / 2;
    return {
      spanY: halfSpan + 40, // slightly beyond wingtip
      lengthX: -30, // slightly in front of nose
    };
  }, [wingSpan]);

  if (!meshData) return null;

  const halfSpan = wingSpan / 2;

  return (
    <group rotation={[-Math.PI / 2, 0, Math.PI / 2]}>
      {/* Wingspan line — horizontal across full span */}
      <Line
        points={[[0, -halfSpan, 0], [0, halfSpan, 0]]}
        color={LINE_COLOR}
        lineWidth={1}
        dashed={false}
      />
      {/* Wingspan ticks */}
      <Line points={[[0, -halfSpan, -10], [0, -halfSpan, 10]]} color={LINE_COLOR} lineWidth={1} />
      <Line points={[[0, halfSpan, -10], [0, halfSpan, 10]]} color={LINE_COLOR} lineWidth={1} />
      {/* Wingspan label */}
      <Html position={[0, 0, 15]} center>
        <span style={LABEL_STYLE}>{wingSpan} mm</span>
      </Html>

      {/* Fuselage length line — along X axis, offset to the side */}
      <Line
        points={[[0, offset.spanY, 0], [fuselageLength, offset.spanY, 0]]}
        color={LINE_COLOR}
        lineWidth={1}
      />
      {/* Length ticks */}
      <Line points={[[0, offset.spanY - 10, 0], [0, offset.spanY + 10, 0]]} color={LINE_COLOR} lineWidth={1} />
      <Line points={[[fuselageLength, offset.spanY - 10, 0], [fuselageLength, offset.spanY + 10, 0]]} color={LINE_COLOR} lineWidth={1} />
      {/* Length label */}
      <Html position={[fuselageLength / 2, offset.spanY + 15, 0]} center>
        <span style={LABEL_STYLE}>{fuselageLength} mm</span>
      </Html>

      {/* Sweep angle arc — only shown when sweep > 0 */}
      {wingSweep > 0 && <SweepArc sweep={wingSweep} halfSpan={halfSpan} />}
    </group>
  );
}

function SweepArc({ sweep, halfSpan }: { sweep: number; halfSpan: number }) {
  // Draw a small arc at the wing root showing sweep angle
  const arcRadius = Math.min(halfSpan * 0.3, 80);
  const sweepRad = (sweep * Math.PI) / 180;

  const arcPoints = useMemo(() => {
    const pts: [number, number, number][] = [];
    const segments = 16;
    for (let i = 0; i <= segments; i++) {
      const t = (i / segments) * sweepRad;
      // Arc in the XY plane from the quarter-chord position
      pts.push([arcRadius * Math.sin(t), arcRadius * Math.cos(t), 0]);
    }
    return pts;
  }, [arcRadius, sweepRad]);

  // Position the arc at the wing root quarter-chord
  const wingX = halfSpan * 0.3; // approximate wing mount X

  return (
    <group position={[wingX, 0, 0]}>
      <Line points={arcPoints} color={LINE_COLOR} lineWidth={1} />
      <Html position={[arcRadius * 0.7, arcRadius * 0.7, 0]} center>
        <span style={LABEL_STYLE}>{sweep}deg</span>
      </Html>
    </group>
  );
}
