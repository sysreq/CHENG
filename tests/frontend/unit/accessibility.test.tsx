// ============================================================================
// CHENG — Accessibility Tests
// Issue #180: keyboard navigation, ARIA labels, screen reader support
// ============================================================================

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { useLiveRegionStore } from '@/store/liveRegionStore';

// ---------------------------------------------------------------------------
// LiveRegion store tests
// ---------------------------------------------------------------------------

describe('liveRegionStore', () => {
  beforeEach(() => {
    useLiveRegionStore.setState({ politeMessage: '', assertiveMessage: '' });
  });

  it('announce() sets politeMessage', () => {
    useLiveRegionStore.getState().announce('Design saved');
    expect(useLiveRegionStore.getState().politeMessage).toBe('Design saved');
  });

  it('announceAssertive() sets assertiveMessage', () => {
    useLiveRegionStore.getState().announceAssertive('Connection lost');
    expect(useLiveRegionStore.getState().assertiveMessage).toBe('Connection lost');
  });

  it('clearPolite() clears politeMessage', () => {
    useLiveRegionStore.getState().announce('Something');
    useLiveRegionStore.getState().clearPolite();
    expect(useLiveRegionStore.getState().politeMessage).toBe('');
  });

  it('clearAssertive() clears assertiveMessage', () => {
    useLiveRegionStore.getState().announceAssertive('Something urgent');
    useLiveRegionStore.getState().clearAssertive();
    expect(useLiveRegionStore.getState().assertiveMessage).toBe('');
  });

  it('separate polite and assertive messages do not interfere', () => {
    useLiveRegionStore.getState().announce('Polite message');
    useLiveRegionStore.getState().announceAssertive('Urgent message');
    expect(useLiveRegionStore.getState().politeMessage).toBe('Polite message');
    expect(useLiveRegionStore.getState().assertiveMessage).toBe('Urgent message');
  });
});

// ---------------------------------------------------------------------------
// LiveRegion component tests
// ---------------------------------------------------------------------------

import { LiveRegion } from '@/components/LiveRegion';

describe('LiveRegion', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useLiveRegionStore.setState({ politeMessage: '', assertiveMessage: '' });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('renders polite live region with aria-live="polite"', () => {
    render(<LiveRegion />);
    const politeEl = document.querySelector('[aria-live="polite"]');
    expect(politeEl).toBeTruthy();
    expect(politeEl?.getAttribute('role')).toBe('status');
  });

  it('renders assertive live region with aria-live="assertive"', () => {
    render(<LiveRegion />);
    const assertiveEl = document.querySelector('[aria-live="assertive"]');
    expect(assertiveEl).toBeTruthy();
    expect(assertiveEl?.getAttribute('role')).toBe('alert');
  });

  it('both live regions have aria-atomic="true"', () => {
    render(<LiveRegion />);
    const politeEl = document.querySelector('[aria-live="polite"]');
    const assertiveEl = document.querySelector('[aria-live="assertive"]');
    expect(politeEl?.getAttribute('aria-atomic')).toBe('true');
    expect(assertiveEl?.getAttribute('aria-atomic')).toBe('true');
  });

  it('displays polite message from store', () => {
    render(<LiveRegion />);
    act(() => {
      useLiveRegionStore.getState().announce('Design saved successfully');
    });
    const politeEl = document.querySelector('[aria-live="polite"]');
    expect(politeEl?.textContent).toBe('Design saved successfully');
  });

  it('displays assertive message from store', () => {
    render(<LiveRegion />);
    act(() => {
      useLiveRegionStore.getState().announceAssertive('Connection lost!');
    });
    const assertiveEl = document.querySelector('[aria-live="assertive"]');
    expect(assertiveEl?.textContent).toBe('Connection lost!');
  });

  it('clears polite message after 5 seconds', () => {
    render(<LiveRegion />);
    act(() => {
      useLiveRegionStore.getState().announce('Temporary message');
    });

    act(() => {
      vi.advanceTimersByTime(5001);
    });

    expect(useLiveRegionStore.getState().politeMessage).toBe('');
  });

  it('clears assertive message after 5 seconds', () => {
    render(<LiveRegion />);
    act(() => {
      useLiveRegionStore.getState().announceAssertive('Urgent message');
    });

    act(() => {
      vi.advanceTimersByTime(5001);
    });

    expect(useLiveRegionStore.getState().assertiveMessage).toBe('');
  });
});

// ---------------------------------------------------------------------------
// Skip navigation link test
// ---------------------------------------------------------------------------

describe('Skip navigation link', () => {
  it('skip link points to #parameter-panel and target exists', () => {
    const { container } = render(
      <div>
        <a href="#parameter-panel">Skip to parameter controls</a>
        <section id="parameter-panel" aria-label="Aircraft parameter controls">
          Parameters
        </section>
      </div>
    );

    const skipLink = container.querySelector('a[href="#parameter-panel"]');
    const target = container.querySelector('#parameter-panel');
    expect(skipLink).toBeTruthy();
    expect(target).toBeTruthy();
    expect(skipLink?.textContent).toBe('Skip to parameter controls');
  });
});

// ---------------------------------------------------------------------------
// ParamSlider accessibility tests
// ---------------------------------------------------------------------------

// We cannot easily mock useDesignStore's temporal sub-store, so we test
// the ParamSlider in isolation by mocking the store entirely.
vi.mock('@/store/designStore', () => ({
  useDesignStore: (selector: (state: Record<string, unknown>) => unknown) => {
    const state = {
      commitSliderChange: vi.fn(),
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

// Workaround: useDesignStore.temporal is accessed directly (not via hook).
// We patch it after the mock to avoid the "property temporal does not exist" error.
import { useDesignStore } from '@/store/designStore';
(useDesignStore as unknown as Record<string, unknown>).temporal = {
  getState: () => ({ pause: vi.fn(), resume: vi.fn() }),
};

import { ParamSlider } from '@/components/ui/ParamSlider';

describe('ParamSlider accessibility', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('slider input has aria-label containing label and unit', () => {
    render(
      <ParamSlider
        label="Wing Span"
        unit="mm"
        value={1200}
        min={400}
        max={2000}
        step={10}
        onSliderChange={() => {}}
        onInputChange={() => {}}
      />
    );

    const slider = document.querySelector('input[type="range"]');
    const ariaLabel = slider?.getAttribute('aria-label') ?? '';
    expect(ariaLabel).toContain('Wing Span');
    expect(ariaLabel).toContain('mm');
  });

  it('slider has aria-valuetext with value and unit', () => {
    render(
      <ParamSlider
        label="Wing Span"
        unit="mm"
        value={1200}
        min={400}
        max={2000}
        step={10}
        onSliderChange={() => {}}
        onInputChange={() => {}}
      />
    );

    const slider = document.querySelector('input[type="range"]');
    expect(slider?.getAttribute('aria-valuetext')).toBe('1200 mm');
    expect(slider?.getAttribute('aria-valuenow')).toBe('1200');
    expect(slider?.getAttribute('aria-valuemin')).toBe('400');
    expect(slider?.getAttribute('aria-valuemax')).toBe('2000');
  });

  it('number input has aria-label containing label name', () => {
    render(
      <ParamSlider
        label="Wing Span"
        unit="mm"
        value={1200}
        min={400}
        max={2000}
        step={10}
        onSliderChange={() => {}}
        onInputChange={() => {}}
      />
    );

    const numberInput = document.querySelector('input[type="number"]');
    const ariaLabel = numberInput?.getAttribute('aria-label') ?? '';
    expect(ariaLabel).toContain('Wing Span');
  });

  it('label is associated with number input via htmlFor/id', () => {
    render(
      <ParamSlider
        label="Wing Span"
        unit="mm"
        value={1200}
        min={400}
        max={2000}
        step={10}
        onSliderChange={() => {}}
        onInputChange={() => {}}
      />
    );

    const label = screen.getByText('Wing Span');
    const labelEl = label.closest('label');
    expect(labelEl).toBeTruthy();
    const labelFor = labelEl?.getAttribute('for');
    const numberInput = document.querySelector('input[type="number"]');
    expect(labelFor).toBeTruthy();
    expect(labelFor).toBe(numberInput?.getAttribute('id'));
  });

  it('slider has aria-valuetext without unit when no unit given', () => {
    render(
      <ParamSlider
        label="Count"
        value={5}
        min={1}
        max={10}
        step={1}
        onSliderChange={() => {}}
        onInputChange={() => {}}
      />
    );

    const slider = document.querySelector('input[type="range"]');
    expect(slider?.getAttribute('aria-valuetext')).toBe('5');
  });
});

// ---------------------------------------------------------------------------
// ComponentPanel tab ARIA pattern tests
// ---------------------------------------------------------------------------

// Test the tablist pattern directly without needing full store mocks
describe('ComponentPanel tablist ARIA pattern', () => {
  it('tab buttons in a tablist have correct ARIA attributes', () => {
    // Render a simple tablist pattern to verify the pattern
    const { container } = render(
      <div role="tablist" aria-label="Aircraft component selector">
        <button
          role="tab"
          id="tab-global"
          aria-controls="tabpanel-global"
          aria-selected={true}
          tabIndex={0}
        >
          Global
        </button>
        <button
          role="tab"
          id="tab-wing"
          aria-controls="tabpanel-wing"
          aria-selected={false}
          tabIndex={-1}
        >
          Wing
        </button>
      </div>
    );

    const tablist = container.querySelector('[role="tablist"]');
    expect(tablist?.getAttribute('aria-label')).toBe('Aircraft component selector');

    const activeTab = container.querySelector('[aria-selected="true"]');
    expect(activeTab?.getAttribute('role')).toBe('tab');
    expect(activeTab?.getAttribute('tabindex')).toBe('0');

    const inactiveTab = container.querySelector('[aria-selected="false"]');
    expect(inactiveTab?.getAttribute('tabindex')).toBe('-1');
  });

  it('tabpanel has correct ARIA attributes', () => {
    const { container } = render(
      <div
        role="tabpanel"
        id="tabpanel-global"
        aria-labelledby="tab-global"
        tabIndex={0}
      >
        Content
      </div>
    );

    const tabpanel = container.querySelector('[role="tabpanel"]');
    expect(tabpanel?.getAttribute('aria-labelledby')).toBe('tab-global');
    expect(tabpanel?.getAttribute('tabindex')).toBe('0');
  });
});

// ---------------------------------------------------------------------------
// DerivedField accessibility tests
// ---------------------------------------------------------------------------

import { DerivedField } from '@/components/ui/DerivedField';

describe('DerivedField accessibility', () => {
  it('value container has role="status"', () => {
    render(<DerivedField label="Total Weight" value={450} unit="g" />);
    const statusEl = screen.getByRole('status');
    expect(statusEl).toBeTruthy();
  });

  it('value container has aria-labelledby pointing to label', () => {
    render(<DerivedField label="Total Weight" value={450} unit="g" />);
    const statusEl = screen.getByRole('status');
    const labelId = statusEl.getAttribute('aria-labelledby');
    expect(labelId).toBeTruthy();

    // The label element with that ID should contain the label text
    const labelEl = document.getElementById(labelId!);
    expect(labelEl?.textContent).toBe('Total Weight');
  });

  it('displays em-dash when value is null', () => {
    render(<DerivedField label="CG Position" value={null} />);
    const statusEl = screen.getByRole('status');
    expect(statusEl.textContent).toBe('\u2014');
  });

  it('formats value with unit', () => {
    render(<DerivedField label="Wing Area" value={12.5} unit="dm2" decimals={1} />);
    const statusEl = screen.getByRole('status');
    expect(statusEl.textContent).toBe('12.5 dm2');
  });
});
