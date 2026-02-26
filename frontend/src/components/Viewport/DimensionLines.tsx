// ============================================================================
// CHENG — 3D Dimension Annotations (inside R3F Canvas)
// Contextual: annotations change based on selectedComponent (#134)
// Direct-edit: click dimension labels to edit values inline (#135)
// ============================================================================

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { Html, Line } from '@react-three/drei';
import { useDesignStore } from '@/store/designStore';
import type { AircraftDesign } from '@/types/design';

/** Extract only numeric keys from AircraftDesign for type-safe editing. */
type NumericDesignKey = { [K in keyof AircraftDesign]: AircraftDesign[K] extends number ? K : never }[keyof AircraftDesign];

/** Parameter ranges for clamping direct-edit annotation values (#199). */
const PARAM_RANGES: Partial<Record<NumericDesignKey, { min: number; max: number }>> = {
  wingSpan: { min: 300, max: 3000 },
  wingChord: { min: 50, max: 500 },
  fuselageLength: { min: 150, max: 2000 },
  hStabSpan: { min: 100, max: 1200 },
  hStabChord: { min: 30, max: 250 },
  vStabHeight: { min: 30, max: 400 },
  vTailSpan: { min: 80, max: 600 },
  vTailChord: { min: 30, max: 200 },
  noseCabinBreakPct: { min: 10, max: 85 },
  cabinTailBreakPct: { min: 15, max: 90 },
  wingSweep: { min: -10, max: 45 },
};

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

// ---------------------------------------------------------------------------
// EditableLabel — click a dimension label to inline-edit its value (#135)
// ---------------------------------------------------------------------------

interface EditableLabelProps {
  /** Display text label prefix (e.g. "Span:", "Root:") */
  label: string;
  /** Current numeric value */
  value: number;
  /** Unit suffix (e.g. "mm", "deg") */
  unit: string;
  /** Design parameter key to update on commit (must be numeric) */
  paramKey: NumericDesignKey;
  /** Whether this label uses context (yellow) styling */
  contextual?: boolean;
  /** 3D position for the Html overlay */
  position: [number, number, number];
  /** Whether the value is read-only (computed, not directly editable) */
  readOnly?: boolean;
}

function EditableLabel({
  label,
  value,
  unit,
  paramKey,
  contextual = false,
  position,
  readOnly = false,
}: EditableLabelProps) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const setParam = useDesignStore((s) => s.setParam);

  const displayText = label ? `${label} ${value} ${unit}` : `${value} ${unit}`;

  const handleClick = useCallback(() => {
    if (readOnly) return;
    setEditValue(String(value));
    setEditing(true);
  }, [readOnly, value]);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const handleCommit = useCallback(() => {
    const parsed = parseFloat(editValue);
    if (!isNaN(parsed)) {
      // Clamp to valid range if defined (#199)
      const range = PARAM_RANGES[paramKey];
      const clamped = range
        ? Math.min(range.max, Math.max(range.min, parsed))
        : parsed;
      if (clamped !== value) {
        setParam(paramKey, clamped as AircraftDesign[typeof paramKey]);
      }
    }
    setEditing(false);
  }, [editValue, value, paramKey, setParam]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        // Let blur handle the commit
        inputRef.current?.blur();
      } else if (e.key === 'Escape') {
        // Reset value before closing so blur won't commit stale edit
        setEditValue(String(value));
        setEditing(false);
      }
      // Stop propagation so keyboard shortcuts don't fire
      e.stopPropagation();
    },
    [value],
  );

  const baseStyle = contextual ? CONTEXT_LABEL_STYLE : LABEL_STYLE;

  if (editing) {
    return (
      <Html position={position} center>
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 2 }}
          onPointerDown={(e) => e.stopPropagation()}
          onPointerUp={(e) => e.stopPropagation()}
          onWheel={(e) => e.stopPropagation()}
        >
          {label && (
            <span style={{ ...baseStyle, pointerEvents: 'none' }}>{label}</span>
          )}
          <input
            ref={inputRef}
            type="number"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={handleCommit}
            aria-label={`Edit ${label || paramKey}`}
            style={{
              width: 60,
              fontSize: 10,
              fontFamily: 'monospace',
              color: '#fff',
              backgroundColor: 'rgba(30, 30, 34, 0.95)',
              border: '1px solid #FFD60A',
              borderRadius: 2,
              padding: '1px 4px',
              outline: 'none',
              textAlign: 'right',
            }}
          />
          <span style={{ ...baseStyle, pointerEvents: 'none' }}>{unit}</span>
        </div>
      </Html>
    );
  }

  return (
    <Html position={position} center>
      <span
        style={{
          ...baseStyle,
          pointerEvents: readOnly ? 'none' : 'auto',
          cursor: readOnly ? 'default' : 'pointer',
          borderBottom: readOnly ? 'none' : '1px dashed currentColor',
          paddingBottom: readOnly ? 0 : 1,
        }}
        onClick={handleClick}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') handleClick();
        }}
        role={readOnly ? undefined : 'button'}
        tabIndex={readOnly ? undefined : 0}
        title={readOnly ? undefined : `Click to edit ${paramKey}`}
      >
        {displayText}
      </span>
    </Html>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

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
      {(selectedComponent === null || selectedComponent === 'global') && <GlobalDimensions />}
      {selectedComponent === 'wing' && <WingDimensions />}
      {selectedComponent === 'tail' && <TailDimensions />}
      {selectedComponent === 'fuselage' && <FuselageDimensions />}
    </group>
  );
}

// ---------------------------------------------------------------------------
// Wing X fraction by fuselage preset — mirrors backend _WING_X_FRACTION
// ---------------------------------------------------------------------------

const WING_X_FRACTION: Record<string, number> = {
  Conventional: 0.30,
  Pod: 0.25,
  'Blended-Wing-Body': 0.35,
};

// ---------------------------------------------------------------------------
// Global Dimensions (no selection)
// ---------------------------------------------------------------------------

function GlobalDimensions() {
  const wingSpan = useDesignStore((s) => s.design.wingSpan);
  const fuselageLength = useDesignStore((s) => s.design.fuselageLength);
  const fuselagePreset = useDesignStore((s) => s.design.fuselagePreset);
  const wingSweep = useDesignStore((s) => s.design.wingSweep);

  const halfSpan = wingSpan / 2;
  // Wingspan line is drawn at the wing mount X position, not the nose.
  // Mirrors backend _WING_X_FRACTION used in engine.py / validation.py.
  const wingXFrac = WING_X_FRACTION[fuselagePreset] ?? 0.30;
  const wingX = fuselageLength * wingXFrac;
  // Fuselage length annotation runs close to the centreline with a small
  // fixed offset, regardless of wingspan.
  const spanY = 40;

  return (
    <>
      {/* Wingspan line — drawn at wing mount X position */}
      <Line points={[[wingX, -halfSpan, 0], [wingX, halfSpan, 0]]} color={LINE_COLOR} lineWidth={1} />
      <Line points={[[wingX, -halfSpan, -10], [wingX, -halfSpan, 10]]} color={LINE_COLOR} lineWidth={1} />
      <Line points={[[wingX, halfSpan, -10], [wingX, halfSpan, 10]]} color={LINE_COLOR} lineWidth={1} />
      <EditableLabel
        label=""
        value={wingSpan}
        unit="mm"
        paramKey="wingSpan"
        position={[wingX, 0, 15]}
      />

      {/* Fuselage length line — 40mm off centreline, parallel to fuselage axis */}
      <Line points={[[0, spanY, 0], [fuselageLength, spanY, 0]]} color={LINE_COLOR} lineWidth={1} />
      <Line points={[[0, spanY - 10, 0], [0, spanY + 10, 0]]} color={LINE_COLOR} lineWidth={1} />
      <Line points={[[fuselageLength, spanY - 10, 0], [fuselageLength, spanY + 10, 0]]} color={LINE_COLOR} lineWidth={1} />
      <EditableLabel
        label=""
        value={fuselageLength}
        unit="mm"
        paramKey="fuselageLength"
        position={[fuselageLength / 2, spanY + 15, 0]}
      />

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
      <EditableLabel
        label="Span:"
        value={wingSpan}
        unit="mm"
        paramKey="wingSpan"
        contextual
        position={[0, 0, 18]}
      />

      {/* Root chord at center */}
      <Line points={[[0, 0, 0], [wingChord, 0, 0]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <EditableLabel
        label="Root:"
        value={wingChord}
        unit="mm"
        paramKey="wingChord"
        contextual
        position={[wingChord / 2, 0, -15]}
      />

      {/* Tip chord at wingtip (read-only — derived from chord * ratio) */}
      <Line points={[[0, halfSpan, 0], [tipChord, halfSpan, 0]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <EditableLabel
        label="Tip:"
        value={Math.round(tipChord)}
        unit="mm"
        paramKey="wingChord"
        contextual
        readOnly
        position={[tipChord / 2, halfSpan, -15]}
      />
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
      <EditableLabel
        label="V-Span:"
        value={vTailSpan}
        unit="mm"
        paramKey="vTailSpan"
        contextual
        position={[0, 0, 15]}
      />

      <Line points={[[-vTailChord, 0, 0], [0, 0, 0]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <EditableLabel
        label="Chord:"
        value={vTailChord}
        unit="mm"
        paramKey="vTailChord"
        contextual
        position={[-vTailChord / 2, 0, -12]}
      />
    </group>
  );
}

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
      <EditableLabel
        label="H-Span:"
        value={hStabSpan}
        unit="mm"
        paramKey="hStabSpan"
        contextual
        position={[0, 0, 15]}
      />

      <Line points={[[-hStabChord, 0, 0], [0, 0, 0]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <EditableLabel
        label="Chord:"
        value={hStabChord}
        unit="mm"
        paramKey="hStabChord"
        contextual
        position={[-hStabChord / 2, 0, -12]}
      />

      <Line points={[[0, 0, 0], [0, 0, vStabHeight]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <EditableLabel
        label="V-Height:"
        value={vStabHeight}
        unit="mm"
        paramKey="vStabHeight"
        contextual
        position={[15, 0, vStabHeight / 2]}
      />
    </group>
  );
}

// ---------------------------------------------------------------------------
// Fuselage Dimensions (fuselage selected)
// ---------------------------------------------------------------------------

function FuselageDimensions() {
  const fuselageLength = useDesignStore((s) => s.design.fuselageLength);
  const noseCabinBreakPct = useDesignStore((s) => s.design.noseCabinBreakPct);
  const cabinTailBreakPct = useDesignStore((s) => s.design.cabinTailBreakPct);

  // Derive absolute section lengths from percentage breakpoints
  const noseLength = (noseCabinBreakPct / 100) * fuselageLength;
  const cabinLength = ((cabinTailBreakPct - noseCabinBreakPct) / 100) * fuselageLength;
  const tailLength = ((100 - cabinTailBreakPct) / 100) * fuselageLength;

  const offsetZ = 30;

  return (
    <>
      {/* Total fuselage length */}
      <Line points={[[0, 0, -offsetZ], [fuselageLength, 0, -offsetZ]]} color={CONTEXT_LINE_COLOR} lineWidth={1.5} />
      <Line points={[[0, 0, -offsetZ - 8], [0, 0, -offsetZ + 8]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Line points={[[fuselageLength, 0, -offsetZ - 8], [fuselageLength, 0, -offsetZ + 8]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <EditableLabel
        label="Total:"
        value={fuselageLength}
        unit="mm"
        paramKey="fuselageLength"
        contextual
        position={[fuselageLength / 2, 0, -offsetZ - 15]}
      />

      {/* Nose section — shown as mm (read-only, derived from noseCabinBreakPct) */}
      <Line points={[[0, 0, offsetZ], [noseLength, 0, offsetZ]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Line points={[[0, 0, offsetZ - 6], [0, 0, offsetZ + 6]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <Line points={[[noseLength, 0, offsetZ - 6], [noseLength, 0, offsetZ + 6]]} color={CONTEXT_LINE_COLOR} lineWidth={1} />
      <EditableLabel
        label="Nose:"
        value={noseCabinBreakPct}
        unit="%"
        paramKey="noseCabinBreakPct"
        contextual
        position={[noseLength / 2, 0, offsetZ + 12]}
      />

      {/* Cabin section */}
      <Line
        points={[[noseLength, 0, offsetZ], [noseLength + cabinLength, 0, offsetZ]]}
        color={CONTEXT_LINE_COLOR}
        lineWidth={1}
      />
      <Line
        points={[
          [noseLength + cabinLength, 0, offsetZ - 6],
          [noseLength + cabinLength, 0, offsetZ + 6],
        ]}
        color={CONTEXT_LINE_COLOR}
        lineWidth={1}
      />
      <EditableLabel
        label="Cabin:"
        value={Math.round(cabinLength)}
        unit="mm"
        paramKey="noseCabinBreakPct"
        contextual
        readOnly
        position={[noseLength + cabinLength / 2, 0, offsetZ + 12]}
      />

      {/* Tail section */}
      <Line
        points={[
          [noseLength + cabinLength, 0, offsetZ],
          [noseLength + cabinLength + tailLength, 0, offsetZ],
        ]}
        color={CONTEXT_LINE_COLOR}
        lineWidth={1}
      />
      <Line
        points={[
          [noseLength + cabinLength + tailLength, 0, offsetZ - 6],
          [noseLength + cabinLength + tailLength, 0, offsetZ + 6],
        ]}
        color={CONTEXT_LINE_COLOR}
        lineWidth={1}
      />
      <EditableLabel
        label="Tail:"
        value={cabinTailBreakPct}
        unit="%"
        paramKey="cabinTailBreakPct"
        contextual
        position={[noseLength + cabinLength + tailLength / 2, 0, offsetZ + 12]}
      />
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
      <EditableLabel
        label=""
        value={sweep}
        unit="deg"
        paramKey="wingSweep"
        position={[arcRadius * 0.7, arcRadius * 0.7, 0]}
      />
    </group>
  );
}
