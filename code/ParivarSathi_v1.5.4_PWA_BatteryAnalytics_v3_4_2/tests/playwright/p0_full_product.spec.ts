import { expect, test } from '@playwright/test';

test('C3/S3 event and backend incident render consistently after caregiver reload', async ({ page }) => {
  const base = process.env.P0_E2E_BASE_URL;
  const expectedEventId = process.env.P0_E2E_EVENT_ID;
  expect(base, 'E2E must provide the isolated local stack').toBeTruthy();
  expect(expectedEventId, 'E2E must provide the production-stack EventKey').toBeTruthy();

  await page.goto(base!);
  await expect(page.locator('#activity')).toContainText('Main door open');
  await expect(page.locator('#connectivity')).toContainText('Hub connected');
  await expect(page.locator('#door')).toContainText('opened during the configured quiet period');
  const event = page.locator('#timeline li').filter({ hasText: 'Motion detected — room' });
  await expect(event).toHaveCount(1);
  expect(await event.first().getAttribute('data-event-id')).toBe(expectedEventId);
  await expect(page.locator('#incidents [data-incident-id]')).toHaveCount(2);

  const firstOrder = await page.locator('#timeline li').evaluateAll(rows =>
    rows.map(row => row.textContent || ''));
  expect(firstOrder[0]).toContain('Call Family requested');
  expect(firstOrder[1]).toContain('No activity for longer than expected');
  expect(firstOrder[2]).toContain('Main door opened during quiet hours');
  await page.reload();
  await expect(page.locator('#activity')).toContainText('Main door open');
  await expect(page.locator('#timeline li[data-event-id]')).toHaveCount(4);
  await expect(page.locator('#incidents [data-incident-id]')).toHaveCount(2);
  await expect(page.locator('body')).not.toContainText('inc_demo');
});
