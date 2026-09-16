export const POLL_INTERVALS = Object.freeze({
  stateMs: 2000,
  reportsMs: 4000,
  notificationsMs: 15000,
});

export function requestDue({inFlight=false, lastStartedAt=0, now=Date.now(), intervalMs=0}={}) {
  return !inFlight && now-lastStartedAt>=intervalMs;
}

export function addBounded(set, value, limit) {
  set.add(value);
  while(set.size>limit)set.delete(set.values().next().value);
  return set;
}

export function renderSignature(value) {
  return JSON.stringify(value);
}

export function shouldApplyStateUpdate(currentSimulationNow, nextSimulationNow, {
  currentEpoch=null, nextEpoch=null, force=false,
}={}) {
  if(force)return true;
  const currentStateEpoch=Number(currentEpoch);
  const nextStateEpoch=Number(nextEpoch);
  if(Number.isFinite(currentStateEpoch) && Number.isFinite(nextStateEpoch) && currentStateEpoch!==nextStateEpoch){
    return nextStateEpoch>currentStateEpoch;
  }
  const current=Number(currentSimulationNow);
  const next=Number(nextSimulationNow);
  if(!Number.isFinite(current) || !Number.isFinite(next))return true;
  return next>=current;
}
