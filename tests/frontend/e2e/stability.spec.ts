/**
 * CHENG E2E Tests — Static Stability Feature
 *
 * Tests for the stability plots overlay panel, live metric updates,
 * keyboard accessibility, and screen reader live region announcements.
 *
 * Requires the full app (backend + frontend) running:
 *   powershell -ExecutionPolicy Bypass -File .\bootup.ps1
 *
 * Backend must have stability.py integrated (issues #307, #309, #311).
 *
 * Run: cd frontend && NODE_PATH=./node_modules npx playwright test e2e/stability.spec.ts
 */

import { test, expect, type Page } from '@playwright/test';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Wait for the app to be fully loaded and WebSocket connected. */
async function waitForAppReady(page: Page): Promise<void> {
  await page.waitForSelector('main', { timeout: 15_000 });
  await page.waitForSelector('canvas', { timeout: 15_000 });
  // Wait for WebSocket connection: "Connected" indicator OR any numeric input visible
  const connectedIndicator = page.getByText('Connected');
  const firstInput = page.locator('input[type="number"]').first();
  await expect(connectedIndicator.or(firstInput)).toBeVisible({ timeout: 10_000 });
}

/** Open the stability overlay by clicking "Toggle Plots" in the toolbar. */
async function openStabilityOverlay(page: Page): Promise<void> {
  const toggleButton = page.getByRole('button', { name: /show stability plots/i });
  await expect(toggleButton).toBeVisible({ timeout: 5_000 });
  await toggleButton.click();
  // Wait for the overlay dialog to appear
  await expect(page.getByRole('dialog', { name: /stability plots/i })).toBeVisible({
    timeout: 5_000,
  });
}

/** Close the stability overlay via the × button, asserting focus returns to toggle. */
async function closeStabilityOverlay(page: Page): Promise<void> {
  const closeButton = page.getByRole('button', { name: /close stability plots/i });
  await closeButton.click();
  await expect(page.getByRole('dialog', { name: /stability plots/i })).not.toBeVisible({
    timeout: 3_000,
  });
}

/** Load a built-in preset via the Toolbar Presets dropdown and confirm. */
async function loadPreset(page: Page, presetName: string): Promise<void> {
  // Target the Presets button in the toolbar specifically (not any other button)
  const presetsButton = page.getByRole('toolbar').getByRole('button', { name: /presets/i });
  await presetsButton.click();
  // Click the preset menu item
  await page.getByRole('menuitem', { name: new RegExp(presetName, 'i') }).click();
  // Confirm in the alert dialog
  const confirmButton = page.locator('[role="alertdialog"] button', { hasText: 'Apply' });
  await expect(confirmButton).toBeVisible({ timeout: 3_000 });
  await confirmButton.click();
  await expect(confirmButton).not.toBeVisible({ timeout: 3_000 });
}

/** Set a slider value using its number input. */
async function setSliderValue(page: Page, labelText: string, value: string): Promise<void> {
  // Use getByLabel for the number input if the label is formally associated.
  // Fallback: locate by container text + number input.
  const container = page.locator('div.mb-3', {
    has: page.locator(`text="${labelText}"`),
  });
  const input = container.locator('input[type="number"]');
  await input.click();
  await input.fill(value);
  await input.press('Enter');
}

// ---------------------------------------------------------------------------
// Test Suite
// ---------------------------------------------------------------------------

test.describe('Stability Feature', () => {

  // ─── Test 1: Toggle Plots button is visible and opens the overlay ──────────

  test('Toggle Plots button is visible in toolbar and opens stability overlay', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // The "Toggle Plots" button should be in the toolbar
    const toggleButton = page.getByRole('button', { name: /show stability plots/i });
    await expect(toggleButton).toBeVisible();

    // Verify aria-pressed=false when overlay is closed
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'false');

    // Click to open the overlay
    await toggleButton.click();

    // Overlay dialog should appear
    const overlay = page.getByRole('dialog', { name: /stability plots/i });
    await expect(overlay).toBeVisible({ timeout: 5_000 });

    // Button should now reflect pressed state
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'true');
  });

  // ─── Test 2: Stability gauges render with real backend values ─────────────

  test('Stability gauges render with computed values after WebSocket connects', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);
    await openStabilityOverlay(page);

    // Wait for WebSocket to deliver derived values — loading state should disappear
    await expect(page.getByText(/waiting for preview data/i)).not.toBeVisible({
      timeout: 10_000,
    });

    // CgVsNpGauge → role="img" with specific aria-label about CG and neutral point
    await expect(
      page.getByRole('img', { name: /neutral point/i })
    ).toBeVisible({ timeout: 5_000 });

    // StaticMarginGauge → role="progressbar" with aria-label about static margin
    await expect(
      page.getByRole('progressbar', { name: /static margin/i })
    ).toBeVisible({ timeout: 5_000 });

    // The overlay should show either STABLE, MARGINAL, OVER-STABLE, or UNSTABLE
    const stableLabel = page.getByText('STABLE');
    const marginalLabel = page.getByText('MARGINAL');
    const overStableLabel = page.getByText('OVER-STABLE');
    const unstableLabel = page.getByText('UNSTABLE');
    await expect(
      stableLabel.or(marginalLabel).or(overStableLabel).or(unstableLabel)
    ).toBeVisible({ timeout: 5_000 });
  });

  // ─── Test 3: Static margin updates when tail arm changes ──────────────────

  test('Static margin updates when tail arm slider is changed', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);
    await openStabilityOverlay(page);

    // Wait for initial WebSocket values to arrive
    await expect(page.getByText(/waiting for preview data/i)).not.toBeVisible({
      timeout: 10_000,
    });

    // Record initial static margin value
    const progressbar = page.getByRole('progressbar', { name: /static margin/i });
    await expect(progressbar).toBeVisible({ timeout: 5_000 });
    const initialValue = await progressbar.getAttribute('aria-valuenow');

    // Navigate to Tail tab and increase the tail arm (longer tail = more pitch stability)
    await page.getByRole('tab', { name: /tail/i }).click();
    await setSliderValue(page, 'Tail Arm', '400');

    // Poll for the progressbar value to change — avoid fixed waitForTimeout
    await expect.poll(
      async () => progressbar.getAttribute('aria-valuenow'),
      {
        message: 'Static margin should update after tail arm change',
        timeout: 8_000,
        intervals: [300, 500, 1000],
      }
    ).not.toBe(initialValue);

    // With a longer tail arm, static margin should increase (more stability)
    const newValue = await progressbar.getAttribute('aria-valuenow');
    const initialParsed = parseFloat(initialValue ?? '0');
    const newParsed = parseFloat(newValue ?? '0');
    expect(newParsed).toBeGreaterThan(initialParsed);
  });

  // ─── Test 4: Trainer preset gives stable static margin ────────────────────

  test('Trainer preset shows stable static margin (not UNSTABLE)', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Load the Trainer preset
    await loadPreset(page, 'Trainer');

    // Open stability overlay
    await openStabilityOverlay(page);

    // Wait for values to arrive
    await expect(page.getByText(/waiting for preview data/i)).not.toBeVisible({
      timeout: 10_000,
    });

    // Trainer preset should produce a non-unstable aircraft
    const stableLabel = page.getByText('STABLE');
    const marginalLabel = page.getByText('MARGINAL');
    const overStableLabel = page.getByText('OVER-STABLE');
    await expect(
      stableLabel.or(marginalLabel).or(overStableLabel)
    ).toBeVisible({ timeout: 5_000 });

    // The static margin progressbar should have a non-negative value for Trainer
    const progressbar = page.getByRole('progressbar', { name: /static margin/i });
    const valuenow = await progressbar.getAttribute('aria-valuenow');
    const parsed = parseFloat(valuenow ?? 'NaN');
    expect(isNaN(parsed)).toBe(false);
    expect(parsed).toBeGreaterThanOrEqual(0);
  });

  // ─── Test 5: Escape key closes the overlay ────────────────────────────────

  test('Escape key closes the stability overlay', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);
    await openStabilityOverlay(page);

    // Overlay is open
    const overlay = page.getByRole('dialog', { name: /stability plots/i });
    await expect(overlay).toBeVisible();

    // Press Escape
    await page.keyboard.press('Escape');

    // Overlay should close
    await expect(overlay).not.toBeVisible({ timeout: 3_000 });

    // Toggle button should now show aria-pressed=false
    const toggleButton = page.getByRole('button', { name: /show stability plots/i });
    await expect(toggleButton).toHaveAttribute('aria-pressed', 'false');
  });

  // ─── Test 6: Close button (×) dismisses the overlay and restores focus ────

  test('Close button dismisses overlay and returns focus to Toggle Plots button', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    const toggleButton = page.getByRole('button', { name: /show stability plots/i });
    await openStabilityOverlay(page);

    // Overlay is open
    const overlay = page.getByRole('dialog', { name: /stability plots/i });
    await expect(overlay).toBeVisible();

    // Click the × close button
    await closeStabilityOverlay(page);

    // Overlay should be gone
    await expect(overlay).not.toBeVisible();

    // Focus should return to the Toggle Plots button
    await expect(toggleButton).toBeFocused();
  });

  // ─── Test 7: Assertive live region is present in DOM ──────────────────────

  test('Assertive live region is present for screen reader announcements', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // The assertive live region should always be in the DOM (rendered by LiveRegion component)
    const assertiveRegion = page.locator('[aria-live="assertive"]');
    await expect(assertiveRegion).toBeAttached({ timeout: 5_000 });

    // The polite live region should also be present
    const politeRegion = page.locator('[aria-live="polite"]').first();
    await expect(politeRegion).toBeAttached({ timeout: 5_000 });
  });

  // ─── Test 8: Expandable raw values section shows labeled fields ───────────

  test('Expandable raw values section shows all six labeled derived fields', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);
    await openStabilityOverlay(page);

    // Wait for values
    await expect(page.getByText(/waiting for preview data/i)).not.toBeVisible({
      timeout: 10_000,
    });

    // The raw values section uses a <details> element — it is collapsed by default
    const rawValuesSummary = page.getByText('Raw Values');
    await expect(rawValuesSummary).toBeVisible({ timeout: 5_000 });

    // Expand the section
    await rawValuesSummary.click();

    // After expanding, the labeled DerivedField sections should appear
    await expect(page.getByText('CG Position')).toBeVisible({ timeout: 3_000 });
    await expect(page.getByText('Neutral Point')).toBeVisible({ timeout: 3_000 });
    await expect(page.getByText('Static Margin')).toBeVisible({ timeout: 3_000 });
    await expect(page.getByText('Tail Volume V_h')).toBeVisible({ timeout: 3_000 });
    await expect(page.getByText('Wing Loading')).toBeVisible({ timeout: 3_000 });
    await expect(page.getByText('MAC')).toBeVisible({ timeout: 3_000 });
  });

});
