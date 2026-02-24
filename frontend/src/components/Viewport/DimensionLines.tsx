// ============================================================================
// CHENG — 3D Dimension Annotations (inside R3F Canvas)
// Contextual: annotations change based on selectedComponent (#134)
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
const CONTEXT_LINE_COLOR = '#FFD60A';
const CONTEXT_LABEL_STYLE: React.CSSProperties = {
  ...LABEL_STYLE,
  color: '#FFD60A',
};

/**
 * 3D dimension annotations rendered inside the R3F canvas.
 * Uses R3F coordinate system: after rotation, X=span, Y=length, Z=up.
 * But the mesh is rotated [-PI/2, 0, PI/2], so we work in CadQuery coords
 * (X=length, Y=span) and let the group rotation handle it.
 *
 * When a component is selected, shows contextual dimensions for that component.
 * When nothing is selected, shows global dimensions (wingspan + fuselage length).
 */
export default function DimensionLines() {
  const meshData = useDesignStore((s) => s.meshData);
  const meshOffset = useDesignStore((s) => s.meshOffset);
  const selectedComponent = useDesignStore((s) => s.selectedComponent);

  if (!meshData) return null;

  const [ox, oy, oz] = meshOffset;

  return (
    <group rotation={[-Math.PI / 2, 0, Math.PI / 2]} position={[ox, oy, oz]}>
      {selectedComponent === null && <GlobalDimensions />}
      {selectedComponent === 'wing' && <WingDimensions />}
      {selectedComponent === 'tail' && <TailDimensions />}
      {selectedComponent === 'fuselage' && <FuselageDimensions />}
    </group>
  );
}

// ---------------------------------------------------------------------------
// Global Dimensions (no selection)
// ---------------------------------------------------------------------------

function GlobalDimensions() {
  const wingSpan = useDesignStore((s) => s.design.wingSpan);
  const fuselageLength = useDesignStore((s) => s.design.fuselageLength);
  const wingSweep = useDesignStore((s) => s.design.wingSweep);

  const halfSpan = wingSpan / 2;
  const spanY = halfSpan + 40;

  return (
    <>
      {/* Wingspan line */}
      <Line points={[[0, -halfSpan, 0], [0, halfSpan, 0]]} color={LINE_COLOR} lineWidth={1} />
      <Line points={[[0, -halfSpan, -10], [0, -halfSpan, 10]]} color={LINE_COLOR} lineWidth={1} />
      <Line points={[[0, halfSpan, -10], [0, halfSpan, 10]]} color={LINE_COLOR} lineWidth={1} />
      <Html position={[0, 0, 15]} center>
        <span style={LABEL_STYLE}>{wingSpan} mm</span>
      </Html>

      {/* Fuselage length line */}
      <Line points={[[0, spanY, 0], [fuselageLength, spanY, 0]]} color={LINE_COLOR} lineWidth={1} />
      <Line points={[[0, spanY - 10, 0], [0, spanY + 10, 0]]} color={LINE_COLOR} lineWidth={1} />
      <Line points={[[fuselageLength, spanY - 10, 0], [fuselageLength, spanY + 10, 0]]} color={LINE_COLOR} lineWidth={1} />
      <Html position={[fuselageLength / 2, spanY + 15, 0]} center>
        <span style={LABEL_STYLE}>{fuselageLength} mm</span>
      </Html>

      {wingSweep > 0 && <SweepArc sweep={wingSweep} />}
    </>
  );
}

// ---------------------------------------------------------------------------
// Wing Dimensions (wing selected)
// ---------------------------------------------------------------------------

function WingDimensions() {
  const wingSpan = useDesignStore((s) => s.design.wingSpan);
  const wingChord = useDesignStore((s) => s.design.wingChord);
  const wingTipRootRatio = useDesignStore((s) => s.design.wingTipRootRatio);

  const halfSpan = wingSpan / 2;
  const tipChord = wingChord * wingTipRootRatio;

  return (
    <>
      {/* Wingspan line */}
      <Line points={[[0, -halfSpan, 0], [0, halfSpan, 0]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <Line points={[[0, -halfSpan, -10], [0, -halfSpan, 10]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Line points={[[0, halfSpan, -10], [0, halfSpan, 10]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Html position={[0, 0, 18]} center>
        <span style={CONTEXT_LABEL_STYLE}>Span: {wingSpan} mm</span>
      </Html>

      {/* Root chord at center */}
      <Line points={[[0, 0, 0], [wingChord, 0, 0]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <Html position={[wingChord / 2, 0, -15]} center>
        <span style={CONTEXT_LABEL_STYLE}>Root: {wingChord} mm</span>
      </Html>

      {/* Tip chord at wingtip */}
      <Line points={[[0, halfSpan, 0], [tipChord, halfSpan, 0]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <Html position={[tipChord / 2, halfSpan, -15]} center>
        <span style={CONTEXT_LABEL_STYLE}>Tip: {Math.round(tipChord)} mm</span>
      </Html>
    </>
  );
}

// ---------------------------------------------------------------------------
// Tail Dimensions (tail selected)
// ---------------------------------------------------------------------------

function TailDimensions() {
  const tailType = useDesignStore((s) => s.design.tailType);

  if (tailType === 'V-Tail') {
    return <VTailDimensions />;
  }
  return <ConventionalTailDimensions />;
}

/** V-Tail specific dimensions — isolated subscriptions. */
function VTailDimensions() {
  const vTailSpan = useDesignStore((s) => s.design.vTailSpan);
  const vTailChord = useDesignStore((s) => s.design.vTailChord);
  const fuselageLength = useDesignStore((s) => s.design.fuselageLength);

  const halfVSpan = vTailSpan / 2;
  return (
    <group position={[fuselageLength, 0, 0]}>
      <Line points={[[0, -halfVSpan, 0], [0, halfVSpan, 0]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <Line points={[[0, -halfVSpan, -8], [0, -halfVSpan, 8]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Line points={[[0, halfVSpan, -8], [0, halfVSpan, 8]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Html position={[0, 0, 15]} center>
        <span style={CONTEXT_LABEL_STYLE}>V-Span: {vTailSpan} mm</span>
      </Html>

      <Line points={[[-vTailChord, 0, 0], [0, 0, 0]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <Html position={[-vTailChord / 2, 0, -12]} center>
        <span style={CONTEXT_LABEL_STYLE}>Chord: {vTailChord} mm</span>
      </Html>
    </group>
  );
}

/** Conventional / T-Tail / Cruciform tail dimensions — isolated subscriptions. */
function ConventionalTailDimensions() {
  const hStabSpan = useDesignStore((s) => s.design.hStabSpan);
  const hStabChord = useDesignStore((s) => s.design.hStabChord);
  const vStabHeight = useDesignStore((s) => s.design.vStabHeight);
  const fuselageLength = useDesignStore((s) => s.design.fuselageLength);

  const halfHSpan = hStabSpan / 2;
  return (
    <group position={[fuselageLength, 0, 0]}>
      <Line points={[[0, -halfHSpan, 0], [0, halfHSpan, 0]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <Line points={[[0, -halfHSpan, -8], [0, -halfHSpan, 8]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Line points={[[0, halfHSpan, -8], [0, halfHSpan, 8]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Html position={[0, 0, 15]} center>
        <span style={CONTEXT_LABEL_STYLE}>H-Span: {hStabSpan} mm</span>
      </Html>

      <Line points={[[-hStabChord, 0, 0], [0, 0, 0]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <Html position={[-hStabChord / 2, 0, -12]} center>
        <span style={CONTEXT_LABEL_STYLE}>Chord: {hStabChord} mm</span>
      </Html>

      <Line points={[[0, 0, 0], [0, 0, vStabHeight]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <Html position={[15, 0, vStabHeight / 2]} center>
        <span style={CONTEXT_LABEL_STYLE}>V-Height: {vStabHeight} mm</span>
      </Html>
    </group>
  );
}

// ---------------------------------------------------------------------------
// Fuselage Dimensions (fuselage selected)
// ---------------------------------------------------------------------------

function FuselageDimensions() {
  const fuselageLength = useDesignStore((s) => s.design.fuselageLength);
  const fuselageNoseLength = useDesignStore((s) => s.design.fuselageNoseLength);
  const fuselageCabinLength = useDesignStore((s) => s.design.fuselageCabinLength);
  const fuselageTailLength = useDesignStore((s) => s.design.fuselageTailLength);

  const offsetZ = 30;

  return (
    <>
      {/* Total fuselage length */}
      <Line points={[[0, 0, -offsetZ], [fuselageLength, 0, -offsetZ]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <Line points={[[0, 0, -offsetZ - 8], [0, 0, -offsetZ + 8]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Line points={[[fuselageLength, 0, -offsetZ - 8], [fuselageLength, 0, -offsetZ + 8]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Html position={[fuselageLength / 2, 0, -offsetZ - 15]} center>
        <span style={CONTEXT_LABEL_STYLE}>Total: {fuselageLength} mm</span>
      </Html>

      {/* Section markers */}
      {/* Nose section */}
      <Line points={[[0, 0, offsetZ], [fuselageNoseLength, 0, offsetZ]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Line points={[[0, 0, offsetZ - 6], [0, 0, offsetZ + 6]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Line points={[[fuselageNoseLength, 0, offsetZ - 6], [fuselageNoseLength, 0, offsetZ + 6]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Html position={[fuselageNoseLength / 2, 0, offsetZ + 12]} center>
        <span style={CONTEXT_LABEL_STYLE}>Nose: {fuselageNoseLength} mm</span>
      </Html>

      {/* Cabin section */}
      <Line
        points={[[fuselageNoseLength, 0, offsetZ], [fuselageNoseLength + fuselageCabinLength, 0, offsetZ]]}
        color={CONTEXT_LINE_COLOR}
        lineWidth={1}
      />
      <Line
        points={[
          [fuselageNoseLength + fuselageCabinLength, 0, offsetZ - 6],
          [fuselageNoseLength + fuselageCabinLength, 0, offsetZ + 6],
        ]}
        color={CONTEXT_LINE_COLOR}
        lineWidth={1}
      />
      <Html position={[fuselageNoseLength + fuselageCabinLength / 2, 0, offsetZ + 12]} center>
        <span style={CONTEXT_LABEL_STYLE}>Cabin: {fuselageCabinLength} mm</span>
      </Html>

      {/* Tail section */}
      <Line
        points={[
          [fuselageNoseLength + fuselageCabinLength, 0, offsetZ],
          [fuselageNoseLength + fuselageCabinLength + fuselageTailLength, 0, offsetZ],
        ]}
        color={CONTEXT_LINE_COLOR}
        lineWidth={1}
      />
      <Line
        points={[
          [fuselageNoseLength + fuselageCabinLength + fuselageTailLength, 0, offsetZ - 6],
          [fuselageNoseLength + fuselageCabinLength + fuselageTailLength, 0, offsetZ + 6],
        ]}
        color={CONTEXT_LINE_COLOR}
        lineWidth={1}
      />
      <Html position={[fuselageNoseLength + fuselageCabinLength + fuselageTailLength / 2, 0, offsetZ + 12]} center>
        <span style={CONTEXT_LABEL_STYLE}>Tail: {fuselageTailLength} mm</span>
      </Html>
    </>
  );
}

// ---------------------------------------------------------------------------
// Sweep Arc Helper
// ---------------------------------------------------------------------------

function SweepArc({ sweep }: { sweep: number }) {
  const wingChord = useDesignStore((s) => s.design.wingChord);
  const fuselageHalfWidth = wingChord * 0.45 / 2;
  const arcRadius = Math.min(fuselageHalfWidth + 20, 80);
  const sweepRad = (sweep * Math.PI) / 180;

  const arcPoints = useMemo(() => {
    const pts: [number, number, number][] = [];
    const segments = 16;
    for (let i = 0; i <= segments; i++) {
      const t = (i / segments) * sweepRad;
      pts.push([arcRadius * Math.sin(t), arcRadius * Math.cos(t), 0]);
    }
    return pts;
  }, [arcRadius, sweepRad]);

  const wingX = fuselageHalfWidth;

  return (
    <group position={[wingX, 0, 0]}>
      <Line points={arcPoints} color={LINE_COLOR} lineWidth={1} />
      <Html position={[arcRadius * 0.7, arcRadius * 0.7, 0]} center>
        <span style={LABEL_STYLE}>{sweep}deg</span>
      </Html>
    </group>
  );
}
