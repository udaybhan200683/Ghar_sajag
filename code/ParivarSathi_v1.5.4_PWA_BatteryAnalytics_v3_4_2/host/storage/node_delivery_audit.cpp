// HOST ONLY: disputed delivery counterexamples against unchanged production components.
// Synthetic rule times are fixture values, never product latency targets.
#include "firmware/node/components/power/power.hpp"
#include "firmware/node/runtime/node_runtime.hpp"
#include "gs/rules.hpp"
#include <cassert>
#include <cstdio>
using namespace gs;
using namespace gs::node;

static DomainEvent event(unsigned seq, EventKind kind, EpochSeconds at,
                         const char* room = "common") {
    DomainEvent e;
    e.key = EventKey("node", 1, seq);
    e.kind = kind; e.location = room; e.occurred_at = at; e.monotonic_ms = at * 1000;
    return e;
}
static void pass(const char* label) { std::printf("PASS %s\n", label); }
int main() {
    {
        NodeRadio q;
        auto motion = event(1, EventKind::Motion, 0);
        auto call = event(2, EventKind::CallFamily, 0);
        assert(q.enqueue(motion, 0));
        q.record_transport_result(motion.key, true, 0);
        assert(q.enqueue(call, 1));
        assert(!q.next_due(1));
        assert(q.next_due_at() && *q.next_due_at() >= 200);
        pass("connected_call_waits_for_global_gate");
        q.set_outage_profile(true, 1);
        assert(q.next_due(1)->kind == EventKind::CallFamily);
        q.record_transport_result(call.key, true, 1);
        assert(!q.apply_ack(call.key, AckClass::ReceivedVolatile));
        assert(!q.next_due(3)); // Both attempted records now obey the global gate.
        pass("outage_nonmotion_first_attempt_bypass_not_unlimited_priority");
    }
    {
        NodeRuntime r("node", 1);
        for (unsigned i = 0; i < 28; ++i)
            assert(r.record(EventKind::Motion, "common", 0, 10, 0));
        assert(!r.record(EventKind::Motion, "common", 0, 10, 0));
        for (unsigned i = 0; i < 4; ++i)
            assert(r.record(EventKind::CallFamily, "hub", 0, 10, 0));
        assert(r.pending() == 32 && r.persisted() == 32);
        assert(!r.record(EventKind::CallFamily, "hub", 0, 10, 0));
        pass("28_motion_plus_4_nonmotion_reserve_no_unbounded_urgent_admission");
    }
    {
        NodeRuntime r("node", 1);
        const auto k1 = r.record(EventKind::Motion, "common", 500, 77, 3);
        const auto k2 = r.record(EventKind::DoorOpen, "entry", 501, 78, 3);
        assert(k1 && k2);
        NodeRuntime reboot("node", 2);
        assert(reboot.restore_recovery(r.recovery_snapshot(), 0));
        auto first = reboot.next_transmission(0);
        assert(first && first->key.str() == k1->str() && first->occurred_at == 77 &&
               first->monotonic_ms == 500 && first->uncertainty_s == 3);
        reboot.transport_result(*k1, true, 0);
        assert(!reboot.acknowledge(*k1, AckClass::ReceivedVolatile));
        assert(reboot.acknowledge(*k1, AckClass::Durable));
        auto next = reboot.next_transmission(0);
        assert(next && next->key.str() == k2->str() && next->occurred_at == 78);
        pass("reboot_preserves_origin_time_and_durable_ack_opens_drain");
    }
    {
        NodeHealthCadence health(120000, 120000);
        assert(health.due(120000, false, false, false, false));
        assert(!health.due(120000, false, true, false, false));
        LightSleepObservation o;
        o.now_ms = 1000; o.next_health_ms = 120000;
        o.authenticated = o.product_ready = o.persistence_clean = true;
        o.pir_high = false;
        o.pir_low_stable = o.debounce_safe = o.wake_source_ready = o.runtime_state_known = true;
        assert(evaluate_light_sleep(o).eligible);
        assert(evaluate_light_sleep(o).requested_sleep_ms == 30000);
        o.pending_tx = o.ack_wait = o.recovery_work = true;
        auto inhibited = evaluate_light_sleep(o);
        assert(!inhibited.eligible && (inhibited.inhibitors & LightSleepInhibitPendingTx));
        pass("held_pending_suppresses_health_and_sleep");
    }
    {
        RoutineConfig cfg{"morning", 50, 70, 80, {"common"}, true};
        RoutineState immediate, delayed;
        immediate.window_id = delayed.window_id = "morning";
        immediate.coverage = delayed.coverage = CoverageState::Covered;
        auto motion = event(1, EventKind::Motion, 60);
        RulesCore::apply_event(immediate, cfg, motion);
        assert(!RulesCore::evaluate_deadline(immediate, cfg, 80, true).create);
        assert(RulesCore::evaluate_deadline(delayed, cfg, 80, true).create);
        RulesCore::apply_event(delayed, cfg, motion);
        assert(delayed.activity_seen && delayed.missing_incident_created);
        pass("late_morning_evidence_does_not_undo_created_incident");
    }
    {
        ActivityRuleConfig cfg;
        cfg.morning_sequence_enabled = cfg.night_activity_enabled = false;
        cfg.daytime_inactivity_seconds = 100;
        ActivityRuleState immediate, delayed;
        RulesCore::apply_activity_event(immediate, cfg, event(1, EventKind::Motion, 0), 720);
        delayed = immediate;
        RulesCore::apply_activity_event(immediate, cfg, event(2, EventKind::Motion, 80), 720);
        assert(RulesCore::evaluate_activity_timers(immediate, cfg, 100, 720).empty());
        assert(RulesCore::evaluate_activity_timers(delayed, cfg, 100, 720).size() == 1);
        delayed.inactivity_alerted = false;
        assert(RulesCore::evaluate_activity_timers(delayed, cfg, 100, 720,
            {HomeMode::Home, CoverageState::Unknown, true}).empty());
        assert(RulesCore::evaluate_activity_timers(delayed, cfg, 100, 720,
            {HomeMode::Home, CoverageState::Covered, false}).empty());
        pass("deferred_motion_false_absence_unknown_coverage_or_time_suppresses");
    }
    {
        ActivityRuleConfig cfg;
        ActivityRuleState a;
        RulesCore::apply_activity_event(a, cfg, event(1, EventKind::Motion, 200), 720);
        RulesCore::apply_activity_event(a, cfg, event(2, EventKind::Motion, 100), 720);
        assert(a.last_activity_at == 100);
        RulesCore::apply_activity_event(a, cfg, event(3, EventKind::DoorOpen, 201), 720);
        RulesCore::apply_activity_event(a, cfg, event(4, EventKind::DoorClosed, 202), 720);
        RulesCore::apply_activity_event(a, cfg, event(5, EventKind::Motion, 150), 720);
        assert(a.post_door_activity_seen);
        pass("out_of_order_motion_regresses_anchor_and_postdoor_chronology");
    }
    {
        ActivityRuleConfig cfg;
        cfg.night_common_visit_threshold = 1; cfg.night_visit_merge_seconds = 10;
        ActivityRuleState a;
        assert(RulesCore::apply_activity_event(a, cfg,
            event(1, EventKind::Motion, 10), 23 * 60).empty());
        auto signals = RulesCore::apply_activity_event(a, cfg,
            event(2, EventKind::Motion, 20), 23 * 60);
        assert(signals.size() == 1 && signals[0].kind == RuleSignalKind::UnusualNightCommonActivity);
        ActivityRuleState wrong_minute;
        RulesCore::apply_activity_event(wrong_minute, cfg,
            event(1, EventKind::Motion, 10), 12 * 60);
        assert(RulesCore::apply_activity_event(wrong_minute, cfg,
            event(2, EventKind::Motion, 20), 12 * 60).empty());
        pass("night_decision_requires_occurrence_minute_and_prompt_evidence");
    }
    {
        ActivityRuleConfig cfg;
        ActivityRuleState chronological, reversed;
        auto open = event(1, EventKind::DoorOpen, 10, "entry");
        auto close = event(2, EventKind::DoorClosed, 20, "entry");
        auto signal = RulesCore::apply_activity_event(chronological, cfg, open, 120);
        assert(signal.size() == 1 && signal[0].kind == RuleSignalKind::UnexpectedDoorOpen);
        RulesCore::apply_activity_event(chronological, cfg, close, 120);
        RulesCore::apply_activity_event(reversed, cfg, close, 120);
        RulesCore::apply_activity_event(reversed, cfg, open, 120);
        assert(!chronological.door_opened_at && reversed.door_opened_at);
        pass("exact_door_records_still_require_ordered_reducer_application");
    }
    std::puts("RESULT=PASS groups=10; component counterexamples only; no RF/NVS/battery/target qualification");
}
