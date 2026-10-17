/** GS-157 caregiver answer endpoint. No mock actor, no synthetic user sessions. */
const id = new URLSearchParams(location.search).get('call_id');
const stateEl = document.querySelector('#callState');
const errorEl = document.querySelector('#callError');
const answerBtn = document.querySelector('#answerBtn');
const endBtn = document.querySelector('#endBtn');
const remote = document.querySelector('#remote');
const validId = /^c_[0-9a-f]{32}$/.test(id || '');
let pc, stream, pollTimer, cursor = 0, answered = false, terminated = false, seenOffer = false;

const setState = text => { stateEl.textContent = text; };
async function api(path = '', body) {
  const response = await fetch(`/v1/voice/calls/${id}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    credentials: 'same-origin', cache: 'no-store',
    headers: body === undefined ? {} : {'Content-Type':'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw Error(data.error || `HTTP ${response.status}`);
  return data;
}
function cleanup() {
  if (pollTimer) clearInterval(pollTimer);
  if (stream) for (const track of stream.getTracks()) track.stop();
  if (pc) pc.close();
  terminated = true;
  answerBtn.disabled = true;
  endBtn.disabled = true;
}
function fail(error) { errorEl.textContent = `Call unavailable: ${error.message}`; setState('Call could not connect'); cleanup(); }

async function connect() {
  if (answered || !validId || terminated) return;
  answerBtn.disabled = true;
  try {
    const initial = await api();
    if (!['REQUESTED','RINGING'].includes(initial.state)) throw Error('Call no longer available');
    // Explicit user button gesture; no unsolicited microphone activation.
    stream = await navigator.mediaDevices.getUserMedia({audio:true,video:false});
    const iceResponse = await fetch('/v1/voice/ice-config', {cache:'no-store',credentials:'same-origin'});
    if (!iceResponse.ok) throw Error('Secure ICE/TURN service unavailable');
    const iceConfig = await iceResponse.json();
    if (!Array.isArray(iceConfig.iceServers) || iceConfig.iceServers.length === 0) throw Error('ICE/TURN is not configured');
    pc = new RTCPeerConnection({iceServers: iceConfig.iceServers});
    for (const track of stream.getTracks()) pc.addTrack(track,stream);
    pc.ontrack = event => {remote.srcObject = event.streams[0] ?? new MediaStream([event.track]);};
    pc.onicecandidate = event => { if (event.candidate) api('/ice',{candidate:event.candidate.toJSON()}).catch(e=>{errorEl.textContent=e.message;}); };
    pc.onconnectionstatechange = async () => {
      if (pc.connectionState === 'connected') {
        setState('Media connected');
        await api('/media_ready', {});
        // Peer connection does not establish a separate human acknowledgment.
      } else if (pc.connectionState === 'failed') fail(Error('Media connection failed'));
    };
    await api('/accept',{});
    answered = true;
    endBtn.disabled = false;
    setState('Answering — waiting for Hub…');
  } catch (e) { fail(e); }
}
async function update() {
  if (terminated) return;
  try {
    const status = await api();
    if (['ENDED','DECLINED','EXPIRED','FAILED'].includes(status.state)) { setState(`Call ${status.state.toLowerCase()}`);cleanup();return; }
    if (['REQUESTED','RINGING'].includes(status.state)) answerBtn.disabled = false;
    if (answered && !seenOffer && status.offer) {
      seenOffer = true;
      await pc.setRemoteDescription({type:'offer',sdp:status.offer});
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      await api('/answer',{sdp: answer.sdp});
      setState('Connecting audio…');
    }
    if (answered && pc && pc.remoteDescription) {
      const items = await api(`/candidates?after=${cursor}`);
      for (const item of items.candidates || []) {
        await pc.addIceCandidate(item.candidate);
        cursor = item.id;
      }
    }
  } catch(e) { errorEl.textContent = `Connection status: ${e.message}`; }
}
answerBtn.addEventListener('click',connect);
endBtn.addEventListener('click',async()=>{
  try {await api('/end',{reason:'hangup'});} catch(_) { /* local cleanup still required */ }
  setState('Call ended');cleanup();
});
if (!validId) fail(Error('Invalid call reference'));
else { pollTimer=setInterval(update,1500);update(); }
window.addEventListener('pagehide',cleanup);
