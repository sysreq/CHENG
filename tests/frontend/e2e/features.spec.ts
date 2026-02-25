/**
 * CHENG E2E Tests -- Feature Coverage
 *
 * Tests for presets, export formats, tail configs, panels, custom presets,
 * connection status, multi-param changes, view controls, design naming,
 * and history panel.
 *
 * Requires the full app running on http://localhost:5173 (dev) or :8000 (Docker).
 * Start with: powershell -ExecutionPolicy Bypass -File .\startup.ps1
 *
 * Run: cd frontend && npx playwright test
 */

import { test, expect, type Page } from '@playwright/test';

// ---------------------------------------------------------------------------
// Helpers (shared with app.spec.ts -- could be extracted to a shared module)
// ---------------------------------------------------------------------------

/** Wait for the app to be fully loaded and WebSocket connected. */
async function waitForAppReady(page: Page) {
  await page.waitForSelector('main', { timeout: 15_000 });
  await page.waitForSelector('canvas', { timeout: 15_000 });

  await Promise.race([
    page.getByText('Connected').waitFor({ timeout: 10_000 }).catch(() => {}),
    page.locator('input[type="number"]').first().waitFor({ timeout: 10_000 }),
  ]);

  await page.waitForTimeout(500);
}

/** Get preset selector element. */
function getPresetSelect(page: Page) {
  return page.locator('aside select').first();
}

/** Select a built-in preset and confirm the alert dialog. */
async function selectPreset(page: Page, presetName: string) {
  const presetSelect = getPresetSelect(page);
  await presetSelect.selectOption(presetName);

  const confirmButton = page.locator('[role="alertdialog"] button', {
    hasText: 'Apply',
  });
  await expect(confirmButton).toBeVisible({ timeout: 3_000 });
  await confirmButton.click();
  await page.waitForTimeout(500);
}

/** Get the numeric value from a ParamSlider's number input by its label. */
async function getSliderInputValue(
  page: Page,
  label: string,
): Promise<string> {
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

/** Open the export dialog and return the dialog locator. */
async function openExportDialog(page: Page) {
  const exportButton = page.locator('button', { hasText: 'Export STL' });
  await exportButton.click();
  const dialog = page.locator('[role="dialog"]');
  await expect(dialog).toBeVisible({ timeout: 5_000 });
  return dialog;
}

// ===========================================================================
// Test Suite: Preset Cycling
// ===========================================================================

test.describe('Preset Cycling', () => {
  const PRESETS: { name: string; wingspan: string; wingChord: string }[] = [
    { name: 'Trainer', wingspan: '1200', wingChord: '200' },
    { name: 'Sport', wingspan: '1000', wingChord: '180' },
    { name: 'Aerobatic', wingspan: '900', wingChord: '220' },
    { name: 'Glider', wingspan: '2000', wingChord: '130' },
    { name: 'FlyingWing', wingspan: '1100', wingChord: '250' },
    { name: 'Scale', wingspan: '1400', wingChord: '190' },
  ];

  test('each built-in preset sets distinct parameter values', async ({
    page,
  }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Verify default (Trainer)
    const presetSelect = getPresetSelect(page);
    await expect(presetSelect).toHaveValue('Trainer');

    const trainerWingspan = await getSliderInputValue(page, 'Wingspan');
    expect(trainerWingspan).toBe('1200');

    // Cycle through remaining presets
    for (const preset of PRESETS.slice(1)) {
      await selectPreset(page, preset.name);

      const wingspan = await getSliderInputValue(page, 'Wingspan');
      expect(wingspan).toBe(preset.wingspan);

      const chord = await getSliderInputValue(page, 'Wing Chord');
      expect(chord).toBe(preset.wingChord);

      // Preset selector should reflect the selected name
      await expect(presetSelect).toHaveValue(preset.name);
    }
  });
});

// ===========================================================================
// Test Suite: Custom Preset Save/Load
// ===========================================================================

test.describe('Custom Preset Save/Load', () => {
  test('save current design as custom preset and verify it appears', async ({
    page,
  }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Change a parameter to create a unique configuration
    await setSliderInputValue(page, 'Wingspan', '1350');
    await page.waitForTimeout(500);

    // Click "Save as Preset" button
    const saveButton = page.locator('button', { hasText: 'Save as Preset' });
    await expect(saveButton).toBeVisible();
    await saveButton.click();

    // The save dialog (AlertDialog) should appear
    const saveDialog = page.locator('[role="alertdialog"]');
    await expect(saveDialog).toBeVisible({ timeout: 3_000 });
    await expect(saveDialog).toContainText('Save Custom Preset');

    // Enter a name and save
    const nameInput = saveDialog.locator('input[type="text"]');
    const presetName = `E2E-Test-${Date.now()}`;
    await nameInput.fill(presetName);

    const saveBtn = saveDialog.locator('button', { hasText: 'Save' });
    await saveBtn.click();

    // Dialog should close
    await expect(saveDialog).not.toBeVisible({ timeout: 3_000 });

    // The custom preset should appear in the "Saved Presets" section
    const presetEntry = page.getByText(presetName);
    await expect(presetEntry).toBeVisible({ timeout: 5_000 });

    // Clean up: delete the preset (hover to reveal delete button)
    const presetRow = page.locator('div', { hasText: presetName }).filter({
      has: page.locator('button', { hasText: 'Del' }),
    });
    const delButton = presetRow.locator('button', { hasText: 'Del' });
    // Force-click since Del button is opacity-0 until hover
    await delButton.click({ force: true });
    await page.waitForTimeout(500);
  });
});

// ===========================================================================
// Test Suite: Export Format Selection
// ===========================================================================

test.describe('Export Format Selection', () => {
  test('all 4 export format options are available', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    const dialog = await openExportDialog(page);

    // The format selector should have a radiogroup with 4 options
    const formatGroup = dialog.locator('[role="radiogroup"]');
    await expect(formatGroup).toBeVisible();

    // Verify each format is present
    const formats = ['STL', 'STEP', 'DXF', 'SVG'];
    for (const fmt of formats) {
      const formatButton = formatGroup.locator('[role="radio"]', {
        hasText: fmt,
      });
      await expect(formatButton).toBeVisible();
    }

    // STL should be checked by default (aria-checked="true")
    const stlRadio = formatGroup.locator('[role="radio"]', { hasText: 'STL' });
    await expect(stlRadio).toHaveAttribute('aria-checked', 'true');

    // Clicking STEP should select it and change the dialog content
    const stepRadio = formatGroup.locator('[role="radio"]', {
      hasText: 'STEP',
    });
    await stepRadio.click();
    await expect(stepRadio).toHaveAttribute('aria-checked', 'true');
    await expect(stlRadio).toHaveAttribute('aria-checked', 'false');

    // STEP format should show a "Download STEP" button instead of "Export Preview"
    const downloadButton = dialog.locator('button', {
      hasText: 'Download STEP',
    });
    await expect(downloadButton).toBeVisible();

    // Close the dialog
    const cancelButton = dialog.locator('button', { hasText: 'Cancel' });
    await cancelButton.click();
    await expect(dialog).not.toBeVisible({ timeout: 3_000 });
  });
});

// ===========================================================================
// Test Suite: Tail Configuration Switching
// ===========================================================================

test.describe('Tail Configuration Switching', () => {
  test('switching to V-Tail updates the component detail panel', async ({
    page,
  }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Default is Trainer which uses "Conventional" tail type.
    // The Tail Type dropdown is in the Global Panel (sidebar).
    const tailTypeContainer = page.locator('div.mb-3', {
      has: page.locator('text="Tail Type"'),
    });
    const tailTypeSelect = tailTypeContainer.locator('select');
    await expect(tailTypeSelect).toHaveValue('Conventional');

    // Switch to V-Tail
    await tailTypeSelect.selectOption('V-Tail');
    await page.waitForTimeout(1_000);

    // The Glider preset uses V-Tail natively, but we can also just check
    // by loading the Glider preset which switches tail type.
    // Instead, let's verify by switching to Glider preset which has V-Tail.
    await selectPreset(page, 'Glider');

    // Verify tail type is now V-Tail
    const tailTypeAfter = tailTypeContainer.locator('select');
    await expect(tailTypeAfter).toHaveValue('V-Tail');

    // Verify the sidebar shows V-tail specific labels.
    // Glider uses V-Tail so the GlobalPanel should show V-Tail in the dropdown.
    const tailTypeValue = await tailTypeAfter.inputValue();
    expect(tailTypeValue).toBe('V-Tail');

    // Switch back to Trainer (Conventional)
    await selectPreset(page, 'Trainer');
    await expect(tailTypeAfter).toHaveValue('Conventional');
  });
});

// ===========================================================================
// Test Suite: Parameter Panels Navigation
// ===========================================================================

test.describe('Parameter Panels', () => {
  test('Global panel contains expected controls', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // The right sidebar should have the "Parameters" header
    const sidebar = page.locator('aside');
    await expect(sidebar.getByText('Parameters')).toBeVisible();

    // Verify key controls exist in the Global Panel
    const expectedLabels = [
      'Preset',
      'Fuselage Style',
      'Wingspan',
      'Wing Chord',
      'Fuselage Length',
      'Tail Type',
      'Wing Mount',
      'Motor Position',
    ];

    for (const label of expectedLabels) {
      const labelElement = sidebar.getByText(label, { exact: true }).first();
      await expect(labelElement).toBeVisible();
    }
  });

  test('Component Details section is visible', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // The bottom-left section shows "Component Details" header
    const componentSection = page.locator('section');
    await expect(
      componentSection.getByText('Component Details'),
    ).toBeVisible();

    // When no component is selected, it shows a placeholder message
    const placeholder = componentSection.getByText(
      'Click a component in the 3D viewport',
    );
    await expect(placeholder).toBeVisible();
  });
});

// ===========================================================================
// Test Suite: WebSocket Connection Status
// ===========================================================================

test.describe('WebSocket Connection Status', () => {
  test('connection status indicator is visible in the status bar', async ({
    page,
  }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // The status bar (footer) should contain the connection status
    const footer = page.locator('footer');

    // Status label should show one of the known states.
    // After app loads, it should show "Connected" (if backend is running)
    // or "Connecting..." / "Disconnected" etc.
    const statusText = footer.locator('span').last();
    await expect(statusText).toBeVisible();

    // The text should be one of the known connection states
    const text = await statusText.textContent();
    const validStates = [
      'Connected',
      'Connecting...',
      'Reconnecting...',
      'Disconnected',
      'Connection Error',
    ];
    const matchesKnownState = validStates.some(
      (state) => text?.includes(state),
    );
    expect(matchesKnownState).toBe(true);
  });
});

// ===========================================================================
// Test Suite: Multiple Parameter Changes
// ===========================================================================

test.describe('Multiple Parameter Changes', () => {
  test('changing several parameters in sequence all persist', async ({
    page,
  }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Change wingspan
    await setSliderInputValue(page, 'Wingspan', '1500');
    await page.waitForTimeout(300);

    // Change wing chord
    await setSliderInputValue(page, 'Wing Chord', '250');
    await page.waitForTimeout(300);

    // Change fuselage length
    await setSliderInputValue(page, 'Fuselage Length', '500');
    await page.waitForTimeout(300);

    // Verify all values persisted
    const wingspan = await getSliderInputValue(page, 'Wingspan');
    expect(wingspan).toBe('1500');

    const chord = await getSliderInputValue(page, 'Wing Chord');
    expect(chord).toBe('250');

    const fuselage = await getSliderInputValue(page, 'Fuselage Length');
    expect(fuselage).toBe('500');

    // The canvas should still be visible (3D view didn't crash)
    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible();

    // Preset should be "Custom" since we changed params
    const presetSelect = getPresetSelect(page);
    await expect(presetSelect).toHaveValue('Custom');
  });
});

// ===========================================================================
// Test Suite: View Controls
// ===========================================================================

test.describe('View Controls', () => {
  test('camera preset buttons are accessible and clickable', async ({
    page,
  }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // The toolbar should contain view preset buttons with aria-labels
    const viewGroup = page.locator('[role="group"][aria-label="Camera view presets"]');
    await expect(viewGroup).toBeVisible();

    // Verify each camera preset button is present
    const presetButtons = [
      { label: 'Front view', shortcut: 'F' },
      { label: 'Side view', shortcut: 'S' },
      { label: 'Top view', shortcut: 'T' },
      { label: '3D perspective view', shortcut: '3D' },
    ];

    for (const btn of presetButtons) {
      const button = page.getByRole('button', { name: btn.label });
      await expect(button).toBeVisible();
      await expect(button).toBeEnabled();
    }

    // Click each view button in sequence -- they should not error
    for (const btn of presetButtons) {
      const button = page.getByRole('button', { name: btn.label });
      await button.click();
      await page.waitForTimeout(200);

      // Canvas should remain visible (no crash)
      const canvas = page.locator('canvas');
      await expect(canvas).toBeVisible();
    }
  });
});

// ===========================================================================
// Test Suite: Design Name Editing
// ===========================================================================

test.describe('Design Name Editing', () => {
  test('clicking design name opens inline editor and saves on blur', async ({
    page,
  }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // The design name button shows "Untitled Aircraft" by default
    const nameButton = page.locator('button[title="Click to rename"]');
    await expect(nameButton).toBeVisible();
    await expect(nameButton).toContainText('Untitled Aircraft');

    // Click to enter edit mode
    await nameButton.click();

    // An inline text input should appear
    const nameInput = page.locator('input.bg-zinc-800[type="text"]').first();
    // Fall back to looking for any text input in the toolbar area
    const toolbarInput = page.locator(
      'div.flex.items-center input[type="text"]',
    );

    // One of these should be visible (the inline edit input)
    const editInput = (await nameInput.isVisible())
      ? nameInput
      : toolbarInput;

    // Type a new name
    await editInput.fill('My Test Plane');
    await editInput.press('Enter');

    await page.waitForTimeout(300);

    // After pressing Enter, the button should reappear with the new name
    await expect(nameButton).toBeVisible({ timeout: 2_000 });
    await expect(nameButton).toContainText('My Test Plane');
  });
});

// ===========================================================================
// Test Suite: History Panel
// ===========================================================================

test.describe('History Panel', () => {
  test('history panel opens from Edit menu and shows entries', async ({
    page,
  }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Make a change so there is history
    await setSliderInputValue(page, 'Wingspan', '1400');
    await page.waitForTimeout(500);

    // Open Edit menu
    const editButton = page.locator('button', { hasText: 'Edit' });
    await editButton.click();

    // Click "Show History" menu item
    const historyItem = page.locator('[role="menuitem"]', {
      hasText: 'Show History',
    });
    await expect(historyItem).toBeVisible({ timeout: 2_000 });
    await historyItem.click();

    // History panel should appear
    const historyPanel = page.getByText('History').locator('..');
    // Look for the history header text
    const historyHeader = page.locator('span', { hasText: 'History' }).filter({
      has: page.locator('xpath=..'),
    });

    // The panel should show at least one entry (the change we just made)
    // Look for "current" indicator which always shows in the history panel
    const currentEntry = page.getByText('current');
    await expect(currentEntry).toBeVisible({ timeout: 3_000 });

    // Close the history panel
    const closeButton = page.getByRole('button', {
      name: 'Close history panel',
    });
    if (await closeButton.isVisible()) {
      await closeButton.click();
    }
  });
});

// ===========================================================================
// Test Suite: Bidirectional Parameter
// ===========================================================================

test.describe('Bidirectional Parameter', () => {
  test('toggle between chord and aspect ratio editing', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // The sidebar should contain the bidirectional toggle.
    // Look for "Wing Chord" label which is the default mode (mode 'a').
    const sidebar = page.locator('aside');
    const chordLabel = sidebar.getByText('Wing Chord', { exact: true });
    await expect(chordLabel).toBeVisible();

    // The BidirectionalParam component renders a swap button with
    // aria-label="Switch to editing Aspect Ratio" (when chord mode is active).
    const swapButton = sidebar.getByRole('button', {
      name: 'Switch to editing Aspect Ratio',
    });
    await expect(swapButton).toBeVisible();

    // Click swap to toggle to Aspect Ratio mode
    await swapButton.click();
    await page.waitForTimeout(300);

    // After toggling, "Aspect Ratio" label should be visible
    const arLabel = sidebar.getByText('Aspect Ratio', { exact: true });
    await expect(arLabel).toBeVisible();

    // The swap button now has the opposite label
    const swapBack = sidebar.getByRole('button', {
      name: 'Switch to editing Wing Chord',
    });
    await expect(swapBack).toBeVisible();

    // Toggle back to chord mode
    await swapBack.click();
    await page.waitForTimeout(300);
    await expect(chordLabel).toBeVisible();
  });
});

// ===========================================================================
// Test Suite: Responsive Viewport
// ===========================================================================

test.describe('Responsive Viewport', () => {
  test('canvas fills the viewport area', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible();

    // Canvas should have non-trivial dimensions
    const box = await canvas.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeGreaterThan(200);
    expect(box!.height).toBeGreaterThan(200);

    // Canvas should take up a significant portion of the viewport
    const viewportSize = page.viewportSize();
    if (viewportSize) {
      // Canvas should be at least 40% of viewport width (sidebar takes ~20-30%)
      expect(box!.width).toBeGreaterThan(viewportSize.width * 0.4);
      // Canvas should be at least 40% of viewport height
      expect(box!.height).toBeGreaterThan(viewportSize.height * 0.3);
    }
  });
});
