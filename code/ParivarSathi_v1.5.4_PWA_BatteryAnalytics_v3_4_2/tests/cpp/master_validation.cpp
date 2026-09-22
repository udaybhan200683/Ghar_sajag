#include "firmware/common/security/security.hpp"
#include "firmware/common/transport/data_plane_codec.hpp"
#include "firmware/common/transport/fota_protocol.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/node/runtime/node_runtime.hpp"
#include "sensing/sensing.hpp"

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

using TestBody = std::function<void()>;

struct TestCase {
    std::string id;
    std::string suite;
    std::string feature;
    TestBody body;
};

[[noreturn]] void fail(const std::string& message) { throw std::runtime_error(message); }
template <typename T>
void require(const T& condition, const std::string& message) {
    if (!static_cast<bool>(condition)) fail(message);
}

struct VirtualClock {
    gs::Milliseconds now{0};
    void advance(gs::Milliseconds delta) {
        require(delta >= 0, "virtual time cannot move backwards");
        now += delta;
    }
};

struct DeliveryFault {
    bool mac_success{true};
    bool packet_lost{false};
    bool duplicate_packet{false};
    bool ack_lost{false};
    bool duplicate_ack{false};
};

struct AttemptResult {
    bool attempted{false};
    bool hub_admitted{false};
    bool state_changed{false};
    bool acked{false};
    gs::EventKey key{};
};

// This harness substitutes only clock and transport. All admission, identity,
// retry, dedupe, journal, ACK and retirement decisions remain production code.
class RuntimePair {
    std::string node_id_;
    std::uint64_t session_;
    bool hub_online_{true};
    std::unique_ptr<gs::hub::HubRuntime> hub_;

public:
    RuntimePair(std::string node_id = "node-1", std::uint64_t session = 7,
                std::size_t node_capacity = 32, std::size_t hub_capacity = 1024)
        : node_id_(std::move(node_id)), session_(session),
          node(node_id_, session_, node_capacity, node_capacity) {
        restart_hub(hub_capacity);
    }

    std::optional<gs::EventKey> motion(const std::string& location = "room") {
        return node.record(gs::EventKind::Motion, location, clock.now,
                           clock.now / 1000, 0, 3800, true, gs::SensorType::Pir, -55);
    }

    AttemptResult attempt(const DeliveryFault& fault = {}) {
        AttemptResult result;
        const auto message = node.next_message(clock.now);
        if (!message) return result;
        result.attempted = true;
        result.key = {message->node_id, message->session_id, message->sequence_number};
        node.transport_result(result.key, fault.mac_success, clock.now);
        if (!fault.mac_success || fault.packet_lost || !hub_online_) return result;
        result.hub_admitted = hub_->radio_message_callback(*message, clock.now / 1000);
        require(result.hub_admitted, "production HubRuntime rejected delivered message");
        auto processed = hub_->run_state_once();
        require(processed.has_value(), "delivered message was not processed");
        result.state_changed = processed->state_changed;
        if (fault.duplicate_packet) {
            require(hub_->radio_message_callback(*message, clock.now / 1000),
                    "duplicate packet should be admitted for journal dedupe");
            const auto duplicate = hub_->run_state_once();
            require(duplicate && duplicate->ack == gs::AckClass::Durable &&
                    !duplicate->state_changed, "duplicate must receive durable idempotent ACK");
        }
        if (!fault.ack_lost) {
            result.acked = node.acknowledge(result.key, processed->ack);
            if (fault.duplicate_ack) {
                require(!node.acknowledge(result.key, processed->ack),
                        "duplicate ACK must not retire a second event");
            }
        }
        return result;
    }

    void restart_hub(std::size_t capacity = 1024) {
        hub_ = std::make_unique<gs::hub::HubRuntime>(32, capacity);
        hub_->authorize_node(node_id_, session_, true);
        hub_online_ = true;
    }
    void set_hub_online(bool online) { hub_online_ = online; }
    gs::hub::HubRuntime& hub() { return *hub_; }

    VirtualClock clock;
    gs::node::NodeRuntime node;

};

gs::Milliseconds first_retry_at(std::uint64_t sequence, gs::Milliseconds sent_at = 0) {
    return sent_at + gs::NodeProtocolPolicy::retry_delays_ms[0] +
           static_cast<gs::Milliseconds>((sequence * 37U) %
               (static_cast<std::uint64_t>(gs::NodeProtocolPolicy::retry_jitter_max_ms) + 1U));
}

void prepare_retry(RuntimePair& pair, bool mac_success = false) {
    const auto key = pair.motion();
    require(key.has_value(), "fixture motion was not admitted");
    const auto first = pair.attempt({mac_success, !mac_success, false, true, false});
    require(first.attempted, "initial attempt missing");
    pair.clock.now = first_retry_at(key->sequence);
}

class AcceptingVerifier final : public gs::SignatureVerifier {
public:
    bool verify(const std::string&, const std::string& signature) const override {
        return signature == "valid";
    }
};

std::vector<TestCase> catalog() {
    std::vector<TestCase> tests;
    auto add = [&](std::string id, std::string suite, std::string feature, TestBody body) {
        tests.push_back({std::move(id), std::move(suite), std::move(feature), std::move(body)});
    };

    add("C3-SMOKE-001", "C3_SMOKE", "sensing-to-durable-retirement", [] {
        gs::node::QualifiedInput pir(gs::EventKind::Motion, std::nullopt, 25, 1000);
        require(!pir.sample(false, 0) && !pir.sample(true, 10), "PIR startup/debounce failed");
        require(pir.sample(true, 35) == gs::EventKind::Motion, "qualified motion missing");
        RuntimePair pair;
        const auto key = pair.motion();
        require(key && key->session_id == 7 && key->sequence == 1, "invalid initial identity");
        const auto result = pair.attempt();
        require(result.acked && pair.node.pending() == 0 && pair.node.persisted() == 0,
                "smoke event did not retire durably");
    });
    add("HUB-SMOKE-001", "HUB_SMOKE", "receive-process-dedupe-ack", [] {
        RuntimePair pair;
        require(pair.motion().has_value(), "motion admission failed");
        const auto result = pair.attempt({true, false, true, false, false});
        require(result.hub_admitted && result.state_changed && result.acked,
                "Hub smoke path failed");
        require(pair.hub().journal().size() == 1, "duplicate changed journal cardinality");
    });
    add("SYSTEM-SMOKE-001", "SYSTEM_SMOKE", "synthetic-motion-node-hub", [] {
        RuntimePair pair;
        require(pair.motion("kitchen"), "synthetic motion failed");
        require(pair.attempt().acked, "end-to-end application ACK failed");
    });

    add("OR-001", "OFFLINE_RESILIENCE", "normal-online-delivery", [] {
        RuntimePair p; require(p.motion(), "motion rejected"); require(p.attempt().acked, "online delivery failed");
    });
    add("OR-002", "OFFLINE_RESILIENCE", "hub-disappears-node-operational", [] {
        RuntimePair p; p.set_hub_online(false); require(p.motion(), "node stopped with Hub absent");
        require(p.attempt().attempted && p.node.persisted() == 1, "offline event not retained");
    });
    add("OR-003", "OFFLINE_RESILIENCE", "offline-motion-acceptance", [] {
        RuntimePair p; p.set_hub_online(false); require(p.motion(), "offline motion not accepted");
    });
    add("OR-004", "OFFLINE_RESILIENCE", "multiple-offline-events", [] {
        RuntimePair p; p.set_hub_online(false); for (int i=0;i<8;++i) require(p.motion(), "offline burst rejected");
        require(p.node.pending()==8 && p.node.persisted()==8, "offline burst count mismatch");
    });
    add("OR-005", "OFFLINE_RESILIENCE", "retention-while-undeliverable", [] {
        RuntimePair p; prepare_retry(p); require(p.node.persisted()==1 && p.node.pending()==1, "event was not retained");
    });
    add("OR-006", "OFFLINE_RESILIENCE", "in-flight-coherence-after-failure", [] {
        RuntimePair p; prepare_retry(p); require(p.node.oldest_pending_key().has_value() && p.node.persisted()==p.node.pending(), "store/retry mismatch");
    });
    add("OR-007", "OFFLINE_RESILIENCE", "first-retry-stage", [] {
        RuntimePair p; const auto key=p.motion(); require(key,"motion rejected"); require(p.attempt({false,true,false,true,false}).attempted,"attempt missing");
        p.clock.now=first_retry_at(key->sequence)-1; require(!p.attempt().attempted,"retry early"); p.clock.advance(1); require(p.attempt({false,true,false,true,false}).attempted,"retry not due");
    });
    add("OR-008", "OFFLINE_RESILIENCE", "subsequent-retry-stages", [] {
        RuntimePair p; const auto key=p.motion(); require(key,"motion rejected");
        p.attempt({false,true,false,true,false}); auto now=first_retry_at(key->sequence); p.clock.now=now; p.attempt({false,true,false,true,false});
        const auto jitter=static_cast<gs::Milliseconds>((key->sequence*37U)%(gs::NodeProtocolPolicy::retry_jitter_max_ms+1U));
        p.clock.now=now+gs::NodeProtocolPolicy::retry_delays_ms[1]+jitter; require(p.attempt({false,true,false,true,false}).attempted,"second retry absent");
    });
    add("OR-009", "OFFLINE_RESILIENCE", "periodic-offline-backoff", [] {
        RuntimePair p; const auto key=p.motion(); require(key,"motion rejected"); gs::Milliseconds now=0;
        for(std::size_t i=0;i<8;++i){p.clock.now=now; require(p.attempt({false,true,false,true,false}).attempted,"backoff attempt absent"); const auto idx=std::min(i,gs::NodeProtocolPolicy::retry_delays_ms.size()-1); now+=gs::NodeProtocolPolicy::retry_delays_ms[idx]+37;}
        require(p.node.radio_stats().periodic_backoff_entries==1,"periodic backoff not entered once");
    });
    add("OR-010", "OFFLINE_RESILIENCE", "mac-failure-retry", [] { RuntimePair p; prepare_retry(p); require(p.attempt().acked,"MAC failure did not recover"); });
    add("OR-011", "OFFLINE_RESILIENCE", "ack-loss-retry", [] {
        RuntimePair p; const auto key=p.motion(); require(key,"motion rejected"); require(!p.attempt({true,false,false,true,false}).acked,"ACK unexpectedly delivered"); p.clock.now=first_retry_at(key->sequence); require(p.attempt().acked,"ACK-loss retry failed");
    });
    add("OR-012", "OFFLINE_RESILIENCE", "mac-success-without-app-ack", [] {
        RuntimePair p; const auto key=p.motion(); require(key,"motion rejected"); p.attempt({true,false,false,true,false}); require(p.node.persisted()==1,"MAC success retired evidence");
    });
    add("OR-013", "OFFLINE_RESILIENCE", "duplicate-transmission", [] {
        RuntimePair p; require(p.motion(),"motion rejected"); require(p.attempt({true,false,true,false,false}).acked,"duplicate path failed"); require(p.hub().journal().size()==1,"duplicate journaled twice");
    });
    add("OR-014", "OFFLINE_RESILIENCE", "duplicate-ack", [] { RuntimePair p; require(p.motion(),"motion rejected"); require(p.attempt({true,false,false,false,true}).acked,"first ACK failed"); });
    add("OR-015", "OFFLINE_RESILIENCE", "same-session-replay", [] {
        RuntimePair p; const auto key=p.motion(); require(key,"motion rejected"); const auto message=p.node.next_message(0); require(message,"message absent"); require(p.attempt().acked,"initial failed");
        require(p.hub().radio_message_callback(*message,1),"replay rejected before dedupe"); const auto replay=p.hub().run_state_once(); require(replay && !replay->state_changed,"replay changed state");
    });
    add("OR-016", "OFFLINE_RESILIENCE", "hub-restart-node-alive", [] {
        RuntimePair p; const auto key=p.motion(); require(key,"motion rejected"); p.attempt({true,false,false,true,false}); p.restart_hub(); p.clock.now=first_retry_at(key->sequence); require(p.attempt().acked,"Hub restart recovery failed");
    });
    add("OR-017", "OFFLINE_RESILIENCE", "hub-restoration", [] { RuntimePair p; p.set_hub_online(false); prepare_retry(p); p.set_hub_online(true); require(p.attempt().acked,"restoration failed"); });
    add("OR-018", "OFFLINE_RESILIENCE", "recovery-without-node-reboot", [] {
        RuntimePair p("n",99); p.set_hub_online(false); const auto key=p.motion(); require(key,"motion rejected"); p.attempt({false,true,false,true,false}); p.set_hub_online(true); p.clock.now=first_retry_at(1); require(p.attempt().acked && key->session_id==99,"session changed during recovery");
    });
    add("OR-019", "OFFLINE_RESILIENCE", "backlog-delivery", [] {
        RuntimePair p; p.set_hub_online(false); for(int i=0;i<10;++i) require(p.motion(),"backlog admission failed"); p.set_hub_online(true); p.clock.now=100000;
        while(p.node.pending()) { require(p.attempt().acked,"backlog item failed"); }
        require(p.node.persisted()==0,"backlog store not empty");
    });
    add("OR-020", "OFFLINE_RESILIENCE", "durable-ack-retirement", [] { RuntimePair p; require(p.motion(),"motion rejected"); require(p.attempt().acked && p.node.stats().durable_acks==1,"durable retirement counter wrong"); });
    add("OR-021", "OFFLINE_RESILIENCE", "final-drain", [] { RuntimePair p; for(int i=0;i<4;++i) require(p.motion(),"motion rejected"); while(p.node.pending()) require(p.attempt().acked,"drain failed"); require(!p.node.oldest_pending_key() && p.node.persisted()==0,"final state not idle"); });
    add("OR-022", "OFFLINE_RESILIENCE", "motion-prolonged-outage", [] { RuntimePair p; p.set_hub_online(false); for(int i=0;i<28;++i){p.clock.advance(6*60*60*1000/28); require(p.motion(),"qualified capacity unexpectedly rejected");} require(p.node.pending()==28,"prolonged outage count wrong"); });
    add("OR-023", "OFFLINE_RESILIENCE", "motion-during-drain", [] { RuntimePair p; for(int i=0;i<6;++i) require(p.motion(),"seed backlog failed"); require(p.attempt().acked,"first drain failed"); require(p.motion("hall"),"new drain-time event failed"); while(p.node.pending()) require(p.attempt().acked,"drain failed"); require(p.hub().journal().size()==7,"event lost during drain"); });
    add("OR-024", "OFFLINE_RESILIENCE", "multiple-outage-cycles", [] { RuntimePair p; for(int i=0;i<20;++i){p.set_hub_online(false); const auto key=p.motion(); require(key,"motion rejected"); p.attempt({false,true,false,true,false}); p.set_hub_online(true); p.clock.now=first_retry_at(key->sequence,p.clock.now); require(p.attempt().acked,"cycle recovery failed");} });
    add("OR-025", "OFFLINE_RESILIENCE", "six-hour-virtual-outage", [] { RuntimePair p; p.set_hub_online(false); const auto key=p.motion(); require(key,"motion rejected"); p.attempt({false,true,false,true,false}); p.clock.advance(6*60*60*1000); require(p.attempt({false,true,false,true,false}).attempted,"six-hour logical retry absent"); });
    add("OR-026", "OFFLINE_RESILIENCE", "deterministic-retry-jitter", [] {
        RuntimePair first; const auto key1=first.motion(); require(key1 && key1->sequence==1,"sequence one missing");
        require(first.attempt({false,true,false,true,false}).attempted,"initial sequence-one attempt missing");
        first.clock.now=236; require(!first.attempt().attempted,"sequence-one retry early");
        first.clock.now=237; require(first.attempt({false,true,false,true,false}).attempted,"sequence-one retry boundary changed");
        RuntimePair second; require(second.motion(),"first setup event missing"); require(second.attempt().acked,"first setup event failed");
        const auto key2=second.motion(); require(key2 && key2->sequence==2,"sequence two missing");
        require(second.attempt({false,true,false,true,false}).attempted,"initial sequence-two attempt missing");
        second.clock.now=273; require(!second.attempt().attempted,"sequence-two retry early");
        second.clock.now=274; require(second.attempt({false,true,false,true,false}).attempted,"sequence-two retry boundary changed");
    });
    add("OR-027", "OFFLINE_RESILIENCE", "session-identity", [] { RuntimePair p("identity",123); const auto key=p.motion(); require(key && key->source_id=="identity" && key->session_id==123,"session identity invalid"); const auto r=p.attempt(); require(r.key.session_id==123,"session not preserved"); });
    add("OR-028", "OFFLINE_RESILIENCE", "sequence-identity", [] { RuntimePair p; for(std::uint64_t i=1;i<=5;++i){const auto key=p.motion(); require(key && key->sequence==i,"sequence not monotonic");} });
    add("OR-029", "OFFLINE_RESILIENCE", "no-simulated-node-reset", [] { RuntimePair p("stable",55); for(int i=0;i<10;++i){require(p.motion(),"motion rejected"); require(p.attempt().acked,"delivery failed");} require(p.node.next_sequence()==11,"runtime reset/progress loss observed"); });
    add("OR-030", "OFFLINE_RESILIENCE", "no-motion-drop-qualified-load", [] { RuntimePair p; for(int i=0;i<28;++i) require(p.motion(),"qualified motion rejected"); require(p.node.stats().dropped_motion==0,"motion_drop nonzero"); });
    add("OR-031", "OFFLINE_RESILIENCE", "no-store-full-qualified-load", [] { RuntimePair p; for(int i=0;i<28;++i) require(p.motion(),"qualified motion rejected"); require(p.node.stats().store_full==0,"store_full nonzero"); });
    add("OR-032", "OFFLINE_RESILIENCE", "no-priority-rejection-qualified-load", [] { RuntimePair p; for(int i=0;i<28;++i) require(p.motion(),"motion rejected"); for(int i=0;i<4;++i) require(p.node.record(gs::EventKind::CallFamily,"room",i,0),"priority rejected"); require(p.node.stats().priority_rejected==0,"priority_rejected nonzero"); });
    add("OR-033", "OFFLINE_RESILIENCE", "node-health-online-offline-recovery", [] {
        RuntimePair p("n",1); p.set_hub_online(false); const auto key=p.motion(); require(key,"offline health setup failed");
        p.attempt({false,true,false,true,false}); p.clock.now=first_retry_at(key->sequence); p.set_hub_online(true);
        require(p.attempt().acked,"health recovery delivery failed");
        gs::NodeHealthSnapshot h; h.node_id="n";h.session_id=1;h.health_sequence=3;h.sensing_liveness=9;h.runtime_liveness=10;
        h.retained_count=static_cast<std::uint16_t>(p.node.persisted());h.retries=p.node.radio_stats().retries;
        h.periodic_backoff_entries=p.node.radio_stats().periodic_backoff_entries;h.durable_acks=p.node.stats().durable_acks;
        const auto encoded=gs::transport::encode_node_health(h); require(encoded,"health encode failed");
        const auto decoded=gs::transport::decode_node_health(encoded.frame.bytes.data(),encoded.frame.size);
        require(decoded && decoded.value->retained_count==0 && decoded.value->retries>=1 && decoded.value->durable_acks==1,
                "production recovery counters were not preserved by NodeHealth");
    });
    add("OR-034", "OFFLINE_RESILIENCE", "recovery-cycle-resource-bounds", [] { RuntimePair p; for(int cycle=0;cycle<200;++cycle){p.set_hub_online(false); const auto key=p.motion(); require(key,"bounded cycle admission failed"); p.attempt({false,true,false,true,false}); p.set_hub_online(true); p.clock.now=first_retry_at(key->sequence,p.clock.now); require(p.attempt().acked,"cycle drain failed"); require(p.node.pending()==0 && p.node.persisted()==0,"progressive retained growth");} });
    add("OR-035", "OFFLINE_RESILIENCE", "qualified-resilience-invariants", [] {
        RuntimePair p; p.set_hub_online(false); for(int i=0;i<28;++i) require(p.motion(),"qualified backlog rejected"); require(!p.motion(),"reserve boundary not enforced"); p.set_hub_online(true); p.clock.now=600000; while(p.node.pending()) require(p.attempt().acked,"qualified backlog recovery failed"); require(p.node.persisted()==0,"qualified final drain failed");
    });

    add("FOTA-PROTOCOL-001", "C3_FOTA", "chunk-crc-and-wire-bounds", [] {
        std::vector<std::uint8_t> image(513); for(std::size_t i=0;i<image.size();++i) image[i]=static_cast<std::uint8_t>(i);
        const auto whole=gs::fota::crc32(image.data(),image.size()); std::uint32_t running=0xFFFFFFFFU;
        running=gs::fota::crc32_update(running,image.data(),200); running=gs::fota::crc32_update(running,image.data()+200,image.size()-200);
        require((running^0xFFFFFFFFU)==whole,"incremental image CRC differs"); require(sizeof(gs::fota::Packet)<=250 && gs::fota::kChunkBytes==200,"FOTA wire bounds changed");
    });
    add("FOTA-POLICY-001", "C3_FOTA", "version-target-signature-policy", [] {
        AcceptingVerifier verifier; gs::security::UpdatePolicy policy(verifier);
        require(policy.validate({"esp32-c3",2,std::string(64,'a'),"valid"},"esp32-c3",1).accepted,"valid update rejected");
        require(!policy.validate({"esp32",2,std::string(64,'a'),"valid"},"esp32-c3",1).accepted,"wrong target accepted");
        require(!policy.validate({"esp32-c3",1,std::string(64,'a'),"valid"},"esp32-c3",1).accepted,"same version accepted");
        require(!policy.validate({"esp32-c3",2,std::string(64,'a'),"bad"},"esp32-c3",1).accepted,"bad signature accepted");
    });

    add("PROTO-ROBUST-001", "PROTOCOL", "malformed-node-message", [] {
        gs::NodeMessage m; m.node_id="n";m.session_id=1;m.sequence_number=1;m.sensor_type=gs::SensorType::Pir;m.event_type=gs::EventKind::Motion;m.location="r";
        const auto encoded=gs::transport::encode_node_message(m); require(encoded,"valid message failed");
        require(gs::transport::decode_node_message(encoded.frame.bytes.data(),encoded.frame.size-1).error==gs::transport::CodecError::Truncated,"truncation accepted");
        auto bad=encoded.frame;bad.bytes[0]^=1;require(gs::transport::decode_node_message(bad.bytes.data(),bad.size).error==gs::transport::CodecError::BadMagic,"bad magic accepted");
    });
    add("QUEUE-BOUNDARY-001", "C3_COMPLETE", "queue-empty-one-near-full-full-drain", [] {
        RuntimePair p; require(p.node.pending()==0,"queue not empty"); for(int i=0;i<28;++i) require(p.motion(),"near-full admission failed"); require(!p.motion(),"motion overflow accepted"); for(int i=0;i<4;++i) require(p.node.record(gs::EventKind::CallFamily,"r",0,0),"reserve admission failed"); require(!p.node.record(gs::EventKind::DoorOpen,"r",0,0),"full overflow accepted"); while(p.node.pending()) require(p.attempt().acked,"drain failed"); require(p.node.pending()==0,"queue not drained");
    });
    add("RESTART-001", "RESTART_RECOVERY", "hub-restart-with-inflight", [] {
        RuntimePair p; const auto key=p.motion();require(key,"motion rejected");p.attempt({true,false,false,true,false});p.restart_hub();p.clock.now=first_retry_at(key->sequence);require(p.attempt().acked,"inflight recovery failed");
    });
    add("C3-STRESS-001", "C3_STRESS", "deterministic-outage-storm", [] {
        RuntimePair p; p.set_hub_online(false); for(int i=0;i<5000;++i){p.clock.advance(10);(void)p.motion();(void)p.attempt({false,true,false,true,false});}
        require(p.node.pending()<=32 && p.node.persisted()==p.node.pending(),"stress bounds/invariant failed");
        require(p.node.stats().accepted+p.node.stats().dropped_motion==5000 && p.node.next_sequence()==5001,
                "stress event accounting/identity progress failed");
        require(p.node.radio_stats().transport_results>0 && p.node.stats().store_full==0,"stress retry/admission counters invalid");
    });
    add("HUB-STRESS-001", "HUB_STRESS", "duplicate-volume", [] {
        RuntimePair p; for(int i=0;i<1000;++i){require(p.motion(),"motion rejected");require(p.attempt({true,false,true,false,false}).acked,"duplicate load failed");}
        require(p.hub().journal().size()==1000 && p.node.stats().durable_acks==1000,"Hub stress identity/ACK count wrong");
        require(p.node.pending()==0 && p.node.persisted()==0,"Hub duplicate stress did not retire node state");
    });
    add("SYSTEM-STRESS-001", "SYSTEM_STRESS", "fixed-seed-chaos", [] {
        RuntimePair p; std::uint32_t state=0x5A17U; for(int i=0;i<500;++i){state=state*1664525U+1013904223U; p.set_hub_online((state&7U)!=0U); (void)p.motion(); auto f=DeliveryFault{};f.mac_success=(state&1U)!=0U;f.packet_lost=(state&2U)!=0U;f.ack_lost=(state&4U)!=0U;(void)p.attempt(f);p.clock.advance(60000);} p.set_hub_online(true);p.clock.advance(6*60*60*1000);while(p.node.pending()) require(p.attempt().acked,"chaos final drain failed");
        require(p.node.persisted()==0 && p.node.pending()==0,"chaos retained leak");
        require(p.node.stats().durable_acks==p.node.stats().accepted && p.hub().journal().size()==p.node.stats().accepted,
                "chaos final event/ACK accounting mismatch");
        require(p.node.radio_stats().retries>0,"chaos fault mix did not exercise retry");
    });
    add("C3-STABILITY-001", "C3_STABILITY", "long-logical-runtime", [] { RuntimePair p("node-1",7,32,20000); for(int i=0;i<10000;++i){p.clock.advance(2160);require(p.motion(),"stability admission failed");require(p.attempt().acked,"stability delivery failed");}require(p.node.pending()==0 && p.node.persisted()==0,"C3 stability growth");require(p.node.stats().accepted==10000 && p.node.stats().durable_acks==10000 && p.node.next_sequence()==10001,"C3 stability accounting/identity mismatch"); });
    add("HUB-STABILITY-001", "HUB_STABILITY", "repeated-processing", [] { RuntimePair p("node-1",7,32,10000); for(int i=0;i<5000;++i){require(p.motion(),"motion rejected");require(p.attempt().acked,"processing failed");}require(p.hub().journal().size()==5000,"Hub stability journal mismatch");require(p.node.pending()==0 && p.node.stats().durable_acks==5000,"Hub stability ACK/final-state mismatch"); });
    add("SYSTEM-SOAK-001", "SYSTEM_SOAK", "virtual-six-hour-mixed-load", [] { RuntimePair p; for(int minute=0;minute<360;++minute){p.clock.advance(60000);p.set_hub_online((minute%37)>2);(void)p.motion();(void)p.attempt({true,false,false,(minute%11)==0,false});}p.set_hub_online(true);p.clock.advance(3600000);while(p.node.pending())require(p.attempt().acked,"soak final drain failed");require(p.node.persisted()==0 && p.node.pending()==0,"soak retained growth");require(p.node.stats().durable_acks==p.node.stats().accepted && p.hub().journal().size()==p.node.stats().accepted,"soak event/ACK accounting mismatch");require(p.node.radio_stats().retries>0,"soak did not exercise recovery"); });
    return tests;
}

}  // namespace

int main(int argc, char** argv) {
    std::string selected_id;
    std::string selected_suite;
    bool list = false;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--list") list = true;
        else if (arg == "--id" && i + 1 < argc) selected_id = argv[++i];
        else if (arg == "--suite" && i + 1 < argc) selected_suite = argv[++i];
        else { std::cerr << "usage: master_validation [--list] [--id ID] [--suite SUITE]\n"; return 2; }
    }
    const auto tests = catalog();
    if (list) {
        for (const auto& test : tests) std::cout << test.id << '\t' << test.suite << '\t' << test.feature << '\n';
        return 0;
    }
    std::size_t selected = 0;
    std::size_t failed = 0;
    const char* injection = std::getenv("GS_VALIDATION_INJECT_FAILURE");
    for (const auto& test : tests) {
        if (!selected_id.empty() && test.id != selected_id) continue;
        if (!selected_suite.empty() && test.suite != selected_suite) continue;
        ++selected;
        const auto started = std::chrono::steady_clock::now();
        try {
            test.body();
            if (injection && test.id == injection) fail("controlled validation self-test failure");
            const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - started).count();
            std::cout << "PASS\t" << test.id << '\t' << test.suite << '\t' << elapsed
                      << '\t' << test.feature << "\t\n";
        } catch (const std::exception& error) {
            ++failed;
            const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - started).count();
            std::cout << "FAIL\t" << test.id << '\t' << test.suite << '\t' << elapsed
                      << '\t' << test.feature << '\t' << error.what() << '\n';
        }
    }
    if (selected == 0) { std::cerr << "no tests matched selection\n"; return 2; }
    std::cout << "SUMMARY\t" << selected << '\t' << (selected - failed) << '\t' << failed << "\tseed=23063\n";
    return failed == 0 ? 0 : 1;
}
