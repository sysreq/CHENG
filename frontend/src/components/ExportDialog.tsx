// ============================================================================
// CHENG — Export Dialog: Format selection + print/export settings + preview + ZIP download
// Issues #28, #59, #119, #167, #170
// ============================================================================

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { useDesignStore } from '../store/designStore';
import { fieldHasWarning, formatWarning, groupWarningsByCategory, WARNING_COLORS } from '../lib/validation';
import { ParamSlider, ParamSelect, ParamToggle, DerivedField } from './ui';
import type { JointType, ExportPreviewPart, ExportPreviewResponse, ExportFormat } from '../types/design';

// ---------------------------------------------------------------------------
// Option Constants
// ---------------------------------------------------------------------------

const JOINT_TYPE_OPTIONS: readonly JointType[] = [
  'Tongue-and-Groove',
  'Dowel-Pin',
  'Flat-with-Alignment-Pins',
] as const;

const EXPORT_FORMATS: { value: ExportFormat; label: string; description: string }[] = [
  { value: 'stl', label: 'STL', description: 'Mesh for 3D printing (sectioned ZIP)' },
  { value: 'step', label: 'STEP', description: 'CAD solid model for further editing' },
  { value: 'dxf', label: 'DXF', description: '2D cross-section profiles' },
  { value: 'svg', label: 'SVG', description: '2D vector outlines for laser cutting' },
];

// ---------------------------------------------------------------------------
// Dialog step type
// ---------------------------------------------------------------------------

type DialogStep = 'settings' | 'preview';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ExportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Estimate the number of sectioned parts based on component dimensions
 * exceeding bed dimensions. Basic client-side heuristic.
 */
function estimatePartCount(
  wingSpan: number,
  fuselageLength: number,
  wingChord: number,
  bedX: number,
  bedY: number,
  bedZ: number,
): number {
  let parts = 0;

  // Wing: spans across Y axis (two halves), each half may be sectioned
  const halfSpan = wingSpan / 2;
  const wingSections = Math.max(1, Math.ceil(halfSpan / bedY));
  // Wing chord may exceed bed Z height (printed upright)
  const wingZSections = Math.max(1, Math.ceil(wingChord / bedZ));
  parts += wingSections * wingZSections * 2; // both wing halves

  // Fuselage: runs along X axis, height check against Z
  const fuselageHeight = wingChord * 0.45; // derived from backend formula
  const fuselageSections = Math.max(1, Math.ceil(fuselageLength / bedX));
  const fuselageZSections = Math.max(1, Math.ceil(fuselageHeight / bedZ));
  parts += fuselageSections * fuselageZSections;

  // Tail: usually fits within bed, estimate 2 pieces (h-stab + v-stab)
  parts += 2;

  return parts;
}

/** Color for a component type in the preview visualization. */
function componentColor(component: string): { fill: string; stroke: string; text: string } {
  switch (component) {
    case 'wing':
      return { fill: '#4a9eff22', stroke: '#4a9eff', text: '#4a9eff' };
    case 'fuselage':
      return { fill: '#8b8b8b22', stroke: '#8b8b8b', text: '#8b8b8b' };
    case 'h_stab':
      return { fill: '#22c55e22', stroke: '#22c55e', text: '#22c55e' };
    case 'v_stab':
      return { fill: '#a855f722', stroke: '#a855f7', text: '#a855f7' };
    case 'v_tail':
      return { fill: '#f59e0b22', stroke: '#f59e0b', text: '#f59e0b' };
    default:
      return { fill: '#6b728022', stroke: '#6b7280', text: '#6b7280' };
  }
}

/** Human-readable label for a component name. */
function componentLabel(component: string): string {
  switch (component) {
    case 'wing': return 'Wing';
    case 'fuselage': return 'Fuselage';
    case 'h_stab': return 'H-Stab';
    case 'v_stab': return 'V-Stab';
    case 'v_tail': return 'V-Tail';
    default: return component;
  }
}

/** Whether a format supports STL-style sectioning and preview. */
function formatSupportsSectioning(format: ExportFormat): boolean {
  return format === 'stl';
}

// ---------------------------------------------------------------------------
// Format Selector — radio group at top of dialog
// ---------------------------------------------------------------------------

function FormatSelector({
  value,
  onChange,
}: {
  value: ExportFormat;
  onChange: (format: ExportFormat) => void;
}) {
  return (
    <div className="mb-4">
      <h4 className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">
        Export Format
      </h4>
      <div className="grid grid-cols-4 gap-1.5" role="radiogroup" aria-label="Export format">
        {EXPORT_FORMATS.map((fmt) => (
          <button
            key={fmt.value}
            role="radio"
            aria-checked={value === fmt.value}
            onClick={() => onChange(fmt.value)}
            className={`px-2 py-2 text-center rounded border transition-colors
              focus:outline-none focus:ring-1 focus:ring-blue-500
              ${value === fmt.value
                ? 'bg-blue-600/30 border-blue-500 text-blue-200'
                : 'bg-zinc-800/50 border-zinc-700/50 text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-300'
              }`}
          >
            <div className="text-xs font-semibold">{fmt.label}</div>
            <div className="text-[9px] mt-0.5 leading-tight opacity-75">{fmt.description}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bed Visualization — simple 2D SVG schematic (settings step)
// ---------------------------------------------------------------------------

function BedVisualization({
  bedX,
  bedY,
  wingSpan,
  fuselageLength,
  wingChord,
}: {
  bedX: number;
  bedY: number;
  wingSpan: number;
  fuselageLength: number;
  wingChord: number;
}) {
  const svgW = 440;
  const svgH = 120;
  const pad = 8;

  // Scale to fit the bed in the SVG
  const maxDim = Math.max(bedX, bedY);
  const scale = Math.min((svgW - pad * 2) / maxDim, (svgH - pad * 2) / maxDim);
  const bw = bedX * scale;
  const bh = bedY * scale;
  const ox = (svgW - bw) / 2;
  const oy = (svgH - bh) / 2;

  // Compute section sizes (clamped to bed)
  const halfSpan = wingSpan / 2;
  const wingSections = Math.max(1, Math.ceil(halfSpan / bedY));
  const wingSecLen = Math.min(halfSpan / wingSections, bedY) * scale;
  const wingSecW = Math.min(wingChord, bedX) * scale;

  const fuseSections = Math.max(1, Math.ceil(fuselageLength / bedX));
  const fuseSecLen = Math.min(fuselageLength / fuseSections, bedX) * scale;
  const fuseSecW = Math.min(wingChord * 0.35, bedY) * scale;

  return (
    <div className="mb-3">
      <p className="text-[10px] text-zinc-500 mb-1">Bed Layout (schematic)</p>
      <svg
        width={svgW}
        height={svgH}
        className="bg-zinc-800/50 border border-zinc-700/50 rounded"
      >
        {/* Bed outline */}
        <rect
          x={ox}
          y={oy}
          width={bw}
          height={bh}
          fill="none"
          stroke="#555"
          strokeWidth={1}
          strokeDasharray="4 2"
        />
        <text x={ox + bw / 2} y={oy - 2} textAnchor="middle" fontSize={9} fill="#888">
          {bedX} x {bedY} mm
        </text>

        {/* Wing section example (blue) */}
        <rect
          x={ox + 4}
          y={oy + 4}
          width={Math.min(wingSecW, bw - 8)}
          height={Math.min(wingSecLen, bh - 8)}
          fill="#4a9eff33"
          stroke="#4a9eff"
          strokeWidth={1}
          rx={2}
        />
        <text
          x={ox + 4 + Math.min(wingSecW, bw - 8) / 2}
          y={oy + 4 + Math.min(wingSecLen, bh - 8) / 2 + 3}
          textAnchor="middle"
          fontSize={8}
          fill="#4a9eff"
        >
          Wing ({wingSections}x2)
        </text>

        {/* Fuselage section example (gray) */}
        <rect
          x={ox + Math.min(wingSecW, bw - 8) + 12}
          y={oy + 4}
          width={Math.min(fuseSecLen, bw - Math.min(wingSecW, bw - 8) - 20)}
          height={Math.min(fuseSecW, bh - 8)}
          fill="#8b8b8b33"
          stroke="#8b8b8b"
          strokeWidth={1}
          rx={2}
        />
        <text
          x={ox + Math.min(wingSecW, bw - 8) + 12 + Math.min(fuseSecLen, bw - Math.min(wingSecW, bw - 8) - 20) / 2}
          y={oy + 4 + Math.min(fuseSecW, bh - 8) / 2 + 3}
          textAnchor="middle"
          fontSize={8}
          fill="#8b8b8b"
        >
          Fuse ({fuseSections})
        </text>
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Part Bed Footprint — SVG showing a single part on the bed
// ---------------------------------------------------------------------------

function PartBedFootprint({
  part,
  bedX,
  bedY,
}: {
  part: ExportPreviewPart;
  bedX: number;
  bedY: number;
}) {
  const svgW = 120;
  const svgH = 80;
  const pad = 6;

  const [dx, dy] = part.dimensionsMm;
  const maxDim = Math.max(bedX, bedY, dx, dy);
  const scale = Math.min((svgW - pad * 2) / maxDim, (svgH - pad * 2) / maxDim);

  const bw = bedX * scale;
  const bh = bedY * scale;
  const ox = (svgW - bw) / 2;
  const oy = (svgH - bh) / 2;

  const pw = dx * scale;
  const ph = dy * scale;

  const colors = componentColor(part.component);

  return (
    <svg width={svgW} height={svgH} className="shrink-0">
      {/* Bed outline */}
      <rect
        x={ox}
        y={oy}
        width={bw}
        height={bh}
        fill="none"
        stroke="#555"
        strokeWidth={0.5}
        strokeDasharray="3 1.5"
      />
      {/* Part footprint */}
      <rect
        x={ox + 2}
        y={oy + 2}
        width={Math.min(pw, bw + 10)}
        height={Math.min(ph, bh + 10)}
        fill={part.fitsBed ? colors.fill : '#ef444422'}
        stroke={part.fitsBed ? colors.stroke : '#ef4444'}
        strokeWidth={1}
        rx={1}
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Export Preview Panel — shows all sectioned parts
// ---------------------------------------------------------------------------

function ExportPreviewPanel({
  preview,
  onBack,
  onExport,
  isExporting,
}: {
  preview: ExportPreviewResponse;
  onBack: () => void;
  onExport: () => void;
  isExporting: boolean;
}) {
  const [bedX, bedY] = preview.bedDimensionsMm;

  return (
    <div>
      {/* Summary */}
      <div className="mb-3 flex items-center gap-3">
        <div className="px-2 py-1.5 text-xs text-zinc-300 bg-zinc-800/50
          border border-zinc-700/50 rounded flex-1">
          Total Parts: <span className="font-medium text-zinc-100">{preview.totalParts}</span>
        </div>
        <div className="px-2 py-1.5 text-xs text-green-300 bg-green-900/30
          border border-green-700/40 rounded flex-1">
          Fit: <span className="font-medium text-green-100">{preview.partsThatFit}</span>
        </div>
        {preview.partsThatExceed > 0 && (
          <div className="px-2 py-1.5 text-xs text-red-300 bg-red-900/30
            border border-red-700/40 rounded flex-1">
            Oversize: <span className="font-medium text-red-100">{preview.partsThatExceed}</span>
          </div>
        )}
      </div>

      {/* Bed dimensions reminder */}
      <p className="text-[10px] text-zinc-500 mb-2">
        Print bed: {bedX} x {bedY} mm
      </p>

      {/* Parts grid */}
      <div className="max-h-[45vh] overflow-y-auto space-y-1.5 pr-1">
        {preview.parts.map((part) => {
          const [dx, dy, dz] = part.dimensionsMm;
          const colors = componentColor(part.component);

          return (
            <div
              key={part.filename}
              className={`flex items-center gap-3 px-2.5 py-2 rounded border text-xs ${
                part.fitsBed
                  ? 'bg-zinc-800/40 border-zinc-700/50'
                  : 'bg-red-900/20 border-red-700/40'
              }`}
            >
              {/* Mini bed footprint */}
              <PartBedFootprint part={part} bedX={bedX} bedY={bedY} />

              {/* Part info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: colors.stroke }}
                  />
                  <span className="font-medium text-zinc-200 truncate">
                    {componentLabel(part.component)}
                    {part.side !== 'center' ? ` (${part.side})` : ''}
                  </span>
                  <span className="text-zinc-500">
                    {part.sectionNum}/{part.totalSections}
                  </span>
                </div>
                <div className="text-zinc-400">
                  {dx.toFixed(1)} x {dy.toFixed(1)} x {dz.toFixed(1)} mm
                </div>
                <div className="text-zinc-500 text-[10px]">
                  {part.printOrientation} &middot; #{part.assemblyOrder}
                </div>
              </div>

              {/* Fit badge */}
              <div className="shrink-0">
                {part.fitsBed ? (
                  <span className="px-1.5 py-0.5 text-[10px] font-medium text-green-200
                    bg-green-800/40 border border-green-700/40 rounded">
                    Fits
                  </span>
                ) : (
                  <span className="px-1.5 py-0.5 text-[10px] font-medium text-red-200
                    bg-red-800/40 border border-red-700/40 rounded">
                    Oversize
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Warning if oversized parts */}
      {preview.partsThatExceed > 0 && (
        <div className="mt-3 px-3 py-2 text-xs text-amber-200 bg-amber-900/30
          border border-amber-700/40 rounded">
          {preview.partsThatExceed} part{preview.partsThatExceed > 1 ? 's' : ''} exceed
          the print bed. The auto-sectioner could not split them further.
          Export will proceed but these parts may not print correctly.
        </div>
      )}

      {/* Navigation buttons */}
      <div className="flex items-center justify-between mt-4 pt-3 border-t border-zinc-700/50">
        <button
          onClick={onBack}
          disabled={isExporting}
          className="px-4 py-1.5 text-xs text-zinc-300 bg-zinc-800 border
            border-zinc-700 rounded hover:bg-zinc-700
            focus:outline-none focus:ring-1 focus:ring-zinc-600
            disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Back to Settings
        </button>

        <button
          onClick={onExport}
          disabled={isExporting}
          className="px-4 py-1.5 text-xs font-medium text-zinc-100 bg-blue-600
            rounded hover:bg-blue-500 focus:outline-none focus:ring-2
            focus:ring-blue-400 focus:ring-offset-1 focus:ring-offset-zinc-900
            disabled:opacity-50 disabled:cursor-not-allowed
            inline-flex items-center gap-1.5"
        >
          {isExporting ? (
            <>
              <span className="generating-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
              Exporting...
            </>
          ) : (
            'Download ZIP'
          )}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TestJointDiagram — schematic SVG of plug + socket
// ---------------------------------------------------------------------------

function TestJointDiagram({
  jointType,
  tolerance,
  overlap,
}: {
  jointType: JointType;
  tolerance: number;
  overlap: number;
}): React.JSX.Element {
  // Simple SVG: two rectangles representing the plug and socket with joint interface
  const svgW = 240;
  const svgH = 80;
  const blockW = 90;
  const blockH = 50;
  const ox = (svgW - blockW * 2 - 20) / 2;
  const oy = (svgH - blockH) / 2;

  return (
    <svg
      width={svgW}
      height={svgH}
      className="w-full bg-zinc-800/50 border border-zinc-700/50 rounded"
    >
      {/* Part A (plug) */}
      <rect x={ox} y={oy} width={blockW} height={blockH}
        fill="#4a9eff22" stroke="#4a9eff" strokeWidth={1} rx={2} />
      <text x={ox + blockW / 2} y={oy + blockH / 2 + 4}
        textAnchor="middle" fontSize={9} fill="#4a9eff">Plug</text>

      {/* Part B (socket) */}
      <rect x={ox + blockW + 20} y={oy} width={blockW} height={blockH}
        fill="#22c55e22" stroke="#22c55e" strokeWidth={1} rx={2} />
      <text x={ox + blockW + 20 + blockW / 2} y={oy + blockH / 2 + 4}
        textAnchor="middle" fontSize={9} fill="#22c55e">Socket</text>

      {/* Joint interface visualization */}
      {jointType === 'Tongue-and-Groove' && (
        <>
          {/* Tongue protruding from plug into the gap */}
          <rect
            x={ox + blockW - 1}
            y={oy + blockH * 0.3}
            width={22}
            height={blockH * 0.4}
            fill="#f59e0b44"
            stroke="#f59e0b"
            strokeWidth={1}
          />
        </>
      )}
      {jointType === 'Dowel-Pin' && (
        <>
          <circle cx={ox + blockW + 10} cy={oy + blockH * 0.35} r={3} fill="#f59e0b" />
          <circle cx={ox + blockW + 10} cy={oy + blockH * 0.65} r={3} fill="#f59e0b" />
        </>
      )}
      {jointType === 'Flat-with-Alignment-Pins' && (
        <>
          <line
            x1={ox + blockW} y1={oy} x2={ox + blockW + 20} y2={oy + blockH}
            stroke="#555" strokeWidth={1} strokeDasharray="3 2" />
          <circle cx={ox + blockW + 10} cy={oy + blockH * 0.5} r={3} fill="#f59e0b" />
        </>
      )}

      {/* Dimension annotation: overlap */}
      <line
        x1={ox + blockW - Math.min(overlap * 0.3, 15)}
        y1={oy + blockH + 8}
        x2={ox + blockW + 20 + Math.min(overlap * 0.3, 15)}
        y2={oy + blockH + 8}
        stroke="#888" strokeWidth={0.5} />
      <text
        x={ox + blockW + 10}
        y={oy + blockH + 17}
        textAnchor="middle"
        fontSize={8}
        fill="#888">
        {overlap}mm overlap ±{tolerance.toFixed(2)}mm
      </text>
    </svg>
  );
}


// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ExportDialog({ open, onOpenChange }: ExportDialogProps): React.JSX.Element {
  const design = useDesignStore((s) => s.design);
  const warnings = useDesignStore((s) => s.warnings);
  const setParam = useDesignStore((s) => s.setParam);

  const [step, setStep] = useState<DialogStep>('settings');
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('stl');
  const [isExporting, setIsExporting] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportSuccess, setExportSuccess] = useState(false);
  const [previewData, setPreviewData] = useState<ExportPreviewResponse | null>(null);

  // Test Joint (#146) state
  const [isExportingTestJoint, setIsExportingTestJoint] = useState(false);
  const [testJointError, setTestJointError] = useState<string | null>(null);
  const [testJointSuccess, setTestJointSuccess] = useState(false);

  const { structural, print } = groupWarningsByCategory(warnings);

  // Whether the selected format supports sectioning/preview
  const hasSectioning = formatSupportsSectioning(selectedFormat);

  // PR08: Min feature thickness = 2 x nozzle diameter (read-only derived)
  const minFeatureThickness = design.nozzleDiameter * 2;

  // Estimated parts count
  const estimatedParts = useMemo(
    () => estimatePartCount(design.wingSpan, design.fuselageLength, design.wingChord, design.printBedX, design.printBedY, design.printBedZ),
    [design.wingSpan, design.fuselageLength, design.wingChord, design.printBedX, design.printBedY, design.printBedZ],
  );

  // Dynamic dialog title based on format and step
  const dialogTitle = useMemo(() => {
    const formatLabel = EXPORT_FORMATS.find((f) => f.value === selectedFormat)?.label ?? 'Export';
    if (step === 'preview') return `Export Preview (${formatLabel})`;
    return `Export ${formatLabel}`;
  }, [selectedFormat, step]);

  const dialogDescription = useMemo(() => {
    if (step === 'preview') {
      return 'Review sectioned parts and their print bed fit before downloading.';
    }
    if (hasSectioning) {
      return 'Configure print bed and sectioning settings before exporting.';
    }
    return `Export your design as ${selectedFormat.toUpperCase()} format.`;
  }, [step, hasSectioning, selectedFormat]);

  // Reset state when dialog opens/closes
  useEffect(() => {
    if (!open) {
      setStep('settings');
      setPreviewData(null);
      setExportError(null);
      setExportSuccess(false);
      setTestJointError(null);
      setTestJointSuccess(false);
    }
  }, [open]);

  // ── Number input handlers ──────────────────────────────────────────

  const setBedXSlider = useCallback(
    (v: number) => setParam('printBedX', v, 'slider'),
    [setParam],
  );
  const setBedXInput = useCallback(
    (v: number) => setParam('printBedX', v, 'text'),
    [setParam],
  );

  const setBedYSlider = useCallback(
    (v: number) => setParam('printBedY', v, 'slider'),
    [setParam],
  );
  const setBedYInput = useCallback(
    (v: number) => setParam('printBedY', v, 'text'),
    [setParam],
  );

  const setBedZSlider = useCallback(
    (v: number) => setParam('printBedZ', v, 'slider'),
    [setParam],
  );
  const setBedZInput = useCallback(
    (v: number) => setParam('printBedZ', v, 'text'),
    [setParam],
  );

  const setAutoSection = useCallback(
    (v: boolean) => setParam('autoSection', v, 'immediate'),
    [setParam],
  );

  const setOverlapSlider = useCallback(
    (v: number) => setParam('sectionOverlap', v, 'slider'),
    [setParam],
  );
  const setOverlapInput = useCallback(
    (v: number) => setParam('sectionOverlap', v, 'text'),
    [setParam],
  );

  const setJointType = useCallback(
    (v: JointType) => setParam('jointType', v, 'immediate'),
    [setParam],
  );

  const setToleranceSlider = useCallback(
    (v: number) => setParam('jointTolerance', v, 'slider'),
    [setParam],
  );
  const setToleranceInput = useCallback(
    (v: number) => setParam('jointTolerance', v, 'text'),
    [setParam],
  );

  const setNozzleSlider = useCallback(
    (v: number) => setParam('nozzleDiameter', v, 'slider'),
    [setParam],
  );
  const setNozzleInput = useCallback(
    (v: number) => setParam('nozzleDiameter', v, 'text'),
    [setParam],
  );

  const setHollowParts = useCallback(
    (v: boolean) => setParam('hollowParts', v, 'immediate'),
    [setParam],
  );

  const setTeMinSlider = useCallback(
    (v: number) => setParam('teMinThickness', v, 'slider'),
    [setParam],
  );
  const setTeMinInput = useCallback(
    (v: number) => setParam('teMinThickness', v, 'text'),
    [setParam],
  );

  // ── Preview handler ─────────────────────────────────────────────────

  const handlePreview = useCallback(async () => {
    setIsPreviewing(true);
    setExportError(null);

    try {
      const res = await fetch('/api/export/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ design, format: selectedFormat }),
      });

      if (!res.ok) {
        const detail = await res.text().catch(() => '');
        throw new Error(detail || `Preview failed (${res.status})`);
      }

      const data = (await res.json()) as ExportPreviewResponse;
      setPreviewData(data);
      setStep('preview');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Preview failed';
      setExportError(msg);
    } finally {
      setIsPreviewing(false);
    }
  }, [design, selectedFormat]);

  // ── Export handler ────────────────────────────────────────────────────

  // #170: No auto-close — user must click Done
  const handleDone = useCallback(() => {
    setExportSuccess(false);
    onOpenChange(false);
  }, [onOpenChange]);

  const handleExport = useCallback(async () => {
    setIsExporting(true);
    setExportError(null);

    try {
      const res = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ design, format: selectedFormat }),
      });

      if (!res.ok) {
        const detail = await res.text().catch(() => '');
        throw new Error(detail || `Export failed (${res.status})`);
      }

      // Stream the ZIP as a blob and trigger download
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = selectedFormat === 'stl' ? '' : `_${selectedFormat}`;
      a.download = `${design.name.replace(/\s+/g, '_')}${ext}_export.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setExportSuccess(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Export failed';
      setExportError(msg);
    } finally {
      setIsExporting(false);
    }
  }, [design, selectedFormat]);

  // ── Test Joint Export handler (#146) ─────────────────────────────────────

  const handleTestJointExport = useCallback(async () => {
    setIsExportingTestJoint(true);
    setTestJointError(null);
    setTestJointSuccess(false);

    try {
      const res = await fetch('/api/export/test-joint', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jointType: design.jointType,
          jointTolerance: design.jointTolerance,
          sectionOverlap: design.sectionOverlap,
          nozzleDiameter: design.nozzleDiameter,
        }),
      });

      if (!res.ok) {
        const detail = await res.text().catch(() => '');
        throw new Error(detail || `Test joint export failed (${res.status})`);
      }

      // Trigger blob download
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'test_joint.zip';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setTestJointSuccess(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Test joint export failed';
      setTestJointError(msg);
    } finally {
      setIsExportingTestJoint(false);
    }
  }, [design.jointType, design.jointTolerance, design.sectionOverlap, design.nozzleDiameter]);

  const handleBack = useCallback(() => {
    setStep('settings');
    setExportError(null);
  }, []);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-40" />
        <Dialog.Content
          className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
            w-[520px] max-h-[85vh] overflow-y-auto bg-zinc-900 border border-zinc-700
            rounded-lg shadow-2xl z-50 p-6"
        >
          <Dialog.Title className="text-sm font-semibold text-zinc-100 mb-1">
            {dialogTitle}
          </Dialog.Title>
          <Dialog.Description className="text-xs text-zinc-500 mb-4">
            {dialogDescription}
          </Dialog.Description>

          {/* ── STEP: PREVIEW ─────────────────────────────────────────── */}
          {step === 'preview' && previewData && (
            <>
              <ExportPreviewPanel
                preview={previewData}
                onBack={handleBack}
                onExport={handleExport}
                isExporting={isExporting}
              />

              {/* Export success */}
              {exportSuccess && (
                <div className="mt-3 px-3 py-2 text-xs text-green-200 bg-green-900/40
                  border border-green-700/50 rounded flex items-center justify-between">
                  <span>Export complete! Download started.</span>
                  <button
                    onClick={handleDone}
                    className="ml-3 px-3 py-1 text-xs font-medium text-zinc-100 bg-zinc-700
                      rounded hover:bg-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-500"
                  >
                    Done
                  </button>
                </div>
              )}

              {/* Export error */}
              {exportError && (
                <div className="mt-3 px-3 py-2 text-xs text-red-200 bg-red-900/40
                  border border-red-700/50 rounded">
                  {exportError}
                </div>
              )}
            </>
          )}

          {/* ── STEP: SETTINGS ────────────────────────────────────────── */}
          {step === 'settings' && (
            <>
              {/* ── Format Selector (#167) ────────────────────────────── */}
              <FormatSelector value={selectedFormat} onChange={setSelectedFormat} />

              {/* ── STL-only: Print Bed + Sectioning + Print Settings ── */}
              {hasSectioning && (
                <>
                  {/* ── Print Bed ────────────────────────────────────────── */}
                  <h4 className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                    Print Bed Size
                  </h4>

                  <div className="grid grid-cols-3 gap-3 mb-3">
                    <div>
                      <ParamSlider
                        label="Bed X"
                        unit="mm"
                        value={design.printBedX}
                        min={100}
                        max={500}
                        step={10}
                        onSliderChange={setBedXSlider}
                        onInputChange={setBedXInput}
                        hasWarning={fieldHasWarning(warnings, 'printBedX')}
                      />
                    </div>
                    <div>
                      <ParamSlider
                        label="Bed Y"
                        unit="mm"
                        value={design.printBedY}
                        min={100}
                        max={500}
                        step={10}
                        onSliderChange={setBedYSlider}
                        onInputChange={setBedYInput}
                        hasWarning={fieldHasWarning(warnings, 'printBedY')}
                      />
                    </div>
                    <div>
                      <ParamSlider
                        label="Bed Z"
                        unit="mm"
                        value={design.printBedZ}
                        min={50}
                        max={500}
                        step={10}
                        onSliderChange={setBedZSlider}
                        onInputChange={setBedZInput}
                        hasWarning={fieldHasWarning(warnings, 'printBedZ')}
                      />
                    </div>
                  </div>

                  {/* Estimated parts */}
                  <div className="mb-3 px-2 py-1.5 text-xs text-zinc-300 bg-zinc-800/50
                    border border-zinc-700/50 rounded cursor-default">
                    Estimated Parts: {estimatedParts} pieces
                  </div>

                  {/* Bed visualization */}
                  <BedVisualization
                    bedX={design.printBedX}
                    bedY={design.printBedY}
                    wingSpan={design.wingSpan}
                    fuselageLength={design.fuselageLength}
                    wingChord={design.wingChord}
                  />

                  {/* ── Sectioning ───────────────────────────────────────── */}
                  <div className="border-t border-zinc-700/50 my-3" />
                  <h4 className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                    Sectioning
                  </h4>

                  <ParamToggle
                    label="Auto-Section Parts"
                    checked={design.autoSection}
                    onChange={setAutoSection}
                    hasWarning={fieldHasWarning(warnings, 'autoSection')}
                  />

                  <ParamSlider
                    label="Section Overlap"
                    unit="mm"
                    value={design.sectionOverlap}
                    min={5}
                    max={30}
                    step={1}
                    onSliderChange={setOverlapSlider}
                    onInputChange={setOverlapInput}
                    hasWarning={fieldHasWarning(warnings, 'sectionOverlap')}
                  />

                  <ParamSelect
                    label="Joint Type"
                    value={design.jointType}
                    options={JOINT_TYPE_OPTIONS}
                    onChange={setJointType}
                    hasWarning={fieldHasWarning(warnings, 'jointType')}
                  />

                  <ParamSlider
                    label="Joint Tolerance"
                    unit="mm"
                    value={design.jointTolerance}
                    min={0.05}
                    max={0.5}
                    step={0.01}
                    onSliderChange={setToleranceSlider}
                    onInputChange={setToleranceInput}
                    hasWarning={fieldHasWarning(warnings, 'jointTolerance')}
                  />

                  {/* ── Test Joint (#146) ─────────────────────────────────── */}
                  <div className="mt-3 mb-3 p-3 bg-zinc-800/40 border border-zinc-700/50 rounded-lg">
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="flex-1">
                        <p className="text-xs font-semibold text-zinc-200 mb-0.5">
                          Print Test Joint
                        </p>
                        <p className="text-[10px] text-zinc-400 leading-relaxed">
                          Print this small test piece to verify your joint tolerance fits before
                          printing the full plane. Takes ~15–30 min on a typical FDM printer.
                        </p>
                      </div>
                    </div>

                    {/* Current joint settings summary */}
                    <div className="grid grid-cols-3 gap-1.5 mb-3">
                      <div className="px-2 py-1 text-[10px] text-zinc-300 bg-zinc-800 border border-zinc-700/50 rounded text-center">
                        <div className="text-zinc-500 mb-0.5">Type</div>
                        {design.jointType.split('-')[0]}
                      </div>
                      <div className="px-2 py-1 text-[10px] text-zinc-300 bg-zinc-800 border border-zinc-700/50 rounded text-center">
                        <div className="text-zinc-500 mb-0.5">Tolerance</div>
                        ±{design.jointTolerance.toFixed(2)} mm
                      </div>
                      <div className="px-2 py-1 text-[10px] text-zinc-300 bg-zinc-800 border border-zinc-700/50 rounded text-center">
                        <div className="text-zinc-500 mb-0.5">Overlap</div>
                        {design.sectionOverlap} mm
                      </div>
                    </div>

                    {/* Schematic diagram */}
                    <TestJointDiagram
                      jointType={design.jointType}
                      tolerance={design.jointTolerance}
                      overlap={design.sectionOverlap}
                    />

                    {/* Download button */}
                    <button
                      onClick={handleTestJointExport}
                      disabled={isExportingTestJoint}
                      className="w-full mt-3 px-4 py-2 text-xs font-medium text-zinc-100
                        bg-emerald-700 hover:bg-emerald-600 rounded
                        focus:outline-none focus:ring-2 focus:ring-emerald-400
                        disabled:opacity-50 disabled:cursor-not-allowed
                        inline-flex items-center justify-center gap-1.5
                        transition-colors"
                    >
                      {isExportingTestJoint ? (
                        <>
                          <span className="generating-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                          Generating Test Joint...
                        </>
                      ) : (
                        'Download Test Joint (ZIP)'
                      )}
                    </button>

                    {testJointSuccess && (
                      <p className="mt-2 text-[10px] text-emerald-300 text-center">
                        Downloaded. Print and check the fit before exporting the full plane.
                      </p>
                    )}
                    {testJointError && (
                      <p className="mt-2 text-[10px] text-red-400">{testJointError}</p>
                    )}
                  </div>

                  {/* ── Print Settings ───────────────────────────────────── */}
                  <div className="border-t border-zinc-700/50 my-3" />
                  <h4 className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                    Print Settings
                  </h4>

                  <ParamSlider
                    label="Nozzle Diameter"
                    unit="mm"
                    value={design.nozzleDiameter}
                    min={0.2}
                    max={1.0}
                    step={0.05}
                    onSliderChange={setNozzleSlider}
                    onInputChange={setNozzleInput}
                    hasWarning={fieldHasWarning(warnings, 'nozzleDiameter')}
                  />

                  {/* PR08 — Min Feature Thickness (read-only derived) */}
                  <DerivedField
                    label="Min Feature Thickness"
                    value={minFeatureThickness}
                    unit="mm"
                    decimals={2}
                  />

                  <ParamToggle
                    label="Hollow Parts"
                    checked={design.hollowParts}
                    onChange={setHollowParts}
                    hasWarning={fieldHasWarning(warnings, 'hollowParts')}
                  />

                  <ParamSlider
                    label="TE Min Thickness"
                    unit="mm"
                    value={design.teMinThickness}
                    min={0.4}
                    max={2.0}
                    step={0.1}
                    onSliderChange={setTeMinSlider}
                    onInputChange={setTeMinInput}
                    hasWarning={fieldHasWarning(warnings, 'teMinThickness')}
                  />
                </>
              )}

              {/* Non-STL format info */}
              {!hasSectioning && (
                <div className="mb-3 px-3 py-2.5 text-xs text-zinc-300 bg-zinc-800/50
                  border border-zinc-700/50 rounded">
                  <p className="font-medium text-zinc-200 mb-1">
                    {selectedFormat.toUpperCase()} Export
                  </p>
                  <p className="text-zinc-400 leading-relaxed">
                    {selectedFormat === 'step' && 'Exports the full aircraft as a STEP solid model. No sectioning is applied. Useful for importing into CAD software for further editing.'}
                    {selectedFormat === 'dxf' && 'Exports 2D cross-section profiles as DXF. Useful for laser cutting templates or CNC routing.'}
                    {selectedFormat === 'svg' && 'Exports 2D vector outlines as SVG. Useful for documentation, laser cutting, or web display.'}
                  </p>
                </div>
              )}

              {/* ── Validation Warnings ──────────────────────────────────── */}
              {warnings.length > 0 && (
                <>
                  <div className="border-t border-zinc-700/50 my-3" />
                  <h4 className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                    Warnings
                    <span
                      className="ml-2 px-1.5 py-0.5 text-[9px] font-medium text-amber-100
                        bg-amber-600 rounded-full"
                    >
                      {warnings.length}
                    </span>
                  </h4>

                  {structural.length > 0 && (
                    <div className="mb-2">
                      <p className="text-[10px] font-medium text-zinc-500 mb-1">Structural</p>
                      {structural.map((w) => (
                        <div
                          key={w.id}
                          className={`px-2 py-1.5 mb-1 text-[10px] rounded border
                            ${WARNING_COLORS.warn.bg} ${WARNING_COLORS.warn.border} ${WARNING_COLORS.warn.text}`}
                        >
                          {formatWarning(w)}
                        </div>
                      ))}
                    </div>
                  )}

                  {print.length > 0 && (
                    <div className="mb-2">
                      <p className="text-[10px] font-medium text-zinc-500 mb-1">Print</p>
                      {print.map((w) => (
                        <div
                          key={w.id}
                          className={`px-2 py-1.5 mb-1 text-[10px] rounded border
                            ${WARNING_COLORS.warn.bg} ${WARNING_COLORS.warn.border} ${WARNING_COLORS.warn.text}`}
                        >
                          {formatWarning(w)}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}

              {/* ── Export Success (#170 — persistent, no auto-close) ────── */}
              {exportSuccess && (
                <div className="mt-3 px-3 py-2 text-xs text-green-200 bg-green-900/40
                  border border-green-700/50 rounded flex items-center justify-between">
                  <span>Export complete! Download started.</span>
                  <button
                    onClick={handleDone}
                    className="ml-3 px-3 py-1 text-xs font-medium text-zinc-100 bg-zinc-700
                      rounded hover:bg-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-500"
                  >
                    Done
                  </button>
                </div>
              )}

              {/* ── Export Error ───────────────────────────────────────────── */}
              {exportError && (
                <div className="mt-3 px-3 py-2 text-xs text-red-200 bg-red-900/40
                  border border-red-700/50 rounded">
                  {exportError}
                </div>
              )}

              {/* ── Action Buttons ───────────────────────────────────────── */}
              <div className="flex items-center justify-end gap-2 mt-4 pt-3 border-t border-zinc-700/50">
                <Dialog.Close asChild>
                  <button
                    disabled={isExporting || isPreviewing}
                    className="px-4 py-1.5 text-xs text-zinc-300 bg-zinc-800 border
                      border-zinc-700 rounded hover:bg-zinc-700
                      focus:outline-none focus:ring-1 focus:ring-zinc-600
                      disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {exportSuccess ? 'Close' : 'Cancel'}
                  </button>
                </Dialog.Close>

                {!exportSuccess && (
                  hasSectioning ? (
                    <button
                      onClick={handlePreview}
                      disabled={isPreviewing || isExporting}
                      className="px-4 py-1.5 text-xs font-medium text-zinc-100 bg-blue-600
                        rounded hover:bg-blue-500 focus:outline-none focus:ring-2
                        focus:ring-blue-400 focus:ring-offset-1 focus:ring-offset-zinc-900
                        disabled:opacity-50 disabled:cursor-not-allowed
                        inline-flex items-center gap-1.5"
                    >
                      {isPreviewing ? (
                        <>
                          <span className="generating-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                          Generating Preview...
                        </>
                      ) : (
                        <>
                          Export Preview
                          {warnings.length > 0 && (
                            <span className="text-[10px] text-blue-200">
                              ({warnings.length} warnings)
                            </span>
                          )}
                        </>
                      )}
                    </button>
                  ) : (
                    <button
                      onClick={handleExport}
                      disabled={isExporting}
                      className="px-4 py-1.5 text-xs font-medium text-zinc-100 bg-blue-600
                        rounded hover:bg-blue-500 focus:outline-none focus:ring-2
                        focus:ring-blue-400 focus:ring-offset-1 focus:ring-offset-zinc-900
                        disabled:opacity-50 disabled:cursor-not-allowed
                        inline-flex items-center gap-1.5"
                    >
                      {isExporting ? (
                        <>
                          <span className="generating-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                          Exporting...
                        </>
                      ) : (
                        `Download ${selectedFormat.toUpperCase()}`
                      )}
                    </button>
                  )
                )}
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
