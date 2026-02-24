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
  ChangeSource,
} from '../types/design';
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
  'fuselageNoseLength', 'fuselageCabinLength', 'fuselageTailLength',
  'wallThickness',
  'printBedX', 'printBedY', 'printBedZ', 'autoSection', 'sectionOverlap',
  'jointType', 'jointTolerance', 'nozzleDiameter', 'hollowParts', 'teMinThickness',
  'supportStrategy',
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

export interface DesignStore {
  // ── Design Parameters (undo/redo tracked) ───────────────────────
  design: AircraftDesign;
  activePreset: PresetName;
  lastChangeSource: ChangeSource;

  setParam: <K extends keyof AircraftDesign>(
    key: K,
    value: AircraftDesign[K],
    source?: ChangeSource,
  ) => void;
  loadPreset: (name: Exclude<PresetName, 'Custom'>) => void;

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

  // ── Viewport Selection ──────────────────────────────────────────
  selectedComponent: ComponentSelection;
  setSelectedComponent: (component: ComponentSelection) => void;

  // ── Mesh centering offset (applied in AircraftMesh) ───────────
  meshOffset: [number, number, number];
  setMeshOffset: (offset: [number, number, number]) => void;

  // ── Camera view preset trigger ────────────────────────────────
  cameraPresetTick: { preset: 'front' | 'side' | 'top' | 'perspective'; tick: number };
  setCameraPreset: (preset: 'front' | 'side' | 'top' | 'perspective') => void;

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
export type UndoableState = Pick<DesignStore, 'design' | 'activePreset'>;

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

      setParam: (key, value, source = 'immediate') => {
        if (get().design[key] === value) return;
        set(
          produce((state: DesignStore) => {
            (state.design[key] as AircraftDesign[typeof key]) = value;
            state.activePreset = 'Custom';
            state.lastChangeSource = source;
            state.isDirty = true;
          }),
        );
      },

      loadPreset: (name) =>
        set(
          produce((state: DesignStore) => {
            const preset = createDesignFromPreset(name);
            // Preserve meta fields
            preset.id = state.design.id;
            preset.name = state.design.name;
            state.design = preset;
            state.activePreset = name;
            state.lastChangeSource = 'immediate';
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

      // ── Viewport ──────────────────────────────────────────────────
      selectedComponent: null,
      setSelectedComponent: (component) =>
        set({ selectedComponent: component }),

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
          designId: null,
          designName: 'Untitled Aircraft',
          isDirty: false,
          derived: null,
          warnings: [],
          meshData: null,
          selectedComponent: null,
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
      // Zundo: only track design params and preset for undo/redo
      partialize: (state): UndoableState => ({
        design: state.design,
        activePreset: state.activePreset,
      }),
      limit: 50,
    },
  ),
);
