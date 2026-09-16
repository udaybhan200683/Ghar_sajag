import {evaluateScenario,renderValidationRow} from './validation_engine.mjs';
import {nextScheduleFeedback} from './schedule_feedback.mjs';
import {POLL_INTERVALS,addBounded,renderSignature,requestDue,shouldApplyStateUpdate} from './performance_runtime.mjs';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let state={
  away:false,homeAlert:false,morning:true,morningMissing:false,morningStatus:'UNAVAILABLE',ok:true,okLastAgeSeconds:null,doorOpen:false,doorLeftOpenAlert:false,doorUnexpectedAlert:false,doorPostCloseAlert:false,doorOpenForSeconds:0,indoorAgo:0,
  nightBathroomVisits:0,nightCommonVisits:0,nightUnusual:false,nightConcernText:'',careSubtitle:'All is well at home.',careProblemKind:null,
  devices:[],events:[],deviceHealth:null,schedules:null,source:'Connecting to backend…'
};
let currentTab='home', reportPeriod='week';
let scheduleEditorOpen=false;
let scheduleFeedbackState={message:'',kind:''};
let phase1EditorOpen=false;
let validation={catalog:null,results:[],running:false,last:null};
let reportState={status:'idle',data:null,error:''};
let reportRequestSeq=0, reportInFlight=false, reportAbortController=null, reportRefreshTimer=null;
const reportApiPeriods={day:'TODAY',week:'WEEK',month:'MONTH'};
let notifiedRecords=new Set();
let notificationPreferenceCache=null, notificationPollInFlight=false, lastNotificationPoll=0;
let statePollInFlight=false;
let scenarioActionQueue=Promise.resolve();
const lastRenderSignature={home:'',devices:'',reports:''};

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

async function backendRequest(path,body,extra={}){
  const headers={'X-Actor-Id':'simulation-owner'};
  const options=body===undefined?{cache:'no-store',headers,...extra}:{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify(body),...extra};
  const response=await fetch(path,options);
  if(!response.ok){
    let detail=''; try{detail=(await response.json()).error||''}catch(_){ }
    throw new Error(detail||`HTTP ${response.status}`);
  }
  return response.json();
}
async function foundationRequest(path,method='GET',body){
  const response=await fetch(`/pwa/foundation/${path}`,{method,cache:'no-store',headers:{'Content-Type':'application/json','X-Actor-Id':'simulation-owner'},body:body===undefined?undefined:JSON.stringify(body)});
  if(!response.ok){let detail='';try{detail=(await response.json()).error||''}catch(_){}throw new Error(detail||`HTTP ${response.status}`)}
  return response.json();
}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function formError(message){const el=$('#phase1Error');if(el)el.textContent=message}
function phase1Dialog(title,content){phase1EditorOpen=true;const d=$('#phase1Dialog');d.innerHTML=`<div class="phase1-head"><h2>${esc(title)}</h2><button type="button" onclick="closePhase1Dialog()" aria-label="Cancel and close">✕</button></div><div id="phase1Error" role="alert" class="status-bad"></div>${content}`;if(!d.open)d.showModal()}
window.closePhase1Dialog=()=>{const d=$('#phase1Dialog');if(d.open)d.close();d.innerHTML='';phase1EditorOpen=false};
$('#phase1Dialog').addEventListener('close',()=>{phase1EditorOpen=false});


async function loadValidationCatalog(){if(!validation.catalog)validation.catalog=await backendRequest('/pwa/validation/catalog');return validation.catalog}
function validationSummary(){const total=validation.catalog?.count||0,done=validation.results.length,passed=validation.results.filter(r=>r.pass).length;return {total,done,passed,failed:done-passed,complete:total>0&&done===total}}
async function runValidationScenario(id,{renderEach=true}={}){
  const result=evaluateScenario(await backendRequest('/pwa/validation/run',{scenario_id:id}));
  validation.last=result; const i=validation.results.findIndex(x=>x.scenario.id===id); if(i>=0)validation.results[i]=result;else validation.results.push(result); if(renderEach)renderValidationOnly(); return result;
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
    try{applyBackend(await backendRequest('/pwa/action',{action:'reset_pass'}),{force:true});}catch(_){}
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
window.runSelectedScenario=async()=>{await loadValidationCatalog();renderValidationOnly();const id=document.querySelector('#scenarioSelect')?.value;if(id)await runValidationScenario(id)};
window.clearValidationResults=()=>{validation.results=[];validation.last=null;renderValidationOnly()};

function applyBackend(view,{force=false}={}){
  if(!shouldApplyStateUpdate(state.simulationNow,view?.simulation_now,{
    currentEpoch:state.stateEpoch,nextEpoch:view?.state_epoch,force
  }))return false;
  state={
    away:false,
    homeAlert:!!view.care?.alert,
    morning:!!view.morning?.ok,
    morningMissing:!!view.morning?.missing,
    morningStatus:view.morning?.status||'UNAVAILABLE',
    ok:!!view.iam_ok?.ok,
    okStatus:view.iam_ok?.status||'NORMAL',
    okLastAgeSeconds:view.iam_ok?.last_ok_age_s ?? null,
    coverageLost:!!view.coverage?.lost,
    doorOpen:!!view.door?.open,
    doorLeftOpenAlert:!!view.door?.left_open_alert,
    doorUnexpectedAlert:!!view.door?.unexpected_alert,
    doorPostCloseAlert:!!view.door?.post_close_inactivity_alert,
    doorOpenForSeconds:Number(view.door?.open_for_s ?? 0),
    indoorAgo:view.door?.indoor_activity_age_min ?? 0,
    nightBathroomVisits:Number(view.night?.bathroom_visits ?? 0),
    nightCommonVisits:Number(view.night?.common_visits ?? 0),
    nightUnusual:!!view.night?.unusual,
    nightConcernText:view.night?.concern_text||'',
    careSubtitle:view.care?.subtitle||'All is well at home.',
    careProblemKind:view.care?.problem_kind||null,
    devices:Array.isArray(view.devices)?view.devices.map(d=>({...d})):state.devices,
    homeDetails:view.home_details||state.homeDetails||null,
    familyMembers:Array.isArray(view.family_members)?view.family_members.map(m=>({...m})):state.familyMembers||[],
    network:view.network||state.network||null,
    deviceHealth:view.device_health||null,
    schedules:view.schedules||state.schedules||null,
    simulationNow:view.simulation_now ?? state.simulationNow ?? null,
    stateEpoch:view.state_epoch ?? state.stateEpoch ?? null,
    source:view.source||'Backend',
    events:(view.events||[]).map(e=>({time:formatSimTime(e.at),icon:e.icon||'•',text:e.title||'Activity',tone:e.tone||'green',at:e.at}))
  };
  render();
  return true;
}

async function refreshFromBackend(showError=false,scope='home',options={}){
  try{return applyBackend(await backendRequest(`/pwa/state?scope=${encodeURIComponent(scope)}`),options);}
  catch(err){if(showError) toast(`Backend unavailable: ${err.message}`);}
  return false;
}
async function pollState(scope){
  if(statePollInFlight)return;
  statePollInFlight=true;
  try{await refreshFromBackend(false,scope)}finally{statePollInFlight=false}
}

async function scenarioAction(body){
  try{
    applyBackend(await backendRequest('/pwa/action',body),{force:true});
  }catch(err){toast(`Simulation failed: ${err.message}`);}
}
function batteryClass(health,drain='NORMAL'){
  if(drain==='HIGH' || health==='CRITICAL' || health==='LOW')return 'red';
  return health==='UNKNOWN'?'amber':'';
}
function homeSeverity(){
  // The banner is only an overall household status summary. Routine-specific
  // details belong to the routine cards below it.
  if(state.homeAlert){
    return {alert:true,title:'Attention needed at home',sub:'Please check the highlighted routine below.'};
  }
  return {alert:false,title:'Home looks normal',sub:'All is well at home.'};
}

function humanizeDuration(seconds){
  const total=Math.max(0,Math.floor(Number(seconds)||0));
  const hours=Math.floor(total/3600), minutes=Math.floor((total%3600)/60);
  if(hours && minutes)return `${hours} hr ${minutes} min`;
  if(hours)return `${hours} hr`;
  if(minutes)return `${minutes} min`;
  return `${total} sec`;
}
function countLabel(value,singular){
  const count=Number(value)||0;
  return `${count} ${count===1?singular:`${singular}s`}`;
}
function requireReportPayload(data){
  if(!data || data.schema_version!==1 || !data.summary || !Array.isArray(data.trend) || !Array.isArray(data.highlights) || !Array.isArray(data.insights))throw new Error('malformed_report');
  if(!['TODAY','WEEK','MONTH'].includes(data.period) || !['DATA','NO_DATA'].includes(data.status))throw new Error('malformed_report');
  return data;
}
async function loadReport({quiet=false}={}){
  if(reportInFlight && quiet)return;
  if(reportInFlight)reportAbortController?.abort();
  cancelReportRefresh();
  const apiPeriod=reportApiPeriods[reportPeriod]||'WEEK';
  const needsLoading=!reportState.data || reportState.data.period!==apiPeriod || reportState.status==='error';
  const requestId=++reportRequestSeq;
  reportInFlight=true;
  reportAbortController=new AbortController();
  if(needsLoading){
    reportState={status:'loading',data:reportState.data,error:''};
    renderReports();
  }
  try{
    const data=requireReportPayload(await backendRequest(`/v1/homes/simulation-home/reports?period=${encodeURIComponent(apiPeriod)}`,undefined,{signal:reportAbortController.signal}));
    if(requestId===reportRequestSeq)reportState={status:data.status==='NO_DATA'?'no-data':'data',data,error:''};
  }catch(err){
    if(requestId===reportRequestSeq){
      reportState={status:'error',data:null,error:'Reports are temporarily unavailable.'};
      if(!quiet && currentTab==='reports')toast('Reports are temporarily unavailable');
    }
  }finally{
    if(requestId===reportRequestSeq)reportInFlight=false;
    if(requestId===reportRequestSeq){renderReports();scheduleReportRefresh()}
  }
}
function cancelReportRefresh(){
  if(reportRefreshTimer!==null)clearTimeout(reportRefreshTimer);
  reportRefreshTimer=null;
}
function scheduleReportRefresh(){
  cancelReportRefresh();
  if(currentTab!=='reports' || document.hidden)return;
  // Anchor the refresh to the completed request. A due check on the 2-second
  // Home poll cadence can turn a 4-second report interval into nearly 6 seconds.
  reportRefreshTimer=setTimeout(()=>{
    reportRefreshTimer=null;
    if(currentTab!=='reports' || document.hidden)return;
    if(validation.running)scheduleReportRefresh();
    else loadReport({quiet:true});
  },POLL_INTERVALS.reportsMs);
}
function reportPeriodLabel(period){return period==='day'?'Today':period==='week'?'This Week':'This Month'}
function reportMetric(value,singular){return countLabel(Number(value)||0,singular)}
function reportTile(icon,value,label,key,tone=''){
  return `<div class="report-tile ${tone}" data-report-card="${esc(key)}">${icon}<strong>${esc(value)}</strong><span>${esc(label)}</span></div>`;
}
function renderReportTrend(data){
  const max=Math.max(1,...data.trend.map(item=>Number(item.activity_events)||0));
  const bars=data.trend.map(item=>{
    const activity=Number(item.activity_events)||0, concerns=Number(item.care_concerns)||0;
    return `<div class="bar-wrap" data-report-bucket="${esc(item.key)}"><div class="bar-val">${activity}</div><div class="bar ${concerns?'concern':''}" style="height:${Math.max(10,Math.round(activity/max*120))}px"></div><div class="bar-label">${esc(item.label)}</div></div>`;
  }).join('');
  return `<div class="card report-card" style="margin-top:16px"><h2>Activity trend</h2><div class="muted">Recorded household activity by day</div><div class="chart report-chart">${bars}</div></div>`;
}
function renderReportHighlights(data){
  if(!data.highlights.length)return `<div class="insight"><strong>No notable activity recorded</strong><div class="muted">There are no caregiver highlights for this period.</div></div>`;
  return data.highlights.map(item=>`<div class="insight report-highlight ${esc(item.tone||'neutral')}" data-report-highlight="${esc(item.tone||'neutral')}"><strong>${esc(item.title)}</strong><div class="muted">${esc(item.time)} · ${esc(item.detail)}</div></div>`).join('');
}
function renderReportInsights(data){
  if(!data.insights.length)return `<div class="insight"><strong>Insufficient history</strong><div class="muted">Reports will summarize trends as more household activity is recorded.</div></div>`;
  return data.insights.map(item=>`<div class="insight"><strong>${esc(item.title)}</strong><div class="muted">${esc(item.detail)}</div></div>`).join('');
}
function renderReportData(data){
  const s=data.summary;
  const concernTone=Number(s.care_concerns)>0?'danger':'';
  const dateRange=data.window?.start_local===data.window?.end_local?data.window?.start_local:`${data.window?.start_local} to ${data.window?.end_local}`;
  const rooms=(data.room_activity||[]).map(item=>`<span>${esc(item.location)}: ${reportMetric(item.count,'event')}</span>`).join('');
  return `
 <div class="card report-card"><h2>${esc(data.label)} at a glance</h2><div class="muted">Backend history from ${esc(dateRange||'this period')}</div><div class="report-grid" style="margin-top:14px">
   ${reportTile('☀️',reportMetric(s.morning_completed,'completion'),'Morning routine','morning')}
   ${reportTile('✓',reportMetric(s.check_ins,'check-in'),'I am OK','check-ins')}
   ${reportTile('☾',reportMetric(s.night_activity,'event'),'Night activity','night')}
   ${reportTile('!',reportMetric(s.care_concerns,'concern'),'Care concerns','concerns',concernTone)}
 </div>${data.partial_data?'<p class="muted report-note">Some report domains have no recorded activity in this period.</p>':''}</div>
 ${renderReportTrend(data)}
 <div class="card report-card" style="margin-top:16px"><h2>Notable activity</h2>${renderReportHighlights(data)}</div>
 <div class="card report-card" style="margin-top:16px"><h2>Caregiver insights</h2>${renderReportInsights(data)}</div>
 <div class="card report-card" style="margin-top:16px"><h2>Rooms and door activity</h2><div class="report-grid compact">
   ${reportTile('🚪',reportMetric(s.door_openings,'opening'),'Main door','door')}
   ${reportTile('☎',reportMetric(s.call_family,'request'),'Call Family','call-family')}
   ${reportTile('📶',reportMetric(s.coverage_lost,'loss'),'Coverage lost','coverage-lost',Number(s.coverage_lost)>0?'danger':'')}
   ${reportTile('✓',reportMetric(s.coverage_restored,'restoration'),'Coverage restored','coverage-restored')}
 </div>${rooms?`<div class="room-summary">${rooms}</div>`:'<p class="muted report-note">No room activity recorded for this period.</p>'}</div>`;
}

function renderHome(){
  const signature=renderSignature({
    homeAlert:state.homeAlert,morningStatus:state.morningStatus,ok:state.ok,okStatus:state.okStatus,
    okLastAgeSeconds:state.okLastAgeSeconds,coverageLost:state.coverageLost,doorOpen:state.doorOpen,
    doorLeftOpenAlert:state.doorLeftOpenAlert,doorUnexpectedAlert:state.doorUnexpectedAlert,
    doorPostCloseAlert:state.doorPostCloseAlert,doorOpenForSeconds:state.doorOpenForSeconds,
    indoorAgo:state.indoorAgo,nightBathroomVisits:state.nightBathroomVisits,
    nightCommonVisits:state.nightCommonVisits,nightUnusual:state.nightUnusual,
    nightConcernText:state.nightConcernText,deviceHealth:state.deviceHealth,events:state.events,
  });
  if(signature===lastRenderSignature.home && $('#homeTab').childElementCount)return;
  lastRenderSignature.home=signature;
  const s=homeSeverity(), health=state.deviceHealth || {low_name:'Unknown',low_percent:0,runtime:'calculating',attention:false,high_drain_devices:[]};
  const highDrain=(health.high_drain_devices||[]).map(id=>health.high_drain_device_names?.[id]||state.devices.find(d=>d.id===id)?.name||id);
  const offlineDevices=(health.offline_devices||[]).map(id=>health.offline_device_names?.[id]||state.devices.find(d=>d.id===id)?.name||id);
  const batteryAlert=Number(health.alert_percent ?? state.schedules?.battery_alert_percent ?? 20);
  const healthHeadline=highDrain.length?`Battery draining faster: ${highDrain.join(', ')}`:(health.low_percent==null?'No battery telemetry':health.low_percent<=batteryAlert?`Low battery: ${health.low_name} ${health.low_percent}%`:`Lowest battery: ${health.low_name} ${health.low_percent}%`);
  const rawRuntime=String(health.runtime||'').trim();
  const runtimeUnavailable=!rawRuntime || /^(calculating|recharge now|unknown)$/i.test(rawRuntime);
  const runtimeText=runtimeUnavailable?'Collecting battery data':rawRuntime;
  const morningStatus=state.morningStatus;
  const morningClass=morningStatus==='MISSED'?'status-bad':morningStatus==='COMPLETED'?'status-good':morningStatus==='IN_PROGRESS'?'status-amber':'muted';
  const morningText=morningStatus==='COMPLETED'?'Completed':morningStatus==='MISSED'?'Activity not completed':morningStatus==='IN_PROGRESS'?'In progress':'Not started';
  const morningDetail=morningStatus==='COMPLETED'?'Bedroom, bathroom and kitchen activity observed':morningStatus==='MISSED'?'Configured morning routine was not completed':morningStatus==='IN_PROGRESS'?'Routine activity is in progress':'Waiting for the configured morning routine to start';
  const doorDetail=state.doorLeftOpenAlert?`Open for ${humanizeDuration(state.doorOpenForSeconds)}`:state.doorUnexpectedAlert?'Opened during configured quiet hours':state.doorPostCloseAlert?'No indoor activity after door closed':state.doorOpen?'Door is currently open':`Indoor activity · ${state.indoorAgo} min ago`;
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
      <div class="hero ${s.alert?'alert':''}" data-severity="${s.alert?'danger':'success'}">
        <div class="hero-row"><div class="hero-icon">${s.alert?'!':'✓'}</div><div><h1>${s.title}</h1><p>${s.sub}</p></div></div>
      </div>
      <div class="grid2 routine-grid">
        <div class="card ${morningStatus==='MISSED'?'alert':''}" data-care-card="morning" data-status="${morningStatus}" data-severity="${morningStatus==='MISSED'?'danger':morningStatus==='COMPLETED'?'success':morningStatus==='IN_PROGRESS'?'warning':'neutral'}"><div class="card-row"><div class="round-icon">☀️</div><div><h2>Morning routine</h2><div class="${morningClass}">${morningText}</div><div class="${morningStatus==='MISSED'?'status-bad':'muted'}">${morningDetail}</div></div></div></div>
        <div class="card ${state.ok?'':'alert'}" data-care-card="ok" data-status="${state.okStatus}" data-severity="${state.ok?'success':'danger'}"><div class="card-row"><div class="round-icon">❤</div><div><h2>I am OK</h2><div class="${state.ok?'status-good':'status-bad'}">${state.okStatus==='OVERDUE'?'I am OK overdue':state.okStatus==='ACKNOWLEDGED'?'Just confirmed':'Confirmed'}</div>${state.okLastAgeSeconds!=null&&state.okStatus!=='OVERDUE'?`<div class="muted">Last confirmed ${humanizeDuration(state.okLastAgeSeconds)} ago</div>`:state.okStatus==='OVERDUE'?'<div class="status-bad">Expected check-in has not arrived</div>':''}</div></div></div>
        <div class="card ${state.doorLeftOpenAlert||state.doorUnexpectedAlert||state.doorPostCloseAlert?'alert':''}" data-care-card="door"><div class="card-row"><div class="round-icon">🚪</div><div><h2>Main door</h2><div class="${state.doorLeftOpenAlert||state.doorUnexpectedAlert||state.doorPostCloseAlert?'status-bad':'status-good'}">${state.doorOpen?'Open':'Closed'}</div><div class="${state.doorLeftOpenAlert||state.doorUnexpectedAlert||state.doorPostCloseAlert?'status-bad':'muted'}">${doorDetail}</div></div></div></div>
        <div class="card ${state.nightUnusual?'alert':''}" data-care-card="night"><div class="card-row"><div class="round-icon night">☾</div><div><h2>Night activity</h2><div>Bathroom: ${countLabel(state.nightBathroomVisits,'time')}<br>Common room: ${countLabel(state.nightCommonVisits,'time')}</div><div class="${state.nightUnusual?'status-bad':'status-good'}">${state.nightUnusual?'Unusual activity':'No unusual activity'}</div>${state.nightUnusual?`<div class="status-bad">${state.nightConcernText||'Night activity is outside the configured routine'}</div>`:'<div class="muted">Within configured night routine</div>'}</div></div></div>
        <div class="card ${health.attention?'alert':''} wide-card" data-care-card="device-health" data-severity="${health.attention?'danger':'neutral'}"><div class="card-row"><div class="round-icon">🔋</div><div><h2>Device health</h2>${state.coverageLost?'<div class="status-bad">Monitoring coverage lost</div>':''}${offlineDevices.length?`<div class="status-bad">Offline: ${offlineDevices.map(esc).join(', ')}</div>`:''}<div class="${health.attention?'status-bad':''}">${healthHeadline}</div><div class="${runtimeUnavailable?'muted':health.attention?'status-bad':'muted'}">Estimated time left: ${runtimeText}</div>${health.attention&&health.low_percent!=null&&health.low_percent<=batteryAlert?'<div class="status-bad">Recharge now</div>':''}</div></div></div>
      </div>
      <div class="timeline"><div class="section-title"><h2>Recent important events</h2><button class="link-btn" onclick="toast('All events view will use backend history in the pilot.')">View all ›</button></div>
        ${state.events.map(e=>`<div class="event"><div class="event-time">${e.time}</div><div>${e.icon}</div><div class="event-pill ${e.tone==='red'?'red':e.tone==='blue'?'blue':''}">${e.text}</div></div>`).join('')}
      </div>
    </div>
  </div>`;
}
function renderDevices(){
 const signature=renderSignature(state.devices);
 if(signature===lastRenderSignature.devices && $('#devicesTab').childElementCount)return;
 lastRenderSignature.devices=signature;
 const active=state.devices.filter(d=>d.active).length;
 $('#devicesTab').innerHTML=`
 <div class="device-summary"><div><h1 style="margin:0">${state.devices.length} devices total</h1><p class="muted">Registered devices from your household backend.</p><button type="button" onclick="openDeviceRegister()">Register simulated device</button></div><div class="metric-box"><strong>${active}</strong><div>active</div></div><div class="metric-box bad"><strong>${state.devices.length-active}</strong><div>inactive</div></div></div>
 <div class="device-list">${state.devices.map(d=>{const batteryAlert=d.battery_health==='LOW'||d.battery_health==='CRITICAL',drainHigh=d.drain_status==='HIGH',attention=!d.active||batteryAlert||drainHigh;const remaining=/^(calculating|unknown|recharge now)$/i.test(String(d.left||''))?'Collecting battery data':d.left;return `<div class="device-card ${attention?'alert':''}" data-device-id="${d.id}" data-status="${d.active?'online':'offline'}" data-battery-status="${d.battery_health}">
   <div class="round-icon">${d.id==='entry'?'🚪':d.id==='hub'?'📶':'🏃'}</div>
   <div><div class="device-name">${esc(d.name)}</div><div class="muted">${esc(d.type)} · ${esc(d.room||'Unassigned')}</div><div class="${d.active?'status-good':'status-bad'}">● ${d.active?'Active':'Inactive'}</div>${drainHigh?'<div class="status-bad">Battery draining faster than usual</div>':''}</div>
   <div class="battery-col"><div class="battery"><div class="battery-icon"><div class="battery-fill ${batteryClass(d.battery_health,d.drain_status)}" style="width:${Math.max(2,Number(d.battery)||0)}%"></div></div><div class="battery-pct">${d.battery==null?'—':`${d.battery}%`}</div></div>
   <div class="${batteryAlert||drainHigh?'status-bad':'status-good'}">Estimated ${d.id==='hub'?'backup':'time left'} ${esc(remaining||'Collecting battery data')}</div>${batteryAlert?'<div class="status-bad">Recharge now</div>':''}<div class="muted">◷ ${d.active?'Last updated':'Last seen'} ${esc(d.updated)}</div></div><button type="button" onclick="openDeviceDetails('${d.id}')">Details ›</button>
 </div>`}).join('')}</div>`;
}
function renderReports(){
 const signature=renderSignature({reportPeriod,reportState});
 if(signature===lastRenderSignature.reports && $('#reportsTab').childElementCount)return;
 lastRenderSignature.reports=signature;
 const status=reportState.status==='idle'?'loading':reportState.status;
 const data=reportState.data;
 const activeApiPeriod=reportApiPeriods[reportPeriod]||'WEEK';
 const stale=data && data.period!==activeApiPeriod;
 const body=status==='error'?`<div class="card report-state error" role="alert" data-report-status="error"><h2>Reports unavailable</h2><p class="muted">${esc(reportState.error||'Reports are temporarily unavailable.')}</p><button type="button" onclick="loadReport()">Try again</button></div>`:
   (status==='loading' || stale)?`<div class="card report-state" data-report-status="loading"><h2>Loading ${esc(reportPeriodLabel(reportPeriod))}</h2><p class="muted">Fetching household history from the backend.</p></div>`:
   status==='no-data'?`<div class="card report-state" data-report-status="no-data"><h2>No recorded activity for ${esc(reportPeriodLabel(reportPeriod).toLowerCase())}</h2><p class="muted">Reports become available as household activity is recorded. No-data is not a backend error.</p></div>`:
   renderReportData(data);
 $('#reportsTab').innerHTML=`
 <div class="card"><div class="card-row"><div class="round-icon">▥</div><div><h1 style="margin:0">Reports</h1><div class="muted">Family care summary from backend history</div></div></div></div>
 <div class="tabs3">${['day','week','month'].map(p=>`<button type="button" class="${reportPeriod===p?'active':''}" data-report-period="${p}" onclick="setReport('${p}')">${reportPeriodLabel(p)}</button>`).join('')}</div>
 <div data-report-period-active="${esc(activeApiPeriod)}" data-report-status="${esc(status)}">${body}</div>`;
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
   <div class="schedule-header"><div><h2>Routines & Activity Rules</h2><p class="muted">These values are household-specific. Change them to match the resident's routine; they are saved as versioned backend configuration.</p></div><button onclick="closeScheduleEditor()">✕</button></div>
   <form id="scheduleForm" onsubmit="saveScheduleSettings(event)">
    <section><h3>Morning routine</h3><label class="toggle-line"><input name="morning_sequence_enabled" type="checkbox" ${r.morning_sequence_enabled?'checked':''}> Enable morning sequence</label>
      <div class="form-grid"><label>Active from<input name="morning_start_minute" type="time" value="${minutesToClock(r.morning_start_minute)}"></label><label>Active until<input name="morning_end_minute" type="time" value="${minutesToClock(r.morning_end_minute)}"></label><label>Complete within (hours)<input name="morning_sequence_window_seconds" type="number" min="0.0167" max="24" step="any" value="${secondsToHours(r.morning_sequence_window_seconds)}"></label>
      <label>Bedroom activity<select name="morning_bedroom_location">${opts(r.morning_bedroom_location)}</select></label><label>Bathroom activity<select name="morning_bathroom_location">${opts(r.morning_bathroom_location)}</select></label><label>Kitchen activity<select name="morning_kitchen_location">${opts(r.morning_kitchen_location)}</select></label></div><p class="rule-help">Completion rule: bedroom activity first, then both configured bathroom and kitchen activity within the configured window.</p></section>
    <section><h3>Night activity</h3><label class="toggle-line"><input name="night_activity_enabled" type="checkbox" ${r.night_activity_enabled?'checked':''}> Enable night-activity monitoring</label>
      <div class="form-grid"><label>Night starts<input name="night_start_minute" type="time" value="${minutesToClock(r.night_start_minute)}"></label><label>Night ends<input name="night_end_minute" type="time" value="${minutesToClock(r.night_end_minute)}"></label><label>Merge motion into one visit (minutes)<input name="night_visit_merge_seconds" type="number" min="0" max="120" step="1" value="${Math.round(r.night_visit_merge_seconds/60)}"></label>
      <label>Bathroom location<select name="night_bathroom_location">${opts(r.night_bathroom_location)}</select></label><label>Bathroom visits allowed<input name="night_bathroom_visit_threshold" type="number" min="0" max="50" value="${r.night_bathroom_visit_threshold}"></label><label>Common-room location<select name="night_common_location">${opts(r.night_common_location)}</select></label><label>Common-room visits allowed<input name="night_common_visit_threshold" type="number" min="0" max="50" value="${r.night_common_visit_threshold}"></label></div><p class="rule-help">A concern is raised only when distinct visits are greater than the configured allowed count.</p></section>
    <section><h3>Main door & indoor activity</h3><div class="form-grid"><label>Door-open concern after (hours)<input name="door_open_timeout_seconds" type="number" min="0.0083" max="24" step="any" value="${secondsToHours(r.door_open_timeout_seconds)}"></label><label class="toggle-line"><input name="post_door_inactivity_enabled" type="checkbox" ${r.post_door_inactivity_enabled?'checked':''}> Watch for inactivity after door closes</label><label>No indoor activity after close (hours)<input name="post_door_inactivity_seconds" type="number" min="0.0833" max="24" step="any" value="${secondsToHours(r.post_door_inactivity_seconds)}"></label></div></section>
    <section><h3>General quiet/inactivity windows</h3><div class="form-grid"><label class="toggle-line"><input name="quiet_hours_enabled" type="checkbox" ${r.quiet_hours_enabled?'checked':''}> Quiet-hour door alerts</label><label>Quiet start<input name="quiet_start_minute" type="time" value="${minutesToClock(r.quiet_start_minute)}"></label><label>Quiet end<input name="quiet_end_minute" type="time" value="${minutesToClock(r.quiet_end_minute)}"></label><label class="toggle-line"><input name="daytime_inactivity_enabled" type="checkbox" ${r.daytime_inactivity_enabled?'checked':''}> General daytime inactivity</label><label>Day starts<input name="daytime_start_minute" type="time" value="${minutesToClock(r.daytime_start_minute)}"></label><label>Day ends<input name="daytime_end_minute" type="time" value="${minutesToClock(r.daytime_end_minute)}"></label><label>General inactivity threshold (hours)<input name="daytime_inactivity_seconds" type="number" min="0.0833" max="24" step="any" value="${secondsToHours(r.daytime_inactivity_seconds)}"></label></div></section>
    <section><h3>Device power & battery</h3><div class="form-grid"><label>Low-battery alert below (%)<input name="battery_alert_percent" type="number" min="2" max="50" step="1" value="${r.battery_alert_percent}"></label><label>Critical-battery alert below (%)<input name="critical_battery_percent" type="number" min="1" max="49" step="1" value="${r.critical_battery_percent}"></label><label class="toggle-line"><input name="abnormal_drain_alert_enabled" type="checkbox" ${r.abnormal_drain_alert_enabled?'checked':''}> Alert on abnormal drain</label></div><p class="rule-help">Battery-life prediction uses each device's calibrated power profile plus its measured voltage and usage counters. Current calibration is host-simulation data until hardware bench measurements are loaded.</p></section>
    <p id="scheduleFeedback" data-save-feedback="${esc(scheduleFeedbackState.kind)}" role="status" aria-live="polite" class="${scheduleFeedbackState.kind==='error'?'status-bad':scheduleFeedbackState.kind==='success'?'status-good':''}">${esc(scheduleFeedbackState.message)}</p><div class="schedule-actions"><button type="button" onclick="closeScheduleEditor()">Cancel</button><button type="submit" class="primary">Save household schedule</button></div>
   </form></div>`;
}
function renderSettings(){
 $('#settingsTab').innerHTML=`
 <div class="card"><h1 style="margin:0">Settings</h1><div class="muted">Customize your home and device preferences</div></div>
 ${settingsGroup('Home Settings',[['🏠','Home Details','Update home name, timezone and locale','openHomeDetails()'],['👥','Family Members','Manage family access and permissions','openFamilyMembers()'],['📶','Wi‑Fi & Network','View hub/network status','openNetworkStatus()']])}
 ${settingsGroup('Device Settings',[['⚙️','Manage Devices','Register, edit or remove devices','openManageDevices()'],['🔔','Notifications','Manage caregiver alert preferences','openNotificationSettings()'],['🔋','Battery Alerts','Set low and critical battery thresholds','openBatterySettings()'],['◷','Routines & Activity Rules','Set household routine windows and alert thresholds','openDeviceSchedules()','Device Schedules']])}
 ${settingsGroup('App Settings',[['🛡️','Privacy & Security','Future: security controls and retention details'],['❓','Help & Support','Phase 2: support guide pending'],['ℹ️','About','Phase 2: build details pending']])}
 <div id="scheduleMount"></div>
 <div style="margin:20px 0;text-align:center"><a href="https://ghar-sajag.rahuljnvakg.chatgpt.site/" target="_blank" rel="noopener" style="color:#0d8a43;font-weight:800">Visit public Ghar Sajag website ↗</a></div>`;
}
function settingsGroup(title,items){return `<div class="settings-group"><h3>${title}</h3>${items.map(x=>{const key=x[4]||x[1];return `<div class="setting" data-setting="${key}" ${x[3]?`onclick="${x[3]}"`:'aria-disabled="true"'}><div class="setting-icon">${x[0]}</div><div><strong>${x[1]}</strong><small>${x[2]}</small></div><div>${x[3]?'›':'Pending'}</div></div>`}).join('')}</div>`}
window.openHomeDetails=async()=>{
  try{const h=await foundationRequest('home');phase1Dialog('Home Details',`<form id="homeDetailsForm" onsubmit="saveHomeDetails(event)" class="phase1-form"><label>Home name<input name="display_name" required minlength="1" maxlength="80" value="${esc(h.display_name)}"></label><label>Timezone<input name="timezone" required maxlength="64" value="${esc(h.timezone)}"></label><label>Locale<input name="language" required maxlength="5" value="${esc(h.language)}"></label><div class="schedule-actions"><button type="button" onclick="closePhase1Dialog()">Cancel</button><button type="submit" class="primary">Save Home Details</button></div></form>`)}catch(err){toast(`Home Details unavailable: ${err.message}`)}
};
window.saveHomeDetails=async ev=>{ev.preventDefault();const f=new FormData(ev.target);try{await foundationRequest('home','PATCH',Object.fromEntries(f));await refreshFromBackend();closePhase1Dialog();toast('Home Details saved')}catch(err){formError(`Not saved: ${err.message}`)}};

function memberForm(m={}){return `<form id="memberForm" onsubmit="saveFamilyMember(event)" class="phase1-form" data-edit-id="${esc(m.member_id||'')}"><label>Member ID<input name="member_id" required pattern="[a-z][a-z0-9-]{1,31}" maxlength="32" value="${esc(m.member_id||'')}" ${m.member_id?'readonly':''}></label><label>Display name<input name="display_name" required maxlength="80" value="${esc(m.display_name||'')}"></label><label>Relationship<input name="relationship" maxlength="40" value="${esc(m.relationship||'')}"></label><label>Role<select name="role">${['OWNER','FAMILY','CAREGIVER'].map(x=>`<option value="${x}" ${m.role===x?'selected':''}>${x==='OWNER'?'Household admin':x==='FAMILY'?'Family member':'Caregiver'}</option>`).join('')}</select></label><label>Email (optional)<input name="contact" type="email" maxlength="120" value="${esc(m.contact||'')}"></label><div class="schedule-actions"><button type="button" onclick="openFamilyMembers()">Cancel</button><button type="submit" class="primary">${m.member_id?'Save member':'Add member'}</button></div></form>`}
window.openFamilyMembers=async()=>{try{const members=await foundationRequest('members');phase1Dialog('Family Members',`<p class="muted">Household admin can manage access. Deactivation keeps historical records.</p><button type="button" onclick="openFamilyMemberEditor()">Add family member</button><div class="phase1-list">${members.map(m=>`<div><strong>${esc(m.display_name)}</strong> · ${esc(m.role)} · ${m.active?'Active':'Inactive'}<br><small>${esc(m.relationship||'')} ${esc(m.contact||'')}</small>${m.active?`<button type="button" onclick="openFamilyMemberEditor('${m.member_id}')">Edit</button><button type="button" onclick="deactivateFamilyMember('${m.member_id}')">Deactivate</button>`:''}</div>`).join('')}</div>`)}catch(err){toast(`Family Members unavailable: ${err.message}`)}};
window.openFamilyMemberEditor=async(id='')=>{try{const members=id?await foundationRequest('members'):[];const m=members.find(x=>x.member_id===id)||{};phase1Dialog(id?'Edit Family Member':'Add Family Member',memberForm(m))}catch(err){toast(`Member unavailable: ${err.message}`)}};
window.saveFamilyMember=async ev=>{ev.preventDefault();const f=new FormData(ev.target),id=ev.target.dataset.editId;const body={member_id:String(f.get('member_id')),display_name:String(f.get('display_name')),relationship:String(f.get('relationship')),role:String(f.get('role')),contact:String(f.get('contact'))||null};try{await foundationRequest(id?`members/${id}`:'members',id?'PATCH':'POST',id?{display_name:body.display_name,relationship:body.relationship,role:body.role,contact:body.contact}:body);await refreshFromBackend();await openFamilyMembers();toast('Family member saved')}catch(err){formError(`Not saved: ${err.message}`)}};
window.deactivateFamilyMember=async id=>{if(!window.confirm('Deactivate this family member? Historical records will remain.'))return;try{await foundationRequest(`members/${id}`,'DELETE',{});await refreshFromBackend();await openFamilyMembers();toast('Member deactivated')}catch(err){formError(`Not deactivated: ${err.message}`)}};

const roomOptions=(selected)=>['Bedroom / Room 1','Kitchen','Main door','Pooja room','Bathroom','Common room','Central hub'].map(x=>`<option value="${esc(x)}" ${x===selected?'selected':''}>${esc(x)}</option>`).join('');
function deviceForm(d={}){const editing=!!d.device_id;return `<form id="deviceForm" onsubmit="saveDevice(event)" class="phase1-form" data-edit-id="${esc(d.device_id||'')}"><p class="muted">${editing?'Edit the registered device.':'Simulator registration only; physical ESP32 pairing remains hardware qualification.'}</p>${!editing?`<label>Device ID<input name="device_id" required pattern="[a-z][a-z0-9-]{1,31}" maxlength="32"></label><label>Type<select name="kind"><option value="NODE">Node</option><option value="HUB">Hub</option></select></label><label>Capability<select name="capability"><option value="MOTION">Motion</option><option value="DOOR">Door</option><option value="MOTION_BUTTON">Motion + resident buttons</option><option value="HUB">Hub</option></select></label>`:''}<label>Display name<input name="display_name" required maxlength="80" value="${esc(d.display_name||'')}"></label><label>Room/location<select name="room">${roomOptions(d.room||'')}</select></label>${editing?`<label class="toggle-line"><input name="enabled" type="checkbox" ${d.enabled?'checked':''}> Enabled</label>`:''}<div class="schedule-actions"><button type="button" onclick="closePhase1Dialog()">Cancel</button><button type="submit" class="primary">${editing?'Save device':'Register simulated device'}</button></div></form>`}
window.openDeviceRegister=()=>phase1Dialog('Register Device',deviceForm());
window.openDeviceDetails=async id=>{try{const d=await foundationRequest(`devices/${id}`),projected=state.devices.find(x=>x.id===id);const remaining=projected&&/^(calculating|unknown|recharge now)$/i.test(String(projected.left||''))?'Collecting battery data':projected?.left||'Collecting battery data';phase1Dialog('Device Details',`<div class="phase1-detail"><p><strong>${esc(d.display_name)}</strong> · ${esc(d.kind)} · ${esc(d.capability)}</p><p>ID: ${esc(d.device_id)} · Room: ${esc(d.room)}</p><p>${d.online?'Online':'Offline'} · ${esc(d.health)}</p><p>Last seen: ${d.last_seen_at==null?'Never':new Date(d.last_seen_at*1000).toLocaleString()}</p><p>Battery: ${d.battery_percent==null?'No telemetry':`${d.battery_percent}%`}</p><p>Estimated time left: ${esc(remaining)}</p>${projected?.drain_status==='HIGH'?'<p>Battery draining faster than usual</p>':''}<p>Firmware: ${esc(d.firmware_version||'Unknown')} · ${esc(d.registration_source)} registration</p></div><button type="button" onclick="openDeviceEditor('${d.device_id}')">Edit / Rename</button><button type="button" onclick="removeDevice('${d.device_id}')">Unregister device</button><button type="button" onclick="closePhase1Dialog()">Close</button>`)}catch(err){toast(`Device Details unavailable: ${err.message}`)}};
window.openDeviceEditor=async id=>{try{phase1Dialog('Edit Device',deviceForm(await foundationRequest(`devices/${id}`)))}catch(err){toast(`Device unavailable: ${err.message}`)}};
window.saveDevice=async ev=>{ev.preventDefault();const f=new FormData(ev.target),id=ev.target.dataset.editId;const body=id?{display_name:String(f.get('display_name')),room:String(f.get('room')),enabled:f.has('enabled')}:{device_id:String(f.get('device_id')),display_name:String(f.get('display_name')),kind:String(f.get('kind')),capability:String(f.get('capability')),room:String(f.get('room'))};try{await foundationRequest(id?`devices/${id}`:'devices',id?'PATCH':'POST',body);await refreshFromBackend(false,'full');closePhase1Dialog();toast(id?'Device saved':'Simulated device registered')}catch(err){formError(`Not saved: ${err.message}`)}};
window.removeDevice=async id=>{if(!window.confirm(`Unregister ${id}? Historical records will remain.`))return;try{await foundationRequest(`devices/${id}`,'DELETE',{});await refreshFromBackend(false,'full');closePhase1Dialog();toast('Device unregistered')}catch(err){formError(`Not unregistered: ${err.message}`)}};
window.openManageDevices=async()=>{try{const devices=await foundationRequest('devices');phase1Dialog('Manage Devices',`<button type="button" onclick="openDeviceRegister()">Register simulated device</button><div class="phase1-list">${devices.map(d=>`<div><strong>${esc(d.display_name)}</strong> · ${esc(d.kind)} · ${esc(d.room)}<button type="button" onclick="openDeviceDetails('${d.device_id}')">Details / Edit</button></div>`).join('')}</div>`)}catch(err){toast(`Manage Devices unavailable: ${err.message}`)}};
window.openNetworkStatus=async()=>{try{const n=await foundationRequest('network');phase1Dialog('Wi-Fi & Network',`<p>Hub: ${n.hub_online?'Online':'Offline'}</p><p>WAN: ${n.wan_online?'Online':'Offline'}</p><p class="muted">Physical Wi-Fi provisioning requires a hub hardware adapter. This simulator does not claim pairing or provisioning success.</p><button type="button" onclick="closePhase1Dialog()">Close</button>`)}catch(err){toast(`Network status unavailable: ${err.message}`)}};
window.openBatterySettings=async()=>{try{const p=await foundationRequest('policy'),r=p.settings;state.schedules=r;phase1Dialog('Battery Alerts',`<form id="batteryForm" onsubmit="saveBatterySettings(event)" class="phase1-form"><label>Low battery (%)<input name="battery_alert_percent" type="number" min="2" max="50" required value="${r.battery_alert_percent}"></label><label>Critical battery (%)<input name="critical_battery_percent" type="number" min="1" max="49" required value="${r.critical_battery_percent}"></label><label class="toggle-line"><input name="abnormal_drain_alert_enabled" type="checkbox" ${r.abnormal_drain_alert_enabled?'checked':''}> Alert on abnormal drain</label><div class="schedule-actions"><button type="button" onclick="closePhase1Dialog()">Cancel</button><button type="submit" class="primary">Save Battery Alerts</button></div></form>`)}catch(err){toast(`Battery Alerts unavailable: ${err.message}`)}};
window.saveBatterySettings=async ev=>{ev.preventDefault();const f=new FormData(ev.target),r={...state.schedules,battery_alert_percent:Number(f.get('battery_alert_percent')),critical_battery_percent:Number(f.get('critical_battery_percent')),abnormal_drain_alert_enabled:f.has('abnormal_drain_alert_enabled')};try{await foundationRequest('policy','PATCH',r);await refreshFromBackend();closePhase1Dialog();toast('Battery policy saved')}catch(err){formError(`Not saved: ${err.message}`)}};
function browserPermissionLabel(){if(!('Notification' in window))return 'Unavailable in this browser';return Notification.permission==='granted'?'Allowed':Notification.permission==='denied'?'Blocked':'Not allowed yet'}
function notificationForm(prefs,records){
 const p=prefs.preferences||{};
 const row=(name,label,detail)=>`<label class="toggle-line"><input name="${name}" type="checkbox" ${p[name]?'checked':''}> <span><strong>${label}</strong><small>${detail}</small></span></label>`;
 const rows=(records||[]).map(r=>`<div class="insight notification-record ${String(r.state).toLowerCase()}" data-notification-state="${esc(r.state)}"><strong>${esc(r.title)}</strong><div class="muted">${esc(r.state==='FAILED'?'Delivery failed':r.state==='SUPPRESSED'?'Suppressed by preference':r.state==='RESOLVED'?'Resolved':'Delivered')} · ${esc(r.message)}</div></div>`).join('');
 return `<form id="notificationForm" onsubmit="saveNotificationSettings(event)" class="phase1-form">
   ${row('safety_alerts','Safety and urgent concerns','Call Family, main door concerns, unusual night activity and similar safety alerts.')}
   ${row('routine_alerts','Routine concerns','Missed morning routine and daytime inactivity concerns.')}
   ${row('check_in_alerts','I am OK concerns','Expected check-ins that have not arrived.')}
   ${row('monitoring_alerts','Monitoring coverage','Coverage loss that may affect household monitoring.')}
   ${row('device_maintenance_alerts','Device maintenance','Separate from care and safety alerts.')}
   ${row('browser_alerts_enabled','Browser alerts on this device','Uses browser permission when available.')}
   <p class="muted">Browser permission: ${esc(browserPermissionLabel())}</p>
   <div class="schedule-actions"><button type="button" onclick="closePhase1Dialog()">Cancel</button><button type="submit" class="primary">Save Notifications</button></div>
   <h3>Recent notification status</h3>
   <div class="notification-history">${rows||'<p class="muted">No notification records yet.</p>'}</div>
 </form>`;
}
window.openNotificationSettings=async()=>{
 try{
   const [prefs,records]=await Promise.all([foundationRequest('notifications/preferences'),foundationRequest('notifications/records')]);
   notificationPreferenceCache=prefs;
   phase1Dialog('Notifications',notificationForm(prefs,records));
 }catch(err){toast(`Notifications unavailable: ${err.message}`)}
};
window.saveNotificationSettings=async ev=>{
 ev.preventDefault();
 const names=['safety_alerts','routine_alerts','check_in_alerts','monitoring_alerts','device_maintenance_alerts','browser_alerts_enabled'];
 const body=Object.fromEntries(names.map(name=>[name,ev.target.elements[name].checked]));
 try{
   notificationPreferenceCache=await foundationRequest('notifications/preferences','PATCH',body);
   toast('Notification settings saved');
   await openNotificationSettings();
 }catch(err){formError(`Not saved: ${err.message}`)}
};
async function pollBrowserNotifications(){
  if(!('Notification' in window) || Notification.permission!=='granted')return;
  const now=Date.now();
  if(!requestDue({inFlight:notificationPollInFlight,lastStartedAt:lastNotificationPoll,now,intervalMs:POLL_INTERVALS.notificationsMs}))return;
  notificationPollInFlight=true;
  lastNotificationPoll=now;
  try{
    const prefs=notificationPreferenceCache||await foundationRequest('notifications/preferences');
    notificationPreferenceCache=prefs;
    if(!prefs.preferences?.browser_alerts_enabled)return;
    const records=await foundationRequest('notifications/records');
    for(const record of records.filter(r=>r.state==='DELIVERED').reverse()){
      if(notifiedRecords.has(record.record_id))continue;
      addBounded(notifiedRecords,record.record_id,200);
      notify(record.title,record.message);
    }
  }catch(_){}
  finally{notificationPollInFlight=false}
}
window.openDeviceSchedules=async()=>{
  scheduleEditorOpen=true;
  scheduleFeedbackState={message:'',kind:''};
  try{
    const policy=await foundationRequest('policy');
    state.schedules=policy.settings;
  }catch(err){
    toast(`Routines & Activity Rules unavailable: ${err.message}`);
  }
  const m=$('#scheduleMount');
  if(m){
    m.innerHTML=scheduleEditor();
    m.scrollIntoView({behavior:'smooth',block:'start'});
  }
}
window.closeScheduleEditor=()=>{
  scheduleEditorOpen=false;
  scheduleFeedbackState={message:'',kind:''};
  const m=$('#scheduleMount');
  if(m)m.innerHTML='';
}
function scheduleFeedback(message='',kind=''){
 scheduleFeedbackState=nextScheduleFeedback(message,kind);
 const el=$('#scheduleFeedback');
 if(!el)return;
 el.textContent=message;
 el.dataset.saveFeedback=kind;
 el.className=kind==='error'?'status-bad':kind==='success'?'status-good':'';
}
window.saveScheduleSettings=async(ev)=>{ev.preventDefault();const f=new FormData(ev.target),r={...state.schedules};
 scheduleFeedback('','');
 const bools=['morning_sequence_enabled','night_activity_enabled','post_door_inactivity_enabled','quiet_hours_enabled','daytime_inactivity_enabled'];for(const k of bools)r[k]=f.has(k);
 for(const k of ['morning_start_minute','morning_end_minute','night_start_minute','night_end_minute','quiet_start_minute','quiet_end_minute','daytime_start_minute','daytime_end_minute'])r[k]=clockToMinutes(f.get(k));
 for(const k of ['morning_bedroom_location','morning_bathroom_location','morning_kitchen_location','night_bathroom_location','night_common_location'])r[k]=String(f.get(k));
 r.morning_sequence_window_seconds=hoursToSeconds(f.get('morning_sequence_window_seconds'));r.door_open_timeout_seconds=hoursToSeconds(f.get('door_open_timeout_seconds'));r.post_door_inactivity_seconds=hoursToSeconds(f.get('post_door_inactivity_seconds'));r.daytime_inactivity_seconds=hoursToSeconds(f.get('daytime_inactivity_seconds'));
 r.night_visit_merge_seconds=Math.round(Number(f.get('night_visit_merge_seconds'))*60);r.night_bathroom_visit_threshold=Number(f.get('night_bathroom_visit_threshold'));r.night_common_visit_threshold=Number(f.get('night_common_visit_threshold'));r.battery_alert_percent=Number(f.get('battery_alert_percent'));r.critical_battery_percent=Number(f.get('critical_battery_percent'));r.abnormal_drain_alert_enabled=f.has('abnormal_drain_alert_enabled');
 try{
   const confirmed=await backendRequest('/pwa/action',{action:'settings_save',settings:r});
   scheduleFeedback('Device schedule saved and applied to the hub','success');
   applyBackend(confirmed,{force:true});
   toast('Device schedule saved and applied to the hub');
   // applyBackend intentionally preserves Settings while editing. Repaint only
   // this editor from the backend-confirmed configuration.
   const m=$('#scheduleMount'); if(m && scheduleEditorOpen)m.innerHTML=scheduleEditor();
 }catch(err){scheduleFeedback(`Not saved: ${err.message}`,'error')}
}

function render(){
  if(currentTab==='home')renderHome();
  else if(currentTab==='devices')renderDevices();
  else if(currentTab==='reports')renderReports();
  // Backend polling can finish after the editor was opened. Rebuilding the
  // Settings tab here would detach the form every ~2 seconds and lose edits.
  // Keep the live editor DOM intact until the user saves or cancels.
  if(currentTab==='settings' && !scheduleEditorOpen && !phase1EditorOpen && !$('#settingsTab').childElementCount)renderSettings();
  $('#awayToggle').checked=false;
  $('#awayToggle').disabled=true;
}
$$('.nav-btn').forEach(b=>b.onclick=async()=>{
  const nextTab=b.dataset.tab;
  if(nextTab===currentTab)return;
  if(nextTab!=='reports')cancelReportRefresh();
  currentTab=nextTab;
  $$('.nav-btn').forEach(x=>x.classList.toggle('active',x===b));
  $$('.tab-panel').forEach(x=>x.classList.remove('active'));
  $('#'+currentTab+'Tab').classList.add('active');
  if(currentTab==='devices')await refreshFromBackend(false,'full');
  else if(currentTab==='home')await refreshFromBackend(false,'home');
  else render();
  if(currentTab==='reports')loadReport({quiet:true});
});
$('#awayToggle').checked=false; $('#awayToggle').disabled=true;
window.setReport=p=>{if(!reportApiPeriods[p])return;reportPeriod=p;loadReport()}
window.toggleDemo=k=>{
  scenarioActionQueue=scenarioActionQueue.then(()=>scenarioAction({action:'toggle',scenario:k}));
  return scenarioActionQueue;
}
window.resetDemo=async()=>{
  scenarioActionQueue=scenarioActionQueue.then(()=>scenarioAction({action:'reset_pass'}));
  await scenarioActionQueue;
  toast('Reset complete: all scenarios PASS');
}
window.toast=t=>{let n=document.createElement('div');n.className='toast';n.textContent=t;document.body.appendChild(n);setTimeout(()=>n.remove(),2200)}
window.enableNotifications=async()=>{if(!('Notification'in window))return toast('Browser notifications are not supported here.');let p=await Notification.requestPermission();toast(p==='granted'?'Notifications enabled':'Notification permission not granted')}
function notify(title,body){if('Notification'in window && Notification.permission==='granted')new Notification(title,{body,icon:'assets/icon.svg'})}
if('serviceWorker'in navigator) navigator.serviceWorker.register('sw.js');
(async()=>{await refreshFromBackend(true,'home',{force:true});if(new URLSearchParams(location.search).get('validation')==='autorun')await runAllValidation()})();
async function pollApplication(){
  if(validation.running)return;
  pollBrowserNotifications();
  if(document.hidden)return;
  pollState(currentTab==='devices'?'full':'home');
}
setInterval(pollApplication,POLL_INTERVALS.stateMs);
document.addEventListener('visibilitychange',()=>{
  if(document.hidden){cancelReportRefresh();return}
  if(!validation.running){pollState(currentTab==='devices'?'full':'home');if(currentTab==='reports')loadReport({quiet:true})}
});
