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
import { createDesignFromPreset, DEFAULT_PRESET } from '../lib/presets';

enableMapSet();

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
  setMeshData: (mesh: MeshData) => void;

  // ── Viewport Selection ──────────────────────────────────────────
  selectedComponent: ComponentSelection;
  setSelectedComponent: (component: ComponentSelection) => void;

  // ── File Operations ─────────────────────────────────────────────
  designId: string | null;
  designName: string;
  isDirty: boolean;
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

      setParam: (key, value, source = 'immediate') =>
        set(
          produce((state: DesignStore) => {
            (state.design[key] as AircraftDesign[typeof key]) = value;
            state.activePreset = 'Custom';
            state.lastChangeSource = source;
            state.isDirty = true;
          }),
        ),

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
      setMeshData: (meshData) => set({ meshData }),

      // ── Viewport ──────────────────────────────────────────────────
      selectedComponent: null,
      setSelectedComponent: (component) =>
        set({ selectedComponent: component }),

      // ── File Operations ───────────────────────────────────────────
      designId: null,
      designName: 'Untitled Aircraft',
      isDirty: false,

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
        const res = await fetch(`/api/designs/${id}`);
        if (!res.ok) throw new Error(`Failed to load design: ${res.status}`);
        const data = (await res.json()) as AircraftDesign;
        set({
          design: data,
          designId: id,
          designName: data.name,
          activePreset: 'Custom',
          isDirty: false,
          derived: null,
          warnings: [],
          meshData: null,
        });
      },

      saveDesign: async () => {
        const { design } = get();
        const res = await fetch('/api/designs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(design),
        });
        if (!res.ok) throw new Error(`Failed to save: ${res.status}`);
        const saved = (await res.json()) as { id: string };
        set({ designId: saved.id, isDirty: false });
        return saved.id;
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
