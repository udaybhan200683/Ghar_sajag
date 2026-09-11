import {evaluateScenario,renderValidationRow} from './validation_engine.mjs';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let state={
  away:false,homeAlert:false,morning:true,ok:true,doorOpen:false,indoorAgo:0,nightVisits:2,
  devices:[],events:[],deviceHealth:null,source:'Connecting to backend…'
};
let currentTab='home', reportPeriod='week';
let validation={catalog:null,results:[],running:false,last:null};

function nowTick(){
  const d=new Date();
  $('#dateText').textContent=d.toLocaleDateString(undefined,{weekday:'short',day:'numeric',month:'short',year:'numeric'});
  $('#timeText').textContent=d.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'});
}
setInterval(nowTick,1000); nowTick();

function formatSimTime(sec){
  // v1.5.4 simulator starts at 08:00 with now=1000. Keep the timeline intuitive.
  const total=8*60 + Math.floor((Number(sec||1000)-1000)/60);
  const h=((Math.floor(total/60)%24)+24)%24, m=((total%60)+60)%60;
  const d=new Date(); d.setHours(h,m,0,0);
  return d.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'});
}

async function backendRequest(path,body){
  const options=body===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};
  const response=await fetch(path,options);
  if(!response.ok){
    let detail=''; try{detail=(await response.json()).error||''}catch(_){ }
    throw new Error(detail||`HTTP ${response.status}`);
  }
  return response.json();
}


async function loadValidationCatalog(){if(!validation.catalog)validation.catalog=await backendRequest('/pwa/validation/catalog');return validation.catalog}
function validationSummary(){const total=validation.catalog?.count||68,done=validation.results.length,passed=validation.results.filter(r=>r.pass).length;return {total,done,passed,failed:done-passed,complete:done===total}}
async function runValidationScenario(id,{renderEach=true}={}){
  const result=evaluateScenario(await backendRequest('/pwa/validation/run',{scenario_id:id}));
  validation.last=result; const i=validation.results.findIndex(x=>x.scenario.id===id); if(i>=0)validation.results[i]=result;else validation.results.push(result); if(renderEach)render(); return result;
}
async function runAllValidation(){
  if(validation.running)return; validation.running=true;validation.results=[];validation.last=null;render();
  try{const c=await loadValidationCatalog();for(const sc of c.scenarios){await runValidationScenario(sc.id,{renderEach:false});renderValidationOnly();await new Promise(r=>setTimeout(r,0));}}
  catch(err){toast(`68-scenario validation failed: ${err.message}`)}finally{validation.running=false;renderValidationOnly()}
}
function renderValidationOnly(){const h=document.querySelector('#validationPanel');if(h)h.innerHTML=validationPanelInner()}
function validationPanelInner(){
  const s=validationSummary(),catalog=validation.catalog?.scenarios||[];
  const opts=catalog.map(x=>`<option value="${x.id}">${x.id} · ${x.title}</option>`).join('');
  const rows=validation.results.map(renderValidationRow).join('');
  const status=s.complete?(s.failed===0?'PASS':'FAIL'):(validation.running?'RUNNING':'READY');
  const details=validation.last?`<div class="validation-detail"><strong>${validation.last.scenario.id}</strong><div>${validation.last.scenario.title}</div>${validation.last.step_results.map((x,i)=>`<small class="${x.passed?'status-good':'status-bad'}">S${i+1}: ${x.passed?'PASS':'FAIL'} · ${x.detail}</small>`).join('')}${validation.last.checks.map((x,i)=>`<small class="${x.pass?'status-good':'status-bad'}">A${i+1}: ${x.pass?'PASS':'FAIL'} · ${x.detail}</small>`).join('')}</div>`:'';
  return `<h3>68-case PWA validation</h3><p class="muted">Temporary engineering validation: C++/hub → backend → HTTP → PWA. Expected results are independently evaluated in JavaScript.</p><div id="validationOverall" class="validation-overall ${status==='PASS'?'pass':status==='FAIL'?'fail':''}" data-validation-status="${status}" data-validation-count="${s.done}">${status} · ${s.passed}/${s.total} passed${s.failed?` · ${s.failed} failed`:''}</div><button id="runAll68" onclick="runAll68()" ${validation.running?'disabled':''}>Run all 68 automatically</button><select id="scenarioSelect">${opts}</select><button onclick="runSelectedScenario()" ${validation.running?'disabled':''}>Run selected scenario</button><button onclick="clearValidationResults()" ${validation.running?'disabled':''}>Clear results</button><div class="validation-results">${rows}</div>${details}`;
}
window.runAll68=async()=>{await runAllValidation()};
window.runSelectedScenario=async()=>{const id=document.querySelector('#scenarioSelect')?.value;if(id)await runValidationScenario(id)};
window.clearValidationResults=()=>{validation.results=[];validation.last=null;renderValidationOnly()};

function applyBackend(view){
  state={
    away:false,
    homeAlert:!!view.care?.alert,
    morning:!!view.morning?.ok,
    ok:!!view.iam_ok?.ok,
    doorOpen:!!view.door?.open,
    indoorAgo:view.door?.indoor_activity_age_min ?? 0,
    nightVisits:Number(view.night?.visits ?? 0),
    devices:(view.devices||[]).map(d=>({...d})),
    deviceHealth:view.device_health||null,
    source:view.source||'Backend',
    events:(view.events||[]).map(e=>({time:formatSimTime(e.at),icon:e.icon||'•',text:e.title||'Activity',tone:e.tone||'green',at:e.at}))
  };
  render();
}

async function refreshFromBackend(showError=false){
  try{applyBackend(await backendRequest('/pwa/state'));}
  catch(err){if(showError) toast(`Backend unavailable: ${err.message}`);}
}

async function scenarioAction(body){
  try{
    applyBackend(await backendRequest('/pwa/action',body));
  }catch(err){toast(`Simulation failed: ${err.message}`);}
}
function batteryClass(p){return p<=10?'red':p<=55?'amber':''}
function homeSeverity(){
  const careAlert =
      !state.morning ||
      !state.ok ||
      state.doorOpen ||
      state.nightVisits >= 6 ||
      state.homeAlert;

  if(careAlert){
    let sub='Please check the home status.';
    if(!state.morning) sub='Morning activity not completed.';
    else if(!state.ok) sub='I am OK has not been confirmed today.';
    else if(state.doorOpen) sub='Main door condition needs review.';
    else if(state.nightVisits >= 6) sub='Night activity is higher than usual.';
    return {alert:true,title:'Attention needed at home',sub};
  }

  return {alert:false,title:'Home looks normal',sub:'All is well at home.'};
}
function renderHome(){
  const s=homeSeverity(), health=state.deviceHealth || {low_name:'Unknown',low_percent:0,runtime:'calculating',attention:false}, active=state.devices.filter(d=>d.active).length;
  $('#homeTab').innerHTML=`
  <div class="home-layout">
    <aside class="sim-sidebar">
      <div class="demo-panel">
        <h3>Pilot simulation</h3>
        <p class="muted">Temporary verification controls. This panel will be removed from the final user interface.</p>
        <div class="demo-grid vertical">
          <button onclick="toggleDemo('morning')">Toggle morning routine</button>
          <button onclick="toggleDemo('ok')">Toggle I am OK</button>
          <button onclick="toggleDemo('door')">Toggle main door</button>
          <button onclick="toggleDemo('night')">Toggle night activity</button>
          <button onclick="toggleDemo('battery')">Toggle battery health</button>
          <button onclick="resetDemo()">Reset all to PASS</button>
          <button onclick="enableNotifications()">Enable browser alerts</button>
        </div>
      </div>
      <div id="validationPanel" class="demo-panel validation-panel">${validationPanelInner()}</div>
    </aside>
    <div class="home-main">
      <div class="hero ${s.alert?'alert':''}">
        <div class="hero-row"><div class="hero-icon">${s.alert?'!':'✓'}</div><div><h1>${s.title}</h1><p>${s.sub}</p></div></div>
        <div class="hero-chips">
          <div class="chip ${!state.morning?'danger':''}">${state.morning?'☀️ Morning routine completed':'🔴 Morning activity missing'}</div>
          <div class="chip ${s.alert?'danger':''}">${s.alert?'🛡️ Attention required':'🛡️ No unusual activity'}</div>
          <div class="chip">📶 ${active}/${state.devices.length} devices online</div>
        </div>
      </div>
      <div class="grid2">
        <div class="card ${state.ok?'':'alert'}"><div class="card-row"><div class="round-icon">❤</div><div><h2>I am OK</h2><div class="${state.ok?'status-good':'status-bad'}">${state.ok?'1 hr ago confirmed':'not confirmed today'}</div></div></div></div>
        <div class="card ${state.doorOpen?'alert':''}"><div class="card-row"><div class="round-icon">🚪</div><div><h2>Main door</h2><div class="${state.doorOpen?'status-bad':'status-good'}">${state.doorOpen?'Open':'Closed'}</div><div class="muted">${state.doorOpen?'Open since 2 hrs · No indoor activity':`Indoor activity · ${state.indoorAgo} min ago`}</div></div></div></div>
        <div class="card ${state.nightVisits>=6?'alert':''}"><div class="card-row"><div class="round-icon night">☾</div><div><h2>Night activity</h2><div>${state.nightVisits} bathroom visits</div><div class="${state.nightVisits>=6?'status-bad':'status-good'}">${state.nightVisits>=6?'unusual':'no concern'}</div></div></div></div>
        <div class="card ${health.attention?'alert':''}"><div class="card-row"><div class="round-icon">🔋</div><div><h2>Device health</h2><div class="${health.attention?'status-bad':''}">${health.attention?'Low battery:':'Lowest battery:'} ${health.low_name} ${health.low_percent}%</div><div class="${health.attention?'status-bad':'muted'}">Recharge in ${health.runtime}</div></div></div></div>
      </div>
      <div class="timeline"><div class="section-title"><h2>Recent important events</h2><button class="link-btn" onclick="toast('All events view will use backend history in the pilot.')">View all ›</button></div>
        ${state.events.map(e=>`<div class="event"><div class="event-time">${e.time}</div><div>${e.icon}</div><div class="event-pill ${e.tone==='red'?'red':e.tone==='blue'?'blue':''}">${e.text}</div></div>`).join('')}
      </div>
    </div>
  </div>`;
}
function renderDevices(){
 const active=state.devices.filter(d=>d.active).length;
 $('#devicesTab').innerHTML=`
 <div class="device-summary"><div><h1 style="margin:0">${state.devices.length} devices total</h1><p class="muted">Keeping your home connected and safe.</p></div><div class="metric-box"><strong>${active}</strong><div>active</div></div><div class="metric-box bad"><strong>${state.devices.length-active}</strong><div>inactive</div></div></div>
 <div class="device-list">${state.devices.map(d=>`<div class="device-card ${!d.active||d.battery<=10?'alert':''}">
   <div class="round-icon">${d.id==='door'?'🚪':d.id==='hub'?'📶':'🏃'}</div>
   <div><div class="device-name">${d.name}</div><div class="muted">${d.type}</div><div class="${d.active?'status-good':'status-bad'}">● ${d.active?'Active':'Inactive'}</div></div>
   <div class="battery-col"><div class="battery"><div class="battery-icon"><div class="battery-fill ${batteryClass(d.battery)}" style="width:${Math.max(2,d.battery)}%"></div></div><div class="battery-pct">${d.battery}%</div></div>
   <div class="${d.battery<=10?'status-bad':'status-good'}">Estimated ${d.id==='hub'?'backup':'time left'} ${d.left}</div><div class="muted">◷ ${d.active?'Last updated':'Last seen'} ${d.updated}</div></div><div class="arrow">›</div>
 </div>`).join('')}</div>`;
}
function renderReports(){
 const vals=[62,78,112,76,48,69,83];
 $('#reportsTab').innerHTML=`
 <div class="card"><div class="card-row"><div class="round-icon">▥</div><div><h1 style="margin:0">Reports</h1><div class="muted">Daily and weekly family care summary</div></div></div></div>
 <div class="tabs3">${['day','week','month'].map(p=>`<button class="${reportPeriod===p?'active':''}" onclick="setReport('${p}')">${p==='day'?'Today':p==='week'?'This Week':'This Month'}</button>`).join('')}</div>
 <div class="card"><h2>This week at a glance</h2><div class="muted">Key highlights from 9–15 Sep</div><div class="report-grid" style="margin-top:14px">
   <div class="report-tile">☀️<strong>6/7 days</strong>Morning routine</div>
   <div class="report-tile">✅<strong>5/7 days</strong>I am OK</div>
   <div class="report-tile">🌙<strong>2 visits</strong>Night avg</div>
   <div class="report-tile">⚠️<strong style="color:#d91920">1</strong>Unusual alert</div>
 </div></div>
 <div class="card" style="margin-top:16px"><h2>Activity trend</h2><div class="muted">Daily activity level (sensor events)</div><div class="chart">
 ${vals.map((v,i)=>`<div class="bar-wrap"><div class="bar-val">${v}</div><div class="bar" style="height:${v/1.25}px"></div><div class="bar-label">${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][i]}</div></div>`).join('')}
 </div></div>
 <div class="card" style="margin-top:16px"><h2>Key insights</h2>
   <div class="insight"><strong>✅ Routine was normal on most days</strong><div class="muted">Morning routine completed on 6 out of 7 days.</div></div>
   <div class="insight"><strong>🌙 Higher night activity seen on Wed</strong><div class="muted">Night activity was higher than usual.</div></div>
   <div class="insight"><strong>🚪 Main door activity lower than usual on Fri</strong><div class="muted">Fewer main door events compared to usual.</div></div>
   <div class="insight"><strong>⚠️ One device needed battery attention</strong><div class="muted">Bathroom sensor battery low this week.</div></div>
 </div>`;
}
function renderSettings(){
 $('#settingsTab').innerHTML=`
 <div class="card"><h1 style="margin:0">Settings</h1><div class="muted">Customize your home and device preferences</div></div>
 ${settingsGroup('Home Settings',[['🏠','Home Details','Update home name, location and preferences'],['👥','Family Members','Manage family access and permissions'],['📶','Wi‑Fi & Network','Manage your home network']])}
 ${settingsGroup('Device Settings',[['⚙️','Manage Devices','View, rename or remove devices'],['🔔','Notifications','Set alerts for critical activities'],['🔋','Battery Alerts','Set low battery notifications'],['◷','Device Schedules','Set active hours and device modes']])}
 ${settingsGroup('App Settings',[['🛡️','Privacy & Security','Manage data and security settings'],['❓','Help & Support','FAQs, user guide and contact support'],['ℹ️','About','App version, terms and policies']])}
 <div style="margin:20px 0;text-align:center"><a href="https://ghar-sajag.rahuljnvakg.chatgpt.site/" target="_blank" rel="noopener" style="color:#0d8a43;font-weight:800">Visit public Ghar Sajag website ↗</a></div>`;
}
function settingsGroup(title,items){return `<div class="settings-group"><h3>${title}</h3>${items.map(x=>`<div class="setting" onclick="toast('${x[1]}: pilot configuration screen')"><div class="setting-icon">${x[0]}</div><div><strong>${x[1]}</strong><small>${x[2]}</small></div><div>›</div></div>`).join('')}</div>`}

function render(){renderHome();renderDevices();renderReports();renderSettings(); $('#awayToggle').checked=false; $('#awayToggle').disabled=true;}
$$('.nav-btn').forEach(b=>b.onclick=()=>{currentTab=b.dataset.tab; $$('.nav-btn').forEach(x=>x.classList.toggle('active',x===b)); $$('.tab-panel').forEach(x=>x.classList.remove('active')); $('#'+currentTab+'Tab').classList.add('active');});
$('#awayToggle').checked=false; $('#awayToggle').disabled=true;
window.setReport=p=>{reportPeriod=p;renderReports()}
window.toggleDemo=async k=>{
  await scenarioAction({action:'toggle',scenario:k});
}
window.resetDemo=async()=>{
  await scenarioAction({action:'reset_pass'});
  toast('Reset complete: all scenarios PASS');
}
window.toast=t=>{let n=document.createElement('div');n.className='toast';n.textContent=t;document.body.appendChild(n);setTimeout(()=>n.remove(),2200)}
window.enableNotifications=async()=>{if(!('Notification'in window))return toast('Browser notifications are not supported here.');let p=await Notification.requestPermission();toast(p==='granted'?'Notifications enabled':'Notification permission not granted')}
function notify(title,body){if('Notification'in window && Notification.permission==='granted')new Notification(title,{body,icon:'assets/icon.svg'})}
if('serviceWorker'in navigator) navigator.serviceWorker.register('sw.js');
(async()=>{try{await loadValidationCatalog()}catch(err){toast(`Validation catalog unavailable: ${err.message}`)}await refreshFromBackend(true);if(new URLSearchParams(location.search).get('validation')==='autorun')await runAllValidation()})();
setInterval(()=>{if(!validation.running)refreshFromBackend(false)},2000);
