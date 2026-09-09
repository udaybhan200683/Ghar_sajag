// @module T01/A02/A04 host adapter | @requirements F05,F06,F07,F12,F13,E04,NFR-08
// Reuses the shipped view/action functions; decisions and incident transitions remain on the server.
import {buildHomeView,timelineLabel} from "/src/features/home/index.mjs";
import {incidentActions,actionCommand,deliveryLabel} from "/src/features/incidents/index.mjs";
import {logError,exportLogText} from "/src/platform/logging.mjs";
const $=id=>document.getElementById(id);
let state;
let busy=false;
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
function button(label,handler){const b=node("button",label);b.addEventListener("click",handler);return b;}
function render(){
  const s=state.simulation;const view=buildHomeView(state.home,s.now);
  $("clock").textContent=`Simulated time t=${s.now}. Time moves only when you advance it.`;
  $("wan").textContent=s.wan?"Disconnect internet":"Reconnect internet";
  $("trusted").textContent=s.clock_trusted?"Distrust clock":"Trust clock";
  $("nodes").replaceChildren(...s.nodes.map(n=>{const row=node("div","","row");row.append(node("span",`${n.id} · link ${n.online?"available":"unavailable"} · retained ${n.retained}`),button(n.online?"Disconnect":"Reconnect",()=>act({action:"node",node:n.id,enabled:!n.online})));return row;}));
  const fields={"Coverage":s.coverage,"Home mode":s.mode,"Activity seen":String(s.activity_seen),"Resident OK":String(s.explicit_ok),"Decision reason":s.reason,"Last node ACK":s.last_ack,"Journal records":s.journal_records,"Pending cloud":s.pending_cloud,"Reducer evidence IDs":s.evidence_count,"Missing intent pending":String(s.missing_pending)};
  $("hub").replaceChildren(...Object.entries(fields).flatMap(([k,v])=>[node("dt",k),node("dd",String(v))]));
  for(const id of ["connectivity","activity"]){const v=view[id];$(id).className=v.tone||"";$(id).replaceChildren(node("h3",v.title),node("p",v.detail));}
  $("incidents").replaceChildren(...state.incidents.map(i=>{const div=node("div","","incident");div.dataset.incidentId=i.incident_id;div.append(node("h3",i.kind.replaceAll("_"," ")),node("p",`${i.state} · owner: ${i.owner_id||"unclaimed"}`));
    for(const a of incidentActions(i,$("actor").value,s.now)){if(a.id==="view")continue;div.append(button(a.label,()=>perform(async()=>{const c=actionCommand(state.home.home_id,i.incident_id,a.id,crypto.randomUUID());await request(c.path,c.body,$("actor").value);})));}return div;}));
  if(!state.incidents.length)$("incidents").append(node("p","No incidents created in this scenario."));
  $("notifications").replaceChildren(...state.notifications.map(j=>node("p",`${j.recipient_id} · stage ${j.stage} · due t=${j.due_at} · ${deliveryLabel(j)}`)));
  $("timeline").replaceChildren(...state.timeline.map(e=>node("li",`t=${e.occurred_at}: ${timelineLabel(e)} · ${e.event_id}`)));
  $("limits").replaceChildren(...state.limitations.map(l=>node("li",l)));
}
async function refresh(){state=await request("/sim/state");render();}
$("reset").onclick=()=>act({action:"reset"});
$("advance60").onclick=()=>act({action:"advance",seconds:60});
$("deadline").onclick=()=>act({action:"advance",seconds:Math.max(0,2300-state.simulation.now)});
$("send").onclick=()=>act({action:"event",node:$("node").value,kind:$("kind").value});
$("wan").onclick=()=>act({action:"wan",enabled:!state.simulation.wan});
$("trusted").onclick=()=>act({action:"clock",enabled:!state.simulation.clock_trusted});
$("duplicate").onclick=()=>act({action:"duplicate"});
$("evaluate").onclick=()=>act({action:"deadline"});
$("notify").onclick=()=>act({action:"notify",accepted:true});
$("notify-fail").onclick=()=>act({action:"notify",accepted:false});
$("actor").onchange=()=>{if(state)render();};
$("suite").onclick=()=>perform(async()=>{const report=await request("/sim/run-suite",{});$("test-status").textContent=`${report.status}: ${report.cases.filter(c=>c.passed).length}/${report.cases.length} scenario checks. ${report.scope}`;$("results").replaceChildren(...report.cases.map(c=>node("li",`${c.passed?"PASS":"FAIL"} · ${c.name} — ${c.expected}`,c.passed?"pass":"fail")));});
$("export-log").onclick=()=>{const url=URL.createObjectURL(new Blob([exportLogText()],{type:"text/plain"}));const a=document.createElement("a");a.href=url;a.download="browser_log.txt";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
await perform(async()=>{});
