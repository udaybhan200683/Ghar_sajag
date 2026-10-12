import {test,expect} from '@playwright/test';

async function waitForHome(page:any){
  await page.goto('/',{waitUntil:'commit'});
  await expect(page.locator('#homeTab .hero')).toBeVisible();
}

test.describe('Phase 3A lightweight runtime contracts',()=>{
  test.beforeEach(async({request})=>{await request.post('/sim/action',{data:{action:'reset',test_fixture:true}})});

  test('keeps initial Home minimal and navigation does not multiply timers, listeners, or DOM rows',async({page},testInfo)=>{
    await page.addInitScript(()=>{
      const state={intervals:0,listeners:0};
      (window as any).__phase3Runtime=state;
      const nativeInterval=window.setInterval.bind(window);
      window.setInterval=((handler:any,timeout?:number,...args:any[])=>{state.intervals+=1;return nativeInterval(handler,timeout,...args)}) as typeof window.setInterval;
      const nativeAdd=EventTarget.prototype.addEventListener;
      EventTarget.prototype.addEventListener=function(type:any,listener:any,options:any){state.listeners+=1;return nativeAdd.call(this,type,listener,options)};
    });
    const requests:string[]=[];
    page.on('request',request=>requests.push(new URL(request.url()).pathname+new URL(request.url()).search));
    await waitForHome(page);
    await page.waitForTimeout(300);
    const cdp=await page.context().newCDPSession(page);
    await cdp.send('Performance.enable');
    const beforeMetrics=await cdp.send('Performance.getMetrics');
    const domCounts:any={home:await page.locator('#homeTab *').count()};
    expect(requests.some(path=>path.startsWith('/v1/homes/')&&path.includes('/reports'))).toBe(false);
    expect(requests.some(path=>path==='/pwa/state')).toBe(false);
    expect(requests.some(path=>path==='/pwa/validation/catalog')).toBe(false);
    expect(requests.some(path=>path==='/pwa/state?scope=home')).toBe(true);
    const baseline=await page.evaluate(()=>(window as any).__phase3Runtime);

    for(let index=0;index<10;index+=1){
      await page.getByRole('button',{name:'Devices'}).click();
      await expect(page.locator('#devicesTab .device-card')).toHaveCount(7);
      if(index===0)domCounts.devices=await page.locator('#devicesTab *').count();
      await page.getByRole('button',{name:'Home'}).click();
      await expect(page.locator('#homeTab [data-care-card]')).toHaveCount(5);
    }
    const after=await page.evaluate(()=>(window as any).__phase3Runtime);
    expect(after.intervals).toBe(baseline.intervals);
    expect(after.listeners).toBe(baseline.listeners);
    await expect(page.locator('#homeTab [data-care-card="device-health"]')).toHaveCount(1);
    await expect(page.locator('#homeTab .timeline')).toHaveCount(1);
    const afterMetrics=await cdp.send('Performance.getMetrics');
    await testInfo.attach('phase3a-browser-resource-trend.json',{body:Buffer.from(JSON.stringify({domCounts,beforeMetrics,afterMetrics},null,2)),contentType:'application/json'});
  });

  test('loads Reports on demand, prevents overlapping refreshes, and Settings avoids full state',async({page},testInfo)=>{
    let reportInFlight=0,maxReportInFlight=0;
    const paths:string[]=[];
    page.on('request',request=>paths.push(new URL(request.url()).pathname+new URL(request.url()).search));
    await page.route('**/v1/homes/*/reports*',async route=>{
      reportInFlight+=1;maxReportInFlight=Math.max(maxReportInFlight,reportInFlight);
      await new Promise(resolve=>setTimeout(resolve,2500));
      const response=await route.fetch();
      await route.fulfill({response});
      reportInFlight-=1;
    });
    await waitForHome(page);
    const fullBefore=paths.filter(path=>path==='/pwa/state').length;
    await page.getByRole('button',{name:'Settings'}).click();
    await expect(page.locator('#settingsTab [data-setting="Notifications"]')).toBeVisible();
    expect(paths.filter(path=>path==='/pwa/state').length).toBe(fullBefore);
    expect(paths.some(path=>path.includes('/reports'))).toBe(false);
    await page.getByRole('button',{name:'Reports'}).click();
    await expect(page.locator('[data-report-status="no-data"]').first()).toBeVisible({timeout:10_000});
    expect(maxReportInFlight).toBe(1);
    await page.getByRole('button',{name:'Reports'}).click();
    await page.waitForTimeout(500);
    expect(maxReportInFlight).toBe(1);
    await testInfo.attach('phase3a-request-behavior.json',{body:Buffer.from(JSON.stringify({paths,maxReportInFlight},null,2)),contentType:'application/json'});
  });

  test('keeps the service-worker cache static-only and bounded',async({page})=>{
    await waitForHome(page);
    const cached=await page.evaluate(async()=>{
      await navigator.serviceWorker.ready;
      const keys=await caches.keys();
      const requests=[] as string[];
      for(const key of keys)for(const request of await (await caches.open(key)).keys())requests.push(new URL(request.url).pathname);
      return {keys,requests};
    });
    expect(cached.requests.length).toBeLessThanOrEqual(9);
    expect(cached.requests.some(path=>path.startsWith('/pwa/')||path.startsWith('/v1/'))).toBe(false);
  });

  test('recovers after a temporary compact-state failure without losing the last safe presentation',async({page,request})=>{
    await waitForHome(page);
    let failed=false;
    await page.route('**/pwa/state?scope=home',route=>{
      if(!failed){failed=true;return route.abort()}
      return route.continue();
    });
    await page.waitForTimeout(2300);
    await expect(page.locator('#homeTab .hero')).toBeVisible();
    await request.post('/pwa/action',{data:{action:'toggle',scenario:'ok'}});
    await expect(page.locator('[data-care-card="ok"]')).toContainText('I am OK overdue',{timeout:6000});
  });
});
