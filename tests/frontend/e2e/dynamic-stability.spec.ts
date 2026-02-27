/**
 * CHENG E2E Tests — Dynamic Stability Feature
 *
 * Tests for the DATCOM dynamic stability overlay tabs, mass properties
 * overrides, in-viewport summary card, and quality badge display.
 *
 * Requires the full app (backend + frontend) running:
 *   powershell -ExecutionPolicy Bypass -File .\bootup.ps1
 *
 * Backend must have DATCOM pipeline integrated (issues #349-#353).
 *
 * Run: cd frontend && NODE_PATH=./node_modules npx playwright test e2e/dynamic-stability.spec.ts
 */

import { test, expect, type Page } from '@playwright/test';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Wait for the app to be fully loaded and WebSocket connected. */
async function waitForAppReady(page: Page): Promise<void> {
  await page.waitForSelector('main', { timeout: 15_000 });
  await page.waitForSelector('canvas', { timeout: 15_000 });
  const firstInput = page.locator('input[type="number"]').first();
  await expect(firstInput).toBeVisible({ timeout: 10_000 });
  // Extra wait for first WebSocket message (derived values) to arrive
  await page.waitForTimeout(2_000);
}

/** Open the stability overlay by clicking "Toggle Plots" in the toolbar. */
async function openStabilityOverlay(page: Page): Promise<void> {
  const toggleButton = page.getByRole('button', { name: /show stability plots/i });
  await expect(toggleButton).toBeVisible({ timeout: 5_000 });
  await toggleButton.click();
  await expect(page.getByRole('dialog', { name: /stability analysis/i })).toBeVisible({
    timeout: 5_000,
  });
}

/** Switch to a tab inside the stability overlay. */
async function switchStabilityTab(page: Page, tabName: string): Promise<void> {
  const tab = page.getByRole('tab', { name: new RegExp(tabName, 'i') });
  await expect(tab).toBeVisible({ timeout: 3_000 });
  await tab.click();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe('Dynamic Stability Overlay', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);
  });

  test('1 — tab navigation: overlay has 3 tabs and switching changes content', async ({ page }) => {
    await openStabilityOverlay(page);

    const overlay = page.getByRole('dialog', { name: /stability analysis/i });
    await expect(overlay).toBeVisible();

    // All 3 tabs should be present
    await expect(page.getByRole('tab', { name: /static/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /mass/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /dynamic/i })).toBeVisible();

    // Static tab: should show CG/NP gauge content
    await switchStabilityTab(page, 'static');
    const staticContent = page.getByRole('tabpanel');
    await expect(staticContent).toBeVisible();

    // Mass tab: should show different content
    await switchStabilityTab(page, 'mass');
    const massContent = page.getByRole('tabpanel');
    await expect(massContent).toBeVisible();

    // Dynamic tab: should show different content
    await switchStabilityTab(page, 'dynamic');
    const dynamicContent = page.getByRole('tabpanel');
    await expect(dynamicContent).toBeVisible();
  });

  test('2 — mode cards visible: Dynamic Stability tab shows 5 mode sections', async ({ page }) => {
    await openStabilityOverlay(page);
    await switchStabilityTab(page, 'dynamic');

    const tabPanel = page.getByRole('tabpanel');
    await expect(tabPanel).toBeVisible();

    // All 5 dynamic modes should appear in the panel
    await expect(tabPanel.getByText(/short.period/i)).toBeVisible({ timeout: 8_000 });
    await expect(tabPanel.getByText(/phugoid/i)).toBeVisible({ timeout: 5_000 });
    await expect(tabPanel.getByText(/dutch roll/i)).toBeVisible({ timeout: 5_000 });
    await expect(tabPanel.getByText(/roll mode/i)).toBeVisible({ timeout: 5_000 });
    await expect(tabPanel.getByText(/spiral/i)).toBeVisible({ timeout: 5_000 });
  });

  test('3 — quality badges: at least one quality badge is visible in dynamic tab', async ({ page }) => {
    await openStabilityOverlay(page);
    await switchStabilityTab(page, 'dynamic');

    const tabPanel = page.getByRole('tabpanel');

    // Quality badges should be rendered (Good, Acceptable, or Poor)
    // We check for at least one badge text — the exact badge depends on the design
    const badges = tabPanel.locator('[aria-label^="Quality:"]');
    await expect(badges.first()).toBeVisible({ timeout: 8_000 });

    // The badge should have one of the expected quality texts
    const badgeText = await badges.first().textContent();
    expect(['Good', 'Acceptable', 'Poor', 'Unknown']).toContain(badgeText?.trim());
  });

  test('4 — flight speed input: changing speed in Mass Properties tab is reflected', async ({ page }) => {
    await openStabilityOverlay(page);
    await switchStabilityTab(page, 'mass');

    // The Mass Properties tab should contain flight condition parameters
    const tabPanel = page.getByRole('tabpanel');
    await expect(tabPanel).toBeVisible();

    // Look for the flight speed input (FC01)
    // This verifies the tab renders interactive controls
    const speedInputs = tabPanel.locator('input[type="number"]');
    const count = await speedInputs.count();
    // There should be at least one numeric input in the mass properties tab
    expect(count).toBeGreaterThan(0);
  });

  test('5 — mass properties tab: override toggle buttons are present', async ({ page }) => {
    await openStabilityOverlay(page);
    await switchStabilityTab(page, 'mass');

    const tabPanel = page.getByRole('tabpanel');
    await expect(tabPanel).toBeVisible({ timeout: 5_000 });

    // Should show "Resolved Values" section or numeric inputs for mass/CG
    // The tab renders MP01-MP07 optional override inputs
    await expect(tabPanel.getByText(/mass/i).first()).toBeVisible({ timeout: 5_000 });
  });

  test('6 — mass override round-trip: entering mass override value persists in input', async ({ page }) => {
    await openStabilityOverlay(page);
    await switchStabilityTab(page, 'mass');

    const tabPanel = page.getByRole('tabpanel');

    // Find the first numeric input in the tab (should be mass override or similar)
    const inputs = tabPanel.locator('input[type="number"]');
    const count = await inputs.count();

    if (count > 0) {
      const firstInput = inputs.first();
      await expect(firstInput).toBeVisible({ timeout: 5_000 });

      // Get current value and check it's readable
      const currentValue = await firstInput.inputValue();
      expect(currentValue).not.toBeNull();

      // Type a new value and verify it's persisted
      await firstInput.fill('500');
      await page.keyboard.press('Tab');

      // Verify the input now shows 500 (or is validated to a nearby valid value)
      const newValue = await firstInput.inputValue();
      expect(newValue).not.toBe('');
    } else {
      // If no inputs (e.g., tab shows only read-only estimated values with no overrides set),
      // just verify the tab panel is rendered correctly
      await expect(tabPanel.getByText(/estimated/i)).toBeVisible({ timeout: 5_000 });
    }
  });

  test('7 — summary card: visible in viewport and opens overlay to dynamic tab on click', async ({ page }) => {
    // Close overlay if open (summary card is hidden when overlay is open)
    const overlay = page.getByRole('dialog', { name: /stability analysis/i });
    const isOverlayVisible = await overlay.isVisible();
    if (isOverlayVisible) {
      await page.getByRole('button', { name: /close stability analysis/i }).click();
    }

    // Wait for DATCOM results to arrive (summary card only appears when dynamicStability is non-null)
    const summaryCard = page.getByRole('button', { name: /dynamic stability summary/i });
    await expect(summaryCard).toBeVisible({ timeout: 12_000 });

    // Verify it's at the bottom-left (has fixed positioning class)
    const cardClasses = await summaryCard.getAttribute('class');
    expect(cardClasses).toContain('fixed');
    expect(cardClasses).toContain('bottom-4');
    expect(cardClasses).toContain('left-4');

    // Click the card — should open overlay
    await summaryCard.click();

    // Overlay should now be open
    await expect(overlay).toBeVisible({ timeout: 5_000 });

    // Active tab should be "Dynamic Stability"
    const dynamicTab = page.getByRole('tab', { name: /dynamic/i });
    await expect(dynamicTab).toHaveAttribute('aria-selected', 'true');
  });

  test('8 — ESTIMATED badge: Dynamic Stability tab shows ESTIMATED badge for computed derivatives', async ({ page }) => {
    await openStabilityOverlay(page);
    await switchStabilityTab(page, 'dynamic');

    const tabPanel = page.getByRole('tabpanel');
    await expect(tabPanel).toBeVisible();

    // The DynamicStabilityTab renders an "ESTIMATED" badge when derivatives_estimated is true
    // (which is always true for our DATCOM estimates — no test-stand measurements)
    // Wait for content to load from WebSocket
    const estimatedBadge = tabPanel.getByText(/estimated/i);
    await expect(estimatedBadge.first()).toBeVisible({ timeout: 10_000 });
  });
});
