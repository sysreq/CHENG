// ============================================================================
// CHENG — Unit Toggle tests
// Issue #153 (Unit toggle: mm / inches)
// ============================================================================

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, render, screen, act, fireEvent } from '@testing-library/react';
import { useUnitStore } from '@/store/unitStore';
import { UnitToggle } from '@/components/UnitToggle';
import {
  mmToIn,
  inToMm,
  toDisplayUnit,
  fromDisplayUnit,
  getDisplayUnit,
  convertSliderRange,
  formatMmValue,
  MM_PER_INCH,
} from '@/lib/units';

// ---------------------------------------------------------------------------
// Unit Conversion Utilities Tests
// ---------------------------------------------------------------------------

describe('Unit conversion utilities', () => {
  it('mmToIn converts correctly', () => {
    expect(mmToIn(25.4)).toBeCloseTo(1.0);
    expect(mmToIn(1000)).toBeCloseTo(39.3701, 3);
    expect(mmToIn(0)).toBe(0);
  });

  it('inToMm converts correctly', () => {
    expect(inToMm(1)).toBeCloseTo(25.4);
    expect(inToMm(0)).toBe(0);
    expect(inToMm(2)).toBeCloseTo(50.8);
  });

  it('mmToIn and inToMm are inverses', () => {
    const originalMm = 500;
    expect(inToMm(mmToIn(originalMm))).toBeCloseTo(originalMm);

    const originalIn = 19.685;
    expect(mmToIn(inToMm(originalIn))).toBeCloseTo(originalIn, 3);
  });

  it('MM_PER_INCH is correct', () => {
    expect(MM_PER_INCH).toBe(25.4);
  });

  describe('toDisplayUnit', () => {
    it('returns value unchanged in mm mode', () => {
      expect(toDisplayUnit(1000, 'mm')).toBe(1000);
    });

    it('converts mm to inches in in mode', () => {
      expect(toDisplayUnit(25.4, 'in')).toBeCloseTo(1.0);
      expect(toDisplayUnit(1000, 'in')).toBeCloseTo(39.3701, 3);
    });
  });

  describe('fromDisplayUnit', () => {
    it('returns value unchanged in mm mode', () => {
      expect(fromDisplayUnit(1000, 'mm')).toBe(1000);
    });

    it('converts inches to mm in in mode', () => {
      expect(fromDisplayUnit(1, 'in')).toBeCloseTo(25.4);
      expect(fromDisplayUnit(39.3701, 'in')).toBeCloseTo(1000, 0);
    });
  });

  describe('getDisplayUnit', () => {
    it('returns mm when in mm mode', () => {
      expect(getDisplayUnit('mm', 'mm')).toBe('mm');
    });

    it('returns in when mm field in inches mode', () => {
      expect(getDisplayUnit('mm', 'in')).toBe('in');
    });

    it('preserves non-mm units in inches mode', () => {
      expect(getDisplayUnit('deg', 'in')).toBe('deg');
      expect(getDisplayUnit('%', 'in')).toBe('%');
      expect(getDisplayUnit('ratio', 'in')).toBe('ratio');
    });

    it('preserves non-mm units in mm mode', () => {
      expect(getDisplayUnit('deg', 'mm')).toBe('deg');
      expect(getDisplayUnit('%', 'mm')).toBe('%');
    });
  });

  describe('convertSliderRange', () => {
    it('returns range unchanged for non-mm units in any mode', () => {
      const range = { min: 0, max: 45, step: 1 };
      expect(convertSliderRange(range, 'deg', 'mm')).toEqual(range);
      expect(convertSliderRange(range, 'deg', 'in')).toEqual(range);
      expect(convertSliderRange(range, '%', 'in')).toEqual(range);
    });

    it('returns range unchanged for mm units in mm mode', () => {
      const range = { min: 300, max: 3000, step: 10 };
      expect(convertSliderRange(range, 'mm', 'mm')).toEqual(range);
    });

    it('converts mm range to inches in in mode', () => {
      const range = { min: 300, max: 3000, step: 10 };
      const converted = convertSliderRange(range, 'mm', 'in');
      expect(converted.min).toBeCloseTo(300 / 25.4, 2);
      expect(converted.max).toBeCloseTo(3000 / 25.4, 2);
      expect(converted.step).toBeGreaterThan(0);
    });

    it('converted step is positive and smaller than converted range', () => {
      const range = { min: 100, max: 500, step: 5 };
      const converted = convertSliderRange(range, 'mm', 'in');
      expect(converted.step).toBeGreaterThan(0);
      expect(converted.step).toBeLessThan(converted.max - converted.min);
    });
  });

  describe('formatMmValue', () => {
    it('formats in mm when unitSystem is mm', () => {
      expect(formatMmValue(1000, 'mm', 1)).toBe('1000.0 mm');
      expect(formatMmValue(180, 'mm', 0)).toBe('180 mm');
    });

    it('formats in inches when unitSystem is in', () => {
      const result = formatMmValue(25.4, 'in', 1, 3);
      expect(result).toBe('1.000 in');
    });

    it('uses correct decimal places for each mode', () => {
      const mmResult = formatMmValue(100, 'mm', 2);
      expect(mmResult).toBe('100.00 mm');

      const inResult = formatMmValue(25.4, 'in', 1, 2);
      expect(inResult).toBe('1.00 in');
    });
  });
});

// ---------------------------------------------------------------------------
// useUnitStore tests
// ---------------------------------------------------------------------------

describe('useUnitStore', () => {
  // Reset store state and localStorage between tests
  beforeEach(() => {
    act(() => {
      useUnitStore.getState().setUnitSystem('mm');
    });
    // Clear localStorage
    window.localStorage.removeItem('cheng-unit-system');
  });

  it('defaults to mm', () => {
    const { result } = renderHook(() => useUnitStore());
    expect(result.current.unitSystem).toBe('mm');
  });

  it('toggleUnit switches from mm to in', () => {
    const { result } = renderHook(() => useUnitStore());
    expect(result.current.unitSystem).toBe('mm');

    act(() => {
      result.current.toggleUnit();
    });

    expect(result.current.unitSystem).toBe('in');
  });

  it('toggleUnit switches from in to mm', () => {
    const { result } = renderHook(() => useUnitStore());

    act(() => {
      result.current.setUnitSystem('in');
    });
    expect(result.current.unitSystem).toBe('in');

    act(() => {
      result.current.toggleUnit();
    });

    expect(result.current.unitSystem).toBe('mm');
  });

  it('setUnitSystem sets the unit directly', () => {
    const { result } = renderHook(() => useUnitStore());

    act(() => {
      result.current.setUnitSystem('in');
    });
    expect(result.current.unitSystem).toBe('in');

    act(() => {
      result.current.setUnitSystem('mm');
    });
    expect(result.current.unitSystem).toBe('mm');
  });
});

// ---------------------------------------------------------------------------
// UnitToggle component tests
// ---------------------------------------------------------------------------

describe('UnitToggle', () => {
  beforeEach(() => {
    act(() => {
      useUnitStore.getState().setUnitSystem('mm');
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders mm button when unitSystem is mm', () => {
    render(<UnitToggle />);
    expect(screen.getByText('mm')).toBeTruthy();
  });

  it('renders in button when unitSystem is in', () => {
    act(() => {
      useUnitStore.getState().setUnitSystem('in');
    });
    render(<UnitToggle />);
    expect(screen.getByText('in')).toBeTruthy();
  });

  it('toggles from mm to in on click', () => {
    render(<UnitToggle />);

    const button = screen.getByRole('button');
    expect(button.textContent).toBe('mm');

    fireEvent.click(button);

    expect(button.textContent).toBe('in');
    expect(useUnitStore.getState().unitSystem).toBe('in');
  });

  it('toggles from in to mm on click', () => {
    act(() => {
      useUnitStore.getState().setUnitSystem('in');
    });

    render(<UnitToggle />);

    const button = screen.getByRole('button');
    expect(button.textContent).toBe('in');

    fireEvent.click(button);

    expect(button.textContent).toBe('mm');
    expect(useUnitStore.getState().unitSystem).toBe('mm');
  });

  it('has correct aria-pressed when in inches mode', () => {
    act(() => {
      useUnitStore.getState().setUnitSystem('in');
    });
    render(<UnitToggle />);
    const button = screen.getByRole('button');
    expect(button.getAttribute('aria-pressed')).toBe('true');
  });

  it('has aria-pressed=false when in mm mode', () => {
    render(<UnitToggle />);
    const button = screen.getByRole('button');
    expect(button.getAttribute('aria-pressed')).toBe('false');
  });

  it('has descriptive aria-label', () => {
    render(<UnitToggle />);
    const button = screen.getByRole('button');
    expect(button.getAttribute('aria-label')).toContain('millimeters');
  });
});
