import { test, expect } from '@playwright/test';

const admin = { 'X-Actor-Id': 'simulation-owner' };
const forbidden = /CALL_FAMILY|MISSING_MORNING|COVERAGE_CHANGED|event_id|record_id|correlation|provider|retry|token|API key|mAh|confidence|debug/i;

async function post(request: any, url: string, data: any, headers: Record<string, string> = {}) {
  const response = await request.post(url, { headers, data });
  expect(response.ok(), `${url} ${response.status()}`).toBeTruthy();
  return response.json();
}

async function openNotifications(page: any) {
  await page.goto('/', { waitUntil: 'commit' });
  await expect(page.locator('#homeTab .hero')).toBeVisible();
  await page.getByRole('button', { name: 'Settings' }).click();
  await page.locator('[data-setting="Notifications"]').click();
  await expect(page.locator('#notificationForm')).toBeVisible();
}

test.describe('Phase 2B Notifications settings and status', () => {
  test.beforeEach(async ({ request }) => {
    await post(request, '/sim/action', { action: 'reset', test_fixture: true });
  });

  test('loads, saves, reloads and cancels caregiver preferences', async ({ page, request }) => {
    await openNotifications(page);
    await expect(page.locator('#notificationForm')).toContainText('Safety and urgent concerns');
    await expect(page.locator('#notificationForm')).toContainText('Browser permission:');
    await expect(page.locator('#notificationForm')).not.toContainText(forbidden);

    await page.locator('#notificationForm [name="safety_alerts"]').uncheck();
    await page.locator('#notificationForm').getByRole('button', { name: 'Cancel', exact: true }).click();
    await page.locator('[data-setting="Notifications"]').click();
    await expect(page.locator('#notificationForm [name="safety_alerts"]')).toBeChecked();

    await page.locator('#notificationForm [name="safety_alerts"]').uncheck();
    await page.locator('#notificationForm [name="browser_alerts_enabled"]').check();
    await page.getByRole('button', { name: 'Save Notifications' }).click();
    await expect(page.locator('#notificationForm [name="safety_alerts"]')).not.toBeChecked();
    await expect(page.locator('#notificationForm [name="browser_alerts_enabled"]')).toBeChecked();

    await page.reload({ waitUntil: 'commit' });
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.locator('[data-setting="Notifications"]').click();
    await expect(page.locator('#notificationForm [name="safety_alerts"]')).not.toBeChecked();
    const prefs = await (await request.get('/pwa/foundation/notifications/preferences', { headers: admin })).json();
    expect(prefs.preferences.safety_alerts).toBe(false);
    const invalid = await request.patch('/pwa/foundation/notifications/preferences', { headers: admin, data: { ...prefs.preferences, safety_alerts: 'yes' } });
    expect(invalid.status()).toBe(400);
  });

  test('records delivered, suppressed, failed and resolved notification states without technical leakage', async ({ page, request }) => {
    await post(request, '/sim/action', { action: 'event', node: 'room1', kind: 'CALL_FAMILY' });
    await openNotifications(page);
    await expect(page.locator('[data-notification-state="DELIVERED"]')).toContainText('Call Family requested');
    await expect(page.locator('#notificationForm')).not.toContainText(forbidden);

    await post(request, '/sim/action', { action: 'reset', test_fixture: true });
    const prefs = await (await request.get('/pwa/foundation/notifications/preferences', { headers: admin })).json();
    await request.patch('/pwa/foundation/notifications/preferences', { headers: admin, data: { ...prefs.preferences, safety_alerts: false } });
    await post(request, '/sim/action', { action: 'event', node: 'room1', kind: 'CALL_FAMILY' });
    await page.reload({ waitUntil: 'commit' });
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.locator('[data-setting="Notifications"]').click();
    await expect(page.locator('[data-notification-state="SUPPRESSED"]')).toContainText('Suppressed by preference');

    await post(request, '/sim/action', { action: 'reset', test_fixture: true });
    await post(request, '/sim/action', { action: 'notification_delivery', available: false });
    await post(request, '/sim/action', { action: 'event', node: 'room1', kind: 'CALL_FAMILY' });
    await page.reload({ waitUntil: 'commit' });
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.locator('[data-setting="Notifications"]').click();
    await expect(page.locator('[data-notification-state="FAILED"]')).toContainText('Delivery failed');

    await post(request, '/sim/action', { action: 'reset', test_fixture: true });
    await post(request, '/sim/action', { action: 'advance', seconds: 121 });
    const overdue = await (await request.get('/pwa/foundation/notifications/records', { headers: admin })).json();
    expect(overdue).toHaveLength(1);
    expect(overdue[0]).toMatchObject({
      category: 'CHECK_IN',
      state: 'DELIVERED',
      title: 'I am OK check-in overdue',
      message: 'The expected I am OK check-in has not arrived.'
    });
    await post(request, '/sim/action', { action: 'event', node: 'room1', kind: 'OK_PRESSED' });
    const resolved = await (await request.get('/pwa/foundation/notifications/records', { headers: admin })).json();
    expect(resolved).toHaveLength(1);
    expect(resolved[0]).toMatchObject({ category: 'CHECK_IN', state: 'RESOLVED', title: 'I am OK check-in overdue' });
    await page.reload({ waitUntil: 'commit' });
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.locator('[data-setting="Notifications"]').click();
    await expect(page.locator('[data-notification-state="RESOLVED"]')).toContainText('I am OK check-in overdue');
  });

  test('duplicates and maintenance activity do not create caregiver notification spam', async ({ page, request }) => {
    await post(request, '/sim/action', { action: 'event', node: 'room1', kind: 'CALL_FAMILY' });
    const before = await (await request.get('/pwa/foundation/notifications/records', { headers: admin })).json();
    expect(before).toHaveLength(1);
    await post(request, '/sim/action', { action: 'duplicate' });
    const after = await (await request.get('/pwa/foundation/notifications/records', { headers: admin })).json();
    expect(after).toHaveLength(1);

    await post(request, '/sim/action', { action: 'reset', test_fixture: true });
    await post(request, '/pwa/action', { action: 'toggle', scenario: 'battery' });
    await openNotifications(page);
    await expect(page.locator('.notification-history')).toContainText('No notification records yet');
    await expect(page.locator('#notificationForm')).not.toContainText(/Battery runtime|mAh|confidence|debug/i);
  });
});
