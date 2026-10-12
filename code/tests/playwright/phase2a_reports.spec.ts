import { test, expect } from '@playwright/test';

const actor = { 'X-Actor-Id': 'simulation-owner' };
const forbidden = /event_id|MOTION|DOOR_OPEN|BATTERY_RUNTIME|mAh|debug|confidence|threshold|source_event_id/i;

async function post(request: any, url: string, data: any, headers: Record<string, string> = {}) {
  const response = await request.post(url, { headers, data });
  expect(response.ok(), `${url} ${response.status()}`).toBeTruthy();
  return response.json();
}

async function seedFromReportWindow(request: any, period = 'TODAY') {
  const baseline = await (await request.get(`/v1/homes/simulation-home/reports?period=${period}`, { headers: actor })).json();
  const start = baseline.window.start_at;
  await post(request, '/v1/homes/simulation-home/events', {
    event_id: `report-ok-${period}`,
    kind: 'OK_PRESSED',
    location: 'room1',
    occurred_at: start + 60,
    hub_received_at: start + 60,
    payload: {}
  }, actor);
  await post(request, '/v1/homes/simulation-home/events', {
    event_id: `report-door-${period}`,
    kind: 'DOOR_OPEN',
    location: 'entry',
    occurred_at: start + 120,
    hub_received_at: start + 120,
    payload: {}
  }, actor);
  await post(request, '/v1/homes/simulation-home/events', {
    event_id: `report-morning-${period}`,
    kind: 'MORNING_ROUTINE_COMPLETED',
    location: 'kitchen',
    occurred_at: start + 180,
    hub_received_at: start + 180,
    payload: {}
  }, actor);
  await post(request, '/v1/homes/simulation-home/events', {
    event_id: `report-concern-${period}`,
    kind: 'CALL_FAMILY',
    location: 'room1',
    occurred_at: start + 240,
    hub_received_at: start + 240,
    payload: {}
  }, actor);
}

async function openReports(page: any) {
  await page.goto('/', { waitUntil: 'commit' });
  await expect(page.locator('#homeTab .hero')).toBeVisible();
  await page.getByRole('button', { name: 'Reports' }).click();
}

test.describe('Phase 2A backend-derived Reports', () => {
  test.beforeEach(async ({ request }) => {
    await post(request, '/sim/action', { action: 'reset', test_fixture: true });
  });

  test('renders Today, Week, and Month from the reports API', async ({ page, request }) => {
    await seedFromReportWindow(request, 'TODAY');
    await openReports(page);

    await page.getByRole('button', { name: 'Today' }).click();
    await expect(page.locator('[data-report-status="data"]').first()).toBeVisible();
    await expect(page.locator('[data-report-card="check-ins"]')).toContainText('1 check-in');
    await expect(page.locator('[data-report-card="morning"]')).toContainText('1 completion');
    await expect(page.locator('[data-report-card="door"]')).toContainText('1 opening');
    await expect(page.locator('[data-report-card="concerns"]')).toContainText('1 concern');
    await expect(page.locator('#reportsTab')).toContainText('Call Family requested');
    await expect(page.locator('#reportsTab')).not.toContainText(forbidden);

    await page.getByRole('button', { name: 'This Week' }).click();
    await expect(page.locator('[data-report-period-active="WEEK"]')).toBeVisible();
    await expect(page.locator('[data-report-status="data"]').first()).toBeVisible();
    await expect(page.locator('[data-report-card="check-ins"]')).toContainText('1 check-in');

    await page.getByRole('button', { name: 'This Month' }).click();
    await expect(page.locator('[data-report-period-active="MONTH"]')).toBeVisible();
    await expect(page.locator('[data-report-status="data"]').first()).toBeVisible();
    await expect(page.locator('.bar-wrap').first()).toBeVisible();
    await expect(page.locator('#reportsTab')).not.toContainText(/Battery draining faster|Recharge now|mAh|confidence/i);
  });

  test('shows no-data without treating it as an error', async ({ page }) => {
    await openReports(page);
    await page.getByRole('button', { name: 'Today' }).click();
    await expect(page.locator('[data-report-status="no-data"]').first()).toBeVisible();
    await expect(page.locator('#reportsTab')).toContainText('No recorded activity');
    await expect(page.locator('#reportsTab')).not.toContainText(/Reports unavailable|0 care concerns|0 check-ins/i);
  });

  test('refreshes after new backend activity', async ({ page, request }) => {
    await openReports(page);
    await page.getByRole('button', { name: 'Today' }).click();
    await expect(page.locator('[data-report-status="no-data"]').first()).toBeVisible();
    await seedFromReportWindow(request, 'TODAY');
    await expect(page.locator('[data-report-status="data"]').first()).toBeVisible({ timeout: 5000 });
    await expect(page.locator('[data-report-card="check-ins"]')).toContainText('1 check-in');
  });

  test('shows backend and malformed response errors explicitly', async ({ page }) => {
    await page.route('**/v1/homes/*/reports*', route => route.abort());
    await openReports(page);
    await expect(page.locator('[data-report-status="error"]').first()).toBeVisible();
    await expect(page.locator('#reportsTab')).toContainText('Reports unavailable');
    await expect(page.locator('#reportsTab')).not.toContainText(/0 check-ins|0 concerns/i);
  });

  test('shows malformed report responses as errors', async ({ page }) => {
    await page.route('**/v1/homes/*/reports*', route => route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }));
    await openReports(page);
    await expect(page.locator('[data-report-status="error"]').first()).toBeVisible();
    await expect(page.locator('#reportsTab')).toContainText('Reports unavailable');
  });
});
