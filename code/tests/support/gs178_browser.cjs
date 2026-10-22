// Browser DNS/transport routing stays inside the ephemeral localhost HTTPS
// stack. Every API body comes from its real authenticated service/database.
// NODE_EXTRA_CA_CERTS trusts only the temporary fixture CA for that connection.
const {chromium, expect} = require('../../frontend/node_modules/@playwright/test');
const fs = require('fs');
const path = require('path');
const os = require('os');

(async () => {
  let input='';for await (const chunk of process.stdin) input+=chunk;
  const config=JSON.parse(input);
  const cached=path.join(os.homedir(),'.cache','ms-playwright');
  const candidates=fs.readdirSync(cached).filter(name=>name.startsWith('chromium-')).flatMap(name=>[
    path.join(cached,name,'chrome-linux64','chrome'),path.join(cached,name,'chrome-linux','chrome')]);
  const executablePath=process.env.GS178_CHROMIUM||candidates.find(file=>fs.existsSync(file));
  if(!executablePath)throw Error('GS178 browser executable unavailable');
  const browser=await chromium.launch({headless:true,executablePath,args:['--no-sandbox','--disable-background-networking']});
  try {
    const context=await browser.newContext();
    const requests=[];let offline=false;
    await context.route('**/*',async route=>{
      if(offline){await route.abort('internetdisconnected');return;}
      const original=new URL(route.request().url());
      if(original.origin!=='https://caregiver.gs178.dev')throw Error('unexpected external browser origin');
      const response=await route.fetch({url:config.base+original.pathname+original.search});
      requests.push({path:original.pathname,status:response.status()});
      await route.fulfill({response});
    });
    const page=await context.newPage();
    await page.goto('https://caregiver.gs178.dev/');
    await page.getByLabel('Email').fill('owner@gs178.dev');
    await page.getByLabel('Password',{exact:true}).fill(config.password);
    await page.getByRole('button',{name:'Log in',exact:true}).click();
    if(config.ruleKind){
      await expect(page.locator('.connected-product-event[data-hub-decision]')).toHaveCount(1);
      const ruleLabels={MORNING_ROUTINE_COMPLETED:'Morning routine completed',
        MISSING_MORNING_ACTIVITY:'Morning routine concern',
        UNUSUAL_NIGHT_BATHROOM_ACTIVITY:'Night activity concern',
        UNUSUAL_NIGHT_COMMON_ACTIVITY:'Night activity concern'};
      await expect(page.locator('#homeTab')).toContainText(ruleLabels[config.ruleKind]||config.ruleKind);
      await expect(page.locator('[data-event-key]')).toHaveCount(config.nodeEventCount);
      const decision=page.locator('.connected-product-event[data-hub-decision]');
      await expect(decision).toContainText('Decision ID:');
      if((await decision.textContent()).includes('EventKey:'))throw Error('Hub decision falsely rendered with Node EventKey');
      let assertions=5;
      if(config.routineKind){
        await page.locator('[data-tab="reports"]').click();
        await page.locator('[data-open-tab="routines"]').click();
        await expect(page.locator('#homeTab [data-hub-decision]')).toHaveCount(1);
        await expect(page.locator('#homeTab')).toContainText(config.routineKind);
        await expect(page.locator('#homeTab')).toContainText('NOT_ENABLED');
        assertions+=3;
      }
      fs.writeFileSync(config.dom,await page.content());
      console.log(JSON.stringify({status:'HOST_SIM_PASS',browser_assertions:assertions,requests,physical:'NOT_RUN'}));
      return;
    }
    const expectedEventCount=config.eventCount||2;
    await expect(page.locator('[data-event-key]')).toHaveCount(expectedEventCount);
    if(config.eventKeys){
      const renderedKeys=await page.locator('[data-event-key]').evaluateAll(nodes=>
        nodes.map(node=>JSON.parse(node.getAttribute('data-event-key'))));
      expect(renderedKeys).toEqual(config.eventKeys);
    }
    await expect(page.locator('#homeTab')).toContainText('Motion recorded');
    await expect(page.locator('#homeTab')).toContainText('Call Family request');
    await expect(page.locator('#homeTab')).toContainText('bedroom');
    let homeMonitoringAssertions=0;
    if(config.monitoring){
      const homeMonitoring=page.locator('#homeTab .connected-home-hero');
      const heading=config.sourceFreshness==='CURRENT'&&config.monitoring==='COVERED'
        ?'Monitoring coverage is current'
        :config.sourceFreshness==='STALE'?'Monitoring source is stale':'Monitoring status is unknown';
      await expect(homeMonitoring).toHaveAttribute('data-source-freshness',config.sourceFreshness);
      await expect(homeMonitoring).toHaveAttribute('data-monitoring',config.monitoring);
      await expect(homeMonitoring).toContainText(heading);
      await expect(page.locator('#homeTab')).toContainText(config.source);
      homeMonitoringAssertions=3;
    }
    await page.locator('[data-tab="devices"]').click();
    await expect(page.locator('[data-node-id]')).toHaveCount(config.nodeCount||2);
    await expect(page.locator('#homeTab')).toContainText('ONLINE');
    await page.locator('[data-tab="reports"]').click();
    await page.locator('[data-open-tab="incidents"]').click();
    for(const [action,state] of [['claim','CLAIMED'],['acknowledge','ACKNOWLEDGED'],['resolve','RESOLVED']]){
      await page.locator(`[data-incident-action="${action}"]`).click();
      await expect(page.locator('[data-incident-id]')).toContainText(state);
    }
    await page.reload();
    await page.locator('[data-tab="reports"]').click();
    await page.locator('[data-open-tab="incidents"]').click();
    await expect(page.locator('[data-incident-id]')).toContainText('RESOLVED');
    offline=true;await context.setOffline(true);
    await page.locator('[data-tab="home"]').click();
    await expect(page.locator('#connectionStatus')).toContainText('OFFLINE');
    await expect(page.locator('#homeTab .connected-home-hero')).toHaveAttribute('data-monitoring','UNKNOWN');
    await expect(page.locator('#homeTab .connected-home-hero')).toContainText('Monitoring status is unknown');
    await expect(page.locator('[data-event-key]')).toHaveCount(0);
    offline=false;await context.setOffline(false);
    await page.locator('[data-tab="home"]').click();
    await expect(page.locator('[data-event-key]')).toHaveCount(expectedEventCount);
    if(config.eventKeys){
      const reloadedKeys=await page.locator('[data-event-key]').evaluateAll(nodes=>
        nodes.map(node=>JSON.parse(node.getAttribute('data-event-key'))));
      expect(reloadedKeys).toEqual(config.eventKeys);
    }
    let assertions=14+homeMonitoringAssertions;
    if(config.routineKind){
      await page.locator('[data-tab="reports"]').click();
      await page.locator('[data-open-tab="routines"]').click();
      await expect(page.locator('#routinesTab [data-hub-decision]')).toHaveCount(1);
      await expect(page.locator('#routinesTab')).toContainText(config.routineKind);
      await expect(page.locator('#routinesTab')).toContainText('NOT_ENABLED');
      assertions+=3;
    }
    fs.writeFileSync(config.dom,await page.content());
    console.log(JSON.stringify({status:'HOST_SIM_PASS',browser_assertions:assertions,requests,physical:'NOT_RUN'}));
  } finally {await browser.close();}
})().catch(error=>{console.error(error.stack);process.exit(1)});
