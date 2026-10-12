import test from 'node:test';
import assert from 'node:assert/strict';

import {POLL_INTERVALS,addBounded,renderSignature,requestDue,shouldApplyStateUpdate} from '../../tools/sim/pwa/performance_runtime.mjs';

test('poll policy prevents overlap and applies domain-specific throttles', () => {
  assert.equal(requestDue({inFlight:true,lastStartedAt:0,now:20_000,intervalMs:1}),false);
  assert.equal(requestDue({lastStartedAt:10_000,now:13_999,intervalMs:POLL_INTERVALS.reportsMs}),false);
  assert.equal(requestDue({lastStartedAt:10_000,now:14_000,intervalMs:POLL_INTERVALS.reportsMs}),true);
  assert.ok(POLL_INTERVALS.notificationsMs>POLL_INTERVALS.stateMs);
});

test('browser notification delivery IDs remain bounded', () => {
  const values=new Set();
  for(let index=0;index<250;index+=1)addBounded(values,`notification-${index}`,200);
  assert.equal(values.size,200);
  assert.equal(values.has('notification-0'),false);
  assert.equal(values.has('notification-249'),true);
});

test('render signatures are stable and change with caregiver state', () => {
  const first=renderSignature({care:{alert:false},events:[]});
  assert.equal(first,renderSignature({care:{alert:false},events:[]}));
  assert.notEqual(first,renderSignature({care:{alert:true},events:[]}));
});

test('stale home poll cannot overwrite a newer action state', () => {
  assert.equal(shouldApplyStateUpdate(8260,1060),false);
  assert.equal(shouldApplyStateUpdate(8260,8260),true);
  assert.equal(shouldApplyStateUpdate(8260,1000,{force:true}),true);
});

test('reset epoch accepts lower simulator time but rejects older epochs', () => {
  assert.equal(shouldApplyStateUpdate(1060,1000,{currentEpoch:4,nextEpoch:5}),true);
  assert.equal(shouldApplyStateUpdate(1000,1060,{currentEpoch:5,nextEpoch:4}),false);
  assert.equal(shouldApplyStateUpdate(8260,1060,{currentEpoch:5,nextEpoch:5}),false);
});
