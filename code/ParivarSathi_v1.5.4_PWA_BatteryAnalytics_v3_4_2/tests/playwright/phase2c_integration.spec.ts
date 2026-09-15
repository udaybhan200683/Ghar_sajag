import { test, expect } from '@playwright/test';

const admin = { 'X-Actor-Id': 'simulation-owner' };
const forbidden = /event_id|record_id|correlation|provider|retry|token|API key|mAh|confidence|debug/i;

async function post(request: any, url: string, data: any) {
  const response = await request.post(url, { data });
  expect(response.ok(), `${url} ${response.status()}`).toBeTruthy();
  return response.json();
}

test.describe('Phase 2C PWA integration', () => {
  test.beforeEach(async ({ request }) => {
    await post(request, '/sim/action', { action: 'reset', test_fixture: true });
  });

  test('shows caregiver-facing routine settings name with stable behavior', async ({ page }) => {
    await page.goto('/', { waitUntil: 'commit' });
    await page.getByRole('button', { name: 'Settings' }).click();
    await expect(page.locator('[data-setting="Device Schedules"]')).toContainText('Routines & Activity Rules');
    await page.locator('[data-setting="Device Schedules"]').click();
    await expect(page.locator('#scheduleEditor')).toBeVisible();
    await expect(page.locator('#scheduleEditor h2')).toContainText('Routines & Activity Rules');
    await expect(page.locator('#settingsTab')).not.toContainText(/Privacy\s+ON|Privacy\s+OFF/i);
  });

  test('reflects backend-owned I-am-OK overdue and acknowledgement timing', async ({ page, request }) => {
    await post(request, '/pwa/action', { action: 'reset_pass' });
    await post(request, '/sim/action', { action: 'advance', seconds: 120 });
    await page.goto('/', { waitUntil: 'commit' });
    const ok = page.locator('[data-care-card="ok"]');
    await expect(ok).toContainText('Confirmed');
    await expect(ok).toContainText('Last confirmed 2 min ago');
    await expect(ok).not.toContainText(forbidden);

    await post(request, '/sim/action', { action: 'reset', test_fixture: true });
    await post(request, '/sim/action', { action: 'advance', seconds: 121 });
    await page.reload({ waitUntil: 'commit' });
    await expect(ok).toContainText('I am OK overdue');
    const recordsBefore = await (await request.get('/pwa/foundation/notifications/records', { headers: admin })).json();
    expect(recordsBefore).toHaveLength(1);
    expect(recordsBefore[0]).toMatchObject({ category: 'CHECK_IN', state: 'DELIVERED' });

    await post(request, '/sim/action', { action: 'event', node: 'room1', kind: 'OK_PRESSED' });
    await page.reload({ waitUntil: 'commit' });
    await expect(ok).toContainText('Just confirmed');
    const recordsAfter = await (await request.get('/pwa/foundation/notifications/records', { headers: admin })).json();
    expect(recordsAfter).toHaveLength(1);
    expect(recordsAfter[0]).toMatchObject({ category: 'CHECK_IN', state: 'RESOLVED' });
  });

  test('keeps optional device maintenance notifications separate from care activity', async ({ page, request }) => {
    const prefs = await (await request.get('/pwa/foundation/notifications/preferences', { headers: admin })).json();
    await request.patch('/pwa/foundation/notifications/preferences', {
      headers: admin,
      data: { ...prefs.preferences, device_maintenance_alerts: true }
    });
    await post(request, '/pwa/action', { action: 'toggle', scenario: 'battery' });
    await page.goto('/', { waitUntil: 'commit' });
    await expect(page.locator('#homeTab .hero')).toContainText('Home looks normal');
    await expect(page.locator('.timeline')).not.toContainText(/battery/i);

    await page.getByRole('button', { name: 'Settings' }).click();
    await page.locator('[data-setting="Notifications"]').click();
    await expect(page.locator('[data-notification-state="DELIVERED"]')).toContainText('Kitchen Node battery needs attention');
    await expect(page.locator('#notificationForm')).not.toContainText(forbidden);
  });
});
