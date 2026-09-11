
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const initialState={
  away:false, homeAlert:false, morning:true, ok:true, doorOpen:false, indoorAgo:14, nightVisits:2,
  devices:[
    {id:'hub',name:'Hub',type:'Living Room Hub',active:true,battery:82,left:'~18 hrs',updated:'10 min ago'},
    {id:'bed',name:'Bedroom Node',type:'Motion Sensor',active:true,battery:42,left:'~5 days',updated:'24 min ago'},
    {id:'draw',name:'Drawing Room Node',type:'Motion Sensor',active:true,battery:68,left:'~9 days',updated:'16 min ago'},
    {id:'door',name:'Main Door Node',type:'Door Sensor',active:true,battery:55,left:'~12 days',updated:'14 min ago'},
    {id:'bath',name:'Bathroom Node',type:'Motion Sensor',active:true,battery:72,left:'~14 days',updated:'18 min ago'},
    {id:'pooja',name:'Pooja Room Node',type:'Motion Sensor',active:true,battery:81,left:'~20 days',updated:'31 min ago'}
  ],
  events:[
    {time:'10:32 AM',icon:'❤',text:"I'm OK received",tone:'green'},
    {time:'10:05 AM',icon:'🏃',text:'Motion in Drawing Room',tone:'blue'},
    {time:'9:20 AM',icon:'🚪',text:'Main door closed',tone:'green'},
    {time:'9:18 AM',icon:'🚪',text:'Main door opened',tone:'red'},
    {time:'7:42 AM',icon:'☀',text:'Morning routine completed',tone:'green'}
  ]
};
const STORAGE_KEY='ps_state_v5';
let state=JSON.parse(localStorage.getItem(STORAGE_KEY)||'null')||structuredClone(initialState);
state.away=false;
normalizeEventTimes();
state.away=false; // Away mode disabled in this verification build.
let currentTab='home', reportPeriod='week';
function save(){localStorage.setItem(STORAGE_KEY,JSON.stringify(state))}
function nowTick(){let d=new Date(); $('#dateText').textContent=d.toLocaleDateString(undefined,{weekday:'short',day:'numeric',month:'short',year:'numeric'}); $('#timeText').textContent=d.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'});}
setInterval(nowTick,1000); nowTick();

function fmtTime(ts){
  return new Date(ts).toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'});
}
function addEvent(text,tone='green',icon='•'){
  state.events.unshift({
    ts:new Date().toISOString(),
    time:fmtTime(new Date()),
    icon,
    text,
    tone
  });
  // Keep a reasonable pilot history.
  state.events=state.events.slice(0,40);
}
function normalizeEventTimes(){
  const now=Date.now();
  state.events=state.events.map((e,i)=>{
    if(!e.ts){
      // Preserve display order while giving old seeded events sortable timestamps.
      e.ts=new Date(now-(i+1)*15*60*1000).toISOString();
    }
    e.time=fmtTime(e.ts);
    return e;
  });
  state.events.sort((a,b)=>new Date(b.ts)-new Date(a.ts));
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
  const s=homeSeverity(), bath=state.devices.find(d=>d.id==='bath'), active=state.devices.filter(d=>d.active).length;
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
        <div class="card ${bath.battery<=10?'alert':''}"><div class="card-row"><div class="round-icon">🔋</div><div><h2>Device health</h2><div class="${bath.battery<=10?'status-bad':''}">${bath.battery<=10?'Low battery:':'Lowest battery:'} ${bath.name.replace(' Node','')} ${bath.battery}%</div><div class="${bath.battery<=10?'status-bad':'muted'}">Recharge in ${bath.left}</div></div></div></div>
      </div>
      <div class="timeline"><div class="section-title"><h2>Recent important events</h2><button class="link-btn" onclick="toast('All events view will use backend history in the pilot.')">View all ›</button></div>
        ${[...state.events].sort((a,b)=>new Date(b.ts||0)-new Date(a.ts||0)).map(e=>`<div class="event"><div class="event-time">${e.ts?fmtTime(e.ts):e.time}</div><div>${e.icon}</div><div class="event-pill ${e.tone==='red'?'red':e.tone==='blue'?'blue':''}">${e.text}</div></div>`).join('')}
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
window.toggleDemo=k=>{
  if(k==='morning'){
    state.morning=!state.morning;
    if(state.morning){
      addEvent('Morning routine restored','green','☀');
      toast('Morning routine: PASS');
    }else{
      addEvent('Morning routine not completed','red','☀');
      toast('Morning routine: NEGATIVE');
    }
  }

  if(k==='ok'){
    state.ok=!state.ok;
    if(state.ok){
      addEvent("I'm OK received",'green','❤');
      toast('I am OK: PASS');
    }else{
      addEvent("I'm OK not confirmed",'red','❤');
      toast('I am OK: NEGATIVE');
    }
  }

  if(k==='door'){
    state.doorOpen=!state.doorOpen;
    if(state.doorOpen){
      addEvent('Main door opened','red','🚪');
      toast('Main door: NEGATIVE');
    }else{
      addEvent('Main door closed','green','🚪');
      state.indoorAgo=0;
      addEvent('Indoor activity seen','blue','🏃');
      toast('Main door: PASS');
    }
  }

  if(k==='night'){
    const negative=state.nightVisits<6;
    state.nightVisits=negative?8:2;
    if(negative){
      addEvent('Unusual night activity: 8 bathroom visits','red','☾');
      toast('Night activity: NEGATIVE');
    }else{
      addEvent('Night activity back to normal','green','☾');
      toast('Night activity: PASS');
    }
  }

  if(k==='battery'){
    const b=state.devices.find(d=>d.id==='bath');
    const negative=b.battery>10;
    if(negative){
      b.battery=5;
      b.left='~2 hrs';
      b.updated='just now';
      b.active=true;
      addEvent('Bathroom sensor battery low: 5%','red','🔋');
      toast('Battery health: NEGATIVE');
    }else{
      b.battery=72;
      b.left='~14 days';
      b.updated='just now';
      b.active=true;
      addEvent('Bathroom sensor battery restored: 72%','green','🔋');
      toast('Battery health: PASS');
    }
  }

  normalizeEventTimes();
  save();
  render();
}
window.resetDemo=()=>{
  state=structuredClone(initialState);
  state.away=false;
  state.events=[];
  addEvent('All scenarios reset to PASS','green','✓');
  localStorage.removeItem(STORAGE_KEY);
  normalizeEventTimes();
  save();
  render();
  toast('Reset complete: all scenarios PASS');
}
window.toast=t=>{let n=document.createElement('div');n.className='toast';n.textContent=t;document.body.appendChild(n);setTimeout(()=>n.remove(),2200)}
window.enableNotifications=async()=>{if(!('Notification'in window))return toast('Browser notifications are not supported here.');let p=await Notification.requestPermission();toast(p==='granted'?'Notifications enabled':'Notification permission not granted')}
function notify(title,body){if('Notification'in window && Notification.permission==='granted')new Notification(title,{body,icon:'assets/icon.svg'})}
if('serviceWorker'in navigator) navigator.serviceWorker.register('sw.js');
render();
