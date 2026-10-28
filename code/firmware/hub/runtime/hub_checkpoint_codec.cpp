#include "hub_checkpoint_codec.hpp"
#include <type_traits>
#include <memory>
#include <new>
#include <set>
namespace gs::hub {
namespace {
// Explicit little-endian schema. Byte/count limits fail closed, never discard evidence.
struct Codec {
    security::Bytes& bytes; bool reading; std::size_t at{0}; bool ok{true};
    template<class T> void scalar(T& value) {
        if(!ok)return;
        if constexpr(std::is_enum_v<T>) {
            std::uint32_t n=static_cast<std::uint32_t>(value); scalar(n);
            if(reading) value=static_cast<T>(n);
        } else if constexpr(std::is_same_v<T,bool>) {
            std::uint8_t n=value; scalar(n); if(n>1) ok=false; if(reading) value=n!=0;
        } else {
            using U=std::make_unsigned_t<T>;
            U n=static_cast<U>(value);
            if(reading) { n=0; if(at+sizeof(T)>bytes.size()) {ok=false;return;}
                for(unsigned i=0;i<sizeof(T);++i) n|=U(bytes[at++])<<(8*i);
                value=static_cast<T>(n);
            } else {
                if(bytes.size()+sizeof(T)>64U*1024U){ok=false;return;}
                for(unsigned i=0;i<sizeof(T);++i) bytes.push_back(n>>(8*i));
            }
        }
    }
    void scalar(std::string& s) {
        if(!ok)return;
        std::uint32_t n=s.size(); scalar(n);
        if(n>1024) {ok=false;return;}
        if(reading) {if(at+n>bytes.size()){ok=false;return;}
            s.assign(bytes.begin()+at,bytes.begin()+at+n); at+=n;
        } else {
            if(bytes.size()+n>64U*1024U){ok=false;return;}
            bytes.insert(bytes.end(),s.begin(),s.end());
        }
    }
    void scalar(std::optional<EpochSeconds>& v) {
        bool present=v.has_value(); scalar(present); EpochSeconds n=v.value_or(0); scalar(n);
        if(reading) v=present ? std::optional<EpochSeconds>(n) : std::nullopt;
    }
    template<class C> void strings(C& values, std::uint32_t limit) {
        std::uint32_t n=values.size(); scalar(n); if(n>limit){ok=false;return;}
        if(reading) { values.clear(); for(std::uint32_t i=0;i<n && ok;++i){std::string s;scalar(s);
            if constexpr(std::is_same_v<C,std::set<std::string>>) {if(!values.insert(s).second)ok=false;}
            else values.push_back(s); }
        } else for(const auto& s:values){if(!ok)break;auto copy=s;scalar(copy);}
    }
};
}
bool HubCheckpointCodec::encode_after_event(HubRuntime& r, const DomainEvent& event,
        std::optional<std::uint16_t> minute,
        const CloudAuthorityBinding* authority, security::Bytes& bytes) {
    // Keep the sizeable runtime object off the target owner's task stack.
    std::unique_ptr<HubRuntime> preview(new (std::nothrow) HubRuntime(0, 0));
    if (!preview) return false;
    preview->routine_ = r.routine_; preview->coverage_ = r.coverage_;
    preview->activity_config_ = r.activity_config_; preview->activity_state_ = r.activity_state_;
    preview->activity_rules_configured_ = r.activity_rules_configured_;
    preview->activity_authority_binding_ = r.activity_authority_binding_;
    preview->power_telemetry_ = r.power_telemetry_;
    preview->pending_rule_decisions_ = r.pending_rule_decisions_;
    const auto signals = preview->apply_committed_event(event, minute);
    const auto decision_time = event.received_at > 0
        ? event.received_at : event.occurred_at;
    if (!preview->append_rule_decisions(signals, decision_time,
            event.key.str(), authority)) return false;
    return encode(*preview, bytes);
}

bool HubCheckpointCodec::encode(HubRuntime& r, security::Bytes& bytes) {
    bytes.clear(); Codec c{bytes,false};
    const bool generic_morning_policy = r.activity_config_.morning_sequence_strict_order ||
        !r.activity_config_.morning_steps.empty() ||
        !r.activity_state_.morning_seen_locations.empty();
    const bool extended_rule_state = r.activity_rules_configured_ ||
        !r.pending_rule_decisions_.empty() ||
        r.activity_authority_binding_.has_value();
    // Keep the legacy v1 byte layout for Hub states that do not use the new
    // authority-bound deterministic rules. This preserves existing reader
    // compatibility for ordinary journal/checkpoint updates. Once a signed
    // Home/epoch binding or pending publication intent exists, store the
    // complete v3 authority and decision state atomically in the checkpoint.
    std::uint32_t version = generic_morning_policy ? 4 : (extended_rule_state ? 3 : 1);
    c.scalar(version);
    c.scalar(r.routine_.config_.start_at);
    c.scalar(r.routine_.config_.end_at);
    c.scalar(r.routine_.config_.grace_end_at);
    c.scalar(r.routine_.config_.enabled);
    c.scalar(r.routine_.state_.activity_seen);
    c.scalar(r.routine_.state_.explicit_ok);
    c.scalar(r.routine_.state_.missing_incident_created);
    c.scalar(r.routine_.state_.coverage);
    c.scalar(r.routine_.state_.mode);
    c.scalar(r.activity_config_.quiet_hours_enabled);
    c.scalar(r.activity_config_.quiet_start_minute);
    c.scalar(r.activity_config_.quiet_end_minute);
    c.scalar(r.activity_config_.door_open_timeout_seconds);
    c.scalar(r.activity_config_.daytime_inactivity_enabled);
    c.scalar(r.activity_config_.daytime_start_minute);
    c.scalar(r.activity_config_.daytime_end_minute);
    c.scalar(r.activity_config_.daytime_inactivity_seconds);
    c.scalar(r.activity_config_.morning_sequence_enabled);
    c.scalar(r.activity_config_.morning_start_minute);
    c.scalar(r.activity_config_.morning_end_minute);
    c.scalar(r.activity_config_.morning_sequence_window_seconds);
    c.scalar(r.activity_config_.morning_bedroom_location);
    c.scalar(r.activity_config_.morning_bathroom_location);
    c.scalar(r.activity_config_.morning_kitchen_location);
    c.scalar(r.activity_config_.night_activity_enabled);
    c.scalar(r.activity_config_.night_start_minute);
    c.scalar(r.activity_config_.night_end_minute);
    c.scalar(r.activity_config_.night_bathroom_location);
    c.scalar(r.activity_config_.night_bathroom_visit_threshold);
    c.scalar(r.activity_config_.night_common_location);
    c.scalar(r.activity_config_.night_common_visit_threshold);
    c.scalar(r.activity_config_.night_visit_merge_seconds);
    c.scalar(r.activity_config_.post_door_inactivity_enabled);
    c.scalar(r.activity_config_.post_door_inactivity_seconds);
    c.strings(r.routine_.config_.qualifying_locations,64);
    c.strings(r.routine_.state_.evidence_ids,16384);
    c.scalar(r.activity_state_.door_left_open_alerted);
    c.scalar(r.activity_state_.inactivity_alerted);
    c.scalar(r.activity_state_.morning_started);
    c.scalar(r.activity_state_.morning_bathroom_seen);
    c.scalar(r.activity_state_.morning_kitchen_seen);
    c.scalar(r.activity_state_.morning_completed);
    c.scalar(r.activity_state_.night_bathroom_visits);
    c.scalar(r.activity_state_.night_common_visits);
    c.scalar(r.activity_state_.night_bathroom_alerted);
    c.scalar(r.activity_state_.night_common_alerted);
    c.scalar(r.activity_state_.night_window_active);
    c.scalar(r.activity_state_.post_door_activity_seen);
    c.scalar(r.activity_state_.post_door_inactivity_alerted);
    c.scalar(r.activity_state_.monitoring_started_at);
    c.scalar(r.activity_state_.last_activity_at);
    if (version >= 3)
        c.scalar(r.activity_state_.last_activity_time_trusted);
    c.scalar(r.activity_state_.door_opened_at);
    c.scalar(r.activity_state_.morning_started_at);
    c.scalar(r.activity_state_.last_night_bathroom_at);
    c.scalar(r.activity_state_.last_night_common_at);
    c.scalar(r.activity_state_.door_closed_at);
    c.scalar(r.activity_state_.last_activity_event_id);
    c.scalar(r.activity_state_.door_open_event_id);
    c.scalar(r.routine_.config_.window_id); c.scalar(r.routine_.state_.window_id);
    c.scalar(r.coverage_.lease_seconds_);
    c.strings(r.coverage_.required_nodes_,64);
    std::uint32_t health_count=r.coverage_.health_.size(); c.scalar(health_count);
    if(health_count>64)c.ok=false;
    if(c.reading) r.coverage_.health_.clear();
    auto health_it=r.coverage_.health_.begin();
    for(std::uint32_t i=0;i<health_count && c.ok;++i) {
        std::string node; NodeHealth h;
        if(!c.reading){node=health_it->first;h=health_it->second;++health_it;}
        c.scalar(node); c.scalar(h.last_contact);c.scalar(h.battery_mv);c.scalar(h.sensor_fault);
        if(c.reading && !r.coverage_.health_.emplace(node,h).second)c.ok=false;
    }
    std::uint32_t power_count=r.power_telemetry_.size(); c.scalar(power_count);
    if(power_count>64)c.ok=false;
    if(c.reading)r.power_telemetry_.clear();
    auto power_it=r.power_telemetry_.begin();
    for(std::uint32_t i=0;i<power_count && c.ok;++i){
        std::string node; NodePowerTelemetry p;
        if(!c.reading){node=power_it->first;p=power_it->second;++power_it;}
        c.scalar(node);
        c.scalar(p.deep_sleep_ms);
        c.scalar(p.awake_ms);
        c.scalar(p.sensor_active_ms);
        c.scalar(p.radio_tx_ms);
        c.scalar(p.radio_rx_ms);
        c.scalar(p.radio_tx_packets);
        c.scalar(p.radio_retries);
        c.scalar(p.wake_count);
        c.scalar(p.heartbeat_count);
        c.scalar(p.boot_count);
        c.scalar(p.brownout_count);
        if(c.reading && (!valid_power_telemetry(p)||!r.power_telemetry_.emplace(node,p).second))c.ok=false;
    }
    if (version >= 2) {
        std::uint32_t decision_count=static_cast<std::uint32_t>(r.pending_rule_decisions_.size());
        c.scalar(decision_count);
        if(decision_count>32)c.ok=false;
        for(std::uint32_t i=0;i<decision_count && c.ok;++i) {
            auto& intent=r.pending_rule_decisions_[i];
            c.scalar(intent.decision.kind); c.scalar(intent.decision.tone);
            c.scalar(intent.decision.stable_key); c.scalar(intent.decision.reason);
            c.scalar(intent.decision.duration_seconds); c.scalar(intent.decision.create);
            c.scalar(intent.decision.resolves_prior); c.scalar(intent.decided_at);
            c.scalar(intent.source_event_key); c.scalar(intent.origin_home_id);
            c.scalar(intent.origin_hub_device_id); c.scalar(intent.origin_ownership_epoch);
        }
    }
    if (version >= 3) {
        bool has_activity_authority = r.activity_authority_binding_.has_value();
        c.scalar(has_activity_authority);
        std::string activity_home;
        std::string activity_hub;
        std::uint64_t activity_epoch = 0;
        if (has_activity_authority) {
            const auto& binding = *r.activity_authority_binding_;
            activity_home = binding.home_id;
            activity_hub = binding.hub_device_id;
            activity_epoch = binding.ownership_epoch;
            if (activity_home.empty() || activity_hub.empty() || activity_epoch == 0)
                c.ok = false;
        }
        c.scalar(activity_home); c.scalar(activity_hub); c.scalar(activity_epoch);
    }
    if (version >= 4) {
        c.scalar(r.activity_config_.morning_sequence_strict_order);
        std::uint32_t step_count = r.activity_config_.morning_steps.size();
        c.scalar(step_count);
        if (step_count > 24) c.ok = false;
        for (auto& step : r.activity_config_.morning_steps) {
            c.scalar(step.location); c.scalar(step.enabled); c.scalar(step.required);
        }
        c.strings(r.activity_state_.morning_seen_locations, 24);
    }
    return c.ok && bytes.size()<=64U*1024U;
}
bool HubCheckpointCodec::restore(HubRuntime& target, const security::Bytes& input) {
    if(input.size()>64U*1024U)return false;
    security::Bytes bytes=input; HubRuntime r(0,0); Codec c{bytes,true};
    std::uint32_t version=0; c.scalar(version); if(version<1 || version>4)c.ok=false;
    c.scalar(r.routine_.config_.start_at);
    c.scalar(r.routine_.config_.end_at);
    c.scalar(r.routine_.config_.grace_end_at);
    c.scalar(r.routine_.config_.enabled);
    c.scalar(r.routine_.state_.activity_seen);
    c.scalar(r.routine_.state_.explicit_ok);
    c.scalar(r.routine_.state_.missing_incident_created);
    c.scalar(r.routine_.state_.coverage);
    c.scalar(r.routine_.state_.mode);
    c.scalar(r.activity_config_.quiet_hours_enabled);
    c.scalar(r.activity_config_.quiet_start_minute);
    c.scalar(r.activity_config_.quiet_end_minute);
    c.scalar(r.activity_config_.door_open_timeout_seconds);
    c.scalar(r.activity_config_.daytime_inactivity_enabled);
    c.scalar(r.activity_config_.daytime_start_minute);
    c.scalar(r.activity_config_.daytime_end_minute);
    c.scalar(r.activity_config_.daytime_inactivity_seconds);
    c.scalar(r.activity_config_.morning_sequence_enabled);
    c.scalar(r.activity_config_.morning_start_minute);
    c.scalar(r.activity_config_.morning_end_minute);
    c.scalar(r.activity_config_.morning_sequence_window_seconds);
    c.scalar(r.activity_config_.morning_bedroom_location);
    c.scalar(r.activity_config_.morning_bathroom_location);
    c.scalar(r.activity_config_.morning_kitchen_location);
    c.scalar(r.activity_config_.night_activity_enabled);
    c.scalar(r.activity_config_.night_start_minute);
    c.scalar(r.activity_config_.night_end_minute);
    c.scalar(r.activity_config_.night_bathroom_location);
    c.scalar(r.activity_config_.night_bathroom_visit_threshold);
    c.scalar(r.activity_config_.night_common_location);
    c.scalar(r.activity_config_.night_common_visit_threshold);
    c.scalar(r.activity_config_.night_visit_merge_seconds);
    c.scalar(r.activity_config_.post_door_inactivity_enabled);
    c.scalar(r.activity_config_.post_door_inactivity_seconds);
    c.strings(r.routine_.config_.qualifying_locations,64);
    c.strings(r.routine_.state_.evidence_ids,16384);
    c.scalar(r.activity_state_.door_left_open_alerted);
    c.scalar(r.activity_state_.inactivity_alerted);
    c.scalar(r.activity_state_.morning_started);
    c.scalar(r.activity_state_.morning_bathroom_seen);
    c.scalar(r.activity_state_.morning_kitchen_seen);
    c.scalar(r.activity_state_.morning_completed);
    c.scalar(r.activity_state_.night_bathroom_visits);
    c.scalar(r.activity_state_.night_common_visits);
    c.scalar(r.activity_state_.night_bathroom_alerted);
    c.scalar(r.activity_state_.night_common_alerted);
    c.scalar(r.activity_state_.night_window_active);
    c.scalar(r.activity_state_.post_door_activity_seen);
    c.scalar(r.activity_state_.post_door_inactivity_alerted);
    c.scalar(r.activity_state_.monitoring_started_at);
    c.scalar(r.activity_state_.last_activity_at);
    if (version >= 3)
        c.scalar(r.activity_state_.last_activity_time_trusted);
    c.scalar(r.activity_state_.door_opened_at);
    c.scalar(r.activity_state_.morning_started_at);
    c.scalar(r.activity_state_.last_night_bathroom_at);
    c.scalar(r.activity_state_.last_night_common_at);
    c.scalar(r.activity_state_.door_closed_at);
    c.scalar(r.activity_state_.last_activity_event_id);
    c.scalar(r.activity_state_.door_open_event_id);
    c.scalar(r.routine_.config_.window_id); c.scalar(r.routine_.state_.window_id);
    c.scalar(r.coverage_.lease_seconds_);
    c.strings(r.coverage_.required_nodes_,64);
    std::uint32_t health_count=r.coverage_.health_.size(); c.scalar(health_count);
    if(health_count>64)c.ok=false;
    if(c.reading) r.coverage_.health_.clear();
    auto health_it=r.coverage_.health_.begin();
    for(std::uint32_t i=0;i<health_count && c.ok;++i) {
        std::string node; NodeHealth h;
        if(!c.reading){node=health_it->first;h=health_it->second;++health_it;}
        c.scalar(node); c.scalar(h.last_contact);c.scalar(h.battery_mv);c.scalar(h.sensor_fault);
        if(c.reading && !r.coverage_.health_.emplace(node,h).second)c.ok=false;
    }
    std::uint32_t power_count=r.power_telemetry_.size(); c.scalar(power_count);
    if(power_count>64)c.ok=false;
    if(c.reading)r.power_telemetry_.clear();
    auto power_it=r.power_telemetry_.begin();
    for(std::uint32_t i=0;i<power_count && c.ok;++i){
        std::string node; NodePowerTelemetry p;
        if(!c.reading){node=power_it->first;p=power_it->second;++power_it;}
        c.scalar(node);
        c.scalar(p.deep_sleep_ms);
        c.scalar(p.awake_ms);
        c.scalar(p.sensor_active_ms);
        c.scalar(p.radio_tx_ms);
        c.scalar(p.radio_rx_ms);
        c.scalar(p.radio_tx_packets);
        c.scalar(p.radio_retries);
        c.scalar(p.wake_count);
        c.scalar(p.heartbeat_count);
        c.scalar(p.boot_count);
        c.scalar(p.brownout_count);
        if(c.reading && (!valid_power_telemetry(p)||!r.power_telemetry_.emplace(node,p).second))c.ok=false;
    }
    if(version>=2) {
        std::uint32_t decision_count=0; c.scalar(decision_count);
        if(decision_count>32)c.ok=false;
        std::set<std::string> decision_ids;
        for(std::uint32_t i=0;i<decision_count && c.ok;++i) {
            HubRuleDecisionIntent intent;
            c.scalar(intent.decision.kind); c.scalar(intent.decision.tone);
            c.scalar(intent.decision.stable_key); c.scalar(intent.decision.reason);
            c.scalar(intent.decision.duration_seconds); c.scalar(intent.decision.create);
            c.scalar(intent.decision.resolves_prior); c.scalar(intent.decided_at);
            c.scalar(intent.source_event_key); c.scalar(intent.origin_home_id);
            c.scalar(intent.origin_hub_device_id); c.scalar(intent.origin_ownership_epoch);
            const auto kind=static_cast<unsigned>(intent.decision.kind);
            const auto tone=static_cast<unsigned>(intent.decision.tone);
            const HubRuleDecisionRequest request{intent.decision,intent.decided_at,
                                                  intent.source_event_key};
            const bool unbound=intent.origin_home_id.empty() &&
                intent.origin_hub_device_id.empty() && intent.origin_ownership_epoch==0;
            const bool bound=!intent.origin_home_id.empty() &&
                !intent.origin_hub_device_id.empty() && intent.origin_ownership_epoch!=0;
            if(kind>static_cast<unsigned>(RuleSignalKind::MissingMorningActivity) ||
               tone>static_cast<unsigned>(RuleTone::Concern) || !intent.decision.create ||
               intent.decided_at<=0 || intent.decision.duration_seconds<0 ||
               intent.decision.stable_key.empty() || intent.decision.stable_key.size()>256 ||
               intent.decision.reason.empty() || intent.decision.reason.size()>96 ||
               intent.source_event_key.size()>256 || (!unbound && !bound) ||
               request.json_body().empty() ||
               !decision_ids.insert(intent.decision_id()).second) c.ok=false;
            if(c.ok) r.pending_rule_decisions_.push_back(std::move(intent));
        }
    }
    if (version >= 3) {
        bool has_activity_authority = false;
        std::string home_id, hub_device_id;
        std::uint64_t ownership_epoch = 0;
        c.scalar(has_activity_authority);
        c.scalar(home_id); c.scalar(hub_device_id); c.scalar(ownership_epoch);
        if (has_activity_authority) {
            if (home_id.empty() || hub_device_id.empty() || ownership_epoch == 0)
                c.ok = false;
            else
                r.activity_authority_binding_ = CloudAuthorityBinding{
                    std::move(home_id), std::move(hub_device_id), ownership_epoch};
        } else if (!home_id.empty() || !hub_device_id.empty() || ownership_epoch != 0) {
            c.ok = false;
        }
    } else if (r.activity_state_.last_activity_at.has_value()) {
        // Older checkpoints cannot prove whether this timestamp came from an
        // authenticated Hub clock. Keep it for chronology but do not use it
        // for timer-driven inactivity until a trusted event resets the flag.
        r.activity_state_.last_activity_time_trusted = false;
    }
    if (version >= 4) {
        c.scalar(r.activity_config_.morning_sequence_strict_order);
        std::uint32_t step_count = 0; c.scalar(step_count);
        if (step_count > 24) c.ok = false;
        std::set<std::string> locations;
        bool required_enabled = false;
        for (std::uint32_t i = 0; i < step_count && c.ok; ++i) {
            MorningRoutineStep step;
            c.scalar(step.location); c.scalar(step.enabled); c.scalar(step.required);
            if (step.location.empty() || step.location.size() > 32 ||
                !std::all_of(step.location.begin(), step.location.end(), [](unsigned char ch) {
                    return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
                           (ch >= '0' && ch <= '9') || ch == '-' || ch == '_';
                }) || !locations.insert(step.location).second) c.ok = false;
            required_enabled = required_enabled || (step.enabled && step.required);
            r.activity_config_.morning_steps.push_back(std::move(step));
        }
        c.strings(r.activity_state_.morning_seen_locations, 24);
        if ((step_count == 0 && r.activity_config_.morning_sequence_strict_order) ||
            (step_count > 0 && !required_enabled)) c.ok = false;
        std::set<std::string> seen_locations;
        for (const auto& seen : r.activity_state_.morning_seen_locations)
            if (locations.count(seen) == 0 || !seen_locations.insert(seen).second)
                c.ok = false;
    }
    r.activity_rules_configured_ = version >= 2;
    if(!c.ok || c.at!=bytes.size() || r.routine_.config_.window_id!=r.routine_.state_.window_id ||
       static_cast<unsigned>(r.routine_.state_.mode)>static_cast<unsigned>(HomeMode::Privacy)||
       static_cast<unsigned>(r.routine_.state_.coverage)>static_cast<unsigned>(CoverageState::Fault)||
       r.coverage_.lease_seconds_<=0)return false;
    target.routine_=std::move(r.routine_);target.coverage_=std::move(r.coverage_);
    target.activity_config_=std::move(r.activity_config_);target.activity_state_=std::move(r.activity_state_);
    target.activity_rules_configured_=r.activity_rules_configured_;
    target.activity_authority_binding_=std::move(r.activity_authority_binding_);
    target.power_telemetry_=std::move(r.power_telemetry_);
    target.pending_rule_decisions_=std::move(r.pending_rule_decisions_);
    // Hub boot ticks cannot refresh a Node lease from the previous boot.
    // Registry/session authority is independently restored by the security owner.
    target.last_authenticated_contact_ms_.clear();target.node_health_.clear();
    target.cloud_contacts_.clear();
    return true;
}
} // namespace gs::hub
