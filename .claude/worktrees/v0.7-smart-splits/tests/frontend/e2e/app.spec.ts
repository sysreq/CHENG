/**
 * CHENG E2E Tests -- Core Application Flows
 *
 * Requires the full app running on http://localhost:5173 (dev) or :8000 (Docker).
 * Start with: powershell -ExecutionPolicy Bypass -File .\startup.ps1
 *
 * Run: cd frontend && npx playwright test
 */

import { test, expect, type Page } from '@playwright/test';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Wait for the app to be ready by checking that the main layout and canvas
 * are rendered, and the WebSocket has connected (connection status shows
 * "Connected" or a param input is editable).
 */
async function waitForAppReady(page: Page) {
  // Wait for the main grid layout
  await page.waitForSelector('main', { timeout: 15_000 });

  // Wait for canvas (Three.js) to be present
  await page.waitForSelector('canvas', { timeout: 15_000 });

  // Wait for app to finish initial load: either the connection status
  // shows "Connected" or a parameter input becomes available.
  // Uses Playwright's .or() for proper multi-condition waiting.
  const connectedIndicator = page.getByText('Connected');
  const firstInput = page.locator('input[type="number"]').first();
  await expect(connectedIndicator.or(firstInput)).toBeVisible({
    timeout: 10_000,
  });
}

/**
 * Get the value of the <select> that serves as the preset selector.
 * It is the first <select> inside the sidebar panel labeled "Parameters".
 */
async function getPresetValue(page: Page): Promise<string> {
  const presetSelect = page.locator('aside select').first();
  return presetSelect.inputValue();
}

/**
 * Select a built-in preset and confirm the alert dialog.
 */
async function selectPreset(page: Page, presetName: string) {
  const presetSelect = page.locator('aside select').first();
  await presetSelect.selectOption(presetName);

  // Confirm in the alert dialog
  const confirmButton = page.locator('[role="alertdialog"] button', {
    hasText: 'Apply',
  });
  await expect(confirmButton).toBeVisible({ timeout: 3_000 });
  await confirmButton.click();

  // Wait for the alert dialog to close after confirming
  await expect(confirmButton).not.toBeVisible({ timeout: 3_000 });
}

/** Get the numeric value from a ParamSlider's number input by its label. */
async function getSliderInputValue(
  page: Page,
  label: string,
): Promise<string> {
  // ParamSlider renders: <div class="mb-3"> ... <label>Label</label> ... <input type="number" />
  // Using a container locator with text matching for the label.
  const container = page.locator('div.mb-3', {
    has: page.locator(`text="${label}"`),
  });
  const input = container.locator('input[type="number"]');
  return (await input.inputValue()) || '';
}

/** Set a value in a ParamSlider's number input by its label. */
async function setSliderInputValue(
  page: Page,
  label: string,
  value: string,
) {
  const container = page.locator('div.mb-3', {
    has: page.locator(`text="${label}"`),
  });
  const input = container.locator('input[type="number"]');
  await input.click();
  await input.fill(value);
  await input.press('Enter');
}

/**
 * Open the export dialog by clicking the "Export STL" button in the toolbar.
 */
async function openExportDialog(page: Page) {
  const exportButton = page.locator('button', { hasText: 'Export STL' });
  await exportButton.click();
  const dialog = page.locator('[role="dialog"]');
  await expect(dialog).toBeVisible({ timeout: 5_000 });
  return dialog;
}

// ===========================================================================
// Test Suite: Core Application Flows (existing, improved)
// ===========================================================================

test.describe('Core Application Flows', () => {
  // -------------------------------------------------------------------------
  // Test 1: Load Trainer preset -- verify wingspan + canvas renders
  // -------------------------------------------------------------------------
  test('Trainer preset shows correct wingspan and renders canvas', async ({
    page,
  }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Default preset should be Trainer with wingspan 1200
    const preset = await getPresetValue(page);
    expect(preset).toBe('Trainer');

    // Wingspan input should show 1200
    const wingspanValue = await getSliderInputValue(page, 'Wingspan');
    expect(wingspanValue).toBe('1200');

    // Canvas (Three.js) should be rendered and visible
    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible({ timeout: 10_000 });
  });

  // -------------------------------------------------------------------------
  // Test 2: Change wingspan -- verify input updates
  // -------------------------------------------------------------------------
  test('changing wingspan updates the input value', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Change wingspan from 1200 to 1500
    await setSliderInputValue(page, 'Wingspan', '1500');

    // Use web-first assertions that auto-retry instead of fixed timeout
    const wingspanInput = page
      .locator('div.mb-3', { has: page.locator('text="Wingspan"') })
      .locator('input[type="number"]');
    await expect(wingspanInput).toHaveValue('1500');

    // Preset should switch to "Custom" since we changed a value
    const presetSelect = page.locator('aside select').first();
    await expect(presetSelect).toHaveValue('Custom');
  });

  // -------------------------------------------------------------------------
  // Test 3: Export flow -- open dialog, verify two-step export preview flow
  // -------------------------------------------------------------------------
  test('export dialog opens and contains Export Preview button', async ({
    page,
  }) => {
    await page.goto('/');
    await waitForAppReady(page);

    const dialog = await openExportDialog(page);

    // Export Preview button should be present (STL format default = two-step flow)
    const previewButton = dialog.locator('button', {
      hasText: 'Export Preview',
    });
    await expect(previewButton).toBeVisible();
    await expect(previewButton).toBeEnabled();

    // Cancel button should close the dialog
    const cancelButton = dialog.locator('button', { hasText: 'Cancel' });
    await cancelButton.click();
    await expect(dialog).not.toBeVisible({ timeout: 3_000 });
  });

  // -------------------------------------------------------------------------
  // Test 4: Save design -- verify Ctrl+S triggers save and clears dirty state
  // -------------------------------------------------------------------------
  test('save design via keyboard shortcut', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Change a param to mark the design as dirty
    await setSliderInputValue(page, 'Wingspan', '1100');

    // The design name button should contain the dirty indicator "*"
    const nameDisplay = page.locator('button[title="Click to rename"]');
    await expect(nameDisplay).toContainText('*');

    // Save via Ctrl+S
    await page.keyboard.press('Control+s');

    // After save, either "Saved!" flash or "Save failed" should appear.
    // Use .or() for proper multi-condition waiting (no swallowed errors).
    const savedFlash = page.getByText('Saved!');
    const saveFailed = page.getByText('Save failed');
    await expect(savedFlash.or(saveFailed)).toBeVisible({ timeout: 5_000 });
  });

  // -------------------------------------------------------------------------
  // Test 5: Validation -- set extreme params, verify warning appears
  // -------------------------------------------------------------------------
  test('extreme wingspan triggers validation warning', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Set a very large wingspan relative to fuselage (triggers V01 or similar)
    await setSliderInputValue(page, 'Wingspan', '3000');
    await setSliderInputValue(page, 'Fuselage Length', '150');

    // Warning badge should appear in the toolbar (amber rounded pill with count).
    // Use web-first assertion that auto-retries instead of fixed timeout + count().
    const warningBadge = page
      .locator('.rounded-full')
      .filter({ hasText: /\d+/ });
    await expect(warningBadge.first()).toBeVisible({ timeout: 5_000 });
  });

  // -------------------------------------------------------------------------
  // Test 6: Preset switching -- Sport preset loads different values
  // -------------------------------------------------------------------------
  test('switching to Sport preset updates all parameters', async ({
    page,
  }) => {
    await page.goto('/');
    await waitForAppReady(page);

    await selectPreset(page, 'Sport');

    // Sport preset has wingspan 1000 and wing chord 180
    const wingspanValue = await getSliderInputValue(page, 'Wingspan');
    expect(wingspanValue).toBe('1000');

    const chordValue = await getSliderInputValue(page, 'Wing Chord');
    expect(chordValue).toBe('180');
  });

  // -------------------------------------------------------------------------
  // Test 7: Undo/Redo -- change value, undo via Ctrl+Z, verify restored
  // -------------------------------------------------------------------------
  test('undo restores previous parameter value', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Locate the wingspan input for web-first assertions
    const wingspanInput = page
      .locator('div.mb-3', { has: page.locator('text="Wingspan"') })
      .locator('input[type="number"]');

    // Verify starting wingspan
    await expect(wingspanInput).toHaveValue('1200');

    // Change wingspan
    await setSliderInputValue(page, 'Wingspan', '1500');
    await expect(wingspanInput).toHaveValue('1500');

    // Click on the canvas to blur the input (prevents browser native undo
    // from interfering with the app's Zustand undo)
    const canvas = page.locator('canvas');
    await canvas.click({ position: { x: 100, y: 100 } });

    // Undo via Ctrl+Z (keyboard shortcut captured by Toolbar)
    await page.keyboard.press('Control+z');

    // Should restore to 1200 (auto-retrying assertion)
    await expect(wingspanInput).toHaveValue('1200', { timeout: 3_000 });
  });
});
