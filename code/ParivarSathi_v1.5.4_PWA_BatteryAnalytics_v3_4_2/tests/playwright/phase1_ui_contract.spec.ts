import { test, expect } from '@playwright/test';
import contract from '../validation/phase1_ui_contract.json';

const card = (page: any, id: string) => page.locator(`[data-care-card="${id}"]`);
const forbidden = {
  morning: /main door|door has|night activity is|battery|mAh\/day|confidence/i,
  ok: /main door|bathroom|common.room|battery|morning routine/i,
  door: /bathroom|common.room|battery|morning activity|mAh\/day|confidence/i,
  night: /main door|door has|opened during|indoor activity|battery|morning routine|mAh\/day|confidence/i,
  health: /mAh\/day|confidence|wakes\/day|RF retries|alert below|threshold|sample count|main door has|bathroom visits|morning activity/i,
  events: /battery (?:low|restored|percentage|runtime|consumption|confidence|threshold)|mAh\/day|RF retries|raw device diagnostic/i
};
const duration = (seconds: number) => {
  const s=Math.max(0,Math.floor(seconds)), h=Math.floor(s/3600), m=Math.floor(s%3600/60);
  return h&&m?`${h} hr ${m} min`:h?`${h} hr`:m?`${m} min`:`${s} sec`;
};
const count = (n: number) => `${n} ${n===1?'time':'times'}`;
async function post(request: any, url: string, data: any) {
  const response=await request.post(url,{data});
  expect(response.ok(),`${url} ${JSON.stringify(data)}: ${response.status()}`).toBeTruthy();
  return response.json();
}
async function ready(page: any) {
  await page.goto('/',{waitUntil:'commit'});
  await expect(page.locator('#homeTab .hero')).toBeVisible();
}
async function assertHome(page: any, request: any) {
  const view=await (await request.get('/pwa/state')).json();
  await page.reload({waitUntil:'commit'});
  const hero=page.locator('#homeTab .hero');
  await expect(hero).toBeVisible();
  await expect(hero).toHaveAttribute('data-severity',view.care.alert?'danger':'success');
  await expect(hero).toContainText(view.care.alert?'Attention needed at home':'Home looks normal');
  await expect(hero).not.toContainText(/Morning routine|Main door|Night activity|battery|I am OK/i);

  const morning=card(page,'morning');
  const morningSeverity: Record<string,string>={NOT_STARTED:'neutral',UNAVAILABLE:'neutral',IN_PROGRESS:'warning',COMPLETED:'success',MISSED:'danger'};
  const morningText: Record<string,string>={NOT_STARTED:'Not started',UNAVAILABLE:'Not started',IN_PROGRESS:'In progress',COMPLETED:'Completed',MISSED:'Activity not completed'};
  await expect(morning).toHaveAttribute('data-status',view.morning.status);
  await expect(morning).toHaveAttribute('data-severity',morningSeverity[view.morning.status]);
  await expect(morning).toContainText(morningText[view.morning.status]);
  const morningColor=await morning.getByText(morningText[view.morning.status],{exact:true}).evaluate((el:any)=>getComputedStyle(el).color);
  const expectedColors:Record<string,string>={NOT_STARTED:'rgb(99, 116, 154)',UNAVAILABLE:'rgb(99, 116, 154)',IN_PROGRESS:'rgb(235, 169, 0)',COMPLETED:'rgb(13, 138, 67)',MISSED:'rgb(217, 25, 32)'};
  expect(morningColor).toBe(expectedColors[view.morning.status]);
  await expect(morning).not.toContainText(forbidden.morning);
  if(view.morning.status==='IN_PROGRESS') {
    await expect(morning.locator('.status-amber')).toBeVisible();
    await expect(morning.locator('.status-bad')).toHaveCount(0);
  }

  const ok=card(page,'ok');
  await expect(ok).toHaveAttribute('data-status',view.iam_ok.status);
  await expect(ok).toHaveAttribute('data-severity',view.iam_ok.ok?'success':'danger');
  await expect(ok).toContainText(view.iam_ok.status==='OVERDUE'?'I am OK overdue':view.iam_ok.status==='ACKNOWLEDGED'?'Just confirmed':'Confirmed');
  if(view.iam_ok.ok) await expect(ok).not.toHaveClass(/alert/);
  else await expect(ok).toHaveClass(/alert/);
  await expect(ok).not.toContainText(forbidden.ok);

  const door=card(page,'door');
  await expect(door.getByText(view.door.open?'Open':'Closed',{exact:true})).toBeVisible();
  const doorAlert=view.door.left_open_alert||view.door.unexpected_alert||view.door.post_close_inactivity_alert;
  if(doorAlert) await expect(door).toHaveClass(/alert/);
  else await expect(door).not.toHaveClass(/alert/);
  if(view.door.left_open_alert) {
    expect(view.door.open_for_s).toBeGreaterThanOrEqual(view.schedules.door_open_timeout_seconds);
    await expect(door).toContainText(`Open for ${duration(view.door.open_for_s)}`);
    await expect(door).not.toContainText(/has remained open longer than configured|door is currently open/i);
  } else if(view.door.open&&!view.door.unexpected_alert) {
    await expect(door).toContainText('Door is currently open');
    await expect(door).not.toContainText('Open for');
  }
  await expect(door).not.toContainText(forbidden.door);

  const night=card(page,'night');
  if(view.night.unusual) await expect(night).toHaveClass(/alert/);
  else await expect(night).not.toHaveClass(/alert/);
  await expect(night).toContainText(`Bathroom: ${count(view.night.bathroom_visits)}`);
  await expect(night).toContainText(`Common room: ${count(view.night.common_visits)}`);
  await expect(night).toContainText(view.night.unusual?'Unusual activity':'No unusual activity');
  if(view.night.unusual) await expect(night).toContainText(view.night.concern_text);
  else await expect(night).not.toContainText(/visits are higher than the configured night limit/i);
  await expect(night).not.toContainText(forbidden.night);

  const health=card(page,'device-health');
  await expect(health).toHaveAttribute('data-severity',view.device_health.attention?'danger':'neutral');
  if(view.coverage.lost) await expect(health).toContainText('Monitoring coverage lost');
  else await expect(health).not.toContainText('Monitoring coverage lost');
  if(view.device_health.low_percent!=null) {
    await expect(health).toContainText(`${view.device_health.low_name} ${view.device_health.low_percent}%`);
    const raw=String(view.device_health.runtime||'');
    const unavailable=!raw||/^(calculating|recharge now|unknown)$/i.test(raw);
    await expect(health).toContainText(`Estimated time left: ${unavailable?'Collecting battery data':raw}`);
    if(!unavailable) await expect(health).not.toContainText('Collecting battery data');
    if(view.device_health.low_percent<=view.device_health.alert_percent) await expect(health).toContainText('Recharge now');
    else await expect(health).not.toContainText('Recharge now');
  }
  for(const id of view.device_health.offline_devices||[]) {
    const device=view.devices.find((d:any)=>d.id===id);
    await expect(health).toContainText(`Offline: ${device.name}`);
  }
  await expect(health).not.toContainText(forbidden.health);

  const events=page.locator('.timeline');
  await expect(events).not.toContainText(forbidden.events);
  const rendered=await events.locator('.event-pill').allTextContents();
  expect(rendered).toEqual(view.events.map((e:any)=>e.title));
  expect(view.events.map((e:any)=>e.at)).toEqual([...view.events.map((e:any)=>e.at)].sort((a:number,b:number)=>b-a));
  return view;
}

test.describe('Phase 1 visible contract and contamination matrix',()=>{
  test.beforeEach(async({request})=>{await post(request,'/pwa/action',{action:'reset_pass'});});
  test.afterEach(async({request})=>{await post(request,'/pwa/action',{action:'reset_pass'});});

  test('single-feature state axes and exact presentation',async({page,request})=>{
    test.setTimeout(240_000);
    await ready(page);
    const scenarios:[string,()=>Promise<any>][]=[
      ['normal PASS',async()=>{}],
      ['morning NOT_STARTED',async()=>{await post(request,'/sim/action',{action:'reset'});}],
      ['morning IN_PROGRESS',async()=>{await post(request,'/sim/action',{action:'reset'});await post(request,'/sim/action',{action:'event',node:'room1',kind:'MOTION'});}],
      ['morning MISSED',async()=>{await post(request,'/pwa/action',{action:'toggle',scenario:'morning'});}],
      ['door OPEN_WITHIN_LIMIT',async()=>{await post(request,'/sim/action',{action:'event',node:'entry',kind:'DOOR_OPEN'});}],
      ['door OPEN_TOO_LONG',async()=>{await post(request,'/pwa/action',{action:'toggle',scenario:'door'});}],
      ['night UNUSUAL_BATHROOM',async()=>{await post(request,'/pwa/action',{action:'toggle',scenario:'night'});}],
      ['night singular bathroom count',async()=>{await post(request,'/sim/action',{action:'time',minute:1380});await post(request,'/sim/action',{action:'event',node:'bathroom',kind:'MOTION'});}],
      ['night UNUSUAL_COMMON_ROOM',async()=>{await post(request,'/pwa/validation/run',{scenario_id:'night-common-over-limit-alerts'});}],
      ['battery CRITICAL + insufficient runtime',async()=>{await post(request,'/pwa/action',{action:'toggle',scenario:'battery'});}],
      ['battery LOW + runtime',async()=>{await post(request,'/sim/action',{action:'battery_usage',target:'kitchen',days:3,intensity:1,battery_mv:3600});}],
      ['battery LOW + insufficient history',async()=>{await post(request,'/sim/action',{action:'battery_usage',target:'kitchen',days:3,intensity:1,battery_mv:3600});await post(request,'/sim/action',{action:'battery_counter_reset',target:'kitchen',battery_mv:3600});}],
      ['device OFFLINE',async()=>{await post(request,'/sim/action',{action:'node',node:'kitchen',enabled:false});}],
      ['I am OK concern',async()=>{await post(request,'/pwa/action',{action:'toggle',scenario:'ok'});}],
      ['I am OK acknowledged',async()=>{await post(request,'/sim/action',{action:'event',node:'room1',kind:'OK_PRESSED'});}]
    ];
    for(const [name,setup] of scenarios) await test.step(name,async()=>{
      await post(request,'/pwa/action',{action:'reset_pass'});
      await setup();
      const view=await assertHome(page,request);
      if(name==='morning IN_PROGRESS') {
        expect(view.care.alert).toBe(false);
        await expect(card(page,'morning').locator('.status-amber')).toBeVisible();
      }
      if(name==='battery LOW + runtime') expect(view.device_health.runtime).toMatch(/~\d+ (days|hrs)/);
      if(name==='battery LOW + insufficient history') expect(view.device_health.runtime).toBe('calculating');
    });
  });

  test('deterministic pairwise and high-risk three-way concern interactions',async({page,request})=>{
    test.setTimeout(240_000);
    await ready(page);
    const combinations=[...contract.pairwise,...contract.high_risk_three_way];
    for(const names of combinations) await test.step(names.join(' + '),async()=>{
      await post(request,'/pwa/action',{action:'reset_pass'});
      for(const name of names) {
        if(name==='offline') await post(request,'/sim/action',{action:'node',node:'kitchen',enabled:false});
        else await post(request,'/pwa/action',{action:'toggle',scenario:name});
      }
      const view=await assertHome(page,request);
      for(const name of names) {
        if(name==='door') expect(view.door.left_open_alert).toBe(true);
        if(name==='night') expect(view.night.unusual).toBe(true);
        if(name==='battery') expect(view.device_health.attention).toBe(true);
        if(name==='offline') expect(view.device_health.offline_devices).toContain('kitchen');
        if(name==='morning') expect(view.morning.status).toBe('MISSED');
        if(name==='ok') expect(view.iam_ok.ok).toBe(false);
      }
      expect(view.care.alert).toBe(names.some(n=>['door','night','morning','ok'].includes(n)));
    });
  });

  test('all exposed caregiver toggles recover without cross-card residue',async({page,request})=>{
    test.setTimeout(180_000);
    await ready(page);
    const fields=(view:any)=>({morning:view.morning.status,ok:view.iam_ok.ok,door:view.door.open,night:view.night.unusual,battery:view.device_health.low_percent});
    for(const name of ['morning','ok','door','night','battery']) await test.step(`${name} concern → recovery`,async()=>{
      await post(request,'/pwa/action',{action:'reset_pass'});
      const base=fields(await (await request.get('/pwa/state')).json());
      await post(request,'/pwa/action',{action:'toggle',scenario:name});
      const negative=await assertHome(page,request);
      const changed=fields(negative);
      expect(changed[name as keyof typeof changed]).not.toEqual(base[name as keyof typeof base]);
      for(const feature of Object.keys(base).filter(x=>x!==name)) expect(changed[feature as keyof typeof changed]).toEqual(base[feature as keyof typeof base]);
      await post(request,'/pwa/action',{action:'toggle',scenario:name});
      const recovered=await assertHome(page,request);
      expect(fields(recovered)).toEqual(base);
      expect(recovered.care.alert).toBe(false);
      await expect(page.locator('.timeline')).not.toContainText(/battery low|battery restored|runtime recalculation/i);
    });
  });

  test('required-node lease expiry is real coverage loss with scoped Home concern and care event',async({page,request})=>{
    await ready(page);
    const base=await (await request.get('/pwa/state')).json();
    await post(request,'/sim/action',{action:'node',node:'kitchen',enabled:false});
    const immediate=await assertHome(page,request);
    expect(immediate.coverage).toEqual({state:'COVERED',lost:false});
    expect(immediate.care.alert).toBe(false);
    expect(immediate.device_health.offline_devices).toContain('kitchen');
    await expect(page.locator('.timeline')).not.toContainText('Monitoring coverage lost');

    await post(request,'/sim/action',{action:'advance',seconds:191});
    const domain=await (await request.get('/sim/state')).json();
    expect(domain.simulation.coverage).toBe('UNKNOWN');
    expect(domain.timeline.some((e:any)=>e.kind==='COVERAGE_CHANGED'&&e.details.reason==='coverage_lost')).toBe(true);
    const lost=await assertHome(page,request);
    expect(lost.coverage).toEqual({state:'UNKNOWN',lost:true});
    expect(lost.care.problem_kind).toBe('MONITORING_COVERAGE_LOST');
    await expect(card(page,'device-health')).toContainText('Offline: Kitchen Node');
    await expect(page.locator('.timeline .event-pill').first()).toHaveText('Monitoring coverage lost');
    await expect(card(page,'door')).not.toContainText(/Monitoring coverage|battery|bathroom/i);
    await expect(card(page,'night')).not.toContainText(/Monitoring coverage|main door|battery/i);
    expect(lost.morning.status).toBe(base.morning.status);
    expect(lost.iam_ok.status).toBe(base.iam_ok.status);
    expect(lost.door.open).toBe(base.door.open);
    expect(lost.night.unusual).toBe(base.night.unusual);
    expect(lost.device_health.low_percent).toBe(base.device_health.low_percent);

    await post(request,'/sim/action',{action:'node',node:'kitchen',enabled:true});
    await post(request,'/sim/action',{action:'advance',seconds:60});
    const recovered=await assertHome(page,request);
    expect(recovered.coverage).toEqual({state:'COVERED',lost:false});
    expect(recovered.care.alert).toBe(false);
    expect(recovered.device_health.offline_devices).not.toContain('kitchen');
    await expect(page.locator('.timeline .event-pill').first()).toHaveText('Monitoring coverage restored');
    await expect(page.locator('.timeline .event-pill').nth(1)).toHaveText('Monitoring coverage lost');
  });

  test('I am OK overdue concern clears on real acknowledgement with chronological events',async({page,request})=>{
    await ready(page);
    const base=await (await request.get('/pwa/state')).json();
    await post(request,'/pwa/action',{action:'toggle',scenario:'ok'});
    const overdue=await assertHome(page,request);
    expect(overdue.iam_ok).toMatchObject({ok:false,status:'OVERDUE'});
    expect(overdue.care.alert).toBe(true);
    expect(overdue.care.problem_kind).toBe('I_AM_OK_OVERDUE');
    await expect(card(page,'ok')).toContainText('I am OK overdue');
    await expect(page.locator('.timeline .event-pill').first()).toHaveText("I'm OK not confirmed");
    for(const [path,value] of [['morning.status',base.morning.status],['door.open',base.door.open],['night.unusual',base.night.unusual],['device_health.low_percent',base.device_health.low_percent]] as const) {
      const [domain,field]=path.split('.');
      expect(overdue[domain][field]).toBe(value);
    }

    await post(request,'/sim/action',{action:'advance',seconds:120});
    await post(request,'/sim/action',{action:'event',node:'room1',kind:'OK_PRESSED'});
    const domain=await (await request.get('/sim/state')).json();
    expect(domain.timeline.some((e:any)=>e.kind==='OK_PRESSED')).toBe(true);
    const acknowledged=await assertHome(page,request);
    expect(acknowledged.iam_ok).toMatchObject({ok:true,status:'ACKNOWLEDGED'});
    expect(acknowledged.care.alert).toBe(false);
    await expect(card(page,'ok')).toContainText('Just confirmed');
    await expect(card(page,'ok')).not.toContainText('overdue');
    await expect(page.locator('.timeline .event-pill').first()).toHaveText("I'm OK received");
    await expect(page.locator('.timeline .event-pill').nth(1)).toHaveText("I'm OK not confirmed");
    expect(acknowledged.events[0].at).toBeGreaterThan(acknowledged.events[1].at);
    expect(acknowledged.morning.status).toBe(base.morning.status);
    expect(acknowledged.door.open).toBe(base.door.open);
    expect(acknowledged.night.unusual).toBe(base.night.unusual);
    expect(acknowledged.device_health.low_percent).toBe(base.device_health.low_percent);
  });

  test('offline I am OK press waits for backend acceptance before clearing caregiver concern',async({page,request})=>{
    await ready(page);
    await post(request,'/pwa/action',{action:'toggle',scenario:'ok'});
    await post(request,'/sim/action',{action:'wan',enabled:false});
    await post(request,'/sim/action',{action:'advance',seconds:120});
    await post(request,'/sim/action',{action:'event',node:'room1',kind:'OK_PRESSED'});
    const domain=await (await request.get('/sim/state')).json();
    expect(domain.timeline.some((e:any)=>e.kind==='OK_PRESSED')).toBe(false);
    const pending=await assertHome(page,request);
    expect(pending.iam_ok.status).toBe('OVERDUE');
    expect(pending.care.alert).toBe(true);
    await expect(card(page,'ok')).toContainText('I am OK overdue');
    await expect(page.locator('.timeline')).not.toContainText("I'm OK received");
    await post(request,'/sim/action',{action:'wan',enabled:true});
    const delivered=await assertHome(page,request);
    expect(delivered.iam_ok.status).toBe('ACKNOWLEDGED');
    expect(delivered.care.alert).toBe(false);
    await expect(card(page,'ok')).not.toContainText('overdue');
    await expect(page.locator('.timeline .event-pill').first()).toHaveText("I'm OK received");
  });
});
