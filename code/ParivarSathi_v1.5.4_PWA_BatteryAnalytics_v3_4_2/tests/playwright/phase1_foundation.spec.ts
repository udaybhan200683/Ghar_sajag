import { test, expect } from '@playwright/test';

async function app(page) {
  await page.goto('/', {waitUntil:'commit'});
  await expect(page.locator('#homeTab .hero')).toBeVisible();
}
const admin = {'X-Actor-Id':'simulation-owner'};

test.describe('Phase 1 authoritative application flows', () => {
  test.beforeEach(async ({request}) => { await request.post('/pwa/action',{data:{action:'reset_pass'}}); });

  test('Home Details load, save, reload, cancel and backend rejection', async ({page,request}) => {
    const original = await (await request.get('/pwa/foundation/home',{headers:admin})).json();
    try {
      await app(page); await page.getByRole('button',{name:'Settings'}).click();
      await page.locator('[data-setting="Home Details"]').click();
      await expect(page.locator('#homeDetailsForm [name="display_name"]')).toHaveValue(original.display_name);
      await page.locator('#homeDetailsForm [name="display_name"]').fill('Phase one home');
      await page.locator('#homeDetailsForm button[type="submit"]').click();
      await expect(page.locator('#phase1Dialog')).not.toBeVisible();
      await page.reload({waitUntil:'commit'}); await page.getByRole('button',{name:'Settings'}).click();
      await page.locator('[data-setting="Home Details"]').click();
      await expect(page.locator('#homeDetailsForm [name="display_name"]')).toHaveValue('Phase one home');
      await page.locator('#homeDetailsForm [name="display_name"]').fill('Canceled name');
      await page.getByRole('button',{name:'Cancel and close'}).click();
      await page.locator('[data-setting="Home Details"]').click();
      await expect(page.locator('#homeDetailsForm [name="display_name"]')).toHaveValue('Phase one home');
      await page.locator('#homeDetailsForm [name="timezone"]').fill('Invalid/Timezone');
      await page.locator('#homeDetailsForm button[type="submit"]').click();
      await expect(page.locator('#phase1Error')).toContainText('Not saved');
    } finally {
      await request.patch('/pwa/foundation/home',{headers:admin,data:{display_name:original.display_name,timezone:original.timezone,language:original.language}});
    }
  });

  test('Family Members add, edit, deactivate and reject last admin removal', async ({page,request}, testInfo) => {
    const memberId=`phase-member-${testInfo.project.name}`;
    await app(page); await page.getByRole('button',{name:'Settings'}).click();
    await page.locator('[data-setting="Family Members"]').click();
    await page.getByRole('button',{name:'Add family member'}).click();
    await page.locator('#memberForm [name="member_id"]').fill(memberId);
    await page.locator('#memberForm [name="display_name"]').fill('Anita');
    await page.locator('#memberForm [name="relationship"]').fill('Daughter');
    await page.locator('#memberForm [name="contact"]').fill(`${memberId}@example.org`);
    await page.locator('#memberForm button[type="submit"]').click();
    await expect(page.locator('#phase1Dialog')).toContainText('Anita');
    await page.getByRole('button',{name:'Edit'}).last().click();
    await page.locator('#memberForm [name="display_name"]').fill('Anita Rao');
    await page.locator('#memberForm button[type="submit"]').click();
    await expect(page.locator('#phase1Dialog')).toContainText('Anita Rao');
    page.once('dialog',d=>d.accept()); await page.getByRole('button',{name:'Deactivate'}).last().click();
    await expect(page.locator('#phase1Dialog')).toContainText('Inactive');
    const lastOwner=await request.delete('/pwa/foundation/members/simulation-owner',{headers:admin,data:{}});
    expect(lastOwner.status()).toBe(400);
  });

  test('Devices and Manage Devices share registration, details, edit and removal', async ({page,request}, testInfo) => {
    const deviceId=`phase-node-${testInfo.project.name}`;
    await app(page); await page.getByRole('button',{name:'Devices'}).click();
    await expect(page.locator('#devicesTab .device-card')).toHaveCount(7);
    await page.getByRole('button',{name:'Register simulated device'}).click();
    await page.locator('#deviceForm [name="device_id"]').fill(deviceId);
    await page.locator('#deviceForm [name="display_name"]').fill('New node');
    await page.locator('#deviceForm [name="room"]').selectOption('Bathroom');
    await page.locator('#deviceForm button[type="submit"]').click();
    await expect(page.locator('#devicesTab .device-card')).toHaveCount(8);
    const duplicate=await request.post('/pwa/foundation/devices',{headers:admin,data:{device_id:deviceId,display_name:'Duplicate',kind:'NODE',capability:'MOTION',room:'Bathroom'}});
    expect(duplicate.status()).toBe(400);
    await page.locator(`[data-device-id="${deviceId}"] button`).click();
    await expect(page.locator('#phase1Dialog')).toContainText(/SIMULATOR registration/i);
    await page.getByRole('button',{name:'Edit / Rename'}).click();
    await page.locator('#deviceForm [name="display_name"]').fill('Renamed node');
    await page.locator('#deviceForm [name="room"]').selectOption('Kitchen');
    await page.locator('#deviceForm button[type="submit"]').click();
    await expect(page.locator(`[data-device-id="${deviceId}"]`)).toContainText('Renamed node');
    await page.getByRole('button',{name:'Settings'}).click();
    await page.locator('[data-setting="Manage Devices"]').click();
    await expect(page.locator('#phase1Dialog')).toContainText('Renamed node');
    await page.getByRole('button',{name:'Details / Edit'}).last().click();
    page.once('dialog',d=>d.accept()); await page.getByRole('button',{name:'Unregister device'}).click();
    await page.getByRole('button',{name:'Devices'}).click();
    await expect(page.locator('#devicesTab .device-card')).toHaveCount(7);
  });

  test('Battery policy and schedules persist and reject invalid threshold relationship', async ({page,request}) => {
    const original=(await (await request.get('/pwa/foundation/policy',{headers:admin})).json()).settings;
    try {
      await app(page); await page.getByRole('button',{name:'Settings'}).click();
      await page.locator('[data-setting="Battery Alerts"]').click();
      await page.locator('#batteryForm [name="battery_alert_percent"]').fill('25');
      await page.locator('#batteryForm [name="critical_battery_percent"]').fill('10');
      await page.locator('#batteryForm button[type="submit"]').click();
      await page.reload({waitUntil:'commit'}); await page.getByRole('button',{name:'Settings'}).click();
      await page.locator('[data-setting="Battery Alerts"]').click();
      await expect(page.locator('#batteryForm [name="battery_alert_percent"]')).toHaveValue('25');
      await page.locator('#batteryForm [name="critical_battery_percent"]').fill('25');
      await page.locator('#batteryForm button[type="submit"]').click();
      await expect(page.locator('#phase1Error')).toContainText('Not saved');
      await page.getByRole('button',{name:'Cancel and close'}).click();
      await page.locator('[data-setting="Device Schedules"]').click();
      await page.locator('#scheduleForm [name="night_bathroom_visit_threshold"]').fill('3');
      await page.locator('#scheduleForm button[type="submit"]').click();
      await expect(page.locator('#scheduleForm [name="night_bathroom_visit_threshold"]')).toHaveValue('3');
    } finally {
      await request.patch('/pwa/foundation/policy',{headers:admin,data:original});
    }
  });

  test('failed Home Details save stays open and never claims success', async ({page}) => {
    await app(page); await page.getByRole('button',{name:'Settings'}).click();
    await page.locator('[data-setting="Home Details"]').click();
    await page.route('**/pwa/foundation/home',route=>route.request().method()==='PATCH'?route.abort():route.continue());
    await page.locator('#homeDetailsForm [name="display_name"]').fill('Unavailable save');
    await page.locator('#homeDetailsForm button[type="submit"]').click();
    await expect(page.locator('#phase1Dialog')).toBeVisible();
    await expect(page.locator('#phase1Error')).toContainText('Not saved');
  });

  test('simulated online/offline transition updates backend-driven device health', async ({page,request}) => {
    await app(page); await page.getByRole('button',{name:'Devices'}).click();
    const kitchen=page.locator('[data-device-id="kitchen"]');
    try {
      const offline=await request.post('/pwa/foundation/devices/kitchen/health',{headers:admin,data:{online:false,health:'OFFLINE',battery_mv:3920,battery_percent:65,drain_status:'NORMAL'}});
      expect(offline.status()).toBe(200);
      await expect(kitchen).toContainText('Inactive',{timeout:10_000});
    } finally {
      await request.post('/pwa/foundation/devices/kitchen/health',{headers:admin,data:{online:true,health:'ACTIVE',battery_mv:3920,battery_percent:65,drain_status:'NORMAL'}});
    }
  });
});
