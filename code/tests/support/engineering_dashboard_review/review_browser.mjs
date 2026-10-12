// Playwright review-artifact preparation only; no production PWA acceptance.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'../../../..');
const evidence=path.join(root,'docs/exec-plans/evidence/engineering_dashboard_20261012');
const require=createRequire(path.join(root,'code/frontend/package.json'));
const {chromium}=require('@playwright/test');
const fixture=JSON.parse(await readFile(path.join(evidence,'REVIEW_FIXTURE.json'),'utf8'));
const server=createServer(async(req,res)=>{
  const filename=req.url==='/review.html'?'review.html':req.url==='/REVIEW_FIXTURE.json'?'REVIEW_FIXTURE.json':null;
  if(req.method!=='GET'||!filename){res.writeHead(404);res.end();return;}
  try{const data=await readFile(path.join(evidence,filename));res.writeHead(200,{'content-type':filename.endsWith('.html')?'text/html':'application/json','cache-control':'no-store'});res.end(data);}catch{res.writeHead(503);res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
let browser;const rows=[];
try{
  browser=await chromium.launch({headless:true});
  for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
    const page=await browser.newPage({viewport});const errors=[];const mutations=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(r.method()!=='GET')mutations.push(r.method()+' '+r.url());});
    await page.goto(`http://127.0.0.1:${server.address().port}/review.html`);
    await page.locator('body[data-ready=true]').waitFor();
    assert.match(await page.locator('.banner').textContent(),/INACTIVE DESIGN PREVIEW/);
    for(const id of ['overview','live','trace','device','communication','installation','advanced']){
      await page.locator(`nav button[data-screen=${id}]`).click();
      assert.equal(await page.locator(`#${id}`).isVisible(),true);
      rows.push({id:`REVIEW-${viewport.width}-${id}`,result:'PASS',scope:'REVIEW_ARTIFACT_ONLY'});
    }
    await page.locator('[data-screen=trace]').click();
    assert.equal(await page.locator('.trace-row').count(),10);
    assert.equal(await page.locator('.trace-row[data-result=UNKNOWN]').count(),9);
    assert.equal(await page.locator('.trace-row[data-result=PASS]').count(),1);
    assert.equal(await page.locator('#event-key').textContent(),fixture.trace.canonical_event_id);
    assert.equal(await page.locator('[data-stage=backend_committed]').getAttribute('data-result'),'PASS');
    rows.push({id:`REVIEW-${viewport.width}-trace-original-key-unknown`,result:'PASS',scope:'SAVED_REAL_API_EVIDENCE'});
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
    rows.push({id:`REVIEW-${viewport.width}-filter-saved-evidence`,result:'PASS',scope:'REVIEW_ARTIFACT_ONLY'});
    await page.reload();await page.locator('body[data-ready=true]').waitFor();
    await page.locator('[data-screen=trace]').click();
    assert.equal(await page.locator('#event-key').textContent(),fixture.trace.canonical_event_id);
    await page.locator('[data-screen=installation]').click();
    assert.match(await page.locator('#installation').textContent(),/NOT_TESTED/);
    assert.equal(await page.locator('#installation button').isDisabled(),true);
    await page.locator('[data-screen=advanced]').click();
    assert.equal(await page.locator('#advanced button:disabled').count(),3);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    rows.push({id:`REVIEW-${viewport.width}-refresh-disabled-controls-layout`,result:'PASS',scope:'REVIEW_ARTIFACT_ONLY'});
    assert.deepEqual(errors,[]);assert.deepEqual(mutations,[]);
    await page.locator('[data-screen=trace]').click();
    await page.screenshot({path:path.join(evidence,`review-${viewport.width}.png`),fullPage:true});
    await page.close();
  }
  await writeFile(path.join(evidence,'review_browser_results.json'),JSON.stringify({scope:'INACTIVE_REVIEW_ARTIFACT',checks:rows.length,cases:rows,production_playwright:'BLOCKED_DESIGN_APPROVAL',physical:'NOT_RUN'},null,2)+'\n');
  console.log(`REVIEW BROWSER PASS cases=${rows.length} production_qualification=BLOCKED physical=NOT_RUN`);
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
