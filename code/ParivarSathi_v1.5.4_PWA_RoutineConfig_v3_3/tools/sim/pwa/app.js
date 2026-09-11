import {evaluateScenario,renderValidationRow} from './validation_engine.mjs';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let state={
  away:false,homeAlert:false,morning:true,morningMissing:false,ok:true,doorOpen:false,doorLeftOpenAlert:false,doorUnexpectedAlert:false,doorPostCloseAlert:false,indoorAgo:0,
  nightBathroomVisits:0,nightCommonVisits:0,nightUnusual:false,careSubtitle:'All is well at home.',careProblemKind:null,
  devices:[],events:[],deviceHealth:null,schedules:null,source:'Connecting to backend…'
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
function validationSummary(){const total=validation.catalog?.count||0,done=validation.results.length,passed=validation.results.filter(r=>r.pass).length;return {total,done,passed,failed:done-passed,complete:total>0&&done===total}}
async function runValidationScenario(id,{renderEach=true}={}){
  const result=evaluateScenario(await backendRequest('/pwa/validation/run',{scenario_id:id}));
  validation.last=result; const i=validation.results.findIndex(x=>x.scenario.id===id); if(i>=0)validation.results[i]=result;else validation.results.push(result); if(renderEach)render(); return result;
}
async function runAllValidation(){
  if(validation.running)return; validation.running=true;validation.results=[];validation.last=null;render();
  try{
    const c=await loadValidationCatalog();
    for(const sc of c.scenarios){
      await runValidationScenario(sc.id,{renderEach:false});
      renderValidationOnly();
      await new Promise(r=>setTimeout(r,0));
    }
  } catch(err){
    toast(`Functional validation failed: ${err.message}`);
  } finally {
    // Do not leave the family dashboard in the final synthetic test state.
    try{applyBackend(await backendRequest('/pwa/action',{action:'reset_pass'}));}catch(_){}
    validation.running=false;
    renderValidationOnly();
  }
}
function renderValidationOnly(){const h=document.querySelector('#validationPanel');if(h)h.innerHTML=validationPanelInner()}
function validationPanelInner(){
  const s=validationSummary(),catalog=validation.catalog?.scenarios||[];
  const opts=catalog.map(x=>`<option value="${x.id}">${x.id} · ${x.title}</option>`).join('');
  const rows=validation.results.map(renderValidationRow).join('');
  const status=s.complete?(s.failed===0?'PASS':'FAIL'):(validation.running?'RUNNING':'READY');
  const details=validation.last?`<div class="validation-detail"><strong>${validation.last.scenario.id}</strong><div>${validation.last.scenario.title}</div>${validation.last.step_results.map((x,i)=>`<small class="${x.passed?'status-good':'status-bad'}">S${i+1}: ${x.passed?'PASS':'FAIL'} · ${x.detail}</small>`).join('')}${validation.last.checks.map((x,i)=>`<small class="${x.pass?'status-good':'status-bad'}">A${i+1}: ${x.pass?'PASS':'FAIL'} · ${x.detail}</small>`).join('')}</div>`:'';
  return `<h3>${s.total||'…'}-case PWA validation</h3><p class="muted">Temporary engineering validation: C++/hub → backend → HTTP → PWA. Expected results are independently evaluated in JavaScript.</p><div id="validationOverall" class="validation-overall ${status==='PASS'?'pass':status==='FAIL'?'fail':''}" data-validation-status="${status}" data-validation-count="${s.done}">${status} · ${s.passed}/${s.total||0} passed${s.failed?` · ${s.failed} failed`:''}</div><button id="runAllValidation" onclick="runAllValidationCases()" ${validation.running?'disabled':''}>Run all ${s.total||''} automatically</button><select id="scenarioSelect">${opts}</select><button onclick="runSelectedScenario()" ${validation.running?'disabled':''}>Run selected scenario</button><button onclick="clearValidationResults()" ${validation.running?'disabled':''}>Clear results</button><div class="validation-results">${rows}</div>${details}`;
}
window.runAllValidationCases=async()=>{await runAllValidation()};
window.runSelectedScenario=async()=>{const id=document.querySelector('#scenarioSelect')?.value;if(id)await runValidationScenario(id)};
window.clearValidationResults=()=>{validation.results=[];validation.last=null;renderValidationOnly()};

function applyBackend(view){
  state={
    away:false,
    homeAlert:!!view.care?.alert,
    morning:!!view.morning?.ok,
    morningMissing:!!view.morning?.missing,
    ok:!!view.iam_ok?.ok,
    doorOpen:!!view.door?.open,
    doorLeftOpenAlert:!!view.door?.left_open_alert,
    doorUnexpectedAlert:!!view.door?.unexpected_alert,
    doorPostCloseAlert:!!view.door?.post_close_inactivity_alert,
    indoorAgo:view.door?.indoor_activity_age_min ?? 0,
    nightBathroomVisits:Number(view.night?.bathroom_visits ?? 0),
    nightCommonVisits:Number(view.night?.common_visits ?? 0),
    nightUnusual:!!view.night?.unusual,
    careSubtitle:view.care?.subtitle||'All is well at home.',
    careProblemKind:view.care?.problem_kind||null,
    devices:(view.devices||[]).map(d=>({...d})),
    deviceHealth:view.device_health||null,
    schedules:view.schedules||null,
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
  // The backend/rule engine is the single source of truth for the care banner.
  // A routine can be pending without being a red-flag condition.
  if(state.homeAlert){
    return {alert:true,title:'Attention needed at home',sub:state.careSubtitle||'Please check the home status.'};
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
          <div class="chip ${state.morningMissing?'danger':''}">${state.morning?'☀️ Morning routine completed':state.morningMissing?'🔴 Morning activity missing':'☀️ Morning routine pending'}</div>
          <div class="chip ${s.alert?'danger':''}">${s.alert?'🛡️ Attention required':'🛡️ No unusual activity'}</div>
          <div class="chip">📶 ${active}/${state.devices.length} devices online</div>
        </div>
      </div>
      <div class="grid2">
        <div class="card ${state.ok?'':'alert'}"><div class="card-row"><div class="round-icon">❤</div><div><h2>I am OK</h2><div class="${state.ok?'status-good':'status-bad'}">${state.ok?'1 hr ago confirmed':'not confirmed today'}</div></div></div></div>
        <div class="card ${state.doorLeftOpenAlert||state.doorUnexpectedAlert||state.doorPostCloseAlert?'alert':''}" data-care-card="door"><div class="card-row"><div class="round-icon">🚪</div><div><h2>Main door</h2><div class="${state.doorLeftOpenAlert||state.doorUnexpectedAlert||state.doorPostCloseAlert?'status-bad':'status-good'}">${state.doorOpen?'Open':'Closed'}</div><div class="${state.doorLeftOpenAlert||state.doorUnexpectedAlert||state.doorPostCloseAlert?'status-bad':'muted'}">${state.doorLeftOpenAlert?'Open longer than configured':state.doorUnexpectedAlert?'Opened during configured quiet hours':state.doorPostCloseAlert?'No indoor activity after door closed':state.doorOpen?'Door is currently open':`Indoor activity · ${state.indoorAgo} min ago`}</div></div></div></div>
        <div class="card ${state.nightUnusual?'alert':''}" data-care-card="night"><div class="card-row"><div class="round-icon night">☾</div><div><h2>Night activity</h2><div>Bathroom ${state.nightBathroomVisits} · Common room ${state.nightCommonVisits}</div><div class="${state.nightUnusual?'status-bad':'status-good'}">${state.nightUnusual?'unusual':'no concern'}</div></div></div></div>
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
function minutesToClock(minute){const h=Math.floor(Number(minute||0)/60)%24,m=Number(minute||0)%60;return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`}
function clockToMinutes(v){const [h,m]=String(v||'00:00').split(':').map(Number);return h*60+m}
function secondsToHours(v){return Number(v||0)/3600}
function hoursToSeconds(v){return Math.round(Number(v||0)*3600)}
function scheduleEditor(){
 const r=state.schedules;if(!r)return `<div class="schedule-editor"><p class="muted">Loading household schedule…</p></div>`;
 const locs=[['room1','Bedroom / Room 1'],['bathroom','Bathroom'],['kitchen','Kitchen'],['common','Common room'],['pooja','Pooja room']];
 const opts=(selected)=>locs.map(([v,l])=>`<option value="${v}" ${v===selected?'selected':''}>${l}</option>`).join('');
 return `<div id="scheduleEditor" class="schedule-editor">
   <div class="schedule-header"><div><h2>Device Schedules & Routine Rules</h2><p class="muted">These values are household-specific. Change them to match the resident's routine; they are saved as versioned backend configuration.</p></div><button onclick="closeScheduleEditor()">✕</button></div>
   <form id="scheduleForm" onsubmit="saveScheduleSettings(event)">
    <section><h3>Morning routine</h3><label class="toggle-line"><input name="morning_sequence_enabled" type="checkbox" ${r.morning_sequence_enabled?'checked':''}> Enable morning sequence</label>
      <div class="form-grid"><label>Active from<input name="morning_start_minute" type="time" value="${minutesToClock(r.morning_start_minute)}"></label><label>Active until<input name="morning_end_minute" type="time" value="${minutesToClock(r.morning_end_minute)}"></label><label>Complete within (hours)<input name="morning_sequence_window_seconds" type="number" min="0.0167" max="24" step="0.25" value="${secondsToHours(r.morning_sequence_window_seconds)}"></label>
      <label>Bedroom activity<select name="morning_bedroom_location">${opts(r.morning_bedroom_location)}</select></label><label>Bathroom activity<select name="morning_bathroom_location">${opts(r.morning_bathroom_location)}</select></label><label>Kitchen activity<select name="morning_kitchen_location">${opts(r.morning_kitchen_location)}</select></label></div><p class="rule-help">Completion rule: bedroom activity first, then both configured bathroom and kitchen activity within the configured window.</p></section>
    <section><h3>Night activity</h3><label class="toggle-line"><input name="night_activity_enabled" type="checkbox" ${r.night_activity_enabled?'checked':''}> Enable night-activity monitoring</label>
      <div class="form-grid"><label>Night starts<input name="night_start_minute" type="time" value="${minutesToClock(r.night_start_minute)}"></label><label>Night ends<input name="night_end_minute" type="time" value="${minutesToClock(r.night_end_minute)}"></label><label>Merge motion into one visit (minutes)<input name="night_visit_merge_seconds" type="number" min="0" max="120" step="1" value="${Math.round(r.night_visit_merge_seconds/60)}"></label>
      <label>Bathroom location<select name="night_bathroom_location">${opts(r.night_bathroom_location)}</select></label><label>Bathroom visits allowed<input name="night_bathroom_visit_threshold" type="number" min="0" max="50" value="${r.night_bathroom_visit_threshold}"></label><label>Common-room location<select name="night_common_location">${opts(r.night_common_location)}</select></label><label>Common-room visits allowed<input name="night_common_visit_threshold" type="number" min="0" max="50" value="${r.night_common_visit_threshold}"></label></div><p class="rule-help">A concern is raised only when distinct visits are greater than the configured allowed count.</p></section>
    <section><h3>Main door & indoor activity</h3><div class="form-grid"><label>Door-open concern after (hours)<input name="door_open_timeout_seconds" type="number" min="0.0083" max="24" step="0.25" value="${secondsToHours(r.door_open_timeout_seconds)}"></label><label class="toggle-line"><input name="post_door_inactivity_enabled" type="checkbox" ${r.post_door_inactivity_enabled?'checked':''}> Watch for inactivity after door closes</label><label>No indoor activity after close (hours)<input name="post_door_inactivity_seconds" type="number" min="0.0833" max="24" step="0.25" value="${secondsToHours(r.post_door_inactivity_seconds)}"></label></div></section>
    <section><h3>General quiet/inactivity windows</h3><div class="form-grid"><label class="toggle-line"><input name="quiet_hours_enabled" type="checkbox" ${r.quiet_hours_enabled?'checked':''}> Quiet-hour door alerts</label><label>Quiet start<input name="quiet_start_minute" type="time" value="${minutesToClock(r.quiet_start_minute)}"></label><label>Quiet end<input name="quiet_end_minute" type="time" value="${minutesToClock(r.quiet_end_minute)}"></label><label class="toggle-line"><input name="daytime_inactivity_enabled" type="checkbox" ${r.daytime_inactivity_enabled?'checked':''}> General daytime inactivity</label><label>Day starts<input name="daytime_start_minute" type="time" value="${minutesToClock(r.daytime_start_minute)}"></label><label>Day ends<input name="daytime_end_minute" type="time" value="${minutesToClock(r.daytime_end_minute)}"></label><label>General inactivity threshold (hours)<input name="daytime_inactivity_seconds" type="number" min="0.0833" max="24" step="0.25" value="${secondsToHours(r.daytime_inactivity_seconds)}"></label></div></section>
    <div class="schedule-actions"><button type="button" onclick="closeScheduleEditor()">Cancel</button><button type="submit" class="primary">Save household schedule</button></div>
   </form></div>`;
}
function renderSettings(){
 $('#settingsTab').innerHTML=`
 <div class="card"><h1 style="margin:0">Settings</h1><div class="muted">Customize your home and device preferences</div></div>
 ${settingsGroup('Home Settings',[['🏠','Home Details','Update home name, location and preferences'],['👥','Family Members','Manage family access and permissions'],['📶','Wi‑Fi & Network','Manage your home network']])}
 ${settingsGroup('Device Settings',[['⚙️','Manage Devices','View, rename or remove devices'],['🔔','Notifications','Set alerts for critical activities'],['🔋','Battery Alerts','Set low battery notifications'],['◷','Device Schedules','Set household routine windows and alert thresholds','openDeviceSchedules()']])}
 ${settingsGroup('App Settings',[['🛡️','Privacy & Security','Manage data and security settings'],['❓','Help & Support','FAQs, user guide and contact support'],['ℹ️','About','App version, terms and policies']])}
 <div id="scheduleMount"></div>
 <div style="margin:20px 0;text-align:center"><a href="https://ghar-sajag.rahuljnvakg.chatgpt.site/" target="_blank" rel="noopener" style="color:#0d8a43;font-weight:800">Visit public Ghar Sajag website ↗</a></div>`;
}
function settingsGroup(title,items){return `<div class="settings-group"><h3>${title}</h3>${items.map(x=>`<div class="setting" data-setting="${x[1]}" onclick="${x[3]||`toast('${x[1]}: pilot configuration screen')`}"><div class="setting-icon">${x[0]}</div><div><strong>${x[1]}</strong><small>${x[2]}</small></div><div>›</div></div>`).join('')}</div>`}
window.openDeviceSchedules=()=>{const m=$('#scheduleMount');if(m){m.innerHTML=scheduleEditor();m.scrollIntoView({behavior:'smooth',block:'start'})}}
window.closeScheduleEditor=()=>{const m=$('#scheduleMount');if(m)m.innerHTML=''}
window.saveScheduleSettings=async(ev)=>{ev.preventDefault();const f=new FormData(ev.target),r={...state.schedules};
 const bools=['morning_sequence_enabled','night_activity_enabled','post_door_inactivity_enabled','quiet_hours_enabled','daytime_inactivity_enabled'];for(const k of bools)r[k]=f.has(k);
 for(const k of ['morning_start_minute','morning_end_minute','night_start_minute','night_end_minute','quiet_start_minute','quiet_end_minute','daytime_start_minute','daytime_end_minute'])r[k]=clockToMinutes(f.get(k));
 for(const k of ['morning_bedroom_location','morning_bathroom_location','morning_kitchen_location','night_bathroom_location','night_common_location'])r[k]=String(f.get(k));
 r.morning_sequence_window_seconds=hoursToSeconds(f.get('morning_sequence_window_seconds'));r.door_open_timeout_seconds=hoursToSeconds(f.get('door_open_timeout_seconds'));r.post_door_inactivity_seconds=hoursToSeconds(f.get('post_door_inactivity_seconds'));r.daytime_inactivity_seconds=hoursToSeconds(f.get('daytime_inactivity_seconds'));
 r.night_visit_merge_seconds=Math.round(Number(f.get('night_visit_merge_seconds'))*60);r.night_bathroom_visit_threshold=Number(f.get('night_bathroom_visit_threshold'));r.night_common_visit_threshold=Number(f.get('night_common_visit_threshold'));
 try{applyBackend(await backendRequest('/pwa/action',{action:'settings_save',settings:r}));toast('Device schedule saved and applied to the hub');setTimeout(()=>openDeviceSchedules(),0)}catch(err){toast(`Settings not saved: ${err.message}`)}
}

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
setInterval(()=>{if(!validation.running && !document.querySelector('#scheduleEditor'))refreshFromBackend(false)},2000);
