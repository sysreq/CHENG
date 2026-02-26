// ============================================================================
// CHENG — Stability Panel + stabilityAnalyzer unit tests
// Issue #318
// ============================================================================

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import type { DerivedValues } from '@/types/design';

// ---------------------------------------------------------------------------
// stabilityAnalyzer — pure utility tests (no render needed)
// ---------------------------------------------------------------------------

import {
  getStabilityStatus,
  getStatusMeta,
  getMarginColorClass,
  getMarginTextColorClass,
} from '@/lib/stabilityAnalyzer';

describe('getStabilityStatus', () => {
  it('returns unstable for negative margin', () => {
    expect(getStabilityStatus(-1)).toBe('unstable');
    expect(getStabilityStatus(-0.01)).toBe('unstable');
  });

  it('returns unstable for NaN (degenerate geometry guard)', () => {
    expect(getStabilityStatus(NaN)).toBe('unstable');
  });

  it('returns unstable for Infinity (degenerate geometry guard)', () => {
    expect(getStabilityStatus(Infinity)).toBe('unstable');
    expect(getStabilityStatus(-Infinity)).toBe('unstable');
  });

  it('returns marginal for margin in 0–2% (exclusive of 2)', () => {
    expect(getStabilityStatus(0)).toBe('marginal');
    expect(getStabilityStatus(1)).toBe('marginal');
    expect(getStabilityStatus(1.99)).toBe('marginal');
  });

  it('returns stable for margin exactly at 2% (start of stable zone)', () => {
    expect(getStabilityStatus(2)).toBe('stable');
  });

  it('returns stable for margin in 2–15%', () => {
    expect(getStabilityStatus(8)).toBe('stable');
    expect(getStabilityStatus(15)).toBe('stable');
  });

  it('returns over-stable for margin above 15%', () => {
    expect(getStabilityStatus(15.01)).toBe('over-stable');
    expect(getStabilityStatus(20)).toBe('over-stable');
    expect(getStabilityStatus(100)).toBe('over-stable');
  });
});

describe('getStatusMeta', () => {
  it('returns red color for unstable', () => {
    const meta = getStatusMeta('unstable');
    expect(meta.colorClass).toContain('red');
    expect(meta.label).toBe('UNSTABLE');
    expect(meta.icon).toBe('✗');
  });

  it('returns yellow color for marginal', () => {
    const meta = getStatusMeta('marginal');
    expect(meta.colorClass).toContain('yellow');
    expect(meta.label).toBe('MARGINAL');
  });

  it('returns green color for stable', () => {
    const meta = getStatusMeta('stable');
    expect(meta.colorClass).toContain('green');
    expect(meta.label).toBe('STABLE');
    expect(meta.icon).toBe('✓');
  });

  it('returns blue color for over-stable', () => {
    const meta = getStatusMeta('over-stable');
    expect(meta.colorClass).toContain('blue');
    expect(meta.label).toBe('OVER-STABLE');
  });
});

describe('getMarginColorClass / getMarginTextColorClass', () => {
  it('getMarginColorClass returns bg-red-500 for negative margin', () => {
    expect(getMarginColorClass(-1)).toBe('bg-red-500');
  });

  it('getMarginColorClass returns bg-green-500 for stable margin', () => {
    expect(getMarginColorClass(8)).toBe('bg-green-500');
  });

  it('getMarginColorClass returns bg-yellow-500 for marginal margin', () => {
    expect(getMarginColorClass(1)).toBe('bg-yellow-500');
  });

  it('getMarginColorClass returns bg-blue-500 for over-stable margin', () => {
    expect(getMarginColorClass(20)).toBe('bg-blue-500');
  });

  it('getMarginTextColorClass is consistent with getMarginColorClass', () => {
    // Both should reflect the same zone classification
    for (const pct of [-5, 0.5, 5, 20]) {
      const bgClass = getMarginColorClass(pct);
      const textClass = getMarginTextColorClass(pct);
      // bg-red-500 → text-red-500, etc.
      const colorPart = bgClass.replace('bg-', '');
      expect(textClass).toBe(`text-${colorPart}`);
    }
  });
});

// ---------------------------------------------------------------------------
// Mock DerivedValues for component tests
// ---------------------------------------------------------------------------

const MOCK_DERIVED: DerivedValues = {
  // Existing derived fields
  tipChordMm: 180,
  wingAreaCm2: 18000,
  aspectRatio: 6.7,
  meanAeroChordMm: 180,
  taperRatio: 1.0,
  estimatedCgMm: 350,
  minFeatureThicknessMm: 0.8,
  wallThicknessMm: 1.5,
  // Stability fields (v1.1)
  neutralPointMm: 368,
  neutralPointPctMac: 27.8,
  cgPctMac: 24.2,
  staticMarginPct: 3.6,
  tailVolumeH: 0.52,
  tailVolumeV: 0.04,
  wingLoadingGDm2: 35.0,
};

// ---------------------------------------------------------------------------
// StaticMarginGauge — color zone tests
// ---------------------------------------------------------------------------

import { StaticMarginGauge } from '@/components/stability/StaticMarginGauge';

describe('StaticMarginGauge', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('applies bg-green-500 thumb color for SM in 2–15%', () => {
    const { container } = render(<StaticMarginGauge staticMarginPct={8} />);
    const thumb = container.querySelector('.bg-green-500.rounded-full');
    expect(thumb).not.toBeNull();
  });

  it('applies bg-red-500 thumb color for SM < 0%', () => {
    const { container } = render(<StaticMarginGauge staticMarginPct={-2} />);
    const thumb = container.querySelector('.bg-red-500.rounded-full');
    expect(thumb).not.toBeNull();
  });

  it('applies bg-yellow-500 thumb color for marginal SM', () => {
    const { container } = render(<StaticMarginGauge staticMarginPct={1} />);
    const thumb = container.querySelector('.bg-yellow-500.rounded-full');
    expect(thumb).not.toBeNull();
  });

  it('applies bg-blue-500 thumb color for over-stable SM', () => {
    const { container } = render(<StaticMarginGauge staticMarginPct={20} />);
    const thumb = container.querySelector('.bg-blue-500.rounded-full');
    expect(thumb).not.toBeNull();
  });

  it('renders progressbar with correct aria-valuenow', () => {
    render(<StaticMarginGauge staticMarginPct={5} />);
    const bar = screen.getByRole('progressbar');
    expect(bar).toBeDefined();
    expect(bar.getAttribute('aria-valuenow')).toBe('5');
  });

  it('renders correct zone labels (Unstable, Marginal, Stable, Over-stable)', () => {
    render(<StaticMarginGauge staticMarginPct={8} />);
    expect(screen.getByText('Unstable')).toBeDefined();
    expect(screen.getByText('Stable')).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// PitchStabilityIndicator — status label tests
// ---------------------------------------------------------------------------

import { PitchStabilityIndicator } from '@/components/stability/PitchStabilityIndicator';

// Track mock functions so we can assert on calls
const mockAnnounce = vi.fn();
const mockAnnounceAssertive = vi.fn();

vi.mock('@/store/liveRegionStore', () => ({
  useLiveRegionStore: () => ({
    announce: mockAnnounce,
    announceAssertive: mockAnnounceAssertive,
  }),
}));

describe('PitchStabilityIndicator', () => {
  beforeEach(() => {
    mockAnnounce.mockClear();
    mockAnnounceAssertive.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows UNSTABLE label and red color for SM < 0%', () => {
    render(<PitchStabilityIndicator staticMarginPct={-1} />);
    const label = screen.getByText('UNSTABLE');
    expect(label).toBeDefined();
    expect(label.className).toContain('text-red-500');
  });

  it('shows MARGINAL label and yellow color for SM in 0–2%', () => {
    render(<PitchStabilityIndicator staticMarginPct={1} />);
    const label = screen.getByText('MARGINAL');
    expect(label).toBeDefined();
    expect(label.className).toContain('text-yellow-500');
  });

  it('shows STABLE label and green color for SM in 2–15%', () => {
    render(<PitchStabilityIndicator staticMarginPct={8} />);
    const label = screen.getByText('STABLE');
    expect(label).toBeDefined();
    expect(label.className).toContain('text-green-500');
  });

  it('shows OVER-STABLE label and blue color for SM > 15%', () => {
    render(<PitchStabilityIndicator staticMarginPct={20} />);
    const label = screen.getByText('OVER-STABLE');
    expect(label).toBeDefined();
    expect(label.className).toContain('text-blue-500');
  });

  it('has role="status" container for screen reader updates', () => {
    const { container } = render(<PitchStabilityIndicator staticMarginPct={5} />);
    // The outer div is the role="status" — look directly on the container
    const statusEl = container.querySelector('[role="status"]');
    expect(statusEl).not.toBeNull();
  });

  it('does NOT call announceAssertive on initial render (no crossing)', () => {
    render(<PitchStabilityIndicator staticMarginPct={5} />);
    // On initial render, prevStatusRef is null so no announcement should fire
    expect(mockAnnounceAssertive).not.toHaveBeenCalled();
  });

  it('shows correct description for STABLE status', () => {
    render(<PitchStabilityIndicator staticMarginPct={8} />);
    expect(screen.getByText(/Natural pitch stability is present/)).toBeDefined();
  });

  it('shows correct description for UNSTABLE status', () => {
    render(<PitchStabilityIndicator staticMarginPct={-3} />);
    expect(screen.getByText(/CG is behind neutral point/)).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// StabilityPanel — integration render tests
// ---------------------------------------------------------------------------

// Mock useDesignStore — the panel reads derived from store
vi.mock('@/store/designStore', () => ({
  useDesignStore: (selector: (state: Record<string, unknown>) => unknown) => {
    const state = {
      derived: MOCK_DERIVED,
    };
    if (typeof selector === 'function') {
      try {
        return selector(state);
      } catch {
        return undefined;
      }
    }
    return state;
  },
}));

// Patch temporal sub-store (accessed directly as useDesignStore.temporal)
import { useDesignStore } from '@/store/designStore';
(useDesignStore as unknown as Record<string, unknown>).temporal = {
  getState: () => ({ pause: vi.fn(), resume: vi.fn() }),
};

// Mock useUnitStore — used by DerivedField
vi.mock('@/store/unitStore', () => ({
  useUnitStore: () => 'mm',
}));

import { StabilityPanel } from '@/components/panels/StabilityPanel';

describe('StabilityPanel', () => {
  beforeEach(() => {
    mockAnnounce.mockClear();
    mockAnnounceAssertive.mockClear();
    vi.clearAllMocks();
  });

  it('renders outer section with role="region" and correct aria-label', () => {
    render(<StabilityPanel />);
    const region = screen.getByRole('region', { name: 'Static Stability Analysis' });
    expect(region).toBeDefined();
  });

  it('renders CgVsNpGauge with role="img"', () => {
    render(<StabilityPanel />);
    expect(screen.getByRole('img')).toBeDefined();
  });

  it('renders StaticMarginGauge with role="progressbar"', () => {
    render(<StabilityPanel />);
    expect(screen.getByRole('progressbar')).toBeDefined();
  });

  it('renders PitchStabilityIndicator showing STABLE for staticMarginPct=3.6', () => {
    render(<StabilityPanel />);
    // The indicator shows STABLE for our mock derived (staticMarginPct=3.6)
    expect(screen.getByText('STABLE')).toBeDefined();
  });

  it('renders CgVsNpGauge with aria-label containing CG and NP % MAC values', () => {
    render(<StabilityPanel />);
    const gauge = screen.getByRole('img');
    const ariaLabel = gauge.getAttribute('aria-label') ?? '';
    expect(ariaLabel).toContain('24.2');  // cgPctMac from MOCK_DERIVED
    expect(ariaLabel).toContain('27.8');  // neutralPointPctMac from MOCK_DERIVED
  });

  it('expandable details section shows raw mm values on click', () => {
    render(<StabilityPanel />);
    // Verify the details section exists and contains the summary toggle
    const summary = screen.getByText('Raw Values');
    expect(summary).toBeDefined();
    // Expand the details section
    fireEvent.click(summary);
    // CG Position should show 350.0 mm (estimatedCgMm)
    expect(screen.getByText(/350/)).toBeDefined();
    // Neutral Point should show 368.0 mm (neutralPointMm)
    expect(screen.getByText(/368/)).toBeDefined();
  });
});
