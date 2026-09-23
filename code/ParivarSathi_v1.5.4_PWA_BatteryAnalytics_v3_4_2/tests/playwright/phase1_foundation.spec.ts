import { test, expect } from '@playwright/test';

async function app(page) {
  await page.goto('/', {waitUntil:'commit'});
  await expect(page.locator('#homeTab .hero')).toBeVisible();
}
const admin = {'X-Actor-Id':'simulation-owner'};
async function watchSuccessMessages(page) {
  await page.evaluate(()=>{
    const w=window as any;
    w.__phase1Messages=[];
    const original=w.toast;
    w.toast=(message:string)=>{w.__phase1Messages.push(message);original(message);};
  });
}
async function noFalseSuccess(page) {
  const messages=await page.evaluate(()=>(window as any).__phase1Messages||[]);
  expect(messages).not.toEqual(expect.arrayContaining([expect.stringMatching(/^(?:Home Details saved|Family member saved|Simulated device registered|Device saved|Battery policy saved|Device schedule saved)/i)]));
}

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
      await expect(page.locator('#homeDetailsForm [name="display_name"]')).not.toHaveValue('Canceled name');
      await page.locator('#homeDetailsForm [name="display_name"]').fill('Canceled name');
      await page.getByRole('button',{name:'Cancel and close'}).click();
      await page.locator('[data-setting="Home Details"]').click();
      await expect(page.locator('#homeDetailsForm [name="display_name"]')).toHaveValue('Phase one home');
      await page.locator('#homeDetailsForm [name="timezone"]').fill('Invalid/Timezone');
      await watchSuccessMessages(page);
      await page.locator('#homeDetailsForm button[type="submit"]').click();
      await expect(page.locator('#phase1Error')).toContainText('Not saved');
      await noFalseSuccess(page);
      await expect(page.locator('#homeDetailsForm [name="display_name"]')).toHaveValue('Phase one home');
      const persisted=await (await request.get('/pwa/foundation/home',{headers:admin})).json();
      expect(persisted.display_name).toBe('Phase one home');
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
    await expect(page.locator('#phase1Dialog')).toContainText('Anita Rao');
    await expect(page.locator('#phase1Dialog .phase1-list>div').filter({hasText:'Anita Rao'}).getByRole('button',{name:'Edit'})).toHaveCount(0);
    await page.reload({waitUntil:'commit'}); await page.getByRole('button',{name:'Settings'}).click();
    await page.locator('[data-setting="Family Members"]').click();
    await expect(page.locator('#phase1Dialog')).toContainText('Anita Rao');
    await expect(page.locator('#phase1Dialog')).toContainText('Inactive');
    const lastOwner=await request.delete('/pwa/foundation/members/simulation-owner',{headers:admin,data:{}});
    expect(lastOwner.status()).toBe(400);
  });

  test('Devices and Manage Devices share registration, details, edit and removal', async ({page,request}, testInfo) => {
    const deviceId=`phase-node-${testInfo.project.name}`;
    await app(page); await page.getByRole('button',{name:'Devices'}).click();
    await expect(page.locator('#devicesTab .device-card')).toHaveCount(7);
    await expect(page.locator('#devicesTab .device-summary')).toContainText('7 devices total');
    await expect(page.locator('#devicesTab .device-list')).not.toContainText(/mAh\/day|confidence|mV|RF retries|wakes\/day/i);
    await page.getByRole('button',{name:'Register simulated device'}).click();
    await page.locator('#deviceForm [name="device_id"]').fill(deviceId);
    await page.locator('#deviceForm [name="display_name"]').fill('New node');
    await page.locator('#deviceForm [name="room"]').selectOption('Bathroom');
    await page.locator('#deviceForm button[type="submit"]').click();
    await expect(page.locator('#devicesTab .device-card')).toHaveCount(8);
    await expect(page.locator('#devicesTab .device-summary')).toContainText('8 devices total');
    const duplicate=await request.post('/pwa/foundation/devices',{headers:admin,data:{device_id:deviceId,display_name:'Duplicate',kind:'NODE',capability:'MOTION',room:'Bathroom'}});
    expect(duplicate.status()).toBe(400);
    await page.locator(`[data-device-id="${deviceId}"] button`).click();
    await expect(page.locator('#phase1Dialog')).toContainText(/SIMULATOR registration/i);
    await expect(page.locator('#phase1Dialog')).not.toContainText(/mAh\/day|confidence|mV|RF retries|wakes\/day/i);
    await expect(page.locator('#phase1Dialog')).toContainText('Estimated time left: Collecting battery data');
    await page.getByRole('button',{name:'Edit / Rename'}).click();
    await page.locator('#deviceForm [name="display_name"]').fill('Renamed node');
    await page.locator('#deviceForm [name="room"]').selectOption('Kitchen');
    await page.locator('#deviceForm button[type="submit"]').click();
    await expect(page.locator(`[data-device-id="${deviceId}"]`)).toContainText('Renamed node');
    await expect(page.locator(`[data-device-id="${deviceId}"]`)).not.toContainText('New node');
    await page.reload({waitUntil:'commit'});
    await page.getByRole('button',{name:'Devices'}).click();
    await expect(page.locator(`[data-device-id="${deviceId}"]`)).toContainText('Renamed node');
    await page.getByRole('button',{name:'Settings'}).click();
    await page.locator('[data-setting="Manage Devices"]').click();
    await expect(page.locator('#phase1Dialog')).toContainText('Renamed node');
    await page.getByRole('button',{name:'Details / Edit'}).last().click();
    page.once('dialog',d=>d.accept()); await page.getByRole('button',{name:'Unregister device'}).click();
    await page.getByRole('button',{name:'Devices'}).click();
    await expect(page.locator('#devicesTab .device-card')).toHaveCount(7);
    await expect(page.locator('#devicesTab .device-summary')).toContainText('7 devices total');
    await expect(page.locator(`[data-device-id="${deviceId}"]`)).toHaveCount(0);
    const retained=await (await request.get(`/pwa/foundation/devices/${deviceId}`,{headers:admin})).json();
    expect(retained.registered).toBeFalsy();
  });

  test('Battery policy and schedules persist and reject invalid threshold relationship', async ({page,request}) => {
    const original=(await (await request.get('/pwa/foundation/policy',{headers:admin})).json()).settings;
    try {
      await app(page); await page.getByRole('button',{name:'Settings'}).click();
      await page.locator('[data-setting="Battery Alerts"]').click();
      await page.locator('#batteryForm [name="battery_alert_percent"]').fill('25');
      await page.locator('#batteryForm [name="critical_battery_percent"]').fill('10');
      const batterySave=page.waitForResponse(r=>r.url().includes('/pwa/foundation/policy')&&r.request().method()==='PATCH');
      await page.locator('#batteryForm button[type="submit"]').click();
      await batterySave;
      await page.reload({waitUntil:'commit'}); await page.getByRole('button',{name:'Settings'}).click();
      await page.locator('[data-setting="Battery Alerts"]').click();
      await expect(page.locator('#batteryForm [name="battery_alert_percent"]')).toHaveValue('25');
      await page.locator('#batteryForm [name="critical_battery_percent"]').fill('25');
      await watchSuccessMessages(page);
      await page.locator('#batteryForm button[type="submit"]').click();
      await expect(page.locator('#phase1Error')).toContainText('Not saved');
      await noFalseSuccess(page);
      await expect(page.locator('#batteryForm [name="battery_alert_percent"]')).toHaveValue('25');
      const persisted=(await (await request.get('/pwa/foundation/policy',{headers:admin})).json()).settings;
      expect(persisted.critical_battery_percent).toBe(10);
      await page.getByRole('button',{name:'Cancel and close'}).click();
      await page.locator('[data-setting="Battery Alerts"]').click();
      await expect(page.locator('#batteryForm [name="critical_battery_percent"]')).toHaveValue('10');
      await page.getByRole('button',{name:'Cancel and close'}).click();
      await page.locator('[data-setting="Device Schedules"]').click();
      await page.locator('#scheduleForm [name="night_bathroom_visit_threshold"]').fill('3');
      await expect(page.locator('#scheduleFeedback')).toHaveAttribute('data-save-feedback','');
      await page.locator('#scheduleForm button[type="submit"]').click();
      await expect(page.locator('[data-save-feedback="success"]')).toHaveText(/saved and applied/i);
      const savedImmediately=(await (await request.get('/pwa/foundation/policy',{headers:admin})).json()).settings;
      expect(savedImmediately.night_bathroom_visit_threshold).toBe(3);
      await expect(page.locator('#scheduleForm [name="night_bathroom_visit_threshold"]')).toHaveValue('3');
      await page.reload({waitUntil:'commit'}); await expect(page.locator('#homeTab .hero')).toBeVisible(); await page.getByRole('button',{name:'Settings'}).click();
      await page.locator('[data-setting="Device Schedules"]').click();
      await expect(page.locator('#scheduleForm [name="night_bathroom_visit_threshold"]')).toHaveValue('3');
      const savedAfterReload=(await (await request.get('/pwa/foundation/policy',{headers:admin})).json()).settings;
      expect(savedAfterReload.night_bathroom_visit_threshold).toBe(3);
    } finally {
      await request.patch('/pwa/foundation/policy',{headers:admin,data:original});
    }
  });

  // This flow must use Playwright routing, rather than an intermittently
  // controlling PWA service worker.  The static-cache behavior itself is
  // covered separately in phase3a_performance.spec.ts.
  test.describe('deterministic failed-save routing', () => {
    test.use({serviceWorkers:'block'});

    test('failed Home Details save stays open and never claims success', async ({page}) => {
      let rejectedPatch=false;
      // Install the route before loading the application.  A fulfilled 503 is
      // a deterministic backend failure and exercises the same UI error path
      // as a real rejected save without depending on abort timing.
      await page.route('**/pwa/foundation/home',async route=>{
        if(route.request().method()!=='PATCH') return route.continue();
        rejectedPatch=true;
        await route.fulfill({
          status:503,
          contentType:'application/json',
          body:JSON.stringify({error:'Simulated save failure'})
        });
      });
      await app(page); await page.getByRole('button',{name:'Settings'}).click();
      await page.locator('[data-setting="Home Details"]').click();
      const displayName=page.locator('#homeDetailsForm [name="display_name"]');
      await displayName.fill('Unavailable save');
      await watchSuccessMessages(page);
      await page.locator('#homeDetailsForm button[type="submit"]').click();
      await expect.poll(()=>rejectedPatch).toBe(true);
      await expect(page.locator('#phase1Dialog')).toBeVisible();
      await expect(page.locator('#phase1Error')).toContainText('Not saved: Simulated save failure');
      await expect(page.locator('#phase1Dialog')).not.toContainText('Home Details saved');
      await expect(displayName).toHaveValue('Unavailable save');
      await noFalseSuccess(page);
    });
  });

  test('simulated online/offline transition updates backend-driven device health', async ({page,request}) => {
    await app(page); await page.getByRole('button',{name:'Devices'}).click();
    const kitchen=page.locator('[data-device-id="kitchen"]');
    try {
      const offline=await request.post('/pwa/foundation/devices/kitchen/health',{headers:admin,data:{online:false,health:'OFFLINE',battery_mv:3920,battery_percent:65,drain_status:'NORMAL'}});
      expect(offline.status()).toBe(200);
      await expect(kitchen).toContainText('Inactive',{timeout:10_000});
      await expect(kitchen).toHaveAttribute('data-status','offline');
      await expect(kitchen).not.toContainText('● Active');
      await expect(page.locator('#devicesTab .device-summary')).toContainText('6');
      await page.getByRole('button',{name:'Home'}).click();
      await expect(page.locator('[data-care-card="device-health"]')).toContainText('Offline: Kitchen Node');
      await expect(page.locator('.timeline')).not.toContainText(/battery percentage|confidence update|mAh\/day/i);
      await page.getByRole('button',{name:'Devices'}).click();
    } finally {
      await request.post('/pwa/foundation/devices/kitchen/health',{headers:admin,data:{online:true,health:'ACTIVE',battery_mv:3920,battery_percent:65,drain_status:'NORMAL'}});
    }
    await expect(kitchen).toContainText('Active',{timeout:10_000});
    await expect(kitchen).toHaveAttribute('data-status','online');
    await page.getByRole('button',{name:'Home'}).click();
    await expect(page.locator('[data-care-card="device-health"]')).not.toContainText('Offline: Kitchen Node');
  });

  test('Network dialog reports host state and hardware boundary without pairing claim',async({page,request})=>{
    await app(page);
    const backend=await (await request.get('/pwa/state')).json();
    await page.getByRole('button',{name:'Settings'}).click();
    await page.locator('[data-setting="Wi‑Fi & Network"]').click();
    const dialog=page.locator('#phase1Dialog');
    await expect(dialog).toContainText(`Hub: ${backend.network.hub_online?'Online':'Offline'}`);
    await expect(dialog).toContainText(`WAN: ${backend.network.wan_online?'Online':'Offline'}`);
    await expect(dialog).toContainText('requires a hub hardware adapter');
    await expect(dialog).not.toContainText(/paired successfully|provisioned successfully|Wi-Fi connected successfully/i);
  });

  test('Family, Manage Devices and Schedules reject invalid saves and discard canceled drafts',async({page,request},testInfo)=>{
    test.setTimeout(180_000);
    await app(page); await page.getByRole('button',{name:'Settings'}).click();
    await page.locator('[data-setting="Family Members"]').click();
    await page.getByRole('button',{name:'Add family member'}).click();
    await page.locator('#memberForm [name="member_id"]').fill('simulation-owner');
    await page.locator('#memberForm [name="display_name"]').fill('Duplicate owner');
    await watchSuccessMessages(page);
    await page.locator('#memberForm button[type="submit"]').click();
    await expect(page.locator('#phase1Error')).toContainText('Not saved');
    await expect(page.locator('#memberForm')).toBeVisible();
    await noFalseSuccess(page);
    await page.locator('#memberForm button[type="button"]').click();
    await expect(page.locator('#phase1Dialog')).not.toContainText('Duplicate owner');
    await page.getByRole('button',{name:'Add family member'}).click();
    const canceledMember=`cancel-family-${testInfo.project.name}`;
    await page.locator('#memberForm [name="member_id"]').fill(canceledMember);
    await page.locator('#memberForm [name="display_name"]').fill('Canceled family');
    await page.locator('#memberForm button[type="button"]').click();
    const members=await (await request.get('/pwa/foundation/members',{headers:admin})).json();
    expect(members.some((m:any)=>m.member_id===canceledMember)).toBe(false);

    await page.getByRole('button',{name:'Cancel and close'}).click();
    await page.locator('[data-setting="Manage Devices"]').click();
    await page.getByRole('button',{name:'Register simulated device'}).click();
    await page.locator('#deviceForm [name="device_id"]').fill('kitchen');
    await page.locator('#deviceForm [name="display_name"]').fill('Duplicate kitchen');
    await page.locator('#deviceForm [name="room"]').selectOption('Kitchen');
    await watchSuccessMessages(page);
    await page.locator('#deviceForm button[type="submit"]').click();
    await expect(page.locator('#phase1Error')).toContainText('Not saved');
    await expect(page.locator('#deviceForm')).toBeVisible();
    await noFalseSuccess(page);
    await page.locator('#deviceForm button[type="button"]').click();
    const canceledDevice=`cancel-device-${testInfo.project.name}`;
    await page.locator('[data-setting="Manage Devices"]').click();
    await page.getByRole('button',{name:'Register simulated device'}).click();
    await page.locator('#deviceForm [name="device_id"]').fill(canceledDevice);
    await page.locator('#deviceForm [name="display_name"]').fill('Canceled device');
    await page.locator('#deviceForm button[type="button"]').click();
    const devices=await (await request.get('/pwa/foundation/devices',{headers:admin})).json();
    expect(devices.some((d:any)=>d.device_id===canceledDevice)).toBe(false);

    const policy=(await (await request.get('/pwa/foundation/policy',{headers:admin})).json()).settings;
    await page.locator('[data-setting="Device Schedules"]').click();
    await expect(page.locator('#scheduleEditor')).toBeVisible();
    await page.locator('#scheduleForm [name="critical_battery_percent"]').fill(String(policy.battery_alert_percent));
    await watchSuccessMessages(page);
    await expect(page.locator('#scheduleFeedback')).toHaveAttribute('data-save-feedback','');
    await page.locator('#scheduleForm button[type="submit"]').click();
    await expect(page.locator('#scheduleEditor')).toBeVisible();
    await expect(page.locator('[data-save-feedback="error"]')).toContainText('Not saved');
    await noFalseSuccess(page);
    const after=(await (await request.get('/pwa/foundation/policy',{headers:admin})).json()).settings;
    expect(after).toEqual(policy);
    await page.locator('#scheduleForm button[type="button"]').click();
    await expect(page.locator('#scheduleEditor')).toHaveCount(0);
    await page.locator('[data-setting="Device Schedules"]').click();
    await expect(page.locator('#scheduleForm [name="critical_battery_percent"]')).toHaveValue(String(policy.critical_battery_percent));
    await expect(page.locator('#homeTab .hero')).not.toHaveClass(/alert/);
  });
});
