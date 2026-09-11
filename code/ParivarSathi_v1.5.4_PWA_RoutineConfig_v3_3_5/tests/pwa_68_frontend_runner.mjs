import assert from 'node:assert/strict';
import {evaluateScenario,renderValidationRow} from '../tools/sim/pwa/validation_engine.mjs';
const base=process.env.GS_PWA_BASE;
if(!base) throw new Error('GS_PWA_BASE required');
async function get(path){const r=await fetch(base+path,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json()}
async function post(path,body){const r=await fetch(base+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw new Error(`${path}: HTTP ${r.status} ${(await r.text()).slice(0,200)}`);return r.json()}
const catalog=await get('/pwa/validation/catalog');
assert.ok(catalog.count>=68);
const results=[];
for(const sc of catalog.scenarios){
  const payload=await post('/pwa/validation/run',{scenario_id:sc.id});
  const result=evaluateScenario(payload);
  results.push(result);
  const html=renderValidationRow(result);
  assert.match(html,new RegExp(`data-validation-case="${sc.id.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}"`));
  assert.match(html,/data-case-status="PASS"/);
}
assert.equal(results.length,catalog.count);
assert.deepEqual(results.filter(x=>!x.pass).map(x=>x.scenario.id),[]);
const rendered=results.map(renderValidationRow).join('\n');
assert.equal((rendered.match(/data-case-status="PASS"/g)||[]).length,catalog.count);
console.log(`PASS frontend JS E2E: ${catalog.count}/${catalog.count} canonical scenarios evaluated and rendered as PASS`);
