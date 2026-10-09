#include "hub_checkpoint_codec.hpp"
#include <type_traits>
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
bool HubCheckpointCodec::encode(HubRuntime& r, security::Bytes& bytes) {
    bytes.clear(); Codec c{bytes,false};
    std::uint32_t version=1; c.scalar(version); if(version!=1)c.ok=false;
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
    return c.ok && bytes.size()<=64U*1024U;
}
bool HubCheckpointCodec::restore(HubRuntime& target, const security::Bytes& input) {
    if(input.size()>64U*1024U)return false;
    security::Bytes bytes=input; HubRuntime r(0,0); Codec c{bytes,true};
    std::uint32_t version=1; c.scalar(version); if(version!=1)c.ok=false;
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
    if(!c.ok || c.at!=bytes.size() || r.routine_.config_.window_id!=r.routine_.state_.window_id ||
       static_cast<unsigned>(r.routine_.state_.mode)>static_cast<unsigned>(HomeMode::Privacy)||
       static_cast<unsigned>(r.routine_.state_.coverage)>static_cast<unsigned>(CoverageState::Fault)||
       r.coverage_.lease_seconds_<=0)return false;
    target.routine_=std::move(r.routine_);target.coverage_=std::move(r.coverage_);
    target.activity_config_=std::move(r.activity_config_);target.activity_state_=std::move(r.activity_state_);
    target.power_telemetry_=std::move(r.power_telemetry_);
    // Hub boot ticks cannot refresh a Node lease from the previous boot.
    // Registry/session authority is independently restored by the security owner.
    target.last_authenticated_contact_ms_.clear();target.node_health_.clear();
    return true;
}
} // namespace gs::hub
