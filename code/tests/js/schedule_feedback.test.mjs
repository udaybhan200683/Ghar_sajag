import test from 'node:test';
import assert from 'node:assert/strict';
import { nextScheduleFeedback } from '../../tools/sim/pwa/schedule_feedback.mjs';

test('schedule feedback state is durable for success, rejection and reset', () => {
  assert.deepEqual(nextScheduleFeedback('Device schedule saved and applied to the hub', 'success'), {
    message: 'Device schedule saved and applied to the hub', kind: 'success',
  });
  assert.deepEqual(nextScheduleFeedback('Not saved: invalid threshold relationship', 'error'), {
    message: 'Not saved: invalid threshold relationship', kind: 'error',
  });
  assert.deepEqual(nextScheduleFeedback(), {message: '', kind: ''});
});
