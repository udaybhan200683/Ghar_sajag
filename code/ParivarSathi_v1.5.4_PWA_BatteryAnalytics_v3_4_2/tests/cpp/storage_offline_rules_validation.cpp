// Focused actual-rule consumers; snapshot copies model a durable checkpoint.
// No new alert/learning algorithm and no production summary adapter.
#include "gs/rules.hpp"
#include <cassert>
#include <cstdio>
using namespace gs;
int main() {
    RoutineConfig cfg{"day0",100,200,210,{"common"},true};
    RoutineState quiet,missing;quiet.window_id=missing.window_id="day0";
    quiet.coverage=CoverageState::Covered;missing.coverage=CoverageState::Unknown;
    auto reboot_quiet=quiet,reboot_missing=missing;
    assert(RulesCore::evaluate_deadline(reboot_quiet,cfg,211,true).create);
    const auto no_obs=RulesCore::evaluate_deadline(reboot_missing,cfg,211,true);
    assert(!no_obs.create && no_obs.reason=="coverage_unknown");
    assert(!RulesCore::evaluate_deadline(reboot_quiet,cfg,212,true).create);
    ActivityRuleConfig ac;ac.night_bathroom_visit_threshold=2;
    ActivityRuleState raw,points;
    for(unsigned i=0;i<4;++i) {
        DomainEvent e;e.key=EventKey("bathroom",1,i+1,"physical1");
        e.kind=EventKind::Motion;e.location="bathroom";
        e.occurred_at=(i==0?100:i==1?200:i==2?500:800);
        auto a=RulesCore::apply_activity_event(raw,ac,e,23*60);
        auto b=RulesCore::apply_activity_event(points,ac,e,23*60);
        assert(a.size()==b.size());
        if(i==3)assert(a.size()==1 && a[0].stable_key==b[0].stable_key);
    }
    assert(raw.night_bathroom_visits==3 && points.night_bathroom_visits==3);
    auto restored=raw; // copies are not an NVS/root/serialization proof
    DomainEvent source_summary;source_summary.kind=EventKind::MotionSummary;
    source_summary.location="bathroom";source_summary.occurred_at=900;
    source_summary.motion_aggregate=DomainEvent::MotionAggregate{100,100001,800023};
    assert(RulesCore::apply_activity_event(restored,ac,source_summary,23*60).empty());
    assert(restored.last_activity_at==raw.last_activity_at);
    assert(restored.last_activity_event_id==raw.last_activity_event_id);
    // An activity checkpoint preserves its exact last-activity anchor; unknown
    // observation coverage cannot fabricate a daytime inactivity conclusion.
    auto covered=restored,unknown=restored;
    auto yes=RulesCore::evaluate_activity_timers(covered,ac,20000,12*60,
        {HomeMode::Home,CoverageState::Covered,true});
    auto no=RulesCore::evaluate_activity_timers(unknown,ac,20000,12*60,
        {HomeMode::Home,CoverageState::Unknown,true});
    assert(yes.size()==1 && no.empty());
    assert(yes[0].stable_key.find(raw.last_activity_event_id)!=std::string::npos);
    DomainEvent open;open.kind=EventKind::DoorOpen;open.key=EventKey("door",1,1,"physical2");
    open.occurred_at=100;open.location="entrance";
    ActivityRuleState door;
    auto alert=RulesCore::apply_activity_event(door,ac,open,120);
    assert(alert.size()==1 && alert[0].kind==RuleSignalKind::UnexpectedDoorOpen);
    auto door_reboot=door;
    DomainEvent close=open;close.kind=EventKind::DoorClosed;close.key.sequence=2;close.occurred_at=10000;
    auto resolution=RulesCore::apply_activity_event(door_reboot,ac,close,180);
    assert(resolution.size()==1 && resolution[0].stable_key.find(open.key.str())!=std::string::npos);
    std::puts("OFFLINE_RULES_HOST_PASS actual RulesCore; sparse-point equivalence, source-summary ignored, covered-vs-unknown, exact anchors/door; copied checkpoint only");
}
