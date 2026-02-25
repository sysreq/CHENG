import { create } from 'zustand';
import { temporal } from 'zundo';
import { enableMapSet, produce } from 'immer';
import type {
  AircraftDesign,
  DerivedValues,
  ValidationWarning,
  MeshData,
  PresetName,
  ComponentSelection,
  SubElementSelection,
  ChangeSource,
  PerComponentPrintSettings,
  ComponentPrintSettings,
  WingAirfoil,
} from '../types/design';
import { COMPONENT_SUB_ELEMENTS } from '../types/design';
import { createDesignFromPreset, DEFAULT_PRESET, PRESET_FACTORIES } from '../lib/presets';

enableMapSet();

/** Keys to compare when detecting if a design matches a preset. Excludes meta fields. */
const PRESET_COMPARE_KEYS: (keyof AircraftDesign)[] = [
  'fuselagePreset', 'engineCount', 'motorConfig', 'wingSpan', 'wingChord',
  'wingMountType', 'fuselageLength', 'tailType', 'wingAirfoil', 'wingSweep',
  'wingTipRootRatio', 'wingDihedral', 'wingSkinThickness',
  'wingIncidence', 'wingTwist',
  'hStabSpan', 'hStabChord', 'hStabIncidence', 'vStabHeight', 'vStabRootChord', 'tailArm',
  'vTailDihedral', 'vTailSpan', 'vTailChord', 'vTailIncidence', 'vTailSweep',
  'noseCabinBreakPct', 'cabinTailBreakPct',
  'wallThickness',
  'printBedX', 'printBedY', 'printBedZ', 'autoSection', 'sectionOverlap',
  'jointType', 'jointTolerance', 'nozzleDiameter', 'hollowParts', 'teMinThickness',
  'supportStrategy',
  // Control surfaces (Issue #144)
  'aileronEnable', 'aileronSpanStart', 'aileronSpanEnd', 'aileronChordPercent',
  'elevatorEnable', 'elevatorSpanPercent', 'elevatorChordPercent',
  'rudderEnable', 'rudderHeightPercent', 'rudderChordPercent',
  'ruddervatorEnable', 'ruddervatorChordPercent', 'ruddervatorSpanPercent',
  'elevonEnable', 'elevonSpanStart', 'elevonSpanEnd', 'elevonChordPercent',
  'wingSections',
  'landingGearType', 'mainGearPosition', 'mainGearHeight', 'mainGearTrack',
  'mainWheelDiameter', 'noseGearHeight', 'noseWheelDiameter',
  'tailWheelDiameter', 'tailGearPosition',
];

function detectPreset(design: AircraftDesign): PresetName {
  for (const [name, factory] of Object.entries(PRESET_FACTORIES)) {
    const ref = factory();
    const match = PRESET_COMPARE_KEYS.every((k) => design[k] === ref[k]);
    if (match) return name as PresetName;
  }
  return 'Custom';
}

// ---------------------------------------------------------------------------
// Store Interface
// ---------------------------------------------------------------------------

/** Human-readable parameter labels for history display. */
const PARAM_LABELS: Partial<Record<keyof AircraftDesign, string>> = {
  wingSpan: 'Wingspan',
  wingChord: 'Wing Chord',
  wingSections: 'Wing Sections',
  fuselageLength: 'Fuselage Length',
  tailType: 'Tail Type',
  wingAirfoil: 'Airfoil',
  wingSweep: 'Wing Sweep',
  wingTipRootRatio: 'Taper Ratio',
  wingDihedral: 'Dihedral',
  wingSkinThickness: 'Skin Thickness',
  wingIncidence: 'Wing Incidence',
  wingTwist: 'Wing Twist',
  hStabSpan: 'H-Stab Span',
  hStabChord: 'H-Stab Chord',
  vStabHeight: 'V-Stab Height',
  vStabRootChord: 'V-Stab Root Chord',
  hStabIncidence: 'H-Stab Incidence',
  tailArm: 'Tail Arm',
  vTailDihedral: 'V-Tail Dihedral',
  vTailSpan: 'V-Tail Span',
  vTailChord: 'V-Tail Chord',
  vTailIncidence: 'V-Tail Incidence',
  vTailSweep: 'V-Tail Sweep',
  noseCabinBreakPct: 'Nose/Cabin Break %',
  cabinTailBreakPct: 'Cabin/Tail Break %',
  wallThickness: 'Wall Thickness',
  fuselagePreset: 'Fuselage Style',
  wingMountType: 'Wing Mount',
  motorConfig: 'Motor Config',
  engineCount: 'Engine Count',
  printBedX: 'Bed X',
  printBedY: 'Bed Y',
  printBedZ: 'Bed Z',
  sectionOverlap: 'Section Overlap',
  jointTolerance: 'Joint Tolerance',
  nozzleDiameter: 'Nozzle Diameter',
  teMinThickness: 'TE Min Thickness',
  // Control surfaces (Issue #144)
  aileronEnable: 'Ailerons',
  elevatorEnable: 'Elevator',
  rudderEnable: 'Rudder',
  ruddervatorEnable: 'Ruddervators',
  elevonEnable: 'Elevons',
  aileronSpanStart: 'Aileron Inboard',
  aileronSpanEnd: 'Aileron Outboard',
  aileronChordPercent: 'Aileron Chord %',
  elevatorSpanPercent: 'Elevator Span %',
  elevatorChordPercent: 'Elevator Chord %',
  rudderHeightPercent: 'Rudder Height %',
  rudderChordPercent: 'Rudder Chord %',
  ruddervatorSpanPercent: 'Ruddervator Span %',
  ruddervatorChordPercent: 'Ruddervator Chord %',
  elevonSpanStart: 'Elevon Inboard',
  elevonSpanEnd: 'Elevon Outboard',
  elevonChordPercent: 'Elevon Chord %',
  landingGearType: 'Landing Gear Type',
  mainGearPosition: 'Main Gear Position',
  mainGearHeight: 'Main Gear Height',
  mainGearTrack: 'Main Gear Track',
  mainWheelDiameter: 'Main Wheel Dia',
  noseGearHeight: 'Nose Gear Height',
  noseWheelDiameter: 'Nose Wheel Dia',
  tailWheelDiameter: 'Tail Wheel Dia',
  tailGearPosition: 'Tail Gear Position',
};

export interface DesignStore {
  // ── Design Parameters (undo/redo tracked) ───────────────────────
  design: AircraftDesign;
  activePreset: PresetName;
  lastChangeSource: ChangeSource;
  /** Human-readable description of the last action (for history panel). */
  lastAction: string;

  setParam: <K extends keyof AircraftDesign>(
    key: K,
    value: AircraftDesign[K],
    source?: ChangeSource,
  ) => void;
  /**
   * Force a Zundo history snapshot of the current design state.
   * Called after slider drag completes (onPointerUp) to commit one history
   * entry for the entire drag gesture (#222).
   */
  commitSliderChange: () => void;
  loadPreset: (name: Exclude<PresetName, 'Custom'>) => void;

  // ── Multi-Section Wing Panel Array Actions (#143, #245) ──────────
  /** Set a specific panel break position by index (0-based). */
  setPanelBreak: (index: number, value: number) => void;
  /** Set a specific panel dihedral by index (0-based, panel 2+ only). */
  setPanelDihedral: (index: number, value: number) => void;
  /** Set a specific panel sweep by index (0-based, panel 2+ only). */
  setPanelSweep: (index: number, value: number) => void;
  /** Set a specific panel airfoil by index (0-based, panel 2+ only). null = inherit root. */
  setPanelAirfoil: (index: number, value: WingAirfoil | null) => void;

  // ── Derived Values (from backend, read-only) ────────────────────
  derived: DerivedValues | null;
  setDerived: (derived: DerivedValues) => void;

  // ── Validation Warnings (from backend) ──────────────────────────
  warnings: ValidationWarning[];
  setWarnings: (warnings: ValidationWarning[]) => void;

  // ── Mesh Data (from WebSocket binary) ───────────────────────────
  meshData: MeshData | null;
  isGenerating: boolean;
  setMeshData: (mesh: MeshData) => void;
  setIsGenerating: (generating: boolean) => void;

  // ── Per-Component Print Settings (#128) ────────────────────────
  componentPrintSettings: PerComponentPrintSettings;
  setComponentPrintSetting: (
    component: 'wing' | 'tail' | 'fuselage' | 'landing_gear',
    settings: Partial<ComponentPrintSettings>,
  ) => void;
  clearComponentPrintSettings: (component: 'wing' | 'tail' | 'fuselage' | 'landing_gear') => void;

  // ── Viewport Selection ──────────────────────────────────────────
  selectedComponent: ComponentSelection;
  selectedSubElement: SubElementSelection;
  /** Index of the currently selected wing panel (0-based), or null if none.
   *  Applies to both left and right halves when wing_sections > 1 (#242). */
  selectedPanel: number | null;
  setSelectedComponent: (component: ComponentSelection) => void;
  /** Set the selected wing panel index. Null deselects. */
  setSelectedPanel: (panelIndex: number | null) => void;
  /** Cycle to next sub-element within the currently selected component. */
  cycleSubElement: () => void;

  // ── Mesh centering offset (applied in AircraftMesh) ───────────
  meshOffset: [number, number, number];
  setMeshOffset: (offset: [number, number, number]) => void;

  // ── Camera view preset trigger ────────────────────────────────
  cameraPresetTick: { preset: 'front' | 'side' | 'top' | 'perspective'; tick: number };
  setCameraPreset: (preset: 'front' | 'side' | 'top' | 'perspective') => void;

  // ── Custom Preset Loading ──────────────────────────────────────
  loadCustomPresetDesign: (design: AircraftDesign) => void;

  // ── File Operations ─────────────────────────────────────────────
  designId: string | null;
  designName: string;
  isDirty: boolean;
  isSaving: boolean;
  isLoading: boolean;
  fileError: string | null;
  clearFileError: () => void;
  setDesignName: (name: string) => void;
  newDesign: () => void;
  loadDesign: (id: string) => Promise<void>;
  saveDesign: () => Promise<string>;
}

/** Subset of state tracked by Zundo for undo/redo. */
export type UndoableState = Pick<DesignStore, 'design' | 'activePreset' | 'lastAction'>;

// ---------------------------------------------------------------------------
// Store Implementation
// ---------------------------------------------------------------------------

const initialDesign = createDesignFromPreset(DEFAULT_PRESET);

export const useDesignStore = create<DesignStore>()(
  temporal(
    (set, get) => ({
      // ── Design State ──────────────────────────────────────────────
      design: initialDesign,
      activePreset: DEFAULT_PRESET,
      lastChangeSource: 'immediate' as ChangeSource,
      lastAction: 'Initial state',

      setParam: (key, value, source = 'immediate') => {
        if (get().design[key] === value) return;
        const label = PARAM_LABELS[key] ?? String(key);
        set(
          produce((state: DesignStore) => {
            (state.design[key] as AircraftDesign[typeof key]) = value;
            state.activePreset = 'Custom';
            state.lastChangeSource = source;
            state.lastAction = `Set ${label} to ${String(value)}`;
            state.isDirty = true;

            // Side-effect: resize panel arrays when wingSections changes (#143)
            if (key === 'wingSections') {
              const newN = value as number;
              const targetLen = Math.max(0, newN - 1);
              const oldBreaks = state.design.panelBreakPositions;
              const oldDihedrals = state.design.panelDihedrals;
              const oldSweeps = state.design.panelSweeps;
              const oldAirfoils = state.design.panelAirfoils;

              if (oldBreaks.length < targetLen) {
                // Append default entries for new panels
                for (let i = oldBreaks.length; i < targetLen; i++) {
                  const breakPct = Math.min(90, 60 + i * 15);
                  oldBreaks.push(breakPct);
                  oldDihedrals.push(10);
                  oldSweeps.push(state.design.wingSweep);
                  oldAirfoils.push(null);
                }
              }
              // Truncate arrays (Immer splice is fine here)
              state.design.panelBreakPositions = oldBreaks.slice(0, targetLen);
              state.design.panelDihedrals = oldDihedrals.slice(0, targetLen);
              state.design.panelSweeps = oldSweeps.slice(0, targetLen);
              state.design.panelAirfoils = oldAirfoils.slice(0, targetLen);
            }
          }),
        );
      },

      commitSliderChange: () => {
        // No-op: the equality function in Zundo config now ensures snapshots
        // are only recorded when design data actually changes. Slider commits
        // are handled transparently — no spurious trigger needed.
      },

      // ── Multi-Section Wing Panel Array Actions (#143) ──────────────────
      setPanelBreak: (index, value) =>
        set(
          produce((state: DesignStore) => {
            state.design.panelBreakPositions[index] = value;
            state.activePreset = 'Custom';
            state.lastChangeSource = 'immediate';
            state.lastAction = `Set Panel ${index + 2} Break to ${value}%`;
            state.isDirty = true;
          }),
        ),

      setPanelDihedral: (index, value) =>
        set(
          produce((state: DesignStore) => {
            state.design.panelDihedrals[index] = value;
            state.activePreset = 'Custom';
            state.lastChangeSource = 'immediate';
            state.lastAction = `Set Panel ${index + 2} Dihedral to ${value}°`;
            state.isDirty = true;
          }),
        ),

      setPanelSweep: (index, value) =>
        set(
          produce((state: DesignStore) => {
            state.design.panelSweeps[index] = value;
            state.activePreset = 'Custom';
            state.lastChangeSource = 'immediate';
            state.lastAction = `Set Panel ${index + 2} Sweep to ${value}°`;
            state.isDirty = true;
          }),
        ),

      setPanelAirfoil: (index, value) =>
        set(
          produce((state: DesignStore) => {
            state.design.panelAirfoils[index] = value;
            state.activePreset = 'Custom';
            state.lastChangeSource = 'immediate';
            state.lastAction = value
              ? `Set Panel ${index + 2} Airfoil to ${value}`
              : `Reset Panel ${index + 2} Airfoil to inherit`;
            state.isDirty = true;
          }),
        ),

      loadPreset: (name) =>
        set(
          produce((state: DesignStore) => {
            const preset = createDesignFromPreset(name);
            preset.id = state.design.id;
            preset.name = state.design.name;
            state.design = preset;
            state.activePreset = name;
            state.lastChangeSource = 'immediate';
            state.lastAction = `Loaded ${name} preset`;
            state.isDirty = true;
          }),
        ),

      // ── Derived / Warnings / Mesh ─────────────────────────────────
      derived: null,
      setDerived: (derived) => set({ derived }),

      warnings: [],
      setWarnings: (warnings) => set({ warnings }),

      meshData: null,
      isGenerating: false,
      setMeshData: (meshData) => set({ meshData, isGenerating: false }),
      setIsGenerating: (isGenerating) => set({ isGenerating }),

      // ── Per-Component Print Settings (#128) ────────────────────────
      componentPrintSettings: {},
      setComponentPrintSetting: (component, settings) =>
        set(
          produce((state: DesignStore) => {
            const existing = state.componentPrintSettings[component as 'wing' | 'tail' | 'fuselage' | 'landing_gear'] ?? {};
            state.componentPrintSettings[component as 'wing' | 'tail' | 'fuselage' | 'landing_gear'] = { ...existing, ...settings };
          }),
        ),
      clearComponentPrintSettings: (component) =>
        set(
          produce((state: DesignStore) => {
            delete state.componentPrintSettings[component as 'wing' | 'tail' | 'fuselage' | 'landing_gear'];
          }),
        ),

      // ── Custom Preset Loading ──────────────────────────────────────
      loadCustomPresetDesign: (design: AircraftDesign) =>
        set(
          produce((state: DesignStore) => {
            // Preserve current meta fields (id, name stay from current design)
            const currentId = state.design.id;
            const currentName = state.design.name;
            state.design = { ...design, id: currentId, name: currentName };
            state.activePreset = 'Custom';
            state.lastChangeSource = 'immediate';
            state.isDirty = true;
          }),
        ),

      // ── Viewport ──────────────────────────────────────────────────
      selectedComponent: null,
      selectedSubElement: null,
      selectedPanel: null,
      setSelectedComponent: (component) =>
        set({ selectedComponent: component, selectedSubElement: null, selectedPanel: null }),
      setSelectedPanel: (panelIndex) =>
        set({ selectedPanel: panelIndex, selectedComponent: 'wing', selectedSubElement: null }),
      cycleSubElement: () => {
        const { selectedComponent, selectedSubElement } = get();
        if (!selectedComponent) return;
        const subs = COMPONENT_SUB_ELEMENTS[selectedComponent];
        if (!subs || subs.length === 0) return;
        const currentIndex = selectedSubElement ? subs.indexOf(selectedSubElement) : -1;
        const nextIndex = currentIndex + 1;
        if (nextIndex >= subs.length) {
          // Cycled through all sub-elements — deselect entirely
          set({ selectedSubElement: null, selectedComponent: null });
        } else {
          set({ selectedSubElement: subs[nextIndex] as SubElementSelection });
        }
      },

      meshOffset: [0, 0, 0] as [number, number, number],
      setMeshOffset: (offset) => set({ meshOffset: offset }),

      cameraPresetTick: { preset: 'perspective' as const, tick: 0 },
      setCameraPreset: (preset) =>
        set((state) => ({
          cameraPresetTick: { preset, tick: state.cameraPresetTick.tick + 1 },
        })),

      // ── File Operations ───────────────────────────────────────────
      designId: null,
      designName: 'Untitled Aircraft',
      isDirty: false,
      isSaving: false,
      isLoading: false,
      fileError: null,

      clearFileError: () => set({ fileError: null }),

      setDesignName: (name) =>
        set(
          produce((state: DesignStore) => {
            state.designName = name;
            state.design.name = name;
            state.isDirty = true;
          }),
        ),

      newDesign: () => {
        const fresh = createDesignFromPreset(DEFAULT_PRESET);
        set({
          design: fresh,
          activePreset: DEFAULT_PRESET,
          lastChangeSource: 'immediate' as ChangeSource,
          lastAction: 'New design',
          designId: null,
          designName: 'Untitled Aircraft',
          isDirty: false,
          derived: null,
          warnings: [],
          meshData: null,
          selectedComponent: null,
          selectedSubElement: null,
          selectedPanel: null,
        });
      },

      loadDesign: async (id: string) => {
        set({ isLoading: true, fileError: null });
        try {
          const res = await fetch(`/api/designs/${id}`);
          if (!res.ok) throw new Error(`Failed to load design: ${res.status}`);
          const data = (await res.json()) as AircraftDesign;
          set({
            design: data,
            designId: id,
            designName: data.name,
            activePreset: detectPreset(data),
            lastChangeSource: 'immediate' as ChangeSource,
            isDirty: false,
            isLoading: false,
            derived: null,
            warnings: [],
            meshData: null,
          });
        } catch (err) {
          const msg = err instanceof Error ? err.message : 'Failed to load design';
          set({ isLoading: false, fileError: msg });
        }
      },

      saveDesign: async () => {
        set({ isSaving: true, fileError: null });
        try {
          const { design } = get();
          const res = await fetch('/api/designs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(design),
          });
          if (!res.ok) throw new Error(`Failed to save: ${res.status}`);
          const saved = (await res.json()) as { id: string };
          set(
            produce((state: DesignStore) => {
              state.designId = saved.id;
              state.design.id = saved.id;
              state.isDirty = false;
              state.isSaving = false;
            }),
          );
          return saved.id;
        } catch (err) {
          const msg = err instanceof Error ? err.message : 'Failed to save design';
          set({ isSaving: false, fileError: msg });
          throw err;
        }
      },
    }),
    {
      // Zundo: track design params, preset, and action label for undo/redo.
      // lastAction is display metadata stored in the snapshot so the history
      // panel can show a human-readable label for each past/future state.
      partialize: (state): UndoableState => ({
        design: state.design,
        activePreset: state.activePreset,
        lastAction: state.lastAction,
      }),
      // Only record a snapshot when design data actually changes (#246).
      // This prevents lastAction-only changes from creating spurious history
      // entries (e.g. commitSliderChange() re-setting lastAction to the same
      // value).
      equality: (a, b) => JSON.stringify(a.design) === JSON.stringify(b.design),
      limit: 50,
    },
  ),
);
