// @module T01/A02/A04 host adapter | @requirements F05,F06,F07,F09,F11,F12,F13,E01,E04,NFR-08
import {buildHomeView,eventPresentation,timelineLabel} from "/src/features/home/index.mjs";
import {incidentActions,actionCommand,deliveryLabel} from "/src/features/incidents/index.mjs";
import {validateActivityRules} from "/src/features/routines/index.mjs";
import {logError,exportLogText} from "/src/platform/logging.mjs";
const $=id=>document.getElementById(id);
let state;
let busy=false;
const NODE_FAULTS=["LOW_BATTERY","BATTERY_DEPLETED","LINK_LOSS","SENSOR_FAULT","OVER_TEMP","WATCHDOG"];
const HUB_FAULTS=["POWER_LOSS","NODE_RADIO_FAILURE","INTERNET_LOSS","OVER_TEMP","WATCHDOG"];
function node(tag,text,cls){const el=document.createElement(tag);el.textContent=text;if(cls)el.className=cls;return el;}
async function request(path,body,actor){
  const response=await fetch(path,{method:body===undefined?"GET":"POST",headers:{"Content-Type":"application/json",...(actor?{"X-Actor-Id":actor}:{})},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const result=await response.json();if(!response.ok)throw Error(result.error||`HTTP ${response.status}`);return result;
}
async function perform(work){
  if(busy)return;busy=true;$("error").hidden=true;
  document.querySelectorAll("button").forEach(b=>b.disabled=true);
  try{await work();await refresh();}catch(e){$("error").textContent=e.message;$("error").hidden=false;logError("SIM","T01","browser.request_failed",e.message);}
  finally{busy=false;document.querySelectorAll("button").forEach(b=>b.disabled=false);}
}
const act=body=>perform(()=>request("/sim/action",body));
function button(label,handler,cls){const b=node("button",label,cls);b.addEventListener("click",handler);return b;}
function statusClass(health){return health==="ACTIVE"?"status-active":health==="DEGRADED"?"status-degraded":"status-offline";}
function refreshFaultOptions(){
  const choices=$("fault-target").value==="hub"?HUB_FAULTS:NODE_FAULTS;
  $("fault-kind").replaceChildren(...choices.map(v=>{const o=node("option",v.replaceAll("_"," "));o.value=v;return o;}));
}

function minuteToTime(value){const h=Math.floor(value/60)%24;const m=value%60;return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`;}
function timeToMinute(value){const m=/^(\d{2}):(\d{2})$/.exec(value||"");if(!m)return NaN;const h=Number(m[1]),min=Number(m[2]);return h*60+min;}
function renderSettings(){
  const s=state.settings;if(!s)return;
  $("quiet-enabled").checked=s.quiet_hours_enabled;
  $("quiet-start").value=minuteToTime(s.quiet_start_minute);
  $("quiet-end").value=minuteToTime(s.quiet_end_minute);
  $("door-timeout").value=String(Math.round(s.door_open_timeout_seconds/60));
  $("inactivity-enabled").checked=s.daytime_inactivity_enabled;
  $("daytime-start").value=minuteToTime(s.daytime_start_minute);
  $("daytime-end").value=minuteToTime(s.daytime_end_minute);
  $("inactivity-minutes").value=String(Math.round(s.daytime_inactivity_seconds/60));
  $("settings-status").textContent=`Configuration v${s.config_version}`;
}
function eventItem(event,now){
  const v=eventPresentation(event,now);const li=node("li","",`event-card ${v.tone||"neutral"}`);
  li.append(node("strong",v.title),node("span",v.detail));return li;
}
function renderDevices(){
  $("device-health").replaceChildren(...state.devices.map(d=>{
    const row=node("div","","device-row");
    const info=node("div","","device-info");
    const heading=node("div","","device-heading");
    const dot=node("span","",`status-radio ${statusClass(d.health)}`);dot.setAttribute("aria-label",d.health);
    heading.append(dot,node("strong",`${d.kind==="HUB"?"Hub":d.id} · ${d.location}`),node("span",d.health,"health-label"));
    info.append(heading,node("div",`${d.code} · ${d.message}`,"small"));
    if(d.diagnostic)info.append(node("div",`Last diagnostic: ${d.diagnostic.code} — ${d.diagnostic.result}`,"diagnostic"));
    const actions=node("div","","device-actions");
    actions.append(button("Troubleshoot",()=>act({action:"troubleshoot",target:d.id})),button("Reboot",()=>act({action:"reboot",target:d.id})));
    row.append(info,actions);return row;
  }));
}
function render(){
  const s=state.simulation;const view=buildHomeView(state.home,s.now);
  $("clock").textContent=`Simulated time t=${s.now}. Time moves only when you advance it.`;
  $("wan").textContent=s.wan?"Disconnect internet":"Reconnect internet";
  $("trusted").textContent=s.clock_trusted?"Distrust clock":"Trust clock";
  $("nodes").replaceChildren(...s.nodes.map(n=>{const row=node("div","","row");row.append(node("span",`${n.id} · link ${n.online?"available":"unavailable"} · retained ${n.retained}`),button(n.online?"Disconnect":"Reconnect",()=>act({action:"node",node:n.id,enabled:!n.online})));return row;}));
  const fields={"Coverage":s.coverage,"Hub runtime":s.hub_online?"ACTIVE":"OFFLINE","Internet":s.wan?"CONNECTED":"OFFLINE","Home mode":s.mode,"Activity seen":String(s.activity_seen),"Resident OK":String(s.explicit_ok),"Decision reason":s.reason,"Last node ACK":s.last_ack,"Journal records":s.journal_records,"Pending cloud":s.pending_cloud,"Reducer evidence IDs":s.evidence_count,"Missing intent pending":String(s.missing_pending)};
  $("hub").replaceChildren(...Object.entries(fields).flatMap(([k,v])=>[node("dt",k),node("dd",String(v))]));
  for(const id of ["connectivity","activity"]){const v=view[id];$(id).className=v.tone||"";$(id).replaceChildren(node("h3",v.title),node("p",v.detail));}
  $("recent-events").replaceChildren(...(state.home.recent_events||[]).map(e=>eventItem(e,s.now)));
  if(!(state.home.recent_events||[]).length)$("recent-events").append(node("li","No household events yet.","neutral"));
  $("incidents").replaceChildren(...state.incidents.map(i=>{const div=node("div","",`incident ${i.kind==="CALL_FAMILY"?"call-incident":"missing-incident"}`);div.dataset.incidentId=i.incident_id;div.append(node("h3",i.kind.replaceAll("_"," ")),node("p",`${i.state} · owner: ${i.owner_id||"unclaimed"}`));
    for(const a of incidentActions(i,$("actor").value,s.now)){if(a.id==="view")continue;div.append(button(a.label,()=>perform(async()=>{const c=actionCommand(state.home.home_id,i.incident_id,a.id,crypto.randomUUID());await request(c.path,c.body,$("actor").value);})));}return div;}));
  if(!state.incidents.length)$("incidents").append(node("p","No open incidents in this scenario."));
  renderDevices();
  renderSettings();
  $("notifications").replaceChildren(...state.notifications.map(j=>node("p",`${j.recipient_id} · stage ${j.stage} · due t=${j.due_at} · ${deliveryLabel(j)}`)));
  $("timeline").replaceChildren(...state.timeline.map(e=>{const li=node("li",`t=${e.occurred_at}: ${timelineLabel(e,s.now)} · ${e.event_id}`,`event-line ${e.tone||"neutral"}`);return li;}));
  $("limits").replaceChildren(...state.limitations.map(l=>node("li",l)));
}
async function refresh(){state=await request("/sim/state");render();}
$("reset").onclick=()=>act({action:"reset"});
$("advance60").onclick=()=>act({action:"advance",seconds:60});
$("advance300").onclick=()=>act({action:"advance",seconds:300});
$("deadline").onclick=()=>act({action:"advance",seconds:Math.max(0,2300-state.simulation.now)});
$("send").onclick=()=>act({action:"event",node:$("node").value,kind:$("kind").value});
$("late-open").onclick=()=>act({action:"event",node:"entry",kind:"DOOR_OPEN",late_night:true});
$("late-close").onclick=()=>act({action:"event",node:"entry",kind:"DOOR_CLOSED",late_night:true});
$("wan").onclick=()=>act({action:"wan",enabled:!state.simulation.wan});
$("trusted").onclick=()=>act({action:"clock",enabled:!state.simulation.clock_trusted});
$("duplicate").onclick=()=>act({action:"duplicate"});
$("evaluate").onclick=()=>act({action:"deadline"});
$("notify").onclick=()=>act({action:"notify",accepted:true});
$("notify-fail").onclick=()=>act({action:"notify",accepted:false});
$("actor").onchange=()=>{if(state)render();};
$("fault-target").onchange=refreshFaultOptions;
$("inject-fault").onclick=()=>act({action:"fault",target:$("fault-target").value,fault:$("fault-kind").value});
$("clear-fault").onclick=()=>act({action:"clear_fault",target:$("fault-target").value});
$("settings-form").onsubmit=(event)=>{
  event.preventDefault();
  const rules={
    quietHoursEnabled:$("quiet-enabled").checked,
    quietStartMinute:timeToMinute($("quiet-start").value),
    quietEndMinute:timeToMinute($("quiet-end").value),
    doorOpenTimeoutSeconds:Number($("door-timeout").value)*60,
    daytimeInactivityEnabled:$("inactivity-enabled").checked,
    daytimeStartMinute:timeToMinute($("daytime-start").value),
    daytimeEndMinute:timeToMinute($("daytime-end").value),
    daytimeInactivitySeconds:Number($("inactivity-minutes").value)*60,
  };
  const validation=validateActivityRules(rules);
  if(!validation.valid){$("settings-status").textContent=Object.values(validation.errors)[0]||"Invalid settings";return;}
  act({action:"settings",settings:{
    quiet_hours_enabled:rules.quietHoursEnabled,quiet_start_minute:rules.quietStartMinute,quiet_end_minute:rules.quietEndMinute,
    door_open_timeout_seconds:rules.doorOpenTimeoutSeconds,daytime_inactivity_enabled:rules.daytimeInactivityEnabled,
    daytime_start_minute:rules.daytimeStartMinute,daytime_end_minute:rules.daytimeEndMinute,
    daytime_inactivity_seconds:rules.daytimeInactivitySeconds,
  }});
};
$("suite").onclick=()=>perform(async()=>{const report=await request("/sim/run-suite",{});$("test-status").textContent=`${report.status}: ${report.cases.filter(c=>c.passed).length}/${report.cases.length} scenario checks. ${report.scope}`;$("results").replaceChildren(...report.cases.map(c=>node("li",`${c.passed?"PASS":"FAIL"} · ${c.id||c.name} — ${c.title||c.expected}${c.failures?.length?` — ${c.failures.join("; ")}`:""}`,c.passed?"pass":"fail")));});
$("export-log").onclick=()=>{const url=URL.createObjectURL(new Blob([exportLogText()],{type:"text/plain"}));const a=document.createElement("a");a.href=url;a.download="browser_log.txt";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
refreshFaultOptions();
await perform(async()=>{});
