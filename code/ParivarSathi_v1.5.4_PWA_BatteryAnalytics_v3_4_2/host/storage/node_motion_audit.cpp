// HOST ONLY. Replay unchanged production components, never a target adapter.
// Ideal prompt durable ACKs; no NVS, RF, target clock or battery measurement.
#include "firmware/node/components/power/power.hpp"
#include "firmware/node/components/sensing/sensing.hpp"
#include "firmware/node/runtime/node_runtime.hpp"
#include "gs/rules.hpp"

#include <algorithm>
#include <cassert>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

using namespace gs;
using namespace gs::node;

static DomainEvent point(std::uint64_t seq, EpochSeconds at,
                         const std::string& room = "common") {
    DomainEvent e;
    e.key = EventKey("node", 1, seq);
    e.kind = EventKind::Motion;
    e.location = room;
    e.occurred_at = at;
    e.monotonic_ms = at * 1000;
    return e;
}

static void counterexamples() {
    QualifiedInput pir(EventKind::Motion, std::nullopt, 150, 1000);
    assert(!pir.sample(true, 0));                 // boot-high is not an edge
    assert(!pir.sample(true, 10000));             // sustained high is not pulses
    assert(!pir.sample(false, 10001));
    assert(!pir.sample(false, 10151));
    assert(!pir.sample(true, 10152));
    assert(!pir.sample(true, 10301));
    assert(pir.sample(true, 10302) == EventKind::Motion);
    assert(!pir.sample(false, 10303));
    assert(!pir.sample(false, 10453));
    assert(!pir.sample(true, 10454));
    assert(!pir.sample(true, 10604));             // within retrigger; no event
    assert(!pir.sample(true, 12000));             // does not synthesize later rise

    ActivityEpisode a;
    a.note_first("common", 0, false);
    a.note_repeat(40000);
    assert(!a.needs_first("common", 80000, false));
    a.poll(85000, false);
    assert(a.pending() && a.pending()->aggregate.first_ms == 40000);
    assert(a.pending()->aggregate.last_ms == 40000);
    a.summary_committed();
    a.note_first("common", 90000, false);
    assert(a.needs_first("common", 135000, false)); // quiet boundary inclusive
    assert(!a.pending());                          // singleton emits no summary

    ActivityEpisode outage;
    outage.note_first("common", 0, true);
    outage.note_repeat(120000);
    assert(!outage.needs_first("common", 300000, true));
    outage.poll(300000, false);                  // radio recovery closes RAM data
    assert(outage.pending()->aggregate.last_ms == 120000);
    outage.summary_committed();
    // One pending same-room summary can span a genuine quiet gap.
    outage.note_first("common", 400000, false);
    outage.note_repeat(420000);
    outage.poll(465000, false);
    outage.note_first("common", 1000000, false);
    outage.note_repeat(1020000);
    outage.poll(1065000, false);
    assert(outage.pending()->aggregate.additional_count == 2);
    assert(outage.pending()->aggregate.first_ms == 420000);
    assert(outage.pending()->aggregate.last_ms == 1020000);

    NodeRuntime runtime("node", 1);
    auto key = runtime.record(EventKind::Motion, "common", 0, 0, 86400);
    assert(key);
    ActivityEpisode volatile_episode;
    volatile_episode.note_first("common", 0, false);
    volatile_episode.note_repeat(40000);
    auto snapshot = runtime.recovery_snapshot();
    assert(snapshot.pending.size() == 1 && !snapshot.pending[0].event.motion_aggregate);
    runtime.transport_result(*key, true, 0);
    auto retry = runtime.next_transmission(1000);
    assert(retry && retry->key.str() == key->str());
    assert(!runtime.acknowledge(*key, AckClass::ReceivedVolatile));
    NodeRuntime reboot("node", 2);
    assert(reboot.restore_recovery(snapshot, 0));
    assert(reboot.next_transmission(0)->key.str() == key->str());
    ActivityEpisode reboot_episode;
    assert(reboot_episode.needs_first("common", 0, false));
    assert(!reboot_episode.pending());            // repeat was never serialized

    ActivityRuleConfig cfg;
    cfg.daytime_inactivity_seconds = 100;
    cfg.morning_sequence_enabled = false;
    cfg.night_activity_enabled = false;
    ActivityRuleState raw, compressed;
    RulesCore::apply_activity_event(raw, cfg, point(1, 0), 12 * 60);
    compressed = raw;
    RulesCore::apply_activity_event(raw, cfg, point(2, 80), 12 * 60);
    DomainEvent summary = point(3, 80);
    summary.kind = EventKind::MotionSummary;
    summary.motion_aggregate = DomainEvent::MotionAggregate{1, 80000, 80000};
    RulesCore::apply_activity_event(compressed, cfg, summary, 12 * 60);
    assert(RulesCore::evaluate_activity_timers(raw, cfg, 100, 12 * 60).empty());
    assert(RulesCore::evaluate_activity_timers(compressed, cfg, 100, 12 * 60).size() == 1);
    ActivityRuleState unknown = compressed;
    unknown.inactivity_alerted = false;
    assert(RulesCore::evaluate_activity_timers(unknown, cfg, 100, 12 * 60,
        {HomeMode::Home, CoverageState::Unknown, true}).empty());

    // First/last/count cannot recover which side of a window an internal point occupied.
    RoutineConfig window{"window", 50, 70, 80, {"common"}, true};
    RoutineState yes, no;
    yes.window_id = no.window_id = window.window_id;
    for (auto t : {0, 60, 120}) RulesCore::apply_event(yes, window, point(t + 1, t));
    for (auto t : {0, 80, 120}) RulesCore::apply_event(no, window, point(t + 1, t));
    assert(yes.activity_seen && !no.activity_seen);
    // Same endpoints/count also yield different night visit counts at the native 300s rule.
    cfg.night_activity_enabled = true;
    ActivityRuleState night_yes, night_no;
    for (auto t : {0, 300, 600})
        RulesCore::apply_activity_event(night_yes, cfg, point(t + 1, t), 23 * 60);
    for (auto t : {0, 299, 600})
        RulesCore::apply_activity_event(night_no, cfg, point(t + 1, t), 23 * 60);
    assert(night_yes.night_common_visits == 3 && night_no.night_common_visits == 2);
    // Motion inside an already open episode can still be essential after another Node's door close.
    ActivityRuleState door;
    auto open = point(1, 0, "entrance"); open.kind = EventKind::DoorOpen;
    auto close = point(2, 10, "entrance"); close.kind = EventKind::DoorClosed;
    RulesCore::apply_activity_event(door, cfg, open, 12 * 60);
    RulesCore::apply_activity_event(door, cfg, close, 12 * 60);
    RulesCore::apply_activity_event(door, cfg, point(3, 20), 12 * 60);
    assert(door.post_door_activity_seen);
    std::puts("ACTUAL_COMPONENT_COUNTEREXAMPLES=PASS boot/debounce/retrigger; quiet/max/outage; sparse-pending gap; RAM recovery limit; retry identity; inactivity/window/night/door");
}

struct Replay {
    ActivityEpisode episode;
    NodeRuntime runtime;
    std::ofstream& csv;
    std::string name;
    int node;
    std::size_t observations{0}, motion{0}, summaries{0}, repeats{0};
    Replay(std::ofstream& out, std::string scenario, int n)
        : runtime("node-" + std::to_string(n), 1), csv(out), name(std::move(scenario)), node(n) {}
    void emit(EventKind kind, Milliseconds created, Milliseconds at,
              std::optional<DomainEvent::MotionAggregate> aggregate = std::nullopt) {
        auto key = runtime.record(kind, "room", at, 0, 86400, 0, false, SensorType::Pir, 0, aggregate);
        assert(key);
        // Target saves recovery here BEFORE radio. Count operations, do not claim physical writes.
        auto event = runtime.next_transmission(created);
        assert(event && event->key.str() == key->str());
        csv << name << ',' << node << ',' << key->sequence << ','
            << (aggregate ? "source_summary" : "motion") << ',' << at << ',' << created << ','
            << (aggregate ? aggregate->additional_count : 0) << ','
            << (aggregate ? aggregate->first_ms : at) << ','
            << (aggregate ? aggregate->last_ms : at) << '\n';
        runtime.transport_result(*key, true, created);
        assert(runtime.acknowledge(*key, AckClass::Durable)); // target saves retirement here
        if (aggregate) { ++summaries; repeats += aggregate->additional_count; }
        else ++motion;
    }
    void flush(Milliseconds now) {
        episode.poll(now, false);
        if (episode.pending()) {
            const auto s = *episode.pending();
            emit(EventKind::MotionSummary, now, s.aggregate.last_ms, s.aggregate);
            episode.summary_committed();
        }
    }
    void observe(Milliseconds now) {
        // Advance the owner's timer BEFORE sampling, as in the target. Prompt
        // summary admission/ACK; no arbitrary delay or guessed reduction factor.
        while (episode.next_deadline_ms() >= 0 && episode.next_deadline_ms() <= now)
            flush(episode.next_deadline_ms());
        ++observations;
        if (episode.needs_first("room", now, false)) {
            emit(EventKind::Motion, now, now);
            episode.note_first("room", now, false);
        } else episode.note_repeat(now);
        flush(now);
    }
    void finish() {
        // Include final closure after the 72h observation interval, conservatively.
        if (episode.next_deadline_ms() >= 0) flush(episode.next_deadline_ms());
        assert(observations == motion + repeats);
        assert(runtime.pending() == 0 && runtime.persisted() == 0);
    }
};

int main(int argc, char** argv) {
    assert(argc == 2);
    counterexamples();
    std::ofstream csv(argv[1]);
    assert(csv);
    csv << "scenario,node,seq,kind,at_ms,created_ms,additional_count,first_ms,last_ms\n";
    for (const auto& name : {"NORMAL", "HIGH", "STRESS", "PAIRED46", "BUSY40", "BUSY80", "BUSY120"}) {
        std::size_t obs = 0, first = 0, summaries = 0;
        for (int node = 0; node < 6; ++node) {
            Replay r(csv, name, node);
            for (int day = 0; day < 3; ++day) {
                const Milliseconds base = (12 * 3600LL + day * 86400LL) * 1000;
                if (std::string(name) == "NORMAL" || std::string(name) == "HIGH") {
                    const bool normal = std::string(name) == "NORMAL";
                    const int sessions = normal ? 40 : 160;
                    for (int i = 0; i < sessions; ++i) {
                        auto t = base + i * (86400000LL / sessions);
                        r.observe(t);
                        if (normal ? i % 2 == 0 : i % 4 != 3)
                            for (auto delta : {1000, 10000, 20000, 30000}) r.observe(t + delta);
                    }
                } else if (std::string(name) == "STRESS" || std::string(name) == "PAIRED46") {
                    const auto period = std::string(name) == "STRESS" ? 45000LL : 46000LL;
                    for (Milliseconds delta = 0; delta + 1000 < 86400000; delta += period) {
                        r.observe(base + delta); r.observe(base + delta + 1000);
                    }
                } else {
                    const int seconds = std::string(name) == "BUSY40" ? 40 :
                        (std::string(name) == "BUSY80" ? 80 : 120);
                    for (Milliseconds delta = 0; delta < 8 * 3600000LL; delta += seconds * 1000)
                        r.observe(base + delta);
                }
            }
            r.finish();
            obs += r.observations; first += r.motion; summaries += r.summaries;
        }
        std::printf("REPLAY %s qualified=%zu Motion=%zu MotionSummary=%zu source_motion_records=%zu ideal_recovery_saves=%zu\n",
                    name, obs, first, summaries, first + summaries, 2 * (first + summaries));
    }
    std::printf("REPLAY_EXIT=0; HOST sizeof(ActivityEpisode)=%zu; physical RF/NVS/battery UNPROVEN\n", sizeof(ActivityEpisode));
}
