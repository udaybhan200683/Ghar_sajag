import {normalizeRuntimeConfig,requestUrl} from './runtime_mode.mjs';

const runtime=normalizeRuntimeConfig(window.PARIVAR_SAATHI_RUNTIME,window.location.origin);
document.body.classList.add('connected-lite-runtime');
const $=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const tabs=['home','devices','incidents','reports','routines','settings'];
let profile=null,tab='home',catalog=null,runs=[],selectedRun=null,view=null,lastSync=null,connection='OFFLINE';
let busy=false,engineeringScreen='Installation Overview';

async function api(path,{method='GET',body}={}){
  const url=requestUrl(runtime,`/lite/v1/${path}`);
  if(!url)throw new Error('Approved HTTPS backend is not configured');
  const reply=await fetch(url,{method,credentials:'include',cache:'no-store',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await reply.json().catch(()=>({error:'invalid_server_response'}));
  if(!reply.ok)throw new Error(data.error||`HTTP ${reply.status}`);
  return data;
}

function status(text,detail){
  const banner=$('#connectionStatus');
  banner.hidden=false;
  banner.dataset.connectionState=text==='CONNECTED'?'online':'offline';
  banner.innerHTML=`<strong>${esc(text)}</strong><span>${esc(detail)}</span>`;
}

function panel(html){
  $('#homeTab').innerHTML=html;
  for(const id of ['devices','reports','settings'])$('#'+id+'Tab').innerHTML='';
  for(const id of ['devices','reports','settings'])$('#'+id+'Tab').classList.remove('active');
  $('#homeTab').classList.add('active');
}

function loginScreen(message=''){
  profile=null;view=null;
  $('.bottom-nav').hidden=true;
  $('.bottom-nav').replaceChildren();
  const problem=message?`<p class="status-bad" role="alert">${esc(message)}</p>`:'';
  panel(`<div class="card connected-auth"><h1>Parivar Saathi</h1><p>Sign in to your authorized Home.</p>${problem}<form id="loginForm"><label>Email<input name="email" type="email" autocomplete="username" required></label><label>Password<input name="password" type="password" autocomplete="current-password" required></label><button type="submit">Log in</button></form><p class="muted">Monitoring status is unknown until current Home data is available.</p></div>`);
  $('#loginForm').onsubmit=async event=>{
    event.preventDefault();
    const data=new FormData(event.target);
    const button=event.target.querySelector('button');button.disabled=true;
    try{
      profile=await api('auth/login',{method:'POST',body:{email:data.get('email'),password:data.get('password')}});
      tab='home';await refresh();
    }catch(error){loginScreen(`Login failed: ${error.message}`)}
  };
}

function nav(){
  // Keep the caregiver's most useful actions visible before the scrollable secondary tabs.
  const available=profile?.role==='ADMIN'&&profile.test_only?
    ['home','simulation','reports','devices','incidents','routines','engineering','settings']:
    ['home','reports','devices','incidents','routines','settings'];
  $('.bottom-nav').hidden=false;
  $('.bottom-nav').innerHTML=available.map(name=>`<button type="button" class="nav-btn ${tab===name?'active':''}" data-tab="${name}" aria-label="${esc(name==='simulation'?'Simulation Lab':name)}" ${tab===name?'aria-current="page"':''}><b>${esc(name==='simulation'?'Simulation Lab':name[0].toUpperCase()+name.slice(1))}</b></button>`).join('');
  $('.bottom-nav').querySelectorAll('button').forEach(button=>button.onclick=()=>openTab(button.dataset.tab));
}
function openTab(next){
  tab=next;selectedRun=null;
  nav();
  // New sections begin above the bottom navigation; keep the header visible.
  window.scrollTo({top:0,behavior:'instant'});
  void refresh();
}
function dataLabel(){return `<p class="test-watermark">TEST_ONLY synthetic Home · ${esc(profile.home_id)} · ${esc(view?.source||'No physical source')}</p>`}
function card(title,body){return `<div class="card"><h2>${esc(title)}</h2>${body}</div>`}
function tableRows(items,render){return items.length?items.map(render).join(''):'<p class="muted">No saved observations.</p>'}
function productSource(){return view?.source==='NODE_ORIGIN_HOST_SIM'}
function productEvents(events){return tableRows(events||[],e=>e.source_type==='HUB_RULE'
  ?`<article class="caregiver-run" data-hub-decision="${esc(e.decision_id)}"><b>${esc(e.kind)}</b><span>Hub rule decision · ${esc(new Date(e.occurred_at*1000).toISOString())}</span><small>Decision ID: ${esc(e.decision_id)} · ${esc(e.details?.reason||'')}</small></article>`
  :`<article class="caregiver-run" data-event-key="${esc(JSON.stringify(e.event_key))}"><b>${esc(e.kind)}</b><span>${esc(e.location)} · ${esc(new Date(e.occurred_at*1000).toISOString())}</span><small>EventKey: ${esc(JSON.stringify(e.event_key))} · ${e.delayed?'Delayed':'Current at receipt'}</small></article>`)}

function renderHome(){
  if(productSource()){
    panel(`${dataLabel()}${card('Node-originated software monitoring',`<p>Backend source: authenticated Hub CloudSync · ${esc(view.source_freshness)}</p><p>Observation coverage: ${esc(view.monitoring)}</p><p>Physical sensing: NOT_RUN. These records came from the production Node/Hub code running on the host.</p>`)}${card('Activity timeline',productEvents(view.recent_events))}${card('Active concerns',`<p>${esc(view.active_incidents?.length||0)} · inspect Incidents for caregiver actions.</p>`)}`);
    return;
  }
  const rows=view?.runs||[];
  const events=view?.recent_events||[];
  const decisions=view?.routine_decisions||[];
  const lastFetch=lastSync?new Date(lastSync).toLocaleString():'Not yet synchronized';
  const latest=view?.latest_simulated_event;
  panel(`<section class="caregiver-hero">
    <p class="caregiver-eyebrow">CAREGIVER HOME · TEST ONLY</p>
    <h1>Your home overview</h1>
    <p>Your test workspace is connected. Real-home monitoring is not active yet.</p>
    <div class="caregiver-actions"><button id="openSimulation" type="button">Run a test scenario</button><button id="openReports" type="button" class="caregiver-secondary">View reports</button></div>
  </section>
  <div class="caregiver-tiles">
    ${card('Cloud connection',`<p class="caregiver-state good">${esc(connection==='CONNECTED'?'Connected':'Unavailable')}</p><p>Last sync: ${esc(lastFetch)}</p><p class="muted">Test workspace only</p>`)}
    ${card('Home monitoring',`<p class="caregiver-state pending">Not yet connected</p><p>Physical Hub events are not reaching this cloud app yet.</p><p class="muted">Device availability and resident status are unknown.</p>`)}
  </div>
  ${card('Recent test events',`${events.length?'<p>Events below were generated by saved TEST_ONLY simulations. Product EventKeys are unavailable.</p>':''}${tableRows(events.slice(0,12),e=>`<details class="caregiver-run"><summary><b>${esc(e.kind)}</b> · ${esc(e.occurred_at||'time unknown')} · ${esc(e.event_id||'simulated ID unavailable')}</summary><p>Source: ${esc(e.provenance)} · Trace: ${esc(e.trace_id)}</p><p>Device: ${esc(e.device_id||'not emitted')} · Location: ${esc(e.location||'not emitted')}</p><p>Received: ${esc(e.received_at||'not emitted')} · Delayed: ${e.delayed?'YES':'NO'}</p><p>Original EventKey: UNAVAILABLE</p><button class="open-run" data-run="${esc(e.run_id)}">Inspect run</button></details>`)}`)}
  ${card('Recent routine decisions',tableRows(decisions.slice(0,8),d=>`<div class="caregiver-run"><b>${esc(d.result)} · ${esc(d.category)}</b><span>${esc(d.scenario_title)}</span><small>${esc(d.decision_reason)} · ${esc(new Date(d.evaluated_at*1000).toLocaleString())}</small><button class="open-run" data-run="${esc(d.run_id)}">Inspect decision trace</button></div>`))}
  ${card('Recent test activity',`<p>${esc(rows.length)} recent saved test runs. ${latest?'Most recent run contains '+esc(latest.kind||'simulated activity'):'No simulated events yet.'}</p>${tableRows(rows.slice(0,8),r=>`<div class="caregiver-run"><b>${esc(r.status)}</b><span>${esc(r.scenario_id)}</span><small>${esc(new Date(r.created_at*1000).toLocaleString())}</small></div>`)}`)}
  <details class="caregiver-tech"><summary>Technical connection details</summary><p>Physical Home: ${esc(view?.physical_status||'UNKNOWN')} / ${esc(view?.physical_status_reason||'REASON_UNKNOWN')}</p><p>Planned real Hub event interface: ${esc(view?.physical_data_contract||'GS-148_CLOUDSYNC')}. This is not an active event source.</p><p>Real monitoring freshness: UNKNOWN. No emergency alerts or physical-device status are provided by this simulation Home.</p></details>`);
  $('#openSimulation').onclick=()=>openTab('simulation');
  $('#openReports').onclick=()=>openTab('reports');
  bindRunButtons();
}
function renderDevices(){
  if(productSource()){
    panel(`${dataLabel()}${card('Devices and NodeHealth',tableRows(view.devices||[],d=>`<article class="caregiver-run" data-node-id="${esc(d.physical_node_id)}"><b>${esc(d.logical_node_id)} · ${esc(d.status)}</b><p>Sensor coverage: ${esc(d.coverage)} · profile ${esc(d.profile_id)}</p><p>Offline coverage is UNKNOWN; it does not establish resident inactivity.</p></article>`))}`);return;
  }
  panel(`${dataLabel()}${card('Devices and NodeHealth',`<p>Physical Home: <strong>${esc(view?.physical_status||'UNKNOWN')} / ${esc(view?.physical_status_reason||'REASON_UNKNOWN')}</strong>.</p><p>Real Hub event source: ${esc(view?.physical_data_contract||'UNKNOWN')}.</p><p>Physical device and NodeHealth measurements: <strong>UNKNOWN</strong>.</p>${tableRows(view?.devices||[],device=>`<details><summary>${esc(device.id)} · ${esc(device.health||'UNKNOWN')} · SIMULATED</summary><pre>${esc(JSON.stringify(device,null,2))}</pre></details>`)}`)}`);
}
function renderIncidents(){
  if(productSource()){
    panel(`${dataLabel()}${card('Incident history',tableRows(view.incidents||[],i=>`<article class="caregiver-run" data-incident-id="${esc(i.incident_id)}"><b>${esc(i.kind)} · ${esc(i.state)} · ${esc(i.severity)}</b><p>Notification or actual phone contact: not established.</p>${i.state==='RESOLVED'?'':['claim','acknowledge','resolve'].map(action=>`<button data-incident-action="${action}" data-id="${esc(i.incident_id)}">${esc(action)}</button>`).join('')}</article>`))}`);
    document.querySelectorAll('[data-incident-action]').forEach(button=>button.onclick=async()=>{try{await api(`homes/${profile.home_id}/incidents/${button.dataset.id}/${button.dataset.incidentAction}`,{method:'POST',body:{}});await refresh()}catch(error){status('ACTION FAILED',error.message)}});return;
  }
  panel(`${dataLabel()}${card('Incident history',tableRows(view?.incidents||[],r=>`<details><summary>${esc(r.kind||'Incident')} · ${esc(r.state||'UNKNOWN')} · SIMULATED</summary><pre>${esc(JSON.stringify(r,null,2))}</pre></details>`))}<p class="muted">No real household incident can be acknowledged from this TEST_ONLY service.</p>`);
}
function renderReports(){
  if(productSource()){panel(`${dataLabel()}${card('Committed event history',`<p>${esc(view.event_count)} durable events</p>${productEvents(view.recent_events)}`)}`);return;}
  panel(`${dataLabel()}${card('Simulation reports',`<label>Period<select id="reportPeriod"><option value="day">Day</option><option value="week">Week</option><option value="month">Month</option></select></label><p>${esc(view?.run_count??0)} saved scenario runs · ${esc(view?.period||'week')}.</p><p>Saved synthetic events: ${esc(view?.event_count??0)} · incident snapshots: ${esc(view?.incident_count??0)}</p><p>PASS ${esc(view?.outcomes?.PASS||0)} · FAIL ${esc(view?.outcomes?.FAIL||0)} · BLOCKED ${esc(view?.outcomes?.BLOCKED||0)}</p>${tableRows(view?.runs||[],r=>`<p>${esc(r.scenario_id)} · ${esc(r.status)} · ${esc(new Date(r.created_at*1000).toLocaleString())}</p>`)}<p class="muted">Real Hub event reports are unavailable until authenticated Hub ingest is deployed.</p>`)}`);
  $('#reportPeriod').value=view?.period||'week';
  $('#reportPeriod').onchange=async event=>{view=await api(`homes/${profile.home_id}/reports?period=${event.target.value}`);renderReports()};
}
function renderRoutines(){
  panel(`${dataLabel()}${card('Routine insights',`<p>Longitudinal learning: <strong>${esc(view?.learning_status||'UNKNOWN')}</strong>.</p><p>Routine scenarios run the existing deterministic activity rules. The current lab does not form a multi-day resident baseline.</p>${tableRows(view?.decisions||[],d=>`<details><summary>${esc(d.scenario_title)} · ${esc(d.result)} · ${esc(d.category)}</summary><p>Evaluated: ${esc(new Date(d.evaluated_at*1000).toLocaleString())} · Trace: ${esc(d.trace_id)}</p><p>Engine reason: <strong>${esc(d.decision_reason)}</strong></p><p>Events: ${esc(d.event_ids.join(', ')||'none emitted')} · Incidents: ${esc(d.incident_count)}</p><p>Learning status: ${esc(d.learning_status)}</p>${tableRows(d.step_results,s=>`<p>Step ${esc(s.index)} · ${s.passed?'PASS':'FAIL'} · ${esc(s.detail)}</p>`)}${tableRows(d.checks,c=>`<p>${c.pass?'PASS':'FAIL'} · ${esc(c.detail)}</p>`)}<button class="open-run" data-run="${esc(d.run_id)}">Open full run trace</button></details>`)}<h3>Saved routine scenarios</h3>${tableRows(view?.runs||[],r=>`<p><button class="open-run" data-run="${esc(r.run_id)}">Inspect ${esc(r.scenario_id)}</button> · ${esc(r.status)} · ${esc(r.category)}</p>`)}<p class="muted">Coverage gaps remain UNKNOWN where the scenario has no evidence. Synthetic output is not a trained resident-specific model.</p>`)}${selectedRun?runDetail(selectedRun):''}`);
  bindRunButtons();
}
function renderSettings(){
  panel(`${dataLabel()}${card('Account',`<p>${esc(profile.email)} · ${esc(profile.role)}</p><p>Session expires: ${esc(new Date(profile.expires_at*1000).toLocaleString())}</p><p>Home: ${esc(profile.home_id)}</p><button id="logoutButton">Log out</button>`)}${card('Connection',`<p>Approved backend: ${esc(runtime.backendOrigin||'UNCONFIGURED')}</p><p>App: ${esc(runtime.appVersion)} (${esc(runtime.sourceRevision)})</p><p>Backend revision: ${esc(profile.backend_revision||'unknown')}</p><p>Backend API connection: ${esc(connection)}</p><p>Physical Hub CloudSync: UNAVAILABLE / NO_HUB_CLOUDSYNC</p>`)}`);
  $('#logoutButton').onclick=async()=>{try{await api('auth/logout',{method:'POST'})}finally{status('SIGNED OUT','Current session has been revoked.');loginScreen()}};
}
function renderEngineering(){
  const health=view?.gs124_health||{};
  const names=['Installation Overview','Live Events','Event Trace','Device Diagnostics','Communication Health','Guided Installation Test','Advanced Diagnostics'];
  const runList=tableRows(view?.runs||[],r=>`<p><button class="open-run" data-run="${esc(r.run_id)}">${esc(r.scenario_id)}</button> · ${esc(r.status)} · HOST_SIMULATION_TEST_ONLY</p>`);
  const common=`<p>Physical Home: <strong>${esc(view?.physical_status||'UNKNOWN')} / ${esc(view?.physical_status_reason||'REASON_UNKNOWN')}</strong>.</p><p>Real Hub event source: ${esc(view?.physical_data_contract||'UNKNOWN')}.</p><p class="muted">Real-device evidence: UNKNOWN or NOT_RUN. Synthetic results are isolated from emergency response.</p>`;
  const screens={
    'Installation Overview':card('Installation Overview',`<p>Home ${esc(profile.home_id)} · TEST_ONLY</p><p>GS-124 health projection: ${esc(health.status||'UNKNOWN')}</p><p>Device manifest and Hub identity: UNSUPPORTED</p>${common}`),
    'Live Events':card('Live Events',`<p>Persistent simulation events; no live physical feed. Original product EventKeys are unavailable.</p>${tableRows(view?.recent_events||[],e=>`<details><summary>${esc(e.kind)} · ${esc(e.occurred_at||'time unknown')} · ${esc(e.event_id||'simulated ID unavailable')}</summary><p>Trace: ${esc(e.trace_id)} · Run: ${esc(e.run_id)} · Source: ${esc(e.provenance)}</p><p>Received: ${esc(e.received_at||'not emitted')} · Delayed: ${e.delayed?'YES':'NO'}</p><p>Original EventKey: UNAVAILABLE</p><button class="open-run" data-run="${esc(e.run_id)}">Inspect processing trace</button></details>`)}${runList}${common}`),
    'Event Trace':card('Event Trace',`<p>Select a saved run to inspect simulated event IDs and processing timeline. Original product EventKey is unavailable in this projection.</p>${runList}${selectedRun?runDetail(selectedRun):''}${common}`),
    'Device Diagnostics':card('Device Diagnostics',`<p>GS-124 authorized health projection: ${esc(health.status||'UNKNOWN')}.</p><p>Physical NodeHealth, firmware, battery, enrollment and RSSI: UNSUPPORTED.</p>${common}`),
    'Communication Health':card('Communication Health',`<p>C3→S3 radio and S3→cloud delivery measurements: UNKNOWN.</p><p>Simulated ACK or retry stages can be inspected in saved run traces.</p>${runList}${common}`),
    'Guided Installation Test':card('Guided Installation Test',`<p>Physical guided installation: NOT_RUN. No board or fixture is connected to this cloud simulation Home.</p><p>Run supported validation scenarios in Simulation Lab to inspect software behavior.</p>${common}`),
    'Advanced Diagnostics':card('Advanced Diagnostics',`<p>Backend source revision: ${esc(view?.source_revision||'unknown')}</p><p>Authorized GS-124 read response: ${esc(health.status||'UNKNOWN')}</p><p>Saved synthetic runs: ${esc(view?.runs?.length||0)}</p>${runList}${common}`),
  };
  panel(`${dataLabel()}<div class="card"><h2>Engineering</h2><label>Approved GS-120 area<select id="engineeringArea">${names.map(name=>`<option ${engineeringScreen===name?'selected':''}>${esc(name)}</option>`).join('')}</select></label></div>${screens[engineeringScreen]}`);
  $('#engineeringArea').onchange=event=>{engineeringScreen=event.target.value;renderEngineering()};
  bindRunButtons();
}
function runDetail(run){
  const result=run.result||{};
  const timeline=result.state?.timeline||[];
  const checks=result.checks||[];
  const steps=result.step_results||[];
  const simulation=result.state?.simulation||{};
  const trace=result.trace||{};
  return card(`Run ${run.run_id}`,`<p>${esc(run.scenario_id)} · ${esc(run.status)} · HOST_SIMULATION_TEST_ONLY</p><p>Trace: ${esc(trace.trace_id||`sim:${run.run_id}`)} · Source revision: ${esc(result.source_revision||'unknown')} · Hardware evidence: ${esc(result.hardware_evidence||'NOT_RUN')}</p><h3>Expected versus observed</h3>${tableRows(checks,c=>`<div class="validation-row"><b>${c.pass?'PASS':'FAIL'}</b><span>${esc(c.detail)}</span></div>`)}<h3>Engine processing steps</h3>${tableRows(steps,s=>`<div class="validation-row"><b>Step ${esc(s.index)} · ${s.passed?'PASS':'FAIL'}</b><span>${esc(s.detail)}</span></div>`)}<h3>Routine / abnormality decision</h3><p>Engine reason: <strong>${esc(simulation.reason||'NOT_EMITTED_BY_SCENARIO')}</strong></p><p>Generated incidents: ${esc(result.state?.incidents?.length||0)} · Notifications in simulation: ${esc(result.state?.notifications?.length||0)}</p><p>These are simulator outputs, not real caregiver notifications or trained resident routines.</p><h3>Event timeline</h3><p class="muted">Original product EventKey is unavailable in this host simulation projection. Simulated event IDs are shown as recorded.</p>${tableRows(timeline.map((e,i)=>({...e,trace_event_id:`sim:${run.run_id}:${i+1}`})),e=>`<details><summary>${esc(e.kind||e.type||'Event')} · ${esc(e.occurred_at||'time unknown')} · ${esc(e.event_id||'no simulated ID')}</summary><p>Event trace: ${esc(e.trace_event_id)} · Run trace: ${esc(trace.trace_id||`sim:${run.run_id}`)}</p><p>Occurred: ${esc(e.occurred_at||'not emitted')} · Received: ${esc(e.received_at||'not emitted')}</p><p>Kind: ${esc(e.kind||e.type||'UNKNOWN')} · Location: ${esc(e.location||'not emitted')} · Delayed: ${e.delayed?'YES':'NO'}</p><p>Source: HOST_SIMULATION_TEST_ONLY · Product EventKey: UNAVAILABLE</p><pre>${esc(JSON.stringify(e,null,2))}</pre></details>`)}<h3>Resulting simulated state</h3><pre>${esc(JSON.stringify(result.state?.home||{},null,2))}</pre><button id="exportJson">Export JSON</button><button id="exportCsv">Export CSV</button>`);
}
function download(name,type,body){
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([body],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
function bindExports(){
  if(!selectedRun)return;
  $('#exportJson').onclick=()=>download(`${selectedRun.run_id}.json`,'application/json',JSON.stringify(selectedRun,null,2));
  $('#exportCsv').onclick=()=>{
    const cells=(selectedRun.result?.state?.timeline||[]).map(e=>[e.event_key||'',e.event_id||'',e.kind||'',e.occurred_at||'',e.source||'HOST_SIMULATION_TEST_ONLY']);
    const csv=[['event_key','simulated_event_id','kind','occurred_at','source'],...cells].map(row=>row.map(value=>`"${String(value).replaceAll('"','""')}"`).join(',')).join('\n');
    download(`${selectedRun.run_id}.csv`,'text/csv',csv);
  };
}
function bindRunButtons(){
  document.querySelectorAll('.open-run').forEach(button=>button.onclick=async()=>{
    selectedRun=await api(`homes/${profile.home_id}/sim/runs/${button.dataset.run}`);
    renderCurrent();bindExports();
  });
  bindExports();
}
function renderSimulation(){
  const choices=catalog?.scenarios||[];
  panel(`${dataLabel()}${card('Simulation Lab',`<p>Choose one synthetic scenario. Results are stored in your test cloud database, not sourced from real sensors.</p><label for="scenarioSearch">Find scenario</label><input id="scenarioSearch" placeholder="Motion, door, morning..." autocomplete="off"><label for="scenarioChoice">Choose a test scenario</label><select id="scenarioChoice" size="1">${choices.map(s=>`<option value="${esc(s.id)}">${esc(s.title)} · ${esc(s.id)}</option>`).join('')}</select><button id="runScenario" class="caregiver-primary" ${busy?'disabled':''}>Run selected scenario</button><p id="runProgress" role="status"></p><details class="caregiver-tech"><summary>Advanced simulation controls</summary><button id="runSuite" ${busy?'disabled':''}>Run full catalog</button><button id="resetFixture" ${busy?'disabled':''}>Start fresh fixture</button></details>`)}${selectedRun?runDetail(selectedRun):''}${card('Saved runs',tableRows(runs,r=>`<p><button class="open-run" data-run="${esc(r.run_id)}">${esc(r.scenario_id)}</button> · ${esc(r.status)} · ${esc(new Date(r.created_at*1000).toLocaleString())}</p>`))}`);
  const search=$('#scenarioSearch'),choice=$('#scenarioChoice');
  search.oninput=()=>{const term=search.value.toLowerCase();choice.innerHTML=choices.filter(s=>(s.id+' '+s.title).toLowerCase().includes(term)).map(s=>`<option value="${esc(s.id)}">${esc(s.id)} · ${esc(s.title)}</option>`).join('')};
  $('#runScenario').onclick=()=>execute([...choice.selectedOptions].map(option=>option.value));
  $('#runSuite').onclick=()=>execute(choices.map(s=>s.id));
  $('#resetFixture').onclick=async()=>{
    try{const reset=await api(`homes/${profile.home_id}/sim/reset`,{method:'POST',body:{}});$('#runProgress').textContent=`Fresh fixture generation ${reset.simulation_generation}; saved history preserved.`}
    catch(error){status('SIMULATION ERROR',error.message)}
  };
  bindRunButtons();
}
async function execute(ids){
  if(busy||!ids.length)return;
  busy=true;
  const buttons=[$('#runScenario'),$('#runSuite')];buttons.forEach(button=>button.disabled=true);
  let done=0,failed=0;
  for(const id of ids){
    try{
      const data=await api(`homes/${profile.home_id}/sim/runs`,{method:'POST',body:{scenario_id:id}});
      selectedRun={run_id:data.run_id,scenario_id:id,status:data.status,result:data.result};
      if(data.status!=='PASS')failed++;
    }catch(error){failed++;status('SIMULATION ERROR',`${id}: ${error.message}`)}
    done++;
    const progress=$('#runProgress');if(progress)progress.textContent=`${done}/${ids.length} complete · ${failed} failed or blocked`;
  }
  busy=false;
  runs=(await api(`homes/${profile.home_id}/sim/runs`)).runs;
  renderSimulation();
}
function renderCurrent(){
  nav();
  ({home:renderHome,devices:renderDevices,incidents:renderIncidents,reports:renderReports,routines:renderRoutines,settings:renderSettings,engineering:renderEngineering,simulation:renderSimulation}[tab]||renderHome)();
}
async function refresh(){
  if(!profile)return;
  try{
    profile=await api('me');
    const home=profile.home_id;
    const area={home:'overview',devices:'devices',incidents:'incidents',reports:'reports',routines:'routines',engineering:'engineering'}[tab];
    if(area)view=await api(`homes/${home}/${area}`);
    if(tab==='simulation'){
      catalog=catalog||await api(`homes/${home}/sim/catalog`);
      runs=(await api(`homes/${home}/sim/runs`)).runs;
    }
    connection='CONNECTED';lastSync=Date.now();
    status('CONNECTED',`TEST_ONLY workspace · last synced ${new Date(lastSync).toLocaleTimeString()}. Real-home monitoring is not connected.`);
    renderCurrent();
  }catch(error){
    connection='OFFLINE';status('OFFLINE / RECONNECTING',`Current data unavailable: ${error.message}. Physical monitoring UNKNOWN.`);
    if(error.message==='not_authorized'){loginScreen('Session expired or access revoked. Please log in again.');return}
    if(profile)panel(`${dataLabel()}${card('Data unavailable','<p>Internet or backend connection failed. Previously loaded data is hidden until authorization and freshness are restored.</p>')}`);
  }
}

$('#awayToggle').disabled=true;
if(!runtime.caregiverApiConfigured){status('OFFLINE / UNCONFIGURED','This APK has no approved HTTPS backend.');loginScreen('Approved HTTPS backend is not configured.');}
else{
  try{profile=await api('me');await refresh()}
  catch{status('SIGN IN REQUIRED','Current monitoring status is unknown.');loginScreen()}
}
// Avoid replacing the scenario selector while the person is choosing/running a test.
setInterval(()=>{if(profile&&!document.hidden&&!busy&&tab!=='simulation')refresh()},15000);
document.addEventListener('visibilitychange',()=>{if(profile&&!document.hidden)refresh()});
