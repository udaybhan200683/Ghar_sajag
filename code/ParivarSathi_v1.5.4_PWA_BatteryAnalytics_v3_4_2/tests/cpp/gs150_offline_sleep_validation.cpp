// GS-150 deterministic owner/transport simulation using production policy,
// NodeRuntime, encrypted recovery, AEAD/rejoin, persistent HubRuntime and PIR.
// RF/flash/OS costs are explicit model inputs, never physical measurements.
#include "power/power.hpp"
#include "power/session_recovery_policy.hpp"
#include "sensing/sensing.hpp"
#include "firmware/node/runtime/node_runtime.hpp"
#include "firmware/node/components/storage/node_recovery_persistence.hpp"
#include "firmware/node/target/esp32c3/node_target_config.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/common/security/runtime_frame_security.hpp"
#include "firmware/common/security/rejoin_protocol.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"
#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <memory>
#include <map>
#include <stdexcept>
#include <vector>

using namespace gs;
using namespace gs::node;
using namespace gs::security;
using gs::host::security::OpenSslCommissioningCrypto;
namespace {
unsigned checks = 0;
void require(bool yes, const char* message) {
    ++checks;
    if (!yes) throw std::runtime_error(message);
}
struct Blob : SecurityBlobStore {
    Bytes data;
    unsigned writes = 0;
    bool fail = false;
    bool read(Bytes& out, bool& found) override { out = data; found = !data.empty(); return true; }
    bool write(const Bytes& in) override {
        if (fail) return false;
        data = in; ++writes; return true;
    }
};
struct Slots : hub::JournalSlotStore {
    std::array<Bytes, 128> data;
    bool read(std::size_t slot, Bytes& out, bool& found) override {
        if (slot >= data.size()) return false;
        out = data[slot]; found = !out.empty(); return true;
    }
    bool write(std::size_t slot, const Bytes& in) override {
        if (slot >= data.size()) return false;
        data[slot] = in; return true;
    }
};
struct Pair {
    OpenSslCommissioningCrypto crypto;
    CommissioningBinding binding;
    Key32 key{};
    Blob blob;
    Slots slots;
    std::unique_ptr<NodeRecoveryRepository> repository;
    std::unique_ptr<NodeRuntime> node;
    std::unique_ptr<hub::HubRuntime> hub;
    std::unique_ptr<RuntimeFrameSecurity> nf, hf;
    std::uint64_t session = 10;
    Pair() {
        binding.device_id = "device"; binding.logical_id = "room";
        binding.home_id = "home"; binding.hub_id = "hub";
        binding.installation_key.fill(9); key.fill(7);
        repository = std::make_unique<NodeRecoveryRepository>(crypto, blob, key, "home", "hub", "room");
        node = std::make_unique<NodeRuntime>("room", session);
        nf = std::make_unique<RuntimeFrameSecurity>(crypto, binding);
        hf = std::make_unique<RuntimeFrameSecurity>(crypto, binding);
        reboot_hub();
        rejoin(session);
    }
    void reboot_hub() {
        hub = std::make_unique<hub::HubRuntime>(32, 128);
        RoutineConfig config; config.window_id = "day"; config.end_at = 2000000000;
        hub->authorize_node("room", session, true);
        hub->start_window(config, HomeMode::Home);
        require(hub->journal().attach_persistence(crypto, slots, key), "Hub journal recovery");
        require(hub->restore_from_journal(), "Hub reducer recovery");
    }
    void rejoin(std::uint64_t next) {
        NodeRejoin nr(crypto, binding, next, 2);
        HubRejoin hr(crypto, binding, next - 1);
        const auto hello = nr.begin();
        require(hello.has_value(), "rejoin Hello");
        const auto challenge = hr.accept(*hello);
        require(challenge.has_value(), "authenticated challenge");
        const auto final = nr.accept(*challenge);
        require(final.has_value(), "bound Final");
        const auto ack = hr.confirm(*final);
        require(ack && nr.commit(*ack), "authenticated session installation");
        require(nf->start(next, *nr.session_salt()) && hf->start(next, *hr.session_salt()), "fresh AEAD contexts");
        session = next; hub->authorize_node("room", session, true);
    }
    EventKey admit(EventKind kind, Milliseconds now) {
        const auto k = node->record(kind, "room", now, 1700000000 + now / 1000);
        require(k.has_value(), "event admission");
        require(repository->save(node->recovery_snapshot()), "durable before exposure");
        return *k;
    }
    SecureFrame deliver(const NodeMessage& msg, Milliseconds now, bool& changed) {
        const auto encoded = transport::encode_node_message(msg);
        SecureFrame wire;
        transport::EncodedFrame opened;
        require(encoded && nf->seal(RuntimeDirection::Uplink, encoded.frame, wire) &&
                hf->open(RuntimeDirection::Uplink, wire, opened), "authenticated new frame for exact-key replay");
        const auto decoded = transport::decode_node_message(opened.bytes.data(), opened.size);
        require(decoded && hub->authenticated_radio_message_callback(*decoded.value,
            "room", "device", session, 1700000000 + now / 1000,
            static_cast<std::uint64_t>(now)), "authenticated owner admission");
        const auto processed = hub->run_state_once();
        require(processed && processed->ack == AckClass::Durable, "durable before application ACK");
        changed = processed->state_changed;
        NodeAckMessage ack; ack.node_id=msg.node_id; ack.session_id=msg.session_id;
        ack.sequence_number=msg.sequence_number; ack.ack_type=processed->ack;
        const auto reply = transport::encode_node_ack(ack);
        SecureFrame protected_ack;
        require(reply && hf->seal(RuntimeDirection::Downlink, reply.frame, protected_ack), "seal Durable ACK");
        return protected_ack;
    }
    bool ack(const SecureFrame& wire) {
        transport::EncodedFrame plain;
        if (!nf->open(RuntimeDirection::Downlink, wire, plain)) return false;
        const auto decoded = transport::decode_node_ack(plain.bytes.data(), plain.size);
        if (!decoded) return false;
        EventKey k{decoded.value->node_id, decoded.value->session_id, decoded.value->sequence_number};
        if (!node->acknowledge(k, decoded.value->ack_type)) return false;
        require(repository->save(node->recovery_snapshot()), "durable ACK retirement");
        return true;
    }
    void reboot_node(Milliseconds now) {
        const auto saved = repository->load();
        require(saved.state.has_value(), "load encrypted pending snapshot");
        const auto next = session + 1;
        node = std::make_unique<NodeRuntime>("room", next);
        require(node->restore_recovery(*saved.state, now), "Node reboot retains original identity");
        require(repository->save(node->recovery_snapshot()), "new boot snapshot");
        rejoin(next);
    }
};
LightSleepObservation observation(Milliseconds now) {
    LightSleepObservation o;
    o.now_ms = now; o.next_health_ms = now + 120000;
    o.authenticated = o.product_ready = o.persistence_clean = true;
    o.pir_high = false; o.pir_low_stable = o.debounce_safe = true;
    o.wake_source_ready = o.runtime_state_known = true;
    return o;
}
void policy_matrix() {
    AckListeningWindow window;
    require(AckListeningWindow::receive_budget_ms == 300, "budget derives from 200 + 100, never MAC timeout");
    window.application_transport_completed(1000, false);
    for (int pending : {0, 1, 8, 32}) {
        auto o = observation(10999); o.next_retry_ms = 61000; o.outage_active = true;
        observe_retained_delivery(o, window, pending != 0, pending != 0);
        require(!evaluate_light_sleep(o).eligible, "awake through required RX budget");
        o = observation(11000); o.next_retry_ms = 61000; o.outage_active = true;
        observe_retained_delivery(o, window, pending != 0, pending != 0);
        require(evaluate_light_sleep(o).eligible, "confirmed outage committed backlog can sleep after boundary");
        o.event_in_flight = true;
        require(!evaluate_light_sleep(o).eligible, "MAC success/failure/timeout must complete before sleep");
    }
    AckListeningWindow quiet; quiet.application_transport_completed(0, false);
    window = quiet;
    auto o = observation(12000); o.next_retry_ms = 61000;
    observe_retained_delivery(o, window, true, true);
    require(!evaluate_light_sleep(o).eligible, "connected and transient failures retain continuous ACK reception");
    o = observation(12000); o.outage_active = true;
    observe_retained_delivery(o, window, true, true);
    require(!evaluate_light_sleep(o).eligible, "unknown pending retry fails awake");
    window.application_transport_completed(0, true);
    o = observation(12000); o.next_retry_ms=61000; o.outage_active=true;
    observe_retained_delivery(o, window, true, true);
    require(!evaluate_light_sleep(o).eligible, "MAC success only inhibits sleep; slow ACK cannot be starved");
    window.authenticated_progress(false);
    require(!window.active(12000), "verified progress after application budget");
    window.application_transport_completed(0, false);
    using Set = void(*)(LightSleepObservation&);
    const std::vector<Set> blockers{
        [](auto& x){x.fota_active = true;}, [](auto& x){x.maintenance_active = true;},
        [](auto& x){x.boot_health_active = true;}, [](auto& x){x.persistence_clean = false;},
        [](auto& x){x.recovery_work = true;}, [](auto& x){x.other_owner_work = true;},
        [](auto& x){x.pir_high = true;}, [](auto& x){x.pir_low_stable = false;},
        [](auto& x){x.debounce_safe = false;}, [](auto& x){x.runtime_state_known = false;},
        [](auto& x){x.wake_source_ready = false;}, [](auto& x){x.health_due = true;},
        [](auto& x){x.security_due = true;}, [](auto& x){x.event_in_flight = true;}};
    for (const auto block : blockers) {
        o = observation(12000); o.next_retry_ms = 61000; o.outage_active = true;
        observe_retained_delivery(o, window, true, true); block(o);
        require(!evaluate_light_sleep(o).eligible, "critical/security/storage/radio/GPIO safety inhibitors preserved");
    }
    for (Milliseconds due : {11900, 12000, 12499, 12999}) {
        o = observation(12000); o.next_retry_ms = due; o.outage_active = true;
        observe_retained_delivery(o, window, true, true);
        require(!evaluate_light_sleep(o).eligible, "expired or too close deadline cannot sleep");
    }
    o = observation(12000); o.next_retry_ms = 61000; o.outage_active = true;
    o.next_radio_ms = 17000;
    observe_retained_delivery(o, window, true, true);
    require(evaluate_light_sleep(o).requested_sleep_ms == 4500, "retirement report deadline bounds sleep");
    o.next_security_ms = 14000;
    require(evaluate_light_sleep(o).requested_sleep_ms == 1500, "active contact recovery deadline bounds sleep");
    window = AckListeningWindow{};
    window.require_until(5000);
    window.transport_completed(2500);
    require(window.active(4999) && !window.active(5000), "short callback cannot shorten security window");
    o = observation(4999); o.authenticated = false; o.rejoin_active = true;
    o.rejoin_backoff = !window.active(o.now_ms); o.next_security_ms = 65000;
    observe_retained_delivery(o, window, true, true);
    require(!evaluate_light_sleep(o).eligible, "active rejoin reception stays awake");
    o = observation(5000); o.authenticated = false; o.rejoin_active = true;
    o.rejoin_backoff = !window.active(o.now_ms); o.next_security_ms = 65000;
    observe_retained_delivery(o, window, true, true);
    require(evaluate_light_sleep(o).eligible, "quiet rejoin backoff sleeps without losing pending events");
    require(SessionRecoveryPolicy::active_deadline(true, 100, 3, 0) == 10100 &&
        !SessionRecoveryPolicy::active_deadline(false, 100, 3, 0) &&
        !SessionRecoveryPolicy::active_deadline(true, 100, 2, 0) &&
        !SessionRecoveryPolicy::active_deadline(true, 100, 3, 101), "existing active rejoin cutoff unchanged");
    QualifiedInput pir(EventKind::Motion, std::nullopt, 150, 1000);
    require(!pir.sample(false, 0) && pir.safe_for_sleep(150), "powered PIR baseline");
    require(!pir.sample(true, 200) && !pir.sample(false, 220) && !pir.sample(true, 240), "bounce does not admit");
    require(pir.sample(true, 400) == EventKind::Motion, "first wake qualified promptly");
    for (Milliseconds now = 420; now < 3000; now += 20)
        require(!pir.sample(true, now) && !pir.safe_for_sleep(now), "held HIGH neither repeats events nor sleep storms");
    require(!pir.sample(false, 3000) && !pir.sample(false, 3160) && pir.safe_for_sleep(3160), "motion does not stall after HIGH clears");
    require(!pir.sample(true, 4000) && pir.sample(true, 4160) == EventKind::Motion, "next motion works without power replug");
}
void authenticated_matrix() {
    Pair p;
    const auto k = p.admit(EventKind::Motion, 1000);
    auto msg = p.node->next_message(1000); require(msg.has_value(), "first immediate opportunity");
    bool changed = false;
    const auto missed = p.deliver(*msg, 1020, changed);
    require(changed, "first logical effect");
    p.node->set_outage_profile(true, 1020); p.node->transport_result(k, false, 1020);
    const auto deadline = p.node->next_retry_deadline();
    AckListeningWindow window; window.application_transport_completed(1020, false);
    auto o = observation(11020); o.next_retry_ms = *deadline; o.outage_active = true;
    observe_retained_delivery(o, window, true, true);
    require(evaluate_light_sleep(o).eligible && p.node->persisted() == 1, "ACK missed in sleep retains K");
    require(!p.node->acknowledge(k, AckClass::ReceivedVolatile) && p.node->persisted() == 1,
        "MAC/volatile ACK never retires business event");
    auto forged = missed; forged.bytes[forged.size - 1] ^= 1;
    require(!p.ack(forged) && p.node->persisted() == 1, "invalid authentication retains K");
    p.reboot_hub(); p.reboot_node(0);
    require(!p.ack(missed) && p.node->persisted() == 1, "old-session ACK cannot retire after rejoin");
    msg = p.node->next_message(0);
    require(msg && msg->session_id == k.session_id && msg->sequence_number == k.sequence &&
        msg->occurred_at == 1700000001, "Node reboot/rejoin preserves original event timestamp and EventKey");
    const auto duplicate = p.deliver(*msg, 20, changed);
    require(!changed && p.hub->journal().size() == 1 &&
        p.hub->routine_state().evidence_ids.size() == 1, "persistent Hub reboot dedupe never reapplies logical effect");
    auto wrong = p.binding; wrong.home_id = "foreign";
    RuntimeFrameSecurity foreign(p.crypto, wrong);
    Key32 salt{}; salt.fill(1); require(foreign.start(p.session, salt), "foreign owner context");
    NodeAckMessage wrong_payload; wrong_payload.node_id="room"; wrong_payload.session_id=k.session_id;
    wrong_payload.sequence_number=k.sequence; wrong_payload.ack_type=AckClass::Durable;
    const auto ack_payload = transport::encode_node_ack(wrong_payload);
    SecureFrame wrong_ack; require(foreign.seal(RuntimeDirection::Downlink, ack_payload.frame, wrong_ack), "foreign ACK fixture");
    require(!p.ack(wrong_ack) && p.node->pending() == 1, "wrong-owner ACK rejected");
    require(p.ack(duplicate) && p.node->pending() == 0 && p.node->persisted() == 0,
        "valid authenticated replay ACK retires durably");
    require(!p.ack(duplicate), "replayed frame has no false second completion");
    p.reboot_node(0); require(p.node->persisted() == 0, "retirement survives reboot");
    // Late authenticated reception while still awake remains legal; the budget
    // never expires the identity or rejects a valid application response.
    const auto late_key = p.admit(EventKind::CallFamily, 1000);
    msg = p.node->next_message(1000); require(msg.has_value(), "resident priority opportunity");
    const auto late = p.deliver(*msg, 1020, changed);
    p.node->transport_result(late_key, true, 1020);
    require(p.ack(late), "late ACK accepted outside listening budget whenever RX is awake");
    // Pressure/reserve/priority use the production 32-record contract.
    NodeRuntime pressure("pressure", 1);
    for (int i = 0; i < 28; ++i) require(pressure.record(EventKind::Motion, "r", i, i).has_value(), "ordinary reserve admission");
    require(!pressure.record(EventKind::Motion, "r", 29, 29), "reserve refuses ordinary overflow");
    pressure.set_outage_profile(true, 30);
    for (const auto kind : {EventKind::DoorOpen, EventKind::DoorClosed, EventKind::CallFamily, EventKind::OkPressed}) {
        const auto priority = pressure.record(kind, "r", 31, 31);
        require(priority.has_value(), "priority reserve protected");
        const auto first = pressure.next_message(31);
        require(first && first->sequence_number == priority->sequence, "resident/door urgent opportunity survives backlog");
        pressure.transport_result(*priority, false, 31);
    }
    require(pressure.pending() == 32 && !pressure.record(EventKind::CallFamily, "r", 32, 32), "bounded protocol limit remains honest");
    Blob failure; failure.fail = true;
    NodeRecoveryRepository bad(p.crypto, failure, p.key, "home", "hub", "room");
    require(!bad.save(p.node->recovery_snapshot()), "failed persistence cannot authorize sleep/send");
}

struct Scenario {
    std::string name;
    int initial = 0;
    Milliseconds return_ms = 0;
    Milliseconds ack_delay_ms = 40;
    bool lost_first_ack = false;
    bool health_ack = false;
    bool retirement = false;
    bool motion = false;
    bool critical = false;
    bool callback_missing = false;
    bool callback_failed = false;
    bool repeated_outage = false;
    Milliseconds horizon_ms = 360000;
};
struct Metrics {
    std::uint64_t loops=0, sleeps=0, timer=0, gpio=0, awake=0, listen=0;
    unsigned tx=0, retry=0, ack=0, missed=0, rejoin=0, admitted=0, retired=0, writes=0, effects=0, health=0, piggyback=0;
    Milliseconds first_latency=-1, ack_latency=-1, return_latency=-1, drain=-1;
};
struct Reply { Milliseconds due; SecureFrame wire; Milliseconds admitted; };
Metrics simulate(const Scenario& s, bool after) {
    Pair p; Metrics m; PowerPolicy power; AckListeningWindow window;
    NodeHealthCadence health(120000,120000);
    ActivityEpisode episode; QualifiedInput pir(EventKind::Motion,std::nullopt,150,1000);
    pir.sample(false,0);
    for (int i=0;i<s.initial;++i) { p.admit(EventKind::Motion,i); ++m.admitted; }
    std::optional<EventKey> inflight;
    Milliseconds callback_at=-1, first_attempt=-1, last_contact=0, rejoin_due=-1, rejoin_listen=-1;
    Milliseconds report_due=-1, report_callback=-1, first_admission=s.initial ? 0 : -1;
    unsigned attempts=0, rejoin_stage=0;
    bool ready=true, raw=false, report_active=false, important_done=false;
    bool hub_context_valid=s.name!="idle_hub_reboot_return";
    bool missed_return_callback=false, current_mac_success=false;
    std::vector<Reply> replies;
    std::map<std::string,unsigned> key_attempts;
    const Milliseconds horizon=s.horizon_ms;
    for (Milliseconds now=0;now<horizon;) {
        ++m.loops;
        const bool online=now>=s.return_ms && !(s.repeated_outage && now>=160000 && now<240000);
        if (!ready && now>=rejoin_due) {
            ++m.rejoin;
            rejoin_listen=now+SessionRecoveryPolicy::retry_delay(0,p.session+1);
            window.require_until(rejoin_listen);
            if (online) {
                p.rejoin(p.session+1); ready=true; hub_context_valid=true;
                last_contact=now; attempts=0; first_attempt=-1;
                p.node->set_outage_profile(false,now); health.observe_authenticated_contact(now);
                window.authenticated_progress();
                if(m.return_latency<0) m.return_latency=now-s.return_ms;
                // The cryptographic handshake is synchronous here. Physical
                // packet/CPU durations are not supplied by this host model.
            } else rejoin_due=now+SessionRecoveryPolicy::retry_delay(rejoin_stage++,p.session+1);
        }
        for(auto it=replies.begin();it!=replies.end();) {
            if(it->due>now) {++it;continue;}
            if(p.ack(it->wire)) {
                ++m.ack; ++m.retired; last_contact=now; first_attempt=-1; attempts=0;
                power.observe_authenticated_contact(); p.node->set_outage_profile(false,now);
                window.authenticated_progress(p.node->pending()==0);
                health.observe_authenticated_contact(now);
                if(m.ack_latency<0) m.ack_latency=now-it->admitted;
            }
            it=replies.erase(it);
        }
        if(inflight && now>=callback_at) {
            if(p.node->has_pending_key(*inflight)) {
                ++attempts; power.observe_unacknowledged_attempt();
                if(power.consecutive_unacknowledged()>=3) p.node->set_outage_profile(true,now);
            }
            p.node->transport_result(*inflight, current_mac_success,now);
            if(p.node->has_pending_key(*inflight))
                window.application_transport_completed(now,current_mac_success);
            else window.transport_completed(now);
            inflight.reset();
        }
        if(report_active && now>=report_callback) {
            report_active=false; window.transport_completed(now);
            report_due=online ? -1 : now+5000;
        }
        if(ready && (SessionRecoveryPolicy::active_expired(s.health_ack,now,first_attempt,attempts,last_contact) ||
            SessionRecoveryPolicy::idle_expired(s.health_ack,now,last_contact))) {
            ready=false; rejoin_stage=0; rejoin_due=now;
            window.session_replaced();
            first_attempt=-1; attempts=0;
            continue; // same required opportunity, no elapsed model time
        }
        raw=s.motion && now>=20000 && now%10000<2000;
        const auto sensed=pir.sample(raw,now);
        episode.poll(now,p.node->outage_profile());
        if(sensed) {
            if(episode.needs_first("room",now,p.node->outage_profile())) {
                p.admit(EventKind::Motion,now); ++m.admitted;
                if(first_admission<0) first_admission=now;
                episode.note_first("room",now,p.node->outage_profile());
            } else episode.note_repeat(now);
        }
        if(s.critical && !important_done && now>=30000) {
            p.admit(EventKind::CallFamily,now); ++m.admitted; important_done=true;
        }
        if(!p.node->outage_profile() && episode.pending()) {
            const auto summary=*episode.pending();
            const auto key=p.node->record(EventKind::MotionSummary,summary.room,summary.aggregate.last_ms,0,
                86400,0,false,SensorType::Pir,0,summary.aggregate);
            require(key && p.repository->save(p.node->recovery_snapshot()),"simulated durable summary");
            ++m.admitted; episode.summary_committed();
        }
        const auto due=p.node->next_retry_deadline();
        if(ready && !inflight && !report_active) {
            if(health.due(now,due && *due<=now,p.node->pending()!=0,p.node->outage_profile(),false)) {
                ++m.health; health.observe_health_attempt(now); window.transport_completed(now);
                if(online && hub_context_valid) {
                    NodeHealthSnapshot hs; hs.node_id="room"; hs.session_id=p.session; hs.health_sequence=m.health;
                    require(p.hub->observe_authenticated_health(hs,"room",p.session,static_cast<std::uint64_t>(now)),
                        "authenticated health lease");
                    if(s.health_ack) last_contact=now;
                }
            }
            if(s.retirement && p.node->pending()!=0 && report_due<0 && !online) report_due=now;
            if(report_due>=0 && now>=report_due) {
                report_active=true; report_callback=now+20;
            } else if(const auto msg=p.node->next_message(now)) {
                EventKey k{msg->node_id,msg->session_id,msg->sequence_number};
                if(key_attempts[k.str()]++>0) ++m.retry;
                const bool drop_callback=s.callback_missing ||
                    (s.name=="missed_ack_in_sleep" && online && !missed_return_callback);
                if(s.name=="missed_ack_in_sleep" && online) missed_return_callback=true;
                current_mac_success=online && !s.callback_failed && !drop_callback;
                ++m.tx; inflight=k; callback_at=now+(drop_callback?1000:20);
                if(first_attempt<0) first_attempt=now;
                if(m.first_latency<0) m.first_latency=now-msg->monotonic_ms;
                if(online && hub_context_valid) {
                    bool changed=false; const auto ack=p.deliver(*msg,now,changed);
                    if(changed) ++m.effects;
                    ++m.piggyback;
                    if(s.lost_first_ack && m.missed==0) ++m.missed;
                    else replies.push_back({now+s.ack_delay_ms,ack,msg->monotonic_ms});
                    if(m.return_latency<0) m.return_latency=now-s.return_ms;
                }
            }
        }
        if(p.node->pending()==0 && m.admitted>0 && m.drain<0) m.drain=now-s.return_ms;
        auto o=observation(now);
        o.next_retry_ms=ready ? p.node->next_retry_deadline().value_or(-1):-1;
        o.next_health_ms=ready && p.node->pending()==0 && !p.node->outage_profile() ? health.next_due_ms():-1;
        o.next_maintenance_ms=episode.next_deadline_ms();
        o.next_radio_ms=ready ? report_due:-1;
        o.authenticated=ready; o.rejoin_active=!ready;
        o.rejoin_backoff=!ready && rejoin_due>now && (!after || !window.active(now));
        o.next_security_ms=ready ? (s.health_ack ? last_contact+SessionRecoveryPolicy::contact_timeout_ms:-1) : rejoin_due;
        const auto ad=SessionRecoveryPolicy::active_deadline(s.health_ack,first_attempt,attempts,last_contact);
        if(after && ready && ad && (o.next_security_ms<0 || *ad<o.next_security_ms)) o.next_security_ms=*ad;
        o.event_in_flight=inflight.has_value() || report_active;
        o.outage_active=ready && p.node->outage_profile();
        o.pir_high=raw; o.pir_low_stable=!raw; o.debounce_safe=pir.safe_for_sleep(now);
        o.recovery_work=p.node->gap_marker_required() || (!p.node->outage_profile() && episode.pending().has_value());
        if(after) observe_retained_delivery(o,window,p.node->pending()!=0,p.node->persisted()!=0);
        else {
            o.pending_tx=ready && p.node->pending()!=0; o.ack_wait=o.pending_tx;
            o.recovery_work=o.recovery_work || (ready && p.node->persisted()!=0);
        }
        const auto sleep=evaluate_light_sleep(o);
        Milliseconds next=std::min(horizon,now+20);
        if(sleep.eligible) {
            ++m.sleeps; next=std::min(horizon,now+sleep.requested_sleep_ms);
            // Actual GPIO pulse wake model; important direct-owner input uses
            // an explicit wake at its injected time, not an invented door GPIO.
            Milliseconds gpio_time=s.motion ? (now<20000?20000:((now/10000)+1)*10000):horizon;
            if(s.critical && !important_done) gpio_time=std::min(gpio_time,Milliseconds{30000});
            if(gpio_time<next) {next=gpio_time;++m.gpio;} else ++m.timer;
            const auto start=now;
            replies.erase(std::remove_if(replies.begin(),replies.end(),[&](const auto& reply){
                if(reply.due>start && reply.due<next) {++m.missed;return true;} return false;
            }),replies.end());
        } else {m.awake+=static_cast<std::uint64_t>(next-now); m.listen+=static_cast<std::uint64_t>(next-now);}
        now=next;
    }
    m.writes=p.blob.writes;
    require(p.node->persisted()==p.node->pending(),"retained/pending conservation");
    require(m.admitted==m.retired+p.node->pending(),"no event loss or false retirement");
    require(p.hub->journal().size()==m.effects,"one logical Hub effect per durable identity");
    require(p.hub->routine_state().evidence_ids.size()<=m.effects,"no duplicate reducer evidence");
    if(s.return_ms>=horizon) require(m.retired==0 && !p.hub->node_online("room",horizon),"outage never fabricates fresh coverage/contact");
    return m;
}
void simulations(const char* output) {
    std::ofstream csv(output);
    require(csv.good(),"simulation evidence output");
    csv<<"scenario,version,loops,sleeps,timer_wakes,gpio_wakes,awake_ms,listen_ms,tx,retries,ack,missed_ack,rejoin,admitted,retired,durable_writes,logical_effects,health_opportunities,health_piggyback_opportunities,first_tx_latency_ms,first_ack_latency_ms,hub_return_contact_ms,drain_ms\n";
    const std::vector<Scenario> cases{
        {"connected_idle"}, {"offline_empty",0,400000},
        {"offline_one",1,400000}, {"offline_many",8,400000},
        {"hub_return",8,130000}, {"hub_return_v2",8,130000,40,false,true},
        {"frequent_pir",0,130000,40,false,true,false,true},
        {"critical_outage",1,130000,40,false,true,false,false,true},
        {"lost_ack",1,0,40,true}, {"delayed_ack",1,0,1000},
        {"outage_late_ack",1,130000,1000,false,false},
        {"ack_after_budget",1,130000,12000,false,false},
        {"missed_ack_in_sleep",1,130000,12000,false,false},
        {"retirement_outage",8,130000,40,false,false,true},
        {"missing_callback",1,130000,40,false,true,false,false,false,true},
        {"failed_callback",1,130000,40,false,true,false,false,false,false,true},
        {"failed_mac_delayed_ack",1,130000,1000,false,false,false,false,false,false,true},
        {"repeated_outage",1,130000,40,false,true,false,true,false,false,false,true},
        {"idle_hub_reboot_return",0,130000,40,false,true,false,false,false,false,false,false,720000}};
    for(const auto& s:cases) {
        const auto before=simulate(s,false), after=simulate(s,true);
        require(before.admitted==after.admitted && before.retired==after.retired && before.effects==after.effects,
            "identical workloads preserve admissions, retirement and logical effects");
        if(s.name=="offline_one" || s.name=="offline_many") {
            require(after.loops*5<before.loops && after.awake*5<before.awake,"substantial quiet outage reduction");
            require(after.tx==before.tx,"outage retry count preserved");
        }
        if(s.name=="missed_ack_in_sleep") require(after.missed>=1 && after.retired==1 &&
            after.effects==1 && after.tx==before.tx+1, "missed sleeping ACK completes via one exact-key retransmission");
        if(s.name=="idle_hub_reboot_return") require(after.rejoin>=1 && after.return_latency>=0,
            "idle Hub reboot triggers existing authenticated recovery without PIR");
        if(s.name=="hub_return") require(after.retired==8 && after.return_latency>=0 && after.return_latency<=60100,
            "automatic authenticated Hub recovery at existing opportunity without PIR");
        for(const auto& version:std::vector<std::pair<const char*,Metrics>>{{"before",before},{"after",after}}) {
            const auto& m=version.second;
            csv<<s.name<<','<<version.first<<','<<m.loops<<','<<m.sleeps<<','<<m.timer<<','<<m.gpio<<','<<m.awake<<','<<m.listen<<','
               <<m.tx<<','<<m.retry<<','<<m.ack<<','<<m.missed<<','<<m.rejoin<<','<<m.admitted<<','<<m.retired<<','<<m.writes<<','
               <<m.effects<<','<<m.health<<','<<m.piggyback<<','<<m.first_latency<<','<<m.ack_latency<<','<<m.return_latency<<','<<m.drain<<'\n';
        }
        std::cout<<s.name<<" loops "<<before.loops<<" -> "<<after.loops<<" awake_ms "<<before.awake<<" -> "<<after.awake
                 <<" tx "<<before.tx<<" -> "<<after.tx<<" retired "<<after.retired<<'\n';
    }
}
}
int main(int argc,char** argv) {
    try {
        policy_matrix(); authenticated_matrix();
        simulations(argc>1?argv[1]:"build/gs150_metrics.csv");
        std::cout<<"GS-150 PASS checks="<<checks<<'\n';
        return 0;
    } catch(const std::exception& e) {std::cerr<<"GS-150 FAIL: "<<e.what()<<'\n';return 1;}
}
