// Reuse the established encrypted recovery / authenticated GS-150 simulation.
// Baseline and candidate both retain GS-150 sleep/retry behavior.
#define main gs150_validation_main
#include "gs150_offline_sleep_validation.cpp"
#undef main
#include "gs/node_health_config.hpp"

void health_matrix() {
    require(deployment::policy.valid() && deployment::policy.heartbeat_seconds==300 &&
            deployment::policy.offline_seconds==910,"JSON default startup policy");
    for (auto seconds : {60U,120U,300U,600U}) {
        auto policy=NodeHealthPolicy::configured(seconds);
        require(policy.valid() && policy.offline_seconds==3*seconds+10,"derived policy examples");
    }
    require(!NodeHealthPolicy::configured(0).valid() &&
            !NodeHealthPolicy::configured(3601).valid(),"typed boot validation");
    require(deployment::for_device("c3-146393c5d158")->offline_seconds==910 &&
            !deployment::for_device("unknown"),"trusted profile identity, unknown never inferred");
    NodeHealthCadence cadence(300000,300000);
    unsigned health_count=0;
    for(Milliseconds t=0;t<=1800000;t+=1000) if(cadence.due(t,false,false,false,false)) {
        ++health_count;cadence.observe_health_attempt(t);
    }
    require(health_count==6,"30 quiet minutes has six health opportunities");
    for(auto event_ms : {299999,300000,300001}) {
        NodeHealthCadence c(300000,300000);
        require(!c.due(event_ms,true,false,false,false),"event due wins over standalone health");
        // Failed TX/missing ACK never supplies authenticated contact.
        require(c.next_due_ms()==300000,"local failure/MAC success does not refresh contact");
        c.observe_authenticated_contact(event_ms+40);
        require(c.next_due_ms()==event_ms+40+300000,"valid application ACK restarts quiet interval");
    }
    NodeHealthCadence c(300000,300000);
    c.observe_authenticated_contact(780000);
    require(c.next_due_ms()==1080000,"10:13 contact produces 10:18 next opportunity");
    require(!c.due(1080000,false,true,false,false) && !c.due(1080000,false,false,true,false) &&
            !c.due(1080000,false,false,false,true),"pending retry/outage/maintenance priorities");
    c.observe_health_attempt(1080000);
    require(c.next_due_ms()==1380000,"failed health schedules bounded attempt without fake contact");

    hub::HubRuntime h;
    for (const auto& row : std::vector<std::pair<std::string,unsigned>>{{"old60",190},{"old120",310},{"new",910},{"custom",1810}}) {
        h.authorize_node(row.first,1,true);h.set_node_offline_timeout(row.first,row.second);
        require(h.observe_authenticated_contact(row.first,1,1000,1000),"authorized per-Node received contact");
        require(h.node_online(row.first,1000+row.second*1000ULL) &&
                !h.node_online(row.first,1001+row.second*1000ULL),"inclusive lease boundary and silent failure");
        require(!h.observe_authenticated_contact(row.first,2,2000),"old/wrong session rejected");
    }
    h.authorize_node("unknown",1,true);h.set_node_offline_timeout("unknown",std::nullopt);
    require(h.observe_authenticated_contact("unknown",1,1000) && !h.node_profile_known("unknown") &&
            !h.node_online("unknown",1000),"unlisted authenticated identity retains unknown profile");
    hub::CoverageTracker coverage;
    coverage.require_node("new");coverage.set_node_lease("new",910);coverage.observe("new",1000);
    require(coverage.current(1910)==CoverageState::Covered && coverage.current(1911)==CoverageState::Unknown,
            "quiet reachable Node remains observed until derived profile lease");
    coverage.set_sensor_fault("new",true);coverage.observe("new",1100);
    require(coverage.current(1100)==CoverageState::Fault,"health does not hide sensor failure");
    coverage.set_node_lease("new",0);
    require(coverage.current(1100)==CoverageState::Unknown,"unknown deployment cannot prove coverage");

    EnergyCounters energy;energy.awake_ms=1000;energy.sensor_active_ms=500;energy.radio_tx_packets=2;
    NodeRuntime n("room",1);
    const auto key=n.record(EventKind::CallFamily,"room",1000,123,0,3800);
    auto msg=n.next_message(1000);require(key && msg,"critical event admitted promptly");
    msg->power=energy.telemetry();auto frame=transport::encode_node_message(*msg);
    const auto decoded=transport::decode_node_message(frame.frame.bytes.data(),frame.frame.size);
    require(frame && decoded && decoded.value->power && decoded.value->occurred_at==123 &&
            decoded.value->sequence_number==key->sequence,"existing authenticated event telemetry preserves EventKey/time");
    require(n.pending()==1,"piggyback does not retire a durable event");
    Pair p;p.admit(EventKind::Motion,1000);
    auto replay=*p.node->next_message(1000);replay.power=energy.telemetry();
    bool changed=false;const auto first_ack=p.deliver(replay,1000,changed);
    require(changed && p.node->pending()==1,"missed ACK retains piggybacked event");
    energy.awake_ms=2000;replay.power=energy.telemetry();
    const auto retry_ack=p.deliver(replay,2000,changed);
    require(!changed && p.hub->journal().size()==1 && p.ack(retry_ack) && p.node->pending()==0,
            "changed optional health telemetry on exact-key retry cannot duplicate logical effects");
    (void)first_ack;
}

int main() {
    try {
        health_matrix(); policy_matrix(); authenticated_matrix();
        std::ofstream csv("build/gs40_metrics.csv");
        csv<<"scenario,interval_s,loops,sleeps,timer_wakes,gpio_wakes,awake_ms,listen_ms,event_tx,retries,ack,missed_ack,rejoin,admitted,retired,durable_writes,logical_effects,standalone_health,event_contacts,first_tx_latency_ms,first_ack_latency_ms,hub_return_contact_ms,drain_ms,false_offline_samples\n";
        std::vector<Scenario> cases;
        Scenario quiet{"quiet_30m"};quiet.horizon_ms=1800020;cases.push_back(quiet);
        Scenario night{"night_8h"};night.horizon_ms=28800020;cases.push_back(night);
        Scenario frequent{"frequent_day"};frequent.motion=true;frequent.horizon_ms=1800000;cases.push_back(frequent);
        auto sporadic=frequent;sporadic.name="sporadic_day";sporadic.motion_period_ms=420000;cases.push_back(sporadic);
        cases.push_back({"confirmed_outage",1,400000});
        cases.push_back({"hub_recovery",8,130000,40,false,true});
        cases.push_back({"lost_ack",1,0,40,true});
        cases.push_back({"delayed_ack",1,0,1000});
        for(const auto& s:cases) {
            const auto before=simulate(s,true,120000,310),after=simulate(s,true,300000,910);
            require(before.admitted==after.admitted && before.retired==after.retired && before.effects==after.effects,
                    "GS-40 workload equivalence: no event loss, false retirement or duplicate logical effects");
            require(before.incorrect_offline==0 && after.incorrect_offline==0,"no healthy authenticated Node false offline");
            require(before.tx==after.tx && before.retry==after.retry,"existing retry schedule unchanged");
            if(s.name=="quiet_30m" || s.name=="night_8h")
                require(after.health*2<before.health && after.awake<=before.awake,"quieter standalone health with equivalent sleep policy");
            for(const auto& version:std::vector<std::pair<unsigned,Metrics>>{{120,before},{300,after}}) {
                const auto& m=version.second;
                csv<<s.name<<','<<version.first<<','<<m.loops<<','<<m.sleeps<<','<<m.timer<<','<<m.gpio<<','<<m.awake<<','<<m.listen<<','
                   <<m.tx<<','<<m.retry<<','<<m.ack<<','<<m.missed<<','<<m.rejoin<<','<<m.admitted<<','<<m.retired<<','<<m.writes<<','
                   <<m.effects<<','<<m.health<<','<<m.piggyback<<','<<m.first_latency<<','<<m.ack_latency<<','<<m.return_latency<<','<<m.drain<<','<<m.incorrect_offline<<'\n';
            }
            std::cout<<s.name<<" standalone "<<before.health<<" -> "<<after.health<<" loops "<<before.loops<<" -> "<<after.loops<<'\n';
        }
        std::cout<<"GS-40 PASS checks="<<checks<<'\n';return 0;
    } catch(const std::exception& e) {std::cerr<<"GS-40 FAIL: "<<e.what()<<'\n';return 1;}
}
