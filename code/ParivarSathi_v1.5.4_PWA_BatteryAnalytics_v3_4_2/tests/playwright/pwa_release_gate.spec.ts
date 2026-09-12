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

  test('routine cards are below the overall banner with Morning before I am OK', async ({ page }) => {
    await waitForApp(page);
    const hero = page.locator('#homeTab .hero');
    await expect(hero).not.toContainText(/Morning routine|I am OK|Main door|Night activity/i);
    const order = await page.locator('#homeTab [data-care-card]').evaluateAll(nodes => nodes.map(n => n.getAttribute('data-care-card')));
    expect(order.slice(0,5)).toEqual(['morning','ok','door','night','device-health']);
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

    // Scope battery assertions to the Device Health card. The same low-battery
    // condition is intentionally also present in Recent Important Events, so a
    // page-wide getByText() violates Playwright strict mode by matching both.
    const deviceHealth = page.locator('[data-care-card="device-health"]');
    await expect(deviceHealth).toHaveClass(/alert/);
    await expect(deviceHealth.getByText(/Low battery:.*5%|Kitchen.*5%/i)).toBeVisible();
    await expect(deviceHealth.getByText(/Estimated time left recharge now/i)).toBeVisible();

    // The event feed should also contain the battery warning.
    await expect(page.locator('.event-pill.red').filter({ hasText: /Kitchen sensor battery low: 5%/i }).first()).toBeVisible();

    // toggle back
    await battery.click();
    await expect(page.getByText(/Home looks normal/i)).toBeVisible();
  });

  test('high battery drain shortens prediction, flags device health, and does not change care banner', async ({ page }) => {
    await waitForApp(page);
    await page.evaluate(async()=>{
      await fetch('/pwa/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'reset_pass'})});
      await fetch('/sim/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'battery_usage',target:'kitchen',days:2,intensity:20})});
    });
    await page.waitForTimeout(2200);
    await expect(page.locator('.hero')).not.toHaveClass(/alert/);
    await expect(page.locator('.hero')).toContainText(/Home looks normal/i);
    const kitchen=page.locator('[data-device-id="kitchen"]');
    await page.getByRole('button', { name: /Devices/i }).click();
    await expect(kitchen).toHaveClass(/alert/);
    await expect(kitchen).toContainText(/Battery draining faster than usual/i);
    await expect(kitchen).toContainText(/HIGH confidence/i);
    await expect(kitchen).toContainText(/RF retries\/day/i);
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
    const originalValue=await bath.inputValue();
    // The PWA polls the backend every 2 s. Keep the editor open for >1 poll
    // cycle and prove it is not detached/re-rendered while the user is editing.
    await page.waitForTimeout(3500);
    await expect(page.locator('#scheduleEditor')).toBeVisible();
    await expect(bath).toHaveValue(originalValue);
    await bath.fill('3');
    const batteryAlert=page.locator('[name="battery_alert_percent"]');
    await expect(batteryAlert).toHaveValue(/\d+/);
    await batteryAlert.fill('25');
    await page.locator('#scheduleForm button[type="submit"]').click();
    await expect(page.locator('#scheduleEditor')).toBeVisible();
    await expect(page.locator('[name="night_bathroom_visit_threshold"]')).toHaveValue('3');
    await expect(page.locator('[name="battery_alert_percent"]')).toHaveValue('25');
  });

  test('missing morning concern uses generic red banner and highlights Morning Routine card', async ({ page }) => {
    await waitForApp(page);
    await page.evaluate(async()=>{
      await fetch('/pwa/validation/run',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({scenario_id:'morning-missing-covered'})
      });
    });
    await page.reload({waitUntil:'commit'});
    await expect(page.locator('#homeTab .hero')).toBeVisible();
    await expect(page.locator('.hero')).toHaveClass(/alert/);
    await expect(page.locator('.hero')).toContainText(/Attention needed at home/i);
    await expect(page.locator('.hero')).toContainText(/Please check the highlighted routine below/i);
    await expect(page.locator('.hero')).not.toContainText(/Morning activity not completed|Morning routine/i);

    const morning=page.locator('[data-care-card="morning"]');
    await expect(morning).toHaveClass(/alert/);
    await expect(morning).toContainText(/Morning routine/i);
    await expect(morning).toContainText(/Activity not completed/i);
  });

  test('post-door inactivity makes overall banner red and shows problem in Main Door card', async ({ page }) => {
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
    await expect(page.locator('.hero')).toContainText(/Please check the highlighted routine below/i);
    await expect(page.locator('[data-care-card="door"]')).toHaveClass(/alert/);
    await expect(page.locator('[data-care-card="door"]')).toContainText(/No indoor activity after door closed/i);
  });

  test('night bathroom concern makes overall banner red and shows problem in Night Activity card', async ({ page }) => {
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
    await expect(page.locator('.hero')).toContainText(/Please check the highlighted routine below/i);
    await expect(page.locator('[data-care-card="night"]')).toContainText(/Bathroom visits are higher/i);
  });

  test('door-left-open and common-room concerns use generic red banner plus affected routine card', async ({ page }) => {
    await waitForApp(page);
    const runScenario=async(id, expected)=>{
      await page.evaluate(async(scenarioId)=>{await fetch('/pwa/validation/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario_id:scenarioId})});},id);
      // validation runner resets/executes backend state; refresh PWA from that exact backend state.
      await page.evaluate(async()=>{const v=await fetch('/pwa/state',{cache:'no-store'}).then(r=>r.json()); window.__lastCare=v.care;});
      await page.reload({waitUntil:'commit'}); await expect(page.locator('#homeTab .hero')).toBeVisible();
      await expect(page.locator('.hero')).toHaveClass(/alert/);
      await expect(page.locator('.hero')).toContainText(/Please check the highlighted routine below/i);
      const target = id.startsWith('door-') ? page.locator('[data-care-card="door"]') : page.locator('[data-care-card="night"]');
      await expect(target).toHaveClass(/alert/);
      await expect(target).toContainText(expected);
    };
    await runScenario('door-left-open-configured-boundary', /Open longer than configured/i);
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
