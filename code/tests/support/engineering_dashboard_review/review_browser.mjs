// Playwright review-artifact preparation only; no production PWA acceptance.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'../../../..');
const reviewSource=path.join(root,'docs/exec-plans/evidence/engineering_dashboard_20261012');
const output=path.join(root,'code/build/engineering_dashboard_preview');
await mkdir(output,{recursive:true});
const require=createRequire(path.join(root,'code/frontend/package.json'));
const {chromium}=require('@playwright/test');
const fixture=JSON.parse(await readFile(path.join(reviewSource,'REVIEW_FIXTURE.json'),'utf8'));
const screenCases=[
  {id:'overview',test:'ED-PREVIEW-OVERVIEW-DESKTOP-001'},
  {id:'live',test:'ED-PREVIEW-LIVE-DESKTOP-001'},
  {id:'trace',test:'ED-PREVIEW-TRACE-DESKTOP-001'},
  {id:'device',test:'ED-PREVIEW-DEVICE-DESKTOP-001'},
  {id:'communication',test:'ED-PREVIEW-COMMUNICATION-DESKTOP-001'},
  {id:'installation',test:'ED-PREVIEW-INSTALLATION-DESKTOP-001'},
  {id:'advanced',test:'ED-PREVIEW-ADVANCED-DESKTOP-001'},
];
const server=createServer(async(req,res)=>{
  const filename=req.url==='/review.html'?'review.html':req.url==='/REVIEW_FIXTURE.json'?'REVIEW_FIXTURE.json':null;
  if(req.method!=='GET'||!filename){res.writeHead(404);res.end();return;}
  try{const data=await readFile(path.join(reviewSource,filename));res.writeHead(200,{'content-type':filename.endsWith('.html')?'text/html':'application/json','cache-control':'no-store'});res.end(data);}catch{res.writeHead(503);res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
let browser;const rows=[];
try{
  browser=await chromium.launch({headless:true});
  for(const viewport of [{name:'desktop',width:1440,height:1000},{name:'mobile',width:390,height:844}]){
    const page=await browser.newPage({viewport:{width:viewport.width,height:viewport.height}});const errors=[];const mutations=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(r.method()!=='GET')mutations.push(r.method()+' '+r.url());});
    await page.goto(`http://127.0.0.1:${server.address().port}/review.html`);
    await page.locator('body[data-ready=true]').waitFor();
    assert.match(await page.locator('.banner').textContent(),/INACTIVE DESIGN PREVIEW/);
    for(const {id,test} of screenCases){
      await page.locator(`nav button[data-screen=${id}]`).click();
      assert.equal(await page.locator(`#${id}`).isVisible(),true);
      const screenCase=test.replace('DESKTOP',viewport.name.toUpperCase());
      rows.push({id:screenCase,result:'PASS',scope:'PREVIEW_ONLY'});
      console.log(`CASE ${screenCase} PASS`);
    }
    await page.locator('[data-screen=trace]').click();
    assert.equal(await page.locator('.trace-row').count(),10);
    assert.equal(await page.locator('.trace-row[data-result=UNKNOWN]').count(),9);
    assert.equal(await page.locator('.trace-row[data-result=PASS]').count(),1);
    assert.equal(await page.locator('#event-key').textContent(),fixture.trace.canonical_event_id);
    assert.equal(await page.locator('[data-stage=backend_committed]').getAttribute('data-result'),'PASS');
    const traceCase=`ED-PREVIEW-TRACE-UNKNOWN-${viewport.name.toUpperCase()}-001`;
    rows.push({id:traceCase,result:'PASS',scope:'PREVIEW_ONLY'});console.log(`CASE ${traceCase} PASS`);
    await page.locator('[data-screen=live]').click();
    assert.equal(await page.locator('#events tr').count(),1);
    assert.match(await page.locator('#events').textContent(),new RegExp(fixture.original_location));
    await page.locator('#kind-filter').selectOption('DOOR_OPEN');
    assert.equal(await page.locator('#events tr').count(),0);
    await page.locator('#kind-filter').selectOption('MOTION');
    assert.equal(await page.locator('#events tr').count(),1);
    await page.locator('#refresh').click();
    await page.waitForTimeout(50);
    assert.equal(await page.locator('#events tr').count(),1);
    const filterCase=`ED-PREVIEW-LIVE-FILTER-${viewport.name.toUpperCase()}-001`;
    rows.push({id:filterCase,result:'PASS',scope:'PREVIEW_ONLY'});console.log(`CASE ${filterCase} PASS`);
    await page.reload();await page.locator('body[data-ready=true]').waitFor();
    await page.locator('[data-screen=trace]').click();
    assert.equal(await page.locator('#event-key').textContent(),fixture.trace.canonical_event_id);
    await page.locator('[data-screen=installation]').click();
    assert.match(await page.locator('#installation').textContent(),/NOT_TESTED/);
    assert.equal(await page.locator('#installation button').isDisabled(),true);
    await page.locator('[data-screen=advanced]').click();
    assert.equal(await page.locator('#advanced button:disabled').count(),3);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    const stateCase=`ED-PREVIEW-STATE-DISABLED-LAYOUT-${viewport.name.toUpperCase()}-001`;
    rows.push({id:stateCase,result:'PASS',scope:'PREVIEW_ONLY'});console.log(`CASE ${stateCase} PASS`);
    assert.deepEqual(errors,[]);assert.deepEqual(mutations,[]);
    await page.locator('[data-screen=trace]').click();
    await page.screenshot({path:path.join(output,`review-${viewport.width}.png`),fullPage:true});
    await page.close();
  }
  assert.equal(rows.length,20,'preview case manifest is incomplete');
  await writeFile(path.join(output,'review_browser_results.json'),JSON.stringify({scope:'PREVIEW_ONLY',screens:7,viewports:2,checks:rows.length,cases:rows,production_qualification:'BLOCKED',physical:'NOT_RUN'},null,2)+'\n');
  console.log(`ENGINEERING DASHBOARD PREVIEW PASS screens=7 viewports=2 cases=${rows.length} scope=PREVIEW_ONLY production_qualification=BLOCKED physical=NOT_RUN output=code/build/engineering_dashboard_preview`);
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
