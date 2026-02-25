// ============================================================================
// CHENG — Per-Component Print Settings (collapsible section)
// Reusable in WingPanel, TailPanel, FuselagePanel
// Issue #128
// ============================================================================

import React, { useCallback, useState } from 'react';
import { useDesignStore } from '../../store/designStore';
import type {
  InfillHint,
  SupportStrategy,
} from '../../types/design';

// ---------------------------------------------------------------------------
// Option Constants
// ---------------------------------------------------------------------------

const INFILL_OPTIONS: readonly InfillHint[] = ['low', 'medium', 'high'] as const;
const SUPPORT_OPTIONS: readonly SupportStrategy[] = [
  'none',
  'minimal',
  'full',
] as const;

const INFILL_LABELS: Record<InfillHint, string> = {
  low: 'Low (10-15%)',
  medium: 'Medium (20-30%)',
  high: 'High (40-60%)',
};

const SUPPORT_LABELS: Record<SupportStrategy, string> = {
  none: 'None',
  minimal: 'Minimal',
  full: 'Full',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface PrintSettingsSectionProps {
  /** Which component these settings apply to */
  component: 'wing' | 'tail' | 'fuselage';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PrintSettingsSection({ component }: PrintSettingsSectionProps): React.JSX.Element {
  const [isOpen, setIsOpen] = useState(false);

  const settings = useDesignStore(
    (s) => s.componentPrintSettings[component],
  );
  const setSetting = useDesignStore((s) => s.setComponentPrintSetting);
  const clearSettings = useDesignStore((s) => s.clearComponentPrintSettings);

  // Global defaults from design
  const globalNozzle = useDesignStore((s) => s.design.nozzleDiameter);
  const defaultWallThickness = globalNozzle * 4; // common FDM default: 4 perimeters

  const toggle = useCallback(() => setIsOpen((v) => !v), []);

  // ── Handlers ──────────────────────────────────────────────────────

  const handleWallThicknessChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseFloat(e.target.value);
      if (!Number.isNaN(val) && val >= 0.4 && val <= 5.0) {
        setSetting(component, { wallThickness: val });
      }
    },
    [component, setSetting],
  );

  const handleInfillChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setSetting(component, { infillHint: e.target.value as InfillHint });
    },
    [component, setSetting],
  );

  const handleSupportChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setSetting(component, { supportStrategy: e.target.value as SupportStrategy });
    },
    [component, setSetting],
  );

  const handleReset = useCallback(() => {
    clearSettings(component);
  }, [component, clearSettings]);

  const hasOverrides = settings != null && Object.keys(settings).length > 0;

  return (
    <div className="mt-3">
      <div className="border-t border-zinc-700/50 mb-2" />

      {/* Collapsible header */}
      <button
        onClick={toggle}
        type="button"
        className="flex items-center justify-between w-full text-left
          focus:outline-none focus:ring-1 focus:ring-blue-500 rounded px-1 py-0.5"
        aria-expanded={isOpen}
        aria-controls={`print-settings-${component}`}
      >
        <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
          Print Settings
          {hasOverrides && (
            <span className="ml-1.5 px-1 py-0.5 text-[9px] font-medium text-blue-300
              bg-blue-900/40 border border-blue-700/40 rounded">
              custom
            </span>
          )}
        </span>
        <span className="text-xs text-zinc-500">
          {isOpen ? '\u25B2' : '\u25BC'}
        </span>
      </button>

      {/* Collapsible content */}
      {isOpen && (
        <div id={`print-settings-${component}`} className="mt-2 space-y-2">
          {/* Wall Thickness */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-0.5">
              Wall Thickness
              <span className="ml-1 text-[9px] text-zinc-500">mm</span>
            </label>
            <input
              type="number"
              min={0.4}
              max={5.0}
              step={0.1}
              value={settings?.wallThickness ?? ''}
              placeholder={defaultWallThickness.toFixed(1)}
              onChange={handleWallThicknessChange}
              className="w-full px-2 py-1 text-xs text-zinc-100 bg-zinc-800
                border border-zinc-700 rounded focus:outline-none focus:border-blue-500
                placeholder:text-zinc-600
                [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none
                [&::-webkit-inner-spin-button]:appearance-none"
            />
          </div>

          {/* Infill Hint */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-0.5">
              Infill Density
            </label>
            <select
              value={settings?.infillHint ?? ''}
              onChange={handleInfillChange}
              className="w-full px-2 py-1.5 text-xs text-zinc-100 bg-zinc-800
                border border-zinc-700 rounded cursor-pointer
                focus:outline-none focus:border-blue-500"
            >
              <option value="" disabled>
                Default (medium)
              </option>
              {INFILL_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {INFILL_LABELS[opt]}
                </option>
              ))}
            </select>
          </div>

          {/* Support Strategy */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-0.5">
              Support Strategy
            </label>
            <select
              value={settings?.supportStrategy ?? ''}
              onChange={handleSupportChange}
              className="w-full px-2 py-1.5 text-xs text-zinc-100 bg-zinc-800
                border border-zinc-700 rounded cursor-pointer
                focus:outline-none focus:border-blue-500"
            >
              <option value="" disabled>
                Default (minimal)
              </option>
              {SUPPORT_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {SUPPORT_LABELS[opt]}
                </option>
              ))}
            </select>
          </div>

          {/* Reset to defaults */}
          {hasOverrides && (
            <button
              onClick={handleReset}
              type="button"
              className="text-[10px] text-zinc-500 hover:text-zinc-300 underline
                focus:outline-none focus:ring-1 focus:ring-blue-500 rounded px-1"
            >
              Reset to global defaults
            </button>
          )}
        </div>
      )}
    </div>
  );
}
