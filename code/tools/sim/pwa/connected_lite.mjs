import {normalizeRuntimeConfig,requestUrl} from './runtime_mode.mjs';

const runtime=normalizeRuntimeConfig(window.PARIVAR_SAATHI_RUNTIME,window.location.origin);
document.body.classList.add('connected-lite-runtime');
performance.mark('gs177-connected-ui-start');
const $=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let profile=null,tab='home',catalog=null,runs=[],selectedRun=null,view=null,lastSync=null,connection='OFFLINE';
let busy=false,engineeringScreen='Installation Overview';
let refreshPromise=null,refreshRequested=false;
let restoreController=null,restorePromise=null,authGeneration=0;
let loginFormTouched=false,loginPending=false,startupLoginMetricRecorded=false;

function updateHeaderClock(){
  const now=new Date();
  $('#dateText').textContent=now.toLocaleDateString(undefined,{weekday:'short',day:'numeric',month:'short',year:'numeric'});
  $('#timeText').textContent=now.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'});
}
updateHeaderClock();
setInterval(updateHeaderClock,15000);

async function api(path,{method='GET',body,signal}={}){
  const url=requestUrl(runtime,`/lite/v1/${path}`);
  if(!url)throw new Error('Approved HTTPS backend is not configured');
  const reply=await fetch(url,{method,credentials:'include',cache:'no-store',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal});
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
  profile=null;view=null;loginPending=false;loginFormTouched=false;
  if(restoreController){authGeneration++;restoreController.abort();restoreController=null;}
  $('.bottom-nav').hidden=true;
  $('.bottom-nav').replaceChildren();
  const reconnect=runtime.localBackendReconnect?'<p><a class="local-backend-reconnect" href="gharsajag://backend/reconnect">Reconnect to laptop server</a></p>':'';
  panel(`<div class="card connected-auth"><h1>Sign in</h1><p>Use your caregiver account to open its authorized Home.</p><p id="loginError" class="status-bad" role="alert" aria-live="polite">${esc(message)}</p><form id="loginForm"><label>Email<input name="email" type="email" autocomplete="username" autocapitalize="none" spellcheck="false" required></label><label>Password<input name="password" type="password" autocomplete="current-password" required></label><button type="submit">Log in</button></form>${reconnect}<p class="muted">Monitoring status remains unknown until the server verifies your session and current Home access.</p></div>`);
  document.querySelector('.local-backend-reconnect')?.addEventListener('click',event=>{event.preventDefault();window.location.href='gharsajag://backend/reconnect'});
  const form=$('#loginForm');
  const markCredentialEntry=()=>{
    loginFormTouched=true;
    if(restoreController&&!restoreController.signal.aborted){
      authGeneration++;
      restoreController.abort();
      restoreController=null;
    }
  };
  form.addEventListener('focusin',markCredentialEntry,{once:true});
  form.addEventListener('input',markCredentialEntry,{once:true});
  if(!startupLoginMetricRecorded){
    performance.mark('gs177-login-form-visible');
    performance.measure('gs177-login-form-visible','gs177-connected-ui-start','gs177-login-form-visible');
    const measurements=performance.getEntriesByName('gs177-login-form-visible','measure');
    const measurement=measurements[measurements.length-1];
    console.info(`GS177_STARTUP login_form_visible_ms=${Math.round(measurement?.duration||0)}`);
    startupLoginMetricRecorded=true;
  }
  form.onsubmit=async event=>{
    event.preventDefault();
    if(loginPending)return;
    markCredentialEntry();
    loginPending=true;
    const data=new FormData(event.target);
    const button=event.target.querySelector('button');button.disabled=true;
    const error=$('#loginError');
    error.textContent='';
    try{
      const loginProfile=await api('auth/login',{method:'POST',body:{email:data.get('email'),password:data.get('password')}});
      const verifiedProfile=await api('me');
      if(!validServerProfile(verifiedProfile)||
          (loginProfile.home_id&&loginProfile.home_id!==verifiedProfile.home_id))
        throw new Error('The server could not verify this session and Home access.');
      loginPending=false;
      profile=verifiedProfile;view=null;tab='home';
      renderCurrent();
      await refresh({verifiedProfile});
    }catch(failure){
      loginPending=false;
      if($('#loginForm')){
        button.disabled=false;
        error.textContent=`Login failed: ${failure.message}`;
      }else if(failure.message==='not_authorized')loginScreen('Session expired or access revoked. Please log in again.');
      else status('HOME DATA UNAVAILABLE',`Current authorized Home data could not be loaded: ${failure.message}. Monitoring is UNKNOWN.`);
    }
  };
}

function validServerProfile(value){
  return Boolean(value&&typeof value.home_id==='string'&&value.home_id&&
    ['ADMIN','CAREGIVER'].includes(value.role)&&Number.isFinite(Number(value.expires_at)));
}

function navCategory(name){
  if(['incidents','routines'].includes(name))return 'reports';
  if(['simulation','engineering'].includes(name))return 'settings';
  return name;
}

function nav(){
  const available=['home','devices','reports','settings'];
  const navigation=$('.bottom-nav');
  navigation.hidden=false;
  const activeTab=navCategory(tab);
  navigation.innerHTML=available.map(name=>`<button type="button" class="nav-btn ${activeTab===name?'active':''}" data-tab="${name}" ${activeTab===name?'aria-current="page"':''}><span>${name[0].toUpperCase()+name.slice(1)}</span></button>`).join('');
  navigation.querySelectorAll('button').forEach(button=>button.onclick=()=>openTab(button.dataset.tab));
}
function openTab(next){
  tab=next;selectedRun=null;
  nav();
  // Secondary views share their parent ribbon label and remain reachable from it.
  window.scrollTo({top:0,behavior:'instant'});
  void refresh();
}
function dataLabel(){
  const label=productSource()?'TEST_ONLY authenticated caregiver data':explicitSimulationHome()
    ?'TEST_ONLY simulator data':'TEST_ONLY · unrecognized source data hidden';
  return `<p class="test-watermark">${label} · ${esc(profile.home_id)} · ${esc(view?.source||'No physical source')}</p>`;
}
function card(title,body){return `<div class="card"><h2>${esc(title)}</h2>${body}</div>`}
function tableRows(items,render){return items.length?items.map(render).join(''):'<p class="muted">No saved observations.</p>'}
function productSource(){return ['NODE_ORIGIN_HOST_SIM','AUTHENTICATED_GS148_TEST_ONLY'].includes(view?.source)}
function explicitSimulationHome(){return profile?.test_only===true&&view?.source==='HOST_SIMULATION_TEST_ONLY'}
function productTime(value){
  const milliseconds=typeof value==='number'?value*1000:Date.parse(value||'');
  return Number.isFinite(milliseconds)?new Date(milliseconds).toLocaleString():'Time unavailable';
}
function productEventLabel(kind){
  return ({MOTION:'Motion recorded',DOOR_OPEN:'Door opened',DOOR_CLOSED:'Door closed',
    OK_PRESSED:'I Am OK check-in',CALL_FAMILY:'Call Family request',
    MORNING_ROUTINE_COMPLETED:'Morning routine completed',MISSING_MORNING_ACTIVITY:'Morning routine concern',
    UNUSUAL_NIGHT_BATHROOM_ACTIVITY:'Night activity concern',UNUSUAL_NIGHT_COMMON_ACTIVITY:'Night activity concern'})[kind]||kind||'Recorded activity';
}
function productEventOrigin(event){
  if(event.source_type==='HUB_RULE'||event.decision_id)return 'Hub rule decision';
  const key=event.event_key||{};
  // This exact TEST_ONLY fixture identity is the previously committed GS-178 host-simulation event.
  // It is a presentation label from the known fixture, never Hub or device attestation.
  if(profile?.home_id==='gs177-test-product'&&key.physical_device_id==='test-c3-bedroom'&&
     key.logical_node_id==='bedroom'&&key.origin_session_id===10&&key.event_sequence===1)
    return 'HOST_SIM · TEST_ONLY';
  return view?.source==='NODE_ORIGIN_HOST_SIM'?'HOST_SIM · TEST_ONLY':'TEST_ONLY · physical origin not verified';
}
const ACTIVE_INCIDENT_STATES=new Set(['OPEN','CLAIMED','ROUTE_EXHAUSTED']);
function incidentIsActive(incident){return ACTIVE_INCIDENT_STATES.has(incident?.state);}
function incidentVisualSeverity(incident,currentSource){
  if(!currentSource||!incidentIsActive(incident))return '';
  return ['URGENT','CONCERN'].includes(incident.severity)?incident.severity:'';
}
function eventVisualSeverity(event,{currentSource=false,routineCoverage='UNKNOWN'}={}){
  if(!currentSource||!event)return '';
  const hubDecision=event.source_type==='HUB_RULE'||Boolean(event.decision_id);
  const routineConcern=['MISSING_MORNING_ACTIVITY','UNUSUAL_NIGHT_BATHROOM_ACTIVITY',
    'UNUSUAL_NIGHT_COMMON_ACTIVITY'].includes(event.kind)||hubDecision;
  if(routineConcern&&routineCoverage!=='COVERED')return '';
  if(hubDecision)return event.details?.tone==='CONCERN'?'CONCERN':'';
  if(event.tone==='danger')return 'CONCERN';
  if(event.tone==='warning')return 'WARNING';
  if(event.tone==='positive')return 'POSITIVE';
  return '';
}
function productEvents(events,{currentSource=false,freshness='UNKNOWN',routineCoverage='UNKNOWN',historical=false}={}){
  if(!events?.length)return '<p class="muted" data-empty-events="true">No committed Node or Hub events are currently returned by the authorized caregiver API. This does not mean there was no household activity.</p>';
  return events.map(event=>{
    const hubDecision=event.source_type==='HUB_RULE'||Boolean(event.decision_id);
    const eventKey=!hubDecision&&event.event_key?JSON.stringify(event.event_key):'';
    const decisionId=hubDecision?(event.decision_id||event.event_id||'') : '';
    const identityAttribute=hubDecision
      ?`data-hub-decision="${esc(decisionId||'unknown')}"`
      :`data-event-key="${esc(eventKey)}"`;
    const identityLabel=hubDecision
      ?`Decision ID: ${decisionId||'Stable decision identity unavailable'}`
      :`EventKey: ${eventKey||'Unavailable'}`;
    const time=productTime(event.occurred_at);
    const room=event.location||event.event_key?.logical_node_id||'Room not reported';
    const icon=hubDecision?'◉':event.kind?.startsWith('DOOR_')?'<svg class="door-icon" viewBox="0 0 24 24" focusable="false"><path d="M5 3.5h14v17H5z"/><path d="M9 20.5v-17M15.5 12h.01"/></svg>':event.kind==='OK_PRESSED'?'♥':'•';
    const visualSeverity=eventVisualSeverity(event,{currentSource,routineCoverage});
    const visualTone=visualSeverity==='CONCERN'?'red':visualSeverity==='WARNING'?'warning':visualSeverity==='POSITIVE'?'blue':'';
    const sourceQuality=historical?'Recorded history':currentSource
      ?(visualSeverity?`Current source · ${visualSeverity}`:'Current source report')
      :freshness==='STALE'?'STALE · last reported':'UNKNOWN · source quality unavailable';
    const received=event.received_at&&event.received_at!==event.occurred_at
      ?`<small>Backend received ${esc(productTime(event.received_at))}${event.delayed?' · delayed':''}</small>`:'';
    return `<article class="event connected-product-event" data-source-origin="${esc(productEventOrigin(event))}" data-visual-severity="${esc(visualSeverity||'NONE')}" ${identityAttribute}><time class="event-time" datetime="${esc(typeof event.occurred_at==='number'?new Date(event.occurred_at*1000).toISOString():event.occurred_at||'')}">${esc(time)}</time><span class="event-icon" aria-hidden="true">${icon}</span><div class="event-detail"><span class="event-pill ${visualTone}">${esc(productEventLabel(event.kind))}</span><span class="event-quality">${esc(sourceQuality)}</span><p>${esc(room)} · <span class="event-origin">${esc(productEventOrigin(event))}</span></p><details><summary>${hubDecision?'Decision details':'Event details'}</summary><code>${esc(identityLabel)}</code></details>${received}</div></article>`;
  }).join('');
}
function latestEvent(kinds){
  return (productSource()?view?.recent_events||[]:[]).find(event=>kinds.includes(event.kind))||null;
}
function latestNightDecision(){
  return (productSource()?view?.decisions||[]:[])
    .filter(item=>String(item.kind||'').startsWith('UNUSUAL_NIGHT_'))
    .sort((a,b)=>Number(b.occurred_at??b.decided_at??0)-Number(a.occurred_at??a.decided_at??0))[0]||null;
}
function connectHomeActions(){
  $('#homeTab').querySelectorAll('[data-open-tab]').forEach(button=>button.onclick=()=>openTab(button.dataset.openTab));
}
function homeInfoCard({id,title,icon,value,detail,tab:targetTab,attention=''}){
  return `<section class="card home-info-card" data-home-card="${esc(id)}" data-attention="${esc(attention||'NONE')}"><div class="home-info-icon" aria-hidden="true">${icon}</div><div class="home-info-copy"><h2>${esc(title)}</h2><strong data-home-value="${esc(id)}">${esc(value)}</strong><p>${esc(detail)}</p></div>${targetTab?`<button class="home-card-link" type="button" data-open-tab="${esc(targetTab)}" aria-label="Open ${esc(title)} details">›</button>`:''}</section>`;
}
function homeDeviceText(devices,coverageCurrent){
  if(!coverageCurrent){
    const lastReported=devices.filter(device=>typeof device.status==='string'&&device.status)
      .map(device=>`${device.logical_node_id||device.physical_node_id||'Node'} ${device.status}`).join(', ');
    return {value:'UNKNOWN',detail:`Device status is unavailable until source freshness and coverage are current.${lastReported?` Last authenticated report: ${lastReported} · source not current.`:''}`};
  }
  if(!devices.length)return {value:'UNKNOWN',detail:'No current NodeHealth records were returned.'};
  const online=devices.filter(device=>device.status==='ONLINE'&&device.coverage==='COVERED').length;
  return {value:`${online} of ${devices.length} covered`,detail:'Current authenticated NodeHealth projection.'};
}

function renderHome(){
  const recognized=productSource();
  const freshness=recognized?(view?.source_freshness||'UNKNOWN'):'UNKNOWN';
  const coverageCurrent=recognized&&freshness==='CURRENT'&&view?.monitoring==='COVERED';
  const routineCoverage=view?.routine_coverage||'UNKNOWN';
  const stale=freshness==='STALE';
  const events=recognized?view?.recent_events||[]:[];
  const decisions=recognized?view?.decisions||[]:[];
  const devices=recognized?view?.devices||[]:[];
  const incidents=recognized?view?.incidents||[]:[];
  const morning=[...events,...decisions]
    .filter(item=>['MORNING_ROUTINE_COMPLETED','MISSING_MORNING_ACTIVITY'].includes(item.kind))
    .sort((a,b)=>Number(b.occurred_at??b.decided_at??0)-Number(a.occurred_at??a.decided_at??0))[0]||null;
  const morningSeverity=coverageCurrent?eventVisualSeverity(morning,{currentSource:true,routineCoverage}):'';
  const missedRoutineQualified=morning?.kind==='MISSING_MORNING_ACTIVITY'&&morningSeverity==='CONCERN';
  const doorStatus=recognized?view?.door_status:null;
  const doorConcern=coverageCurrent&&doorStatus?.state==='OPEN'&&(doorStatus.left_open===true||doorStatus.unexpected===true);
  const nightDecision=latestNightDecision();
  const nightSeverity=coverageCurrent?eventVisualSeverity(nightDecision,{currentSource:true,routineCoverage}):'';
  const activeIncidents=coverageCurrent?incidents.filter(item=>item.state!=='RESOLVED'):null;
  const urgentIncident=activeIncidents?.find(item=>incidentVisualSeverity(item,true)==='URGENT')||null;
  const concernIncident=activeIncidents?.find(item=>incidentVisualSeverity(item,true)==='CONCERN')||null;
  const otherConcern=(coverageCurrent?events:[]).find(item=>item.kind!=='MISSING_MORNING_ACTIVITY'&&
    eventVisualSeverity(item,{currentSource:true,routineCoverage})==='CONCERN')||null;
  const attention=urgentIncident?'URGENT':(missedRoutineQualified||concernIncident||otherConcern||doorConcern||nightSeverity==='CONCERN')?'CONCERN':'';
  const heading=urgentIncident?'Urgent incident needs attention':missedRoutineQualified?'Attention needed at home':
    concernIncident||otherConcern||doorConcern||nightSeverity==='CONCERN'?'A home concern needs attention':coverageCurrent?'Monitoring coverage is current':
      stale?'Monitoring source is stale':'Monitoring status is unknown';
  const hubContact=recognized&&view?.last_hub_at?`Latest authenticated Hub contact: ${productTime(view.last_hub_at)}.`:'No current authenticated Hub contact is available.';
  const morningSummary=morning?(!coverageCurrent?`${stale?'STALE':'UNKNOWN'} · last reported: ${productEventLabel(morning.kind)}`:
    morning.kind==='MISSING_MORNING_ACTIVITY'&&routineCoverage!=='COVERED'?'UNKNOWN · routine observation coverage unavailable':
    missedRoutineQualified?'Morning activity missed':productEventLabel(morning.kind)):'Routine status UNKNOWN';
  const acknowledgedCount=activeIncidents?.filter(item=>item.state==='ACKNOWLEDGED').length||0;
  const incidentSummary=activeIncidents?`Unresolved incidents: ${activeIncidents.length}${acknowledgedCount?` · acknowledged ${acknowledgedCount}`:''}`:'Unusual-activity status UNKNOWN';
  const deviceSummary=homeDeviceText(devices,coverageCurrent);
  const okEvent=latestEvent(['OK_PRESSED']);
  const doorEvent=latestEvent(['DOOR_OPEN','DOOR_CLOSED']);
  const freshnessQualifier=coverageCurrent?'Current source report':stale?'STALE · last reported':'UNKNOWN';
  const okValue=okEvent?(coverageCurrent?'Reported':'STALE · last reported'):'UNKNOWN';
  const okDetail=okEvent?`${freshnessQualifier} · ${productTime(okEvent.occurred_at)}`:'No current I am OK event is available.';
  const doorValue=doorStatus?`${coverageCurrent?'':stale?'STALE · ':'UNKNOWN · '}${doorStatus.state==='OPEN'?'Open':doorStatus.state==='CLOSED'?'Closed':'state unavailable'}`:
    doorEvent?`${coverageCurrent?'Last event':stale?'STALE · last event':'UNKNOWN · last event'}: ${doorEvent.kind==='DOOR_OPEN'?'opened':'closed'}`:'UNKNOWN';
  const doorDetail=doorStatus?(doorStatus.state==='OPEN'&&doorStatus.since?`${freshnessQualifier} · open since ${productTime(doorStatus.since)}${doorConcern?' · attention':''}`:`${freshnessQualifier} · state from latest door report`):
    doorEvent?`${freshnessQualifier} · ${productTime(doorEvent.occurred_at)}`:'No current door event is available.';
  const nightValue=nightDecision?(coverageCurrent?productEventLabel(nightDecision.kind):`${stale?'STALE':'UNKNOWN'} · last reported: ${productEventLabel(nightDecision.kind)}`):'UNKNOWN';
  const nightDetail=nightDecision?`${freshnessQualifier} · ${productTime(nightDecision.occurred_at||nightDecision.decided_at)}`:'No current night-activity decision is available.';
  const deviceDetail=coverageCurrent?`Current NodeHealth · ${devices.length} enrolled Node${devices.length===1?'':'s'}`:deviceSummary.detail;
  const deviceAttention=recognized&&freshness==='CURRENT'&&devices.some(device=>device.status==='OFFLINE')?'WARNING':'';
  const timeline=events.slice(0,5);
  const unknownProjection=!recognized&&view!==null;
  const testLabel=profile?.test_only?`<p class="test-watermark">TEST_ONLY · ${recognized?'authenticated GS-148 caregiver data':'Home monitoring unavailable'} · Home ${esc(profile.home_id)} · physical C3/S3 qualification NOT_RUN</p>`:'';
  const unknownNote=unknownProjection?'<p class="home-unknown-note">The current authorized backend did not provide a recognized Home projection. Monitoring, events and resident status are unknown; simulated data is not shown.</p>':'';
  panel(`${testLabel}<div class="connected-home">
    ${unknownNote}
    <section class="hero connected-home-hero" data-source-freshness="${esc(freshness)}" data-monitoring="${coverageCurrent?'COVERED':'UNKNOWN'}" data-attention="${esc(attention||'NONE')}">
      <div class="hero-row"><div class="hero-icon" aria-hidden="true">${attention?'!':coverageCurrent?'✓':'?'}</div><div class="home-hero-copy"><p class="home-eyebrow">HOME MONITORING</p><h1>${esc(heading)}</h1><p>${missedRoutineQualified?'Morning activity was not completed. Please check the home status. Severity: CONCERN; this is not an emergency classification.':urgentIncident?'An active incident is reported by the authorized service. Review its status in Reports.':concernIncident||otherConcern?'A current authorized source reported a concern. Review the recorded details.':`${esc(hubContact)} Monitoring coverage never establishes resident wellbeing.`}</p></div></div>
      <div class="connected-home-summary" aria-label="Current Home summary">
        <div class="home-summary-chip" data-home-summary="routine" data-attention="${esc(morningSeverity||'NONE')}" data-source-quality="${coverageCurrent?'CURRENT':esc(freshness)}"><span aria-hidden="true">☀</span><p><b>Routine</b><br>${esc(morningSummary)}</p></div>
        <div class="home-summary-chip" data-home-summary="incidents" data-attention="${urgentIncident?'URGENT':concernIncident?'CONCERN':'NONE'}"><span aria-hidden="true">!</span><p><b>Unusual activity</b><br>${esc(incidentSummary)}</p></div>
        <div class="home-summary-chip" data-home-summary="devices" data-attention="${deviceAttention}"><span aria-hidden="true">◉</span><p><b>Device connectivity</b><br>${esc(deviceSummary.value)}</p></div>
      </div>
    </section>
    <div class="connected-home-cards">
      ${homeInfoCard({id:'ok',title:'I am OK',icon:'♥',value:okValue,detail:okDetail,tab:'reports'})}
      ${homeInfoCard({id:'door',title:'Main door',icon:'<svg class="door-icon" viewBox="0 0 24 24" focusable="false"><path d="M5 3.5h14v17H5z"/><path d="M9 20.5v-17M15.5 12h.01"/></svg>',value:doorValue,detail:doorDetail,tab:'reports',attention:doorConcern?'CONCERN':''})}
      ${homeInfoCard({id:'night',title:'Night activity',icon:'☾',value:nightValue,detail:nightDetail,tab:'routines',attention:nightSeverity})}
      ${homeInfoCard({id:'device-health',title:'Device health',icon:'<svg class="battery-icon" viewBox="0 0 24 24" focusable="false"><rect x="2" y="5" width="18" height="14" rx="2"/><path d="M22 10v4"/><path d="M5 8h10v8H5z" class="battery-fill"/></svg>',value:deviceSummary.value,detail:deviceDetail,tab:'devices',attention:deviceAttention})}
    </div>
    <section class="timeline connected-home-timeline" aria-labelledby="recentEventsTitle"><div class="section-title"><h2 id="recentEventsTitle">Recent important events</h2><button type="button" class="link-btn" data-open-tab="reports">View all ›</button></div>${productEvents(timeline,{currentSource:coverageCurrent,freshness,routineCoverage})}</section>
  </div>`);
  connectHomeActions();
}
function renderDevices(){
  if(productSource()){
    const devices=view.devices||[];
    const current=view.source_freshness==='CURRENT';
    const online=current?devices.filter(d=>d.status==='ONLINE'&&d.coverage==='COVERED').length:null;
    const offline=current?devices.filter(d=>d.status==='OFFLINE').length:null;
    const quality=view.source_freshness==='STALE'?'STALE · latest authenticated reports':
      !current?'UNKNOWN · source freshness unavailable':view.monitoring==='COVERED'?'Current source · coverage covered':'Current source · coverage UNKNOWN';
    const summary=current
      ?`<div class="device-summary-count"><strong>${devices.length}</strong><span>reported NodeHealth records</span></div><div class="device-summary-state"><strong>${online}</strong><span>online and covered</span></div><div class="device-summary-state ${offline?'warning':''}"><strong>${offline}</strong><span>offline reports</span></div>`
      :`<div class="device-summary-count"><strong>${devices.length}</strong><span>last reported NodeHealth records</span></div><p>${esc(quality)}</p>`;
    const rows=devices.map(d=>{
      const rowState=current?d.status:'UNKNOWN';
      const visibleStatus=current?d.status:view.source_freshness==='STALE'?`STALE · last ${d.status}`:`UNKNOWN · last ${d.status}`;
      const warning=current&&d.status==='OFFLINE';
      return `<article class="device-row" data-node-id="${esc(d.physical_node_id)}" data-device-state="${esc(rowState)}" data-attention="${warning?'WARNING':'NONE'}"><span class="device-status-mark" aria-hidden="true">${warning?'!':'●'}</span><div class="device-row-copy"><h2>${esc(d.logical_node_id||'Node')}</h2><p class="device-identity">Node ID ${esc(d.physical_node_id||'UNKNOWN')} · profile ${esc(d.profile_id||'UNKNOWN')}</p><p class="device-state">NodeHealth: <strong>${esc(visibleStatus)}</strong> · coverage ${esc(d.coverage||'UNKNOWN')}</p><span class="device-source-quality">${esc(quality)}</span></div></article>`;
    }).join('')||'<p class="muted">No NodeHealth records are available from this authorized Home.</p>';
    panel(`${dataLabel()}<section class="screen-heading"><h1>Devices</h1><p>Authorized NodeHealth and monitoring coverage</p></section><section class="device-summary" aria-label="NodeHealth summary">${summary}</section><div class="device-list" aria-label="Reported Nodes">${rows}</div><p class="device-note">Offline or unknown NodeHealth means monitoring coverage is unavailable; it does not establish resident inactivity or an emergency.</p>`);return;
  }
  if(explicitSimulationHome()){
    panel(`${dataLabel()}${card('Devices and NodeHealth',`<p>Physical Home: <strong>${esc(view?.physical_status||'UNKNOWN')} / ${esc(view?.physical_status_reason||'REASON_UNKNOWN')}</strong>.</p><p>Real Hub event source: ${esc(view?.physical_data_contract||'UNKNOWN')}.</p><p>Physical device and NodeHealth measurements: <strong>UNKNOWN</strong>.</p>${tableRows(view?.devices||[],device=>`<details><summary>${esc(device.id)} · ${esc(device.health||'UNKNOWN')} · SIMULATED</summary><pre>${esc(JSON.stringify(device,null,2))}</pre></details>`)}`)}`);return;
  }
  panel(`${dataLabel()}${card('Devices unavailable',`<p>The authorized service did not provide a recognized NodeHealth projection. Device status, battery and coverage are UNKNOWN.</p>`)}`);
}
function renderIncidents(){
  if(productSource()){
    const current=view.source_freshness==='CURRENT'&&view.monitoring==='COVERED';
    const incidents=view.incidents||[];
    const rows=incidents.map(i=>{
      const severity=incidentVisualSeverity(i,current);
      const stateLabel=i.state==='ACKNOWLEDGED'?'Acknowledged':i.state==='RESOLVED'?'Resolved':
        view.source_freshness==='STALE'?`STALE · last state ${i.state}`:current?i.state:`UNKNOWN · last state ${i.state}`;
      return `<article class="incident-row" data-incident-id="${esc(i.incident_id)}" data-incident-state="${esc(i.state)}" data-visual-severity="${esc(severity||'NONE')}"><div class="incident-row-heading"><h2>${esc(productEventLabel(i.kind))}</h2><span class="incident-state">${esc(stateLabel)}</span></div><p class="incident-severity ${severity==='URGENT'?'urgent':severity==='CONCERN'?'concern':''}">Severity ${esc(i.severity||'UNKNOWN')}</p><p>Service state only · notification delivery or actual phone contact is not established.</p>${i.state==='RESOLVED'?'':['claim','acknowledge','resolve'].map(action=>`<button data-incident-action="${action}" data-id="${esc(i.incident_id)}">${esc(action)}</button>`).join('')}</article>`;
    }).join('')||'<p class="muted">No incident records are currently returned by the authorized service.</p>';
    panel(`${dataLabel()}<section class="screen-heading"><h1>Incident history</h1><p>Severity and lifecycle are shown as returned by the authorized service.</p></section><div class="incident-list">${rows}</div>`);
    document.querySelectorAll('[data-incident-action]').forEach(button=>button.onclick=async()=>{try{await api(`homes/${profile.home_id}/incidents/${button.dataset.id}/${button.dataset.incidentAction}`,{method:'POST',body:{}});await refresh()}catch(error){status('ACTION FAILED',error.message)}});return;
  }
  if(explicitSimulationHome()){
    panel(`${dataLabel()}${card('Incident history',tableRows(view?.incidents||[],r=>`<details><summary>${esc(r.kind||'Incident')} · ${esc(r.state||'UNKNOWN')} · SIMULATED</summary><pre>${esc(JSON.stringify(r,null,2))}</pre></details>`))}<p class="muted">No real household incident can be acknowledged from this TEST_ONLY service.</p>`);return;
  }
  panel(`${dataLabel()}${card('Incident history unavailable','<p>The authorized service did not provide a recognized incident projection. No incident action is available.</p>')}`);
}
function renderReports(){
  const links='<div class="secondary-view-links" aria-label="Reports and history"><button type="button" data-open-tab="incidents">Incidents</button><button type="button" data-open-tab="routines">Routine activity</button></div>';
  if(productSource()){
    const count=Number.isFinite(Number(view.event_count))?String(view.event_count):'UNKNOWN';
    panel(`${dataLabel()}<section class="screen-heading"><h1>Reports</h1><p>Durable event history from the authorized caregiver service</p></section><section class="report-summary"><span class="report-summary-icon" aria-hidden="true">▤</span><div><h2>Recorded events</h2><p><strong>${esc(count)}</strong> durable event records</p><small>Source-backed times and provenance</small></div></section><div class="report-section-title"><h2>Important report items</h2><span>Latest recorded events</span></div><section class="report-history">${productEvents(view.recent_events,{historical:true})}</section>${links}`);connectHomeActions();return;
  }
  if(explicitSimulationHome()){
    panel(`${dataLabel()}${card('Simulation reports',`<label>Period<select id="reportPeriod"><option value="day">Day</option><option value="week">Week</option><option value="month">Month</option></select></label><p>${esc(view?.run_count??0)} saved scenario runs · ${esc(view?.period||'week')}.</p><p>Saved synthetic events: ${esc(view?.event_count??0)} · incident snapshots: ${esc(view?.incident_count??0)}</p><p>PASS ${esc(view?.outcomes?.PASS||0)} · FAIL ${esc(view?.outcomes?.FAIL||0)} · BLOCKED ${esc(view?.outcomes?.BLOCKED||0)}</p>${tableRows(view?.runs||[],r=>`<p>${esc(r.scenario_id)} · ${esc(r.status)} · ${esc(new Date(r.created_at*1000).toLocaleString())}</p>`)}<p class="muted">Real Hub event reports are unavailable until authenticated Hub ingest is deployed.</p>`)}${links}`);
    connectHomeActions();
    $('#reportPeriod').value=view?.period||'week';
    $('#reportPeriod').onchange=async event=>{view=await api(`homes/${profile.home_id}/reports?period=${event.target.value}`);renderReports()};return;
  }
  panel(`${dataLabel()}${card('Reports unavailable','<p>The authorized service did not provide a recognized report projection. Historical metrics are UNKNOWN.</p>')}`);
}
function renderRoutines(){
  if(productSource()){
    panel(`${dataLabel()}${card('Hub routine decisions',`<p>Observation coverage: <strong>${esc(view?.observation_coverage||'UNKNOWN')}</strong>.</p>${tableRows(view?.decisions||[],d=>`<article class="caregiver-run" data-hub-decision="${esc(d.decision_id)}"><b>${esc(d.kind)} · ${esc(d.details?.tone||'UNKNOWN')}</b><span>${esc(new Date(d.occurred_at*1000).toISOString())}</span><small>Decision ID: ${esc(d.decision_id)} · ${esc(d.details?.reason||'')}</small></article>`)}`)}${card('Personalized routines',`<p>Learning status: <strong>${esc(view?.learning_status||'UNKNOWN')}</strong>.</p><p>Only committed deterministic Hub decisions are shown. Personalized learning is not enabled.</p>`)}`);
    return;
  }
  if(!explicitSimulationHome()){
    panel(`${dataLabel()}${card('Routine activity unavailable','<p>The authorized service did not provide a recognized routine projection. Routine status is UNKNOWN.</p>')}`);return;
  }
  panel(`${dataLabel()}${card('Routine insights',`<p>Longitudinal learning: <strong>${esc(view?.learning_status||'UNKNOWN')}</strong>.</p><p>Routine scenarios run the existing deterministic activity rules. The current lab does not form a multi-day resident baseline.</p>${tableRows(view?.decisions||[],d=>`<details><summary>${esc(d.scenario_title)} · ${esc(d.result)} · ${esc(d.category)}</summary><p>Evaluated: ${esc(new Date(d.evaluated_at*1000).toLocaleString())} · Trace: ${esc(d.trace_id)}</p><p>Engine reason: <strong>${esc(d.decision_reason)}</strong></p><p>Events: ${esc(d.event_ids.join(', ')||'none emitted')} · Incidents: ${esc(d.incident_count)}</p><p>Learning status: ${esc(d.learning_status)}</p>${tableRows(d.step_results,s=>`<p>Step ${esc(s.index)} · ${s.passed?'PASS':'FAIL'} · ${esc(s.detail)}</p>`)}${tableRows(d.checks,c=>`<p>${c.pass?'PASS':'FAIL'} · ${esc(c.detail)}</p>`)}<button class="open-run" data-run="${esc(d.run_id)}">Open full run trace</button></details>`)}<h3>Saved routine scenarios</h3>${tableRows(view?.runs||[],r=>`<p><button class="open-run" data-run="${esc(r.run_id)}">Inspect ${esc(r.scenario_id)}</button> · ${esc(r.status)} · ${esc(r.category)}</p>`)}<p class="muted">Coverage gaps remain UNKNOWN where the scenario has no evidence. Synthetic output is not a trained resident-specific model.</p>`)}${selectedRun?runDetail(selectedRun):''}`);
  bindRunButtons();
}
function renderSettings(){
  const hubState=productSource()?`${view.monitoring} / ${view.source_freshness}`:'UNKNOWN / NO_HUB_CLOUDSYNC';
  const hubSetup=runtime.hubWifiNativeDiscovery
    ?'<button id="addHubWifi" type="button">Add Hub / configure Hub Wi-Fi</button><p class="muted">Nearby BLE discovery is available in Android. Secure pairing, protected credential storage and Home claim must be ready before a password can be sent.</p>'
    :'<p class="muted">Hub Wi-Fi setup requires the Parivar Saathi Android app. Secure pairing and protected credential storage are still required.</p>';
  const adminTools=profile?.role==='ADMIN'&&profile?.test_only===true
    ?card('Engineering and simulation · TEST_ONLY','<p>These tools are available only to the authorized TEST_ONLY administrator. They do not populate caregiver monitoring results.</p><div class="secondary-view-links"><button id="openSimulation" type="button">Simulation Lab</button><button id="openEngineering" type="button">Engineering</button></div>')
    :'';
  const routineConfig=profile?.test_only===true
    ?'<section class="settings-section" aria-labelledby="routinePolicyHeading"><h2 id="routinePolicyHeading">Household routine policy · TEST_ONLY</h2><div id="householdRoutineConfiguration" role="status" aria-live="polite"><p>Checking the authenticated development backend…</p></div><p class="muted">Only current server-confirmed desired and Hub-applied policy is shown.</p></section>'
    :'';
  const localReconnect=runtime.localBackendReconnect?'<div class="settings-actions"><a class="local-backend-reconnect" href="gharsajag://backend/reconnect">Change local server</a><a class="local-backend-reset" href="gharsajag://backend/reset">Use paired laptop</a></div>':'';
  panel(`${dataLabel()}<section class="screen-heading settings-heading"><h1>Settings</h1><p>Account, Home and supported connection options</p></section><div class="settings-grid"><section class="settings-section"><h2>Account &amp; session</h2><div class="settings-row"><span class="settings-icon" aria-hidden="true">●</span><div><strong>Signed-in account</strong><p>${esc(profile.email)} · ${esc(profile.role)}</p></div></div><div class="settings-row"><span class="settings-icon" aria-hidden="true">⌂</span><div><strong>Authorized Home</strong><p>${esc(profile.home_id)}</p></div></div><div class="settings-row"><span class="settings-icon" aria-hidden="true">◷</span><div><strong>Session expires</strong><p>${esc(new Date(profile.expires_at*1000).toLocaleString())}</p></div></div><div class="settings-actions"><button id="logoutButton">Log out</button></div></section>${routineConfig}<section class="settings-section"><h2>Hub setup</h2><div class="settings-row"><span class="settings-icon network" aria-hidden="true">⌁</span><div><strong>Hub Wi-Fi</strong>${hubSetup}</div></div></section><section class="settings-section"><h2>App &amp; connection</h2><div class="settings-row"><span class="settings-icon network" aria-hidden="true">◉</span><div><strong>Backend API · ${esc(connection)}</strong><p>${esc(runtime.backendOrigin||'UNCONFIGURED')}</p>${localReconnect}</div></div><div class="settings-row"><span class="settings-icon" aria-hidden="true">?</span><div><strong>Hub monitoring · ${esc(hubState)}</strong><p>Current source and coverage are shown on Home.</p></div></div><div class="settings-row"><span class="settings-icon" aria-hidden="true">i</span><div><strong>App version</strong><p>${esc(runtime.appVersion)} · source ${esc(runtime.sourceRevision)}</p><p>Backend revision: ${esc(profile.backend_revision||'unknown')}</p></div></div></section>${adminTools}</div>`);
  if(profile?.test_only===true)void refreshHouseholdRoutineConfiguration(profile.home_id);
  if(runtime.hubWifiNativeDiscovery)$('#addHubWifi').onclick=()=>{window.location.href='gharsajag://hub-wifi/add'};
  document.querySelector('.local-backend-reconnect')?.addEventListener('click',event=>{event.preventDefault();window.location.href='gharsajag://backend/reconnect'});
  document.querySelector('.local-backend-reset')?.addEventListener('click',event=>{event.preventDefault();window.location.href='gharsajag://backend/reset'});
  $('#openSimulation')?.addEventListener('click',()=>openTab('simulation'));
  $('#openEngineering')?.addEventListener('click',()=>openTab('engineering'));
  $('#logoutButton').onclick=async()=>{try{await api('auth/logout',{method:'POST'})}finally{status('SIGNED OUT','Current session has been revoked.');loginScreen()}};
}
async function refreshHouseholdRoutineConfiguration(homeId){
  const target=$('#householdRoutineConfiguration');
  if(!target)return;
  try{
    const snapshot=await api(`homes/${encodeURIComponent(homeId)}/routine-config`);
    if(snapshot.home_id!==homeId||!Number.isSafeInteger(snapshot.desired_version)||
       !(snapshot.applied_version===null||Number.isSafeInteger(snapshot.applied_version)))
      throw new Error('invalid_configuration_status');
    const desired=snapshot.desired_version;
    const applied=snapshot.applied_version;
    let label='Pending on Hub';
    if(desired===0)label='No household policy saved';
    else if(applied===desired)label='Applied on Hub';
    else if(applied!==null&&applied>desired)label='Configuration conflict';
    const state=document.createElement('p');state.className='household-config-state';
    state.textContent=`${label} · desired v${desired} · applied ${applied===null?'none':`v${applied}`}`;
    const note=document.createElement('p');note.textContent=snapshot.desired_status==='DESIRED'
      ?'The latest saved policy is waiting for Hub confirmation.'
      :snapshot.desired_status==='APPLIED'
        ?'The Hub confirmed the latest saved policy.'
        :'No policy details were returned.';
    const policy=snapshot.desired_config||snapshot.applied_config;
    const steps=policy?.activity_rules?.morning_steps;
    const policyForm=document.createElement('form');policyForm.className='routine-policy-editor';
    if(Array.isArray(steps)&&steps.length){
      for(const [index,step] of steps.entries()){
        if(!step||typeof step.location!=='string')continue;
        const row=document.createElement('div');row.className='settings-row';
        const enabled=document.createElement('input');enabled.type='checkbox';enabled.checked=step.enabled===true;
        enabled.setAttribute('aria-label',`${step.location} enabled`);
        const required=document.createElement('select');required.setAttribute('aria-label',`${step.location} requirement`);
        for(const [value,label] of [['true','Required'],['false','Optional']]){
          const option=document.createElement('option');option.value=value;option.textContent=label;
          required.append(option);
        }
        required.value=step.required===true?'true':'false';
        const name=document.createElement('strong');name.textContent=step.location;
        const controls=document.createElement('div');controls.append(enabled,document.createTextNode(' Enabled · '),required);
        row.append(name,controls);policyForm.append(row);
        row.dataset.stepIndex=String(index);
      }
      const save=document.createElement('button');save.type='submit';save.textContent='Save desired routine policy';
      policyForm.append(save);
      policyForm.addEventListener('submit',async event=>{
        event.preventDefault();save.disabled=true;
        try{
          const next=JSON.parse(JSON.stringify(policy));
          for(const row of policyForm.querySelectorAll('[data-step-index]')){
            const index=Number(row.dataset.stepIndex);const step=next.activity_rules.morning_steps[index];
            step.enabled=Boolean(row.querySelector('input').checked);
            step.required=row.querySelector('select').value==='true';
          }
          await api(`homes/${encodeURIComponent(homeId)}/routine-config`,{
            method:'POST',body:{expected_version:desired,config:next}});
          await refreshHouseholdRoutineConfiguration(homeId);
        }catch(error){
          const failure=document.createElement('p');failure.setAttribute('role','alert');
          failure.textContent=`Policy save failed: ${error.message}`;policyForm.prepend(failure);
        }finally{save.disabled=false;}
      });
    }else{
      const missing=document.createElement('p');
      missing.textContent='No desired or applied routine policy is available to edit.';
      policyForm.append(missing);
    }
    target.replaceChildren(state,note,policyForm);
  }catch(error){
    target.textContent=`Configuration status unavailable from the authenticated backend (${error.message}). No local or simulated policy is shown.`;
  }
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
async function refresh({verifiedProfile=null}={}){
  if(!profile)return;
  if(refreshPromise){refreshRequested=true;return refreshPromise;}
  refreshPromise=(async()=>{
    const requestedTab=tab;
    try{
      const currentProfile=verifiedProfile||await api('me');
      if(!validServerProfile(currentProfile))throw new Error('not_authorized');
      if(!profile)return;
      profile=currentProfile;
      if(requestedTab!==tab){refreshRequested=true;return;}
      const home=profile.home_id;
      const base=`homes/${encodeURIComponent(home)}`;
      const area={devices:'devices',incidents:'incidents',reports:'reports',routines:'routines',settings:'overview',engineering:'engineering'}[requestedTab];
      let nextView=null;
      if(requestedTab==='home'){
        const [overview,devices,routines,incidents]=await Promise.all([
          api(`${base}/overview`),api(`${base}/devices`),api(`${base}/routines`),api(`${base}/incidents`),
        ]);
        if([overview,devices,routines,incidents].some(result=>result.home_id!==home||
            Boolean(result.test_only)!==Boolean(profile.test_only)))
          throw new Error('authorized_home_projection_mismatch');
        nextView={...overview,devices:devices.devices||[],decisions:routines.decisions||[],
          incidents:incidents.incidents||[],routine_coverage:routines.observation_coverage||'UNKNOWN'};
      }else if(requestedTab==='devices'||requestedTab==='incidents'){
        const [overview,projection]=await Promise.all([
          api(`${base}/overview`),api(`${base}/${requestedTab}`),
        ]);
        if([overview,projection].some(result=>result.home_id!==home||
            Boolean(result.test_only)!==Boolean(profile.test_only)))
          throw new Error('authorized_home_projection_mismatch');
        nextView={...projection,source_freshness:overview.source_freshness||'UNKNOWN',
          monitoring:overview.monitoring||'UNKNOWN',last_hub_at:overview.last_hub_at||null};
      }else if(area)nextView=await api(`${base}/${area}`);
      if(requestedTab==='simulation'){
        if(profile.role!=='ADMIN'||profile.test_only!==true)throw new Error('not_authorized');
        catalog=catalog||await api(`homes/${home}/sim/catalog`);
        runs=(await api(`homes/${home}/sim/runs`)).runs;
      }
      if(requestedTab!==tab){refreshRequested=true;return;}
      if(nextView&&('home_id' in nextView)&&
          (nextView.home_id!==home||Boolean(nextView.test_only)!==Boolean(profile.test_only)))
        throw new Error('authorized_home_projection_mismatch');
      view=nextView;
      connection='CONNECTED';lastSync=Date.now();
      status('CONNECTED',productSource()
        ?`Caregiver API connected · monitoring ${view.monitoring||'UNKNOWN'} · source ${view.source_freshness||'UNKNOWN'}.`
        :`TEST_ONLY workspace · last synced ${new Date(lastSync).toLocaleTimeString()}. Physical monitoring remains UNKNOWN.`);
      renderCurrent();
    }catch(error){
      if(error.name==='AbortError')return;
      if(error.message==='not_authorized'){
        loginScreen('Session expired or access revoked. Please log in again.');
        return;
      }
      connection='OFFLINE';view=null;
      status('OFFLINE / RECONNECTING',`Current authorized Home data is unavailable: ${error.message}. Monitoring is UNKNOWN.`);
      if(profile&&requestedTab===tab)renderCurrent();
    }
  })();
  try{await refreshPromise}
  finally{
    refreshPromise=null;
    if(refreshRequested&&profile){refreshRequested=false;void refresh();}
  }
}

async function restoreSession(){
  if(restorePromise)return restorePromise;
  if(!runtime.caregiverApiConfigured)return null;
  const generation=authGeneration;
  const controller=new AbortController();
  restoreController=controller;
  restorePromise=(async()=>{
    try{
      const session=await api('me',{signal:controller.signal});
      if(controller.signal.aborted||generation!==authGeneration||loginFormTouched||loginPending)return null;
      if(!validServerProfile(session))throw new Error('invalid_server_session');
      profile=session;view=null;tab='home';
      renderCurrent();
      await refresh({verifiedProfile:session});
      return session;
    }catch(error){
      if(error.name!=='AbortError'&&generation===authGeneration&&!loginFormTouched&&!loginPending){
        profile=null;view=null;
        status('SIGN IN REQUIRED','No current authorized session was restored. Sign in to access Home data.');
      }
      return null;
    }finally{
      if(restoreController===controller)restoreController=null;
    }
  })();
  return restorePromise;
}

$('#awayToggle').disabled=true;
loginScreen();
if(!runtime.caregiverApiConfigured){
  status('OFFLINE / UNCONFIGURED','This APK has no approved HTTPS backend.');
}else{
  status('CHECKING SESSION','Home data remains hidden until the server verifies this session and its Home access.');
  void restoreSession();
}
// Home and caregiver API refreshes are single-flight; the simulation remains user-triggered.
setInterval(()=>{if(profile&&!document.hidden&&!busy&&tab!=='simulation')void refresh()},15000);
document.addEventListener('visibilitychange',()=>{if(profile&&!document.hidden)void refresh()});
