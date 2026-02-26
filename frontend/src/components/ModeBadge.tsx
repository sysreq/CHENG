// ============================================================================
// CHENG — ModeBadge: Toolbar deployment mode indicator
// Issue #152 (Mode badge — Local/Cloud indicator)
// ============================================================================

import React from 'react';
import { useModeInfo } from '@/hooks/useModeInfo';
import type { DeploymentMode } from '@/hooks/useModeInfo';

// ---------------------------------------------------------------------------
// Style config per mode
// ---------------------------------------------------------------------------

const MODE_CONFIG: Record<
  DeploymentMode,
  { label: string; className: string; title: string }
> = {
  local: {
    label: 'Local',
    className:
      'px-2 py-0.5 text-[10px] font-medium rounded-full ' +
      'bg-zinc-700 text-zinc-300 border border-zinc-600',
    title: 'Running in local Docker mode',
  },
  cloud: {
    label: 'Cloud',
    className:
      'px-2 py-0.5 text-[10px] font-medium rounded-full ' +
      'bg-emerald-900 text-emerald-300 border border-emerald-700',
    title: 'Running in Cloud (Google Cloud Run) mode',
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Small pill badge shown in the toolbar indicating the deployment mode.
 *
 * - "Local" -- subtle gray/zinc styling (Docker local mode)
 * - "Cloud" -- green styling (Google Cloud Run mode)
 *
 * Fetches /api/info on mount; defaults to "local" on error or while loading.
 * Renders nothing until the fetch resolves to avoid a flash.
 */
export function ModeBadge(): React.JSX.Element | null {
  const info = useModeInfo();

  // Don't render until fetch resolves (avoids layout shift)
  if (info === null) return null;

  const config = MODE_CONFIG[info.mode];

  return (
    <span
      className={config.className}
      title={config.title}
      aria-label={`Deployment mode: ${config.label}`}
    >
      {config.label}
    </span>
  );
}
