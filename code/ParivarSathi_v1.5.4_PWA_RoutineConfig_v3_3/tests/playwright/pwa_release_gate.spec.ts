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
  test.afterEach(async ({ request }) => {
    await request.post('/pwa/action', { data: { action: 'reset_pass' } });
  });

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
    await expect(events.first()).toContainText(/Main door left open/i);
  });

  test('Device Schedules exposes and saves family-specific routine thresholds', async ({ page }) => {
    await waitForApp(page);
    await page.getByRole('button', { name: /Settings/i }).click();
    await page.locator('[data-setting="Device Schedules"]').click();
    await expect(page.locator('#scheduleEditor')).toBeVisible();
    const bath=page.locator('[name="night_bathroom_visit_threshold"]');
    await expect(bath).toHaveValue(/\d+/);
    await bath.fill('3');
    await page.locator('#scheduleForm button[type="submit"]').click();
    await expect(page.locator('#scheduleEditor')).toBeVisible();
    await expect(page.locator('[name="night_bathroom_visit_threshold"]')).toHaveValue('3');
  });

  test('post-door inactivity concern renders light-red main banner with specific problem', async ({ page }) => {
    await waitForApp(page);
    await page.evaluate(async()=>{
      await fetch('/pwa/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'reset_pass'})});
      const post=async(body)=>fetch('/sim/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json());
      const state=await fetch('/sim/state').then(r=>r.json());
      const settings={...state.settings}; delete settings.config_version; settings.post_door_inactivity_seconds=300;
      await post({action:'settings',settings}); await post({action:'time',minute:720}); await post({action:'event',node:'entry',kind:'DOOR_OPEN'}); await post({action:'event',node:'entry',kind:'DOOR_CLOSED'}); await post({action:'advance',seconds:300});
    });
    await page.waitForTimeout(2200);
    await expect(page.locator('.hero')).toHaveClass(/alert/);
    await expect(page.locator('.hero')).toContainText(/No indoor activity was detected after the main door closed/i);
    await expect(page.locator('[data-care-card="door"]')).toHaveClass(/alert/);
  });

  test('night bathroom threshold concern renders red night card and main banner', async ({ page }) => {
    await waitForApp(page);
    await page.evaluate(async()=>{
      await fetch('/pwa/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'reset_pass'})});
      const post=async(body)=>fetch('/sim/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json());
      const state=await fetch('/sim/state').then(r=>r.json()); const settings={...state.settings}; delete settings.config_version; settings.night_bathroom_visit_threshold=1;settings.night_visit_merge_seconds=0;
      await post({action:'settings',settings});await post({action:'time',minute:1380});await post({action:'event',node:'bathroom',kind:'MOTION'});await post({action:'event',node:'bathroom',kind:'MOTION'});
    });
    await page.waitForTimeout(2200);
    await expect(page.locator('.hero')).toHaveClass(/alert/);
    await expect(page.locator('[data-care-card="night"]')).toHaveClass(/alert/);
    await expect(page.locator('.hero')).toContainText(/Bathroom visits are higher/i);
  });

  test('door-left-open and common-room red flags each drive the main care banner', async ({ page }) => {
    await waitForApp(page);
    const runScenario=async(id, expected)=>{
      await page.evaluate(async(scenarioId)=>{await fetch('/pwa/validation/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario_id:scenarioId})});},id);
      // validation runner resets/executes backend state; refresh PWA from that exact backend state.
      await page.evaluate(async()=>{const v=await fetch('/pwa/state',{cache:'no-store'}).then(r=>r.json()); window.__lastCare=v.care;});
      await page.reload({waitUntil:'commit'}); await expect(page.locator('#homeTab .hero')).toBeVisible();
      await expect(page.locator('.hero')).toHaveClass(/alert/); await expect(page.locator('.hero')).toContainText(expected);
    };
    await runScenario('door-left-open-configured-boundary', /Main door has remained open longer than configured/i);
    await runScenario('night-common-over-limit-alerts', /Common-room visits are higher/i);
  });

  test('run all canonical scenarios through PWA and verify visible PASS summary', async ({ page }) => {
    await waitForApp(page);

    const runAll = page.locator('#runAllValidation');
    await expect(runAll).toBeVisible();
    await runAll.click();

    // Wait for browser-visible completion. Support a few likely phrasings.
    const passSummary = page.locator('#validationOverall[data-validation-status="PASS"]');
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
