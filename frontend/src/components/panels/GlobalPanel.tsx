// ============================================================================
// CHENG — Global Panel: Core aircraft parameters + preset selector
// Issue #25
// ============================================================================

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import * as AlertDialog from '@radix-ui/react-alert-dialog';
import { useDesignStore } from '../../store/designStore';
import { PRESET_DESCRIPTIONS } from '../../lib/presets';
import { fieldHasWarning, getFieldWarnings, formatWarning } from '../../lib/validation';
import {
  listCustomPresets,
  loadCustomPreset,
  saveCustomPreset,
  deleteCustomPreset,
} from '../../lib/presetApi';
import { ParamSlider, ParamSelect, BidirectionalParam } from '../ui';
import type {
  PresetName,
  FuselagePreset,
  MotorConfig,
  WingMountType,
  TailType,
  CustomPresetSummary,
} from '../../types/design';

// ---------------------------------------------------------------------------
// Option Constants
// ---------------------------------------------------------------------------

const PRESET_OPTIONS: readonly (Exclude<PresetName, 'Custom'>)[] = [
  'Trainer',
  'Sport',
  'Aerobatic',
  'Glider',
  'FlyingWing',
  'Scale',
] as const;

/** Display labels for preset names — handles multi-word names like FlyingWing (#197). */
const PRESET_DISPLAY_LABELS: Record<Exclude<PresetName, 'Custom'>, string> = {
  Trainer: 'Trainer',
  Sport: 'Sport',
  Aerobatic: 'Aerobatic',
  Glider: 'Glider',
  FlyingWing: 'Flying Wing',
  Scale: 'Scale',
};

const FUSELAGE_PRESET_OPTIONS: readonly FuselagePreset[] = [
  'Pod',
  'Conventional',
  'Blended-Wing-Body',
] as const;

const MOTOR_CONFIG_OPTIONS: readonly MotorConfig[] = [
  'Tractor',
  'Pusher',
] as const;

const WING_MOUNT_OPTIONS: readonly WingMountType[] = [
  'High-Wing',
  'Mid-Wing',
  'Low-Wing',
  'Shoulder-Wing',
] as const;

const TAIL_TYPE_OPTIONS: readonly TailType[] = [
  'Conventional',
  'T-Tail',
  'V-Tail',
  'Cruciform',
] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GlobalPanel(): React.JSX.Element {
  const design = useDesignStore((s) => s.design);
  const activePreset = useDesignStore((s) => s.activePreset);
  const warnings = useDesignStore((s) => s.warnings);
  const setParam = useDesignStore((s) => s.setParam);
  const loadPreset = useDesignStore((s) => s.loadPreset);
  const loadCustomPresetDesign = useDesignStore((s) => s.loadCustomPresetDesign);

  // ── Preset (with confirmation dialog) ──────────────────────────────

  const [pendingPreset, setPendingPreset] = useState<Exclude<PresetName, 'Custom'> | null>(null);

  const handlePresetChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const value = e.target.value as PresetName;
      if (value !== 'Custom') {
        setPendingPreset(value as Exclude<PresetName, 'Custom'>);
      }
    },
    [],
  );

  const confirmPreset = useCallback(() => {
    if (pendingPreset) {
      loadPreset(pendingPreset);
      setPendingPreset(null);
    }
  }, [pendingPreset, loadPreset]);

  const cancelPreset = useCallback(() => {
    setPendingPreset(null);
  }, []);

  // ── Custom Presets ──────────────────────────────────────────────────

  const [customPresets, setCustomPresets] = useState<CustomPresetSummary[]>([]);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [savePresetName, setSavePresetName] = useState('');
  const [presetError, setPresetError] = useState<string | null>(null);
  const [isSavingPreset, setIsSavingPreset] = useState(false);
  const [isLoadingPreset, setIsLoadingPreset] = useState(false);
  const [pendingDeletePreset, setPendingDeletePreset] = useState<CustomPresetSummary | null>(null);

  // Fetch custom presets on mount
  const refreshPresets = useCallback(async () => {
    try {
      const presets = await listCustomPresets();
      setCustomPresets(presets);
      setPresetError(null);
    } catch (err) {
      console.error('Failed to fetch custom presets:', err);
    }
  }, []);

  useEffect(() => {
    refreshPresets();
  }, [refreshPresets]);

  const handleSavePreset = useCallback(async () => {
    if (!savePresetName.trim()) return;
    setIsSavingPreset(true);
    setPresetError(null);
    try {
      await saveCustomPreset(savePresetName.trim(), design);
      setShowSaveDialog(false);
      setSavePresetName('');
      await refreshPresets();
    } catch (err) {
      setPresetError(err instanceof Error ? err.message : 'Failed to save preset');
    } finally {
      setIsSavingPreset(false);
    }
  }, [savePresetName, design, refreshPresets]);

  const handleLoadCustomPreset = useCallback(
    async (id: string) => {
      setIsLoadingPreset(true);
      setPresetError(null);
      try {
        const presetData = await loadCustomPreset(id);
        loadCustomPresetDesign(presetData);
      } catch (err) {
        setPresetError(err instanceof Error ? err.message : 'Failed to load preset');
      } finally {
        setIsLoadingPreset(false);
      }
    },
    [loadCustomPresetDesign],
  );

  const handleConfirmDeletePreset = useCallback(
    async () => {
      if (!pendingDeletePreset) return;
      setPresetError(null);
      try {
        await deleteCustomPreset(pendingDeletePreset.id);
        await refreshPresets();
      } catch (err) {
        setPresetError(err instanceof Error ? err.message : 'Failed to delete preset');
      } finally {
        setPendingDeletePreset(null);
      }
    },
    [pendingDeletePreset, refreshPresets],
  );

  // ── Param Setters (dropdowns — immediate source) ────────────────────

  const setFuselagePreset = useCallback(
    (v: FuselagePreset) => setParam('fuselagePreset', v, 'immediate'),
    [setParam],
  );
  const setMotorConfig = useCallback(
    (v: MotorConfig) => setParam('motorConfig', v, 'immediate'),
    [setParam],
  );
  const setWingMountType = useCallback(
    (v: WingMountType) => setParam('wingMountType', v, 'immediate'),
    [setParam],
  );
  const setTailType = useCallback(
    (v: TailType) => setParam('tailType', v, 'immediate'),
    [setParam],
  );

  // ── Engine count (number input — text source) ───────────────────────

  const handleEngineCountChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseInt(e.target.value, 10);
      if (!Number.isNaN(val) && val >= 0 && val <= 4) {
        setParam('engineCount', val, 'text');
      }
    },
    [setParam],
  );

  // ── Chord / Aspect Ratio bidirectional mode ────────────────────────
  // 'a' = chord is editable, aspect ratio is derived
  // 'b' = aspect ratio is editable, chord is derived from wingspan / AR
  const [chordArMode, setChordArMode] = useState<'a' | 'b'>('a');

  // Compute aspect ratio from current wingspan and chord (simple rectangular approx)
  const computedAspectRatio = useMemo(
    () => (design.wingChord > 0 ? design.wingSpan / design.wingChord : 0),
    [design.wingSpan, design.wingChord],
  );

  // When user changes aspect ratio, compute chord = wingspan / AR and send it
  const handleArSliderChange = useCallback(
    (ar: number) => {
      if (ar > 0) {
        const newChord = Math.round(design.wingSpan / ar / 5) * 5; // snap to step=5
        const clamped = Math.min(500, Math.max(50, newChord));
        setParam('wingChord', clamped, 'slider');
      }
    },
    [design.wingSpan, setParam],
  );
  const handleArInputChange = useCallback(
    (ar: number) => {
      if (ar > 0) {
        const newChord = Math.round(design.wingSpan / ar / 5) * 5;
        const clamped = Math.min(500, Math.max(50, newChord));
        setParam('wingChord', clamped, 'text');
      }
    },
    [design.wingSpan, setParam],
  );

  // ── Slider handlers ─────────────────────────────────────────────────

  const setWingSpanSlider = useCallback(
    (v: number) => setParam('wingSpan', v, 'slider'),
    [setParam],
  );
  const setWingSpanInput = useCallback(
    (v: number) => setParam('wingSpan', v, 'text'),
    [setParam],
  );
  const setWingChordSlider = useCallback(
    (v: number) => setParam('wingChord', v, 'slider'),
    [setParam],
  );
  const setWingChordInput = useCallback(
    (v: number) => setParam('wingChord', v, 'text'),
    [setParam],
  );
  const setFuselageLengthSlider = useCallback(
    (v: number) => setParam('fuselageLength', v, 'slider'),
    [setParam],
  );
  const setFuselageLengthInput = useCallback(
    (v: number) => setParam('fuselageLength', v, 'text'),
    [setParam],
  );

  const warnText = (field: string) =>
    getFieldWarnings(warnings, field).map(formatWarning).join('\n') || undefined;

  return (
    <div className="p-3">
      {/* ── Preset Selector ─────────────────────────────────────────── */}
      <div className="mb-4">
        <label className="block text-xs font-medium text-zinc-300 mb-1">Preset</label>
        <select
          value={activePreset}
          onChange={handlePresetChange}
          className="w-full px-2 py-1.5 text-xs text-zinc-100 bg-zinc-800
            border border-zinc-700 rounded cursor-pointer
            focus:outline-none focus:border-blue-500"
        >
          {PRESET_OPTIONS.map((name) => (
            <option key={name} value={name}>
              {PRESET_DISPLAY_LABELS[name]} — {PRESET_DESCRIPTIONS[name]}
            </option>
          ))}
          {activePreset === 'Custom' && (
            <option value="Custom" disabled>
              Custom
            </option>
          )}
        </select>
        {activePreset !== 'Custom' && (
          <p className="mt-1 text-[10px] text-zinc-500">
            {PRESET_DESCRIPTIONS[activePreset]}
          </p>
        )}

        {/* Preset confirmation dialog */}
        <AlertDialog.Root open={pendingPreset !== null} onOpenChange={(open) => { if (!open) cancelPreset(); }}>
          <AlertDialog.Portal>
            <AlertDialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
            <AlertDialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[340px] bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl z-50 p-5">
              <AlertDialog.Title className="text-sm font-semibold text-zinc-200 mb-2">
                Load Preset
              </AlertDialog.Title>
              <AlertDialog.Description className="text-xs text-zinc-400 mb-4">
                Load <span className="text-zinc-200 font-medium">{pendingPreset ? PRESET_DISPLAY_LABELS[pendingPreset] : ''}</span> preset?
                This will replace all parameters.
              </AlertDialog.Description>
              <div className="flex justify-end gap-2">
                <AlertDialog.Cancel asChild>
                  <button
                    className="px-3 py-1.5 text-xs text-zinc-400 bg-zinc-800 border border-zinc-700 rounded hover:bg-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-600"
                    onClick={cancelPreset}
                  >
                    Cancel
                  </button>
                </AlertDialog.Cancel>
                <AlertDialog.Action asChild>
                  <button
                    className="px-3 py-1.5 text-xs font-medium text-zinc-100 bg-blue-600 rounded hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-400"
                    onClick={confirmPreset}
                  >
                    Apply
                  </button>
                </AlertDialog.Action>
              </div>
            </AlertDialog.Content>
          </AlertDialog.Portal>
        </AlertDialog.Root>
      </div>

      {/* ── Save as Preset Button ────────────────────────────────────── */}
      <button
        onClick={() => { setShowSaveDialog(true); setSavePresetName(''); }}
        className="w-full mt-2 px-3 py-1.5 text-xs font-medium text-zinc-300
          bg-zinc-800 border border-zinc-700 rounded
          hover:bg-zinc-700 hover:text-zinc-100
          focus:outline-none focus:ring-1 focus:ring-blue-500
          transition-colors"
      >
        Save as Preset
      </button>

      {/* Save preset dialog */}
      <AlertDialog.Root open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <AlertDialog.Portal>
          <AlertDialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
          <AlertDialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[340px] bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl z-50 p-5">
            <AlertDialog.Title className="text-sm font-semibold text-zinc-200 mb-2">
              Save Custom Preset
            </AlertDialog.Title>
            <AlertDialog.Description className="text-xs text-zinc-400 mb-3">
              Save the current parameter configuration as a named preset.
            </AlertDialog.Description>
            <input
              type="text"
              placeholder="Preset name..."
              value={savePresetName}
              onChange={(e) => setSavePresetName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSavePreset(); }}
              className="w-full px-2 py-1.5 mb-3 text-xs text-zinc-100 bg-zinc-800
                border border-zinc-700 rounded
                focus:outline-none focus:border-blue-500
                placeholder:text-zinc-600"
              autoFocus
            />
            {presetError && (
              <p className="text-[10px] text-red-400 mb-2">{presetError}</p>
            )}
            <div className="flex justify-end gap-2">
              <AlertDialog.Cancel asChild>
                <button
                  className="px-3 py-1.5 text-xs text-zinc-400 bg-zinc-800 border border-zinc-700 rounded hover:bg-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-600"
                >
                  Cancel
                </button>
              </AlertDialog.Cancel>
              <AlertDialog.Action asChild>
                <button
                  disabled={!savePresetName.trim() || isSavingPreset}
                  onClick={(e) => { e.preventDefault(); handleSavePreset(); }}
                  className="px-3 py-1.5 text-xs font-medium text-zinc-100 bg-blue-600 rounded
                    hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-400
                    disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSavingPreset ? 'Saving...' : 'Save'}
                </button>
              </AlertDialog.Action>
            </div>
          </AlertDialog.Content>
        </AlertDialog.Portal>
      </AlertDialog.Root>

      {/* ── Custom Presets List ──────────────────────────────────────── */}
      {customPresets.length > 0 && (
        <div className="mt-3">
          <h4 className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">
            Saved Presets
          </h4>
          <div className="space-y-1 max-h-[160px] overflow-y-auto">
            {customPresets.map((p) => (
              <div
                key={p.id}
                className="flex items-center gap-1.5 px-2 py-1 bg-zinc-800/50 border border-zinc-700/50 rounded text-xs group"
              >
                <span className="flex-1 text-zinc-300 truncate" title={p.name}>
                  {p.name}
                </span>
                <button
                  onClick={() => handleLoadCustomPreset(p.id)}
                  disabled={isLoadingPreset}
                  className="px-1.5 py-0.5 text-[10px] text-blue-400 hover:text-blue-300
                    hover:bg-blue-500/10 rounded transition-colors
                    disabled:opacity-50"
                  title="Load this preset"
                >
                  Load
                </button>
                <button
                  onClick={() => setPendingDeletePreset(p)}
                  className="px-1.5 py-0.5 text-[10px] text-zinc-500 hover:text-red-400
                    hover:bg-red-500/10 rounded transition-colors
                    opacity-60 group-hover:opacity-100"
                  title="Delete this preset"
                >
                  Del
                </button>
              </div>
            ))}
          </div>
          {presetError && !showSaveDialog && (
            <p className="mt-1 text-[10px] text-red-400">{presetError}</p>
          )}
        </div>
      )}

      {/* Delete preset confirmation dialog (#198) */}
      <AlertDialog.Root open={pendingDeletePreset !== null} onOpenChange={(open) => { if (!open) setPendingDeletePreset(null); }}>
        <AlertDialog.Portal>
          <AlertDialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
          <AlertDialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[340px] bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl z-50 p-5">
            <AlertDialog.Title className="text-sm font-semibold text-zinc-200 mb-2">
              Delete Preset
            </AlertDialog.Title>
            <AlertDialog.Description className="text-xs text-zinc-400 mb-4">
              Delete preset <span className="text-zinc-200 font-medium">{pendingDeletePreset?.name}</span>? This cannot be undone.
            </AlertDialog.Description>
            <div className="flex justify-end gap-2">
              <AlertDialog.Cancel asChild>
                <button
                  className="px-3 py-1.5 text-xs text-zinc-400 bg-zinc-800 border border-zinc-700 rounded hover:bg-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-600"
                >
                  Cancel
                </button>
              </AlertDialog.Cancel>
              <AlertDialog.Action asChild>
                <button
                  onClick={handleConfirmDeletePreset}
                  className="px-3 py-1.5 text-xs font-medium text-zinc-100 bg-red-600 rounded hover:bg-red-500 focus:outline-none focus:ring-2 focus:ring-red-400"
                >
                  Delete
                </button>
              </AlertDialog.Action>
            </div>
          </AlertDialog.Content>
        </AlertDialog.Portal>
      </AlertDialog.Root>

      {/* ── Separator ───────────────────────────────────────────────── */}
      <div className="border-t border-zinc-700/50 mb-3 mt-3" />

      <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
        Global Parameters
      </h3>

      {/* G01 — Fuselage Preset */}
      <div data-section="fuselage" />
      <ParamSelect
        label="Fuselage Style"
        value={design.fuselagePreset}
        options={FUSELAGE_PRESET_OPTIONS}
        onChange={setFuselagePreset}
        hasWarning={fieldHasWarning(warnings, 'fuselagePreset')}
      />

      {/* G02 — Engine Count */}
      <div className="mb-3">
        <label className="block text-xs font-medium text-zinc-300 mb-1">
          Engine Count
        </label>
        <input
          type="number"
          min={0}
          max={4}
          step={1}
          value={design.engineCount}
          onChange={handleEngineCountChange}
          className="w-full px-2 py-1 text-xs text-zinc-100 bg-zinc-800
            border border-zinc-700 rounded focus:outline-none focus:border-blue-500
            [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none
            [&::-webkit-inner-spin-button]:appearance-none"
        />
      </div>

      {/* P02 — Motor Config */}
      <ParamSelect
        label="Motor Position"
        value={design.motorConfig}
        options={MOTOR_CONFIG_OPTIONS}
        onChange={setMotorConfig}
        hasWarning={fieldHasWarning(warnings, 'motorConfig')}
      />

      {/* G03 — Wing Span */}
      <ParamSlider
        label="Wingspan"
        unit="mm"
        value={design.wingSpan}
        min={300}
        max={3000}
        step={10}
        onSliderChange={setWingSpanSlider}
        onInputChange={setWingSpanInput}
        hasWarning={fieldHasWarning(warnings, 'wingSpan')}
        warningText={warnText('wingSpan')}
      />

      {/* G05 — Wing Chord / Aspect Ratio (bidirectional) */}
      <BidirectionalParam
        labelA="Wing Chord"
        labelB="Aspect Ratio"
        valueA={design.wingChord}
        valueB={Math.round(computedAspectRatio * 100) / 100}
        unitA="mm"
        minA={50}
        maxA={500}
        stepA={5}
        minB={2}
        maxB={30}
        stepB={0.5}
        mode={chordArMode}
        onModeChange={setChordArMode}
        onSliderChangeA={setWingChordSlider}
        onInputChangeA={setWingChordInput}
        onSliderChangeB={handleArSliderChange}
        onInputChangeB={handleArInputChange}
        hasWarningA={fieldHasWarning(warnings, 'wingChord')}
        warningTextA={warnText('wingChord')}
        decimalsA={0}
        decimalsB={2}
      />

      {/* F13 — Wing Mount Type */}
      <ParamSelect
        label="Wing Mount"
        value={design.wingMountType}
        options={WING_MOUNT_OPTIONS}
        onChange={setWingMountType}
        hasWarning={fieldHasWarning(warnings, 'wingMountType')}
      />

      {/* F01 — Fuselage Length */}
      <ParamSlider
        label="Fuselage Length"
        unit="mm"
        value={design.fuselageLength}
        min={150}
        max={2000}
        step={10}
        onSliderChange={setFuselageLengthSlider}
        onInputChange={setFuselageLengthInput}
        hasWarning={fieldHasWarning(warnings, 'fuselageLength')}
        warningText={warnText('fuselageLength')}
      />

      {/* G06 — Tail Type */}
      <ParamSelect
        label="Tail Type"
        value={design.tailType}
        options={TAIL_TYPE_OPTIONS}
        onChange={setTailType}
        hasWarning={fieldHasWarning(warnings, 'tailType')}
      />
    </div>
  );
}
