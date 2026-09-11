import { test, expect } from '@playwright/test';

async function waitForApp(page) {
  // Chromium can delay lifecycle events while PWA/service-worker resources are
  // being initialized. Validate what matters: response committed + the real app
  // JavaScript has rendered the Home hero from backend state.
  await page.goto('/', { waitUntil: 'commit', timeout: 30_000 });
  await expect(page.getByText('Parivar Sathi')).toBeVisible();
  await expect(page.locator('#homeTab .hero')).toBeVisible({ timeout: 30_000 });
}

test.describe('Parivar Sathi mandatory browser release gate', () => {
  test('PWA loads and primary tabs are visible', async ({ page }) => {
    await waitForApp(page);
    await expect(page.getByRole('button', { name: /Home/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Devices/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Reports/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Settings/i })).toBeVisible();
  });

  test('battery health negative scenario changes only device health and not top banner', async ({ page }) => {
    await waitForApp(page);

    const reset = page.getByRole('button', { name: /Reset all to PASS/i });
    if (await reset.count()) {
      await reset.click();
    }

    const battery = page.getByRole('button', { name: /battery/i }).filter({ hasText: /Toggle|Simulate/i }).first();
    await expect(battery).toBeVisible();
    await battery.click();

    await expect(page.getByText(/Home looks normal/i)).toBeVisible();
    await expect(page.getByText(/Low battery:.*5%|Bathroom.*5%/i)).toBeVisible();

    // toggle back
    await battery.click();
    await expect(page.getByText(/Home looks normal/i)).toBeVisible();
  });

  test('recent important events are newest-first after scenario toggles', async ({ page }) => {
    await waitForApp(page);

    const reset = page.getByRole('button', { name: /Reset all to PASS/i });
    if (await reset.count()) await reset.click();

    const okButton = page.getByRole('button', { name: /I am OK/i }).filter({ hasText: /Toggle|Simulate/i }).first();
    const doorButton = page.getByRole('button', { name: /door/i }).filter({ hasText: /Toggle|Simulate/i }).first();

    await okButton.click();
    await page.waitForTimeout(500);
    await doorButton.click();

    const events = page.locator('.event');
    await expect(events.first()).toContainText(/Main door opened/i);
  });

  test('run all 68 canonical scenarios through PWA and verify visible PASS summary', async ({ page }) => {
    await waitForApp(page);

    const runAll = page.getByRole('button', { name: /Run all 68 automatically/i });
    await expect(runAll).toBeVisible();
    await runAll.click();

    // Wait for browser-visible completion. Support a few likely phrasings.
    const passSummary = page.getByText(/68\/68.*PASS|PASS.*68\/68|68 of 68.*PASS/i);
    await expect(passSummary).toBeVisible({ timeout: 120_000 });

    // No visible FAIL result should remain.
    const failText = page.getByText(/\bFAIL\b/i);
    if (await failText.count()) {
      const visibleFails = await failText.evaluateAll(nodes => nodes.filter(n => {
        const s = getComputedStyle(n);
        return s.visibility !== 'hidden' && s.display !== 'none' && n.getClientRects().length > 0;
      }).length);
      expect(visibleFails).toBe(0);
    }
  });
});
