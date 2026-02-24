/**
 * API functions for custom presets CRUD.
 * Mirrors the pattern from the designs API in designStore.ts.
 */

import type { AircraftDesign, CustomPresetSummary } from '../types/design';

const API_BASE = '/api/presets';

/**
 * List all saved custom presets, sorted newest first.
 */
export async function listCustomPresets(): Promise<CustomPresetSummary[]> {
  const res = await fetch(API_BASE);
  if (!res.ok) throw new Error(`Failed to list presets: ${res.status}`);
  return res.json() as Promise<CustomPresetSummary[]>;
}

/**
 * Load a single custom preset's full design data.
 */
export async function loadCustomPreset(id: string): Promise<AircraftDesign> {
  const res = await fetch(`${API_BASE}/${id}`);
  if (!res.ok) throw new Error(`Failed to load preset: ${res.status}`);
  return res.json() as Promise<AircraftDesign>;
}

/**
 * Save the current design as a named custom preset.
 * Returns the generated id and name.
 */
export async function saveCustomPreset(
  name: string,
  design: AircraftDesign,
): Promise<{ id: string; name: string }> {
  const res = await fetch(API_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, design }),
  });
  if (!res.ok) throw new Error(`Failed to save preset: ${res.status}`);
  return res.json() as Promise<{ id: string; name: string }>;
}

/**
 * Delete a custom preset by id.
 */
export async function deleteCustomPreset(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to delete preset: ${res.status}`);
}
