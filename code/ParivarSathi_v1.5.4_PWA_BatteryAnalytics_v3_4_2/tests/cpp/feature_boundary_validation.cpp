// GS-130: production component boundaries, virtual time only; no board APIs.
#include "sensing/sensing.hpp"
#include "storage/node_store.hpp"
#include "lifecycle/lifecycle.hpp"
#include "firmware/hub/components/lifecycle/config_service.hpp"
#include "firmware/hub/components/time/clock.hpp"
#include "firmware/hub/components/ingest/ingest.hpp"
#include "power/session_recovery_policy.hpp"
#include "coverage/coverage.hpp"
#include "ui/resident_ui.hpp"
#include "gs/rules.hpp"
#include <iostream>
#include <stdexcept>
using namespace gs;
namespace {
unsigned checks=0;
void require(bool yes,const char* why){++checks;if(!yes)throw std::runtime_error(why);}
DomainEvent event(unsigned sequence){DomainEvent e;e.key={"node",2,sequence};e.kind=EventKind::Motion;e.occurred_at=100+sequence;return e;}
void sensing_boundaries(){
 node::QualifiedInput pir(EventKind::Motion,std::nullopt,25,100);
 require(!pir.sample(true,0)&&!pir.sample(true,1000),"boot HIGH is not first motion");
 require(!pir.sample(false,1010)&&!pir.sample(false,1035),"LOW qualifies without an event");
 require(!pir.sample(true,1040)&&!pir.sample(true,1064),"bounce cannot cross debounce early");
 require(pir.sample(true,1065)==EventKind::Motion,"exact qualified first motion boundary");
 require(!pir.sample(true,2000)&&!pir.safe_for_sleep(2000),"held HIGH cannot generate events or sleep wake storm");
 require(!pir.sample(false,2010)&&!pir.sample(false,2035)&&pir.safe_for_sleep(2035),"LOW restores sensing and sleep after prior motion");
 require(!pir.safe_for_sleep(2009),"backwards sleep clock fails safe");
 node::QualifiedInput door(EventKind::DoorOpen,EventKind::DoorClosed,25,0);
 require(!door.sample(false,0)&&!door.sample(true,1),"door initializes and debounces");
 require(door.sample(true,26)==EventKind::DoorOpen,"door OPEN preserved");
 require(!door.sample(false,27)&&door.sample(false,52)==EventKind::DoorClosed,"door CLOSE distinct at exact boundary");
}
void store_boundaries(){
 node::NodeStore store(2);auto a=event(1),b=event(2),c=event(3);
 require(!store.oldest()&&!store.acknowledge(a.key,AckClass::Durable),"empty store and unknown ACK");
 require(store.append(a)&&store.append(b),"exact capacity admits original events");
 require(!store.append(c)&&store.gap_marker_required()&&store.size()==2,"overflow is honest and does not erase accepted events");
 require(!store.acknowledge(a.key,AckClass::ReceivedVolatile)&&store.oldest()->key.str()==a.key.str(),"MAC/volatile acknowledgement cannot delete business event");
 require(!store.acknowledge({"other",2,1},AckClass::Durable)&&store.size()==2,"wrong source ACK rejected");
 require(store.acknowledge(a.key,AckClass::Durable)&&store.append(c),"durable retirement frees bounded capacity");
 auto rows=store.retained_snapshot();require(rows.size()==2&&rows[0].key.str()==b.key.str()&&rows[0].occurred_at==b.occurred_at&&rows[1].key.str()==c.key.str(),"retained EventKeys timestamps chronology remain original");
 require(!store.acknowledge(a.key,AckClass::Durable)&&store.size()==2,"duplicate retired ACK is harmless");
 store.clear_gap_marker();require(!store.gap_marker_required(),"explicit gap clear");
 store.restore_gap_marker(true);require(store.gap_marker_required(),"gap recovery never hides coverage loss");
}
void node_config_boundaries(){
 node::LifecycleService owner;NodeConfig c{1,"node","room",true,false,15};
 require(owner.apply(c).applied,"legacy lifecycle lower bound");
 for(auto seconds:{0U,14U,3601U}){auto bad=c;bad.version=2;bad.heartbeat_seconds=seconds;require(!owner.apply(bad).applied&&owner.active()->version==1,"invalid config is rejected atomically");}
 auto bad=c;bad.version=2;bad.node_id.clear();require(!owner.apply(bad).applied,"missing identity rejected");
 bad=c;bad.version=2;bad.pir_enabled=false;require(!owner.apply(bad).applied,"no enabled sensor rejected");
 c.version=2;c.heartbeat_seconds=3600;require(owner.apply(c).applied&&!owner.apply(c).applied,"upper bound applies once with monotonic version");
 owner.open_service_window(1000,500);require(owner.service_window_open(1500)&&!owner.service_window_open(1501),"service window exact inclusive expiry");
 owner.open_service_window(2000,100);require(owner.service_window_open(2100)&&!owner.service_window_open(2101),"new bounded window recovers maintenance opportunity");
}
void hub_config_boundaries(){
 hub::ConfigService owner;HomeConfig c;c.home_id="home";c.timezone="UTC";c.version=1;
 c.morning.enabled=true;c.morning.start_at=100;c.morning.end_at=200;c.morning.grace_end_at=300;
 require(owner.apply(c).applied,"valid complete home snapshot");
 auto bad=c;bad.version=2;bad.morning.end_at=100;require(!owner.apply(bad).applied&&owner.active()->version==1,"invalid morning equality preserves active state");
 bad=c;bad.version=2;bad.morning.grace_end_at=199;require(!owner.apply(bad).applied,"grace ordering rejected");
 bad=c;bad.version=2;bad.timezone.clear();require(!owner.apply(bad).applied,"timezone required");
 for(auto seconds:{29U,86401U}){bad=c;bad.version=2;bad.activity_rules.door_open_timeout_seconds=seconds;require(!owner.apply(bad).applied,"door timeout range rejects without mutation");}
 bad=c;bad.version=2;bad.activity_rules.quiet_start_minute=1440;require(!owner.apply(bad).applied,"minute boundary rejects");
 c.version=2;c.activity_rules.door_open_timeout_seconds=30;c.activity_rules.daytime_inactivity_seconds=300;require(owner.apply(c).applied,"minimum configured activity bounds");
 c.version=3;c.activity_rules.door_open_timeout_seconds=86400;c.activity_rules.daytime_inactivity_seconds=86400;require(owner.apply(c).applied&&!owner.apply(c).applied,"maximum bounds and stale version rejected");
}
void clock_boundaries(){
 hub::TrustedClock clock;require(!clock.valid_for_absence(0),"missing time cannot infer inactivity");
 clock.anchor(1700000000,1000,2);
 require(clock.estimate(999).trust==hub::TimeTrust::Untrusted,"monotonic discontinuity cannot borrow another epoch");
 require(clock.valid_for_absence(1000,2)&&clock.estimate(1999).earliest==1699999998,"anchor and subsecond boundary");
 require(clock.estimate(2000).earliest==1699999999,"whole second progression");
 require(clock.valid_for_absence(1000+9999*1000,2)&&!clock.valid_for_absence(1000+10000*1000,2),"uncertainty drift blocks absence at exact boundary");
 require(clock.estimate(1000+72LL*3600*1000).trust==hub::TimeTrust::Trusted&&clock.estimate(1000+(72LL*3600+1)*1000).trust==hub::TimeTrust::Expired,"72 hour trust expiry boundary");
 clock.anchor(1800000000,400000000,1);require(clock.valid_for_absence(400000000)&&clock.estimate(400000000).earliest==1799999999,"new trusted anchor restores valid current epoch");
}
void ingest_boundaries(){
 hub::PeerRegistry peers;peers.authorize("node",5);hub::IngestQueue queue(2);auto a=event(1),b=event(2);
 require(!queue.callback_copy(a,peers),"old event boot is not raw authenticated transport");
 require(queue.callback_copy_authenticated(a,peers,"node",5),"authenticated current session permits exact retained old EventKey");
 require(!queue.callback_copy_authenticated(b,peers,"other",5),"cross-device retained key rejected");
 require(queue.callback_copy_authenticated(b,peers,"node",5)&&!queue.callback_copy_authenticated(event(3),peers,"node",5),"bounded callback queue rejects overflow");
 require(queue.high_water()==2&&queue.pop()->key.str()==a.key.str()&&queue.pop()->key.str()==b.key.str()&&!queue.pop(),"FIFO identity and high-water remain bounded");
 peers.revoke("node");require(!queue.callback_copy_authenticated(a,peers,"node",5),"revoked owner cannot append");
 peers.authorize("node",6);require(!queue.callback_copy_authenticated(a,peers,"node",5)&&queue.callback_copy_authenticated(a,peers,"node",6),"session restoration rejects stale transport but preserves durable original key");
 queue.discard_source("node");require(queue.size()==0,"source removal clears queued processing");
}
void coverage_boundaries(){
 hub::CoverageTracker coverage;coverage.require_node("old");coverage.require_node("new");
 coverage.set_node_lease("old",190);coverage.set_node_lease("new",910);
 require(coverage.current(100)==CoverageState::Unknown,"unknown identity/contact cannot establish coverage");
 coverage.observe("old",100);coverage.observe("new",100);
 require(coverage.current(290)==CoverageState::Covered&&coverage.current(291)==CoverageState::Unknown,"each mixed profile expires independently");
 coverage.observe("old",291);coverage.set_sensor_fault("new",true);
 require(coverage.current(291)==CoverageState::Fault,"authenticated health cannot hide explicit sensor fault");
 coverage.observe("new",292);require(coverage.current(292)==CoverageState::Fault,"health does not clear fault");
 coverage.set_sensor_fault("new",false);require(coverage.current(292)==CoverageState::Covered,"explicit recovery restores coverage");
 require(coverage.current(99)==CoverageState::Unknown,"backwards time cannot prove coverage");
 coverage.set_node_lease("new",0);require(coverage.current(292)==CoverageState::Unknown,"unknown policy lease fails closed");
 coverage.forget_node("new");require(coverage.current(292)==CoverageState::Covered,"removed Node cannot poison unrelated required coverage");
}
void routine_boundaries(){
 RoutineConfig config;config.enabled=true;config.window_id="morning";config.start_at=100;config.end_at=200;config.grace_end_at=230;
 config.qualifying_locations.insert("room");
 auto motion=event(10);motion.location="room";motion.occurred_at=99;motion.uncertainty_s=1;
 require(RulesCore::event_overlaps_window(motion,config),"uncertainty touching start qualifies");
 motion.uncertainty_s=0;require(!RulesCore::event_overlaps_window(motion,config),"outside exact start excludes");
 motion.occurred_at=200;require(RulesCore::event_overlaps_window(motion,config),"exact end included");
 motion.occurred_at=201;require(!RulesCore::event_overlaps_window(motion,config),"after end excludes");
 RoutineState state;state.window_id="morning";state.coverage=CoverageState::Covered;
 require(!RulesCore::evaluate_deadline(state,config,229,true).create,"before grace cannot alarm");
 for(auto mode:{HomeMode::Away,HomeMode::Paused,HomeMode::Privacy,HomeMode::Visitor}){state.mode=mode;require(!RulesCore::evaluate_deadline(state,config,230,true).create,"non-Home passive concern suppressed");}
 state.mode=HomeMode::Home;
 require(!RulesCore::evaluate_deadline(state,config,230,false).create,"untrusted clock cannot infer inactivity");
 state.coverage=CoverageState::Unknown;require(!RulesCore::evaluate_deadline(state,config,230,true).create,"missing coverage is not inactivity");
 state.coverage=CoverageState::Covered;
 require(RulesCore::evaluate_deadline(state,config,230,true).create&&!RulesCore::evaluate_deadline(state,config,231,true).create,"exact grace creates one stable concern");
 RoutineState private_state;private_state.window_id="morning";private_state.mode=HomeMode::Privacy;
 motion.occurred_at=150;RulesCore::apply_event(private_state,config,motion);require(!private_state.activity_seen,"internal privacy suppresses passive evidence");
 motion.kind=EventKind::PrivacyOff;RulesCore::apply_event(private_state,config,motion);
 motion.kind=EventKind::MotionSummary;RulesCore::apply_event(private_state,config,motion);require(!private_state.activity_seen,"summary is not new activity");
 motion.kind=EventKind::Motion;motion.is_test=true;RulesCore::apply_event(private_state,config,motion);require(!private_state.activity_seen,"test event cannot prove resident wellbeing");
 motion.is_test=false;RulesCore::apply_event(private_state,config,motion);require(private_state.activity_seen,"privacy withdrawal followed by real eligible observation recovers");
 require(RulesCore::minute_in_window(1439,1320,360)&&RulesCore::minute_in_window(0,1320,360)&&!RulesCore::minute_in_window(360,1320,360)&&!RulesCore::minute_in_window(1440,0,0),"midnight inclusive start exclusive end bounds");
}
void resident_boundaries(){
 hub::ResidentUi ui;auto ok=ui.make_action(hub::ResidentAction::Ok,"hub",2,1,100);
 auto call=ui.make_action(hub::ResidentAction::CallFamily,"hub",2,2,101);
 require(ok.kind==EventKind::OkPressed&&call.kind==EventKind::CallFamily&&ok.key.str()!=call.key.str(),"resident actions have distinct semantics and immutable identities");
 require(ok.occurred_at==100&&call.occurred_at==101&&!ok.is_test,"original occurrence times preserved");
 require(ui.feedback_for(hub::ResidentAction::Ok,false).code=="OK_SAVED"&&ui.feedback_for(hub::ResidentAction::CallFamily,false).code=="CALL_SAVED","offline local feedback never fakes remote acceptance");
 require(ui.feedback_for(hub::ResidentAction::CallFamily,false).display_text.find("internet unavailable")!=std::string::npos,"offline request wording honest");
 require(ui.make_action(hub::ResidentAction::Ok,"hub",2,3,102,true).is_test,"test resident action distinguishable from real care event");
}
void recovery_boundaries(){
 using P=node::SessionRecoveryPolicy;
 require(!P::active_deadline(false,1000,3,0)&&!P::active_deadline(true,1000,2,0),"unnegotiated or insufficient attempts cannot force session recovery");
 require(P::active_deadline(true,1000,3,0)==11000&&!P::active_expired(true,10999,1000,3,0)&&P::active_expired(true,11000,1000,3,0),"10 second active boundary preserved");
 require(!P::active_expired(true,11000,1000,3,1001),"new authenticated contact cancels active recovery");
 require(!P::idle_expired(true,430999,1000)&&P::idle_expired(true,431000,1000)&&!P::idle_expired(true,999,1000),"idle timeout exact boundary with backwards-clock safety");
 require(P::health_ack_matches(true,7,7)&&!P::health_ack_matches(true,7,8)&&!P::health_ack_matches(true,std::nullopt,7)&&!P::health_ack_matches(true,0,0),"health ACK must match nonzero outstanding nonce");
 require(P::may_fallback(false,false,2,30000)&&!P::may_fallback(false,false,2,29999)&&!P::may_fallback(true,false,2,30000)&&!P::may_fallback(false,true,2,30000),"pinned or authenticated capability cannot downgrade");
 require(!P::ambiguity_expired(181000,1000,3,180000)&&P::ambiguity_expired(181000,1000,4,180000),"ambiguity expiry requires bounded final exchanges");
 require(P::next_ambiguity_window(180000)==360000&&P::next_ambiguity_window(3600000)==3600000,"ambiguity backoff cap preserved");
 for(unsigned attempt=0;attempt<20;++attempt){auto delay=P::retry_delay(attempt,7);require(delay>0&&delay<=60100,"retry delay stays bounded including saturated stage");}
}
}
int main(){try{
 sensing_boundaries();std::cout<<"NODE-TC-130-001 PASS\n";
 store_boundaries();std::cout<<"NODE-TC-130-002 PASS\n";
 node_config_boundaries();std::cout<<"NODE-TC-130-003 PASS\n";
 hub_config_boundaries();std::cout<<"HUB-TC-130-001 PASS\n";
 clock_boundaries();std::cout<<"HUB-TC-130-002 PASS\n";
 ingest_boundaries();std::cout<<"LINK-TC-130-001 PASS\n";
 coverage_boundaries();std::cout<<"HUB-TC-130-003 PASS\n";
 routine_boundaries();std::cout<<"HUB-TC-130-004 PASS\n";
 resident_boundaries();std::cout<<"HUB-TC-130-005 PASS\n";
 recovery_boundaries();std::cout<<"SEC-TC-130-001 PASS\n";
 std::cout<<"GS130 FEATURE BOUNDARIES PASS checks="<<checks<<"\n";return 0;
}catch(const std::exception& error){std::cerr<<"GS130 FAIL "<<error.what()<<'\n';return 1;}}
