// Optional actual-browser test. Run against `make lab`, then `node tests/simulation_browser_test.cjs`.
// Requires Playwright + its Chromium browser; manual browser use has no npm dependency.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1280,height:900}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(process.env.GS_LAB_URL||'http://127.0.0.1:8765');
    await page.waitForFunction(()=>document.querySelector('#clock').textContent.includes('t=1000'));
    await page.locator('#send').click();
    await page.waitForFunction(()=>document.querySelector('#activity').textContent.includes('kitchen'));
    await page.locator('#deadline').click();
    await page.waitForFunction(()=>document.querySelector('#hub').textContent.includes('evidence_present'));
    assert.match(await page.locator('#incidents').innerText(),/No incidents/);
    await page.locator('#reset').click();
    await page.waitForFunction(()=>document.querySelector('#clock').textContent.includes('t=1000'));
    await page.locator('#deadline').click();
    await page.getByRole('button',{name:'I’ll check',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#incidents').textContent.includes('CLAIMED'));
    await page.getByRole('button',{name:'Acknowledged',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#incidents').textContent.includes('ACKNOWLEDGED'));
    await page.getByRole('button',{name:'Resolve',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#incidents').textContent.includes('RESOLVED'));
    await page.locator('#suite').click();
    await page.waitForFunction(()=>document.querySelector('#test-status').textContent.includes('PASS: 13/13'));
    assert.equal(await page.locator('#error').isVisible(),false);
    fs.mkdirSync('logs',{recursive:true});
    await page.screenshot({path:'logs/lab_desktop.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
    await page.screenshot({path:'logs/lab_mobile.png',fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('PASS browser: sensor event, morning decision, caregiver lifecycle, 13-scenario button, 390px layout, no page errors');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
