// ============================================================================
// CHENG — Export Dialog: Print/export settings + validation warnings + ZIP download
// Issue #28, #59
// ============================================================================

import React, { useState, useCallback, useMemo } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { useDesignStore } from '../store/designStore';
import { fieldHasWarning, formatWarning, groupWarningsByCategory, WARNING_COLORS } from '../lib/validation';
import { ParamSlider, ParamSelect, ParamToggle, DerivedField } from './ui';
import type { JointType } from '../types/design';

// ---------------------------------------------------------------------------
// Option Constants
// ---------------------------------------------------------------------------

const JOINT_TYPE_OPTIONS: readonly JointType[] = [
  'Tongue-and-Groove',
  'Dowel-Pin',
  'Flat-with-Alignment-Pins',
] as const;

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
  bedX: number,
  bedY: number,
): number {
  let parts = 0;

  // Wing: spans across Y axis (two halves), each half may be sectioned
  const halfSpan = wingSpan / 2;
  const wingSections = Math.max(1, Math.ceil(halfSpan / bedY));
  parts += wingSections * 2; // both wing halves

  // Fuselage: runs along X axis
  const fuselageSections = Math.max(1, Math.ceil(fuselageLength / bedX));
  parts += fuselageSections;

  // Tail: usually fits within bed, estimate 2 pieces (h-stab + v-stab)
  parts += 2;

  return parts;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ExportDialog({ open, onOpenChange }: ExportDialogProps): React.JSX.Element {
  const design = useDesignStore((s) => s.design);
  const warnings = useDesignStore((s) => s.warnings);
  const setParam = useDesignStore((s) => s.setParam);

  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const { structural, print } = groupWarningsByCategory(warnings);

  // PR08: Min feature thickness = 2 x nozzle diameter (read-only derived)
  const minFeatureThickness = design.nozzleDiameter * 2;

  // Estimated parts count
  const estimatedParts = useMemo(
    () => estimatePartCount(design.wingSpan, design.fuselageLength, design.printBedX, design.printBedY),
    [design.wingSpan, design.fuselageLength, design.printBedX, design.printBedY],
  );

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

  // ── Export handler ────────────────────────────────────────────────────

  const handleExport = useCallback(async () => {
    setIsExporting(true);
    setExportError(null);

    try {
      const res = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ design, format: 'stl' }),
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
      a.download = `${design.name.replace(/\s+/g, '_')}_export.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      onOpenChange(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Export failed';
      setExportError(msg);
    } finally {
      setIsExporting(false);
    }
  }, [design, onOpenChange]);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-40" />
        <Dialog.Content
          className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
            w-[480px] max-h-[85vh] overflow-y-auto bg-zinc-900 border border-zinc-700
            rounded-lg shadow-2xl z-50 p-6"
        >
          <Dialog.Title className="text-sm font-semibold text-zinc-100 mb-1">
            Export STL
          </Dialog.Title>
          <Dialog.Description className="text-xs text-zinc-500 mb-4">
            Configure print bed and sectioning settings before exporting.
          </Dialog.Description>

          {/* ── Print Bed ────────────────────────────────────────────── */}
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

          {/* ── Sectioning ───────────────────────────────────────────── */}
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

          {/* ── Print Settings ───────────────────────────────────────── */}
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
                disabled={isExporting}
                className="px-4 py-1.5 text-xs text-zinc-300 bg-zinc-800 border
                  border-zinc-700 rounded hover:bg-zinc-700
                  focus:outline-none focus:ring-1 focus:ring-zinc-600
                  disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Cancel
              </button>
            </Dialog.Close>

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
                <>
                  Export ZIP
                  {warnings.length > 0 && (
                    <span className="text-[10px] text-blue-200">
                      ({warnings.length} warnings)
                    </span>
                  )}
                </>
              )}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
