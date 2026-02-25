// ============================================================================
// CHENG — Shared ControlSurfaceSection component tests (Issue #272)
// ============================================================================

import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ControlSurfaceSection } from '@/components/panels/shared/ControlSurfaceSection';

describe('ControlSurfaceSection (shared component)', () => {
  it('renders the title in the toggle button', () => {
    render(
      <ControlSurfaceSection title="Ailerons">
        <span>Child content</span>
      </ControlSurfaceSection>,
    );
    expect(screen.getByText('Ailerons')).toBeTruthy();
  });

  it('starts collapsed — children are not visible', () => {
    render(
      <ControlSurfaceSection title="Elevator">
        <span>Elevator child</span>
      </ControlSurfaceSection>,
    );
    expect(screen.queryByText('Elevator child')).toBeNull();
  });

  it('expands children when the button is clicked', () => {
    render(
      <ControlSurfaceSection title="Rudder">
        <span>Rudder child</span>
      </ControlSurfaceSection>,
    );
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    expect(screen.getByText('Rudder child')).toBeTruthy();
  });

  it('collapses children when clicked a second time', () => {
    render(
      <ControlSurfaceSection title="Elevons">
        <span>Elevon child</span>
      </ControlSurfaceSection>,
    );
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    expect(screen.getByText('Elevon child')).toBeTruthy();
    fireEvent.click(btn);
    expect(screen.queryByText('Elevon child')).toBeNull();
  });

  it('sets aria-expanded correctly on the toggle button', () => {
    render(
      <ControlSurfaceSection title="Ailerons">
        <span>child</span>
      </ControlSurfaceSection>,
    );
    const btn = screen.getByRole('button');
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(btn);
    expect(btn.getAttribute('aria-expanded')).toBe('true');
  });

  it('renders the optional tooltip on the button', () => {
    render(
      <ControlSurfaceSection title="Test" tooltip="My tooltip">
        <span>child</span>
      </ControlSurfaceSection>,
    );
    const btn = screen.getByRole('button');
    expect(btn.getAttribute('title')).toBe('My tooltip');
  });

  it('renders without a tooltip when none is provided', () => {
    render(
      <ControlSurfaceSection title="No tooltip">
        <span>child</span>
      </ControlSurfaceSection>,
    );
    const btn = screen.getByRole('button');
    // title attribute should be absent or empty when tooltip prop is omitted
    expect(btn.getAttribute('title')).toBeNull();
  });
});
