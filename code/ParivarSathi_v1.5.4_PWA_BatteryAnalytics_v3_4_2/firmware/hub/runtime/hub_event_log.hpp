#pragma once

#include "gs/domain.hpp"
#include "gs/protocol.hpp"

#include <string>

namespace gs::hub {

inline const char* event_log_sensor_name(SensorType sensor) {
    switch (sensor) {
        case SensorType::Unknown: return "UNKNOWN";
        case SensorType::Pir: return "PIR";
        case SensorType::Reed: return "REED";
        case SensorType::Button: return "BUTTON";
        case SensorType::Heartbeat: return "HEARTBEAT";
        case SensorType::System: return "SYSTEM";
    }
    return "UNKNOWN";
}

inline const char* event_log_kind_name(EventKind kind) {
    switch (kind) {
        case EventKind::Motion: return "MOTION";
        case EventKind::DoorOpen: return "DOOR_OPEN";
        case EventKind::DoorClosed: return "DOOR_CLOSED";
        case EventKind::OkPressed: return "OK_PRESSED";
        case EventKind::CallFamily: return "CALL_FAMILY";
        case EventKind::Heartbeat: return "HEARTBEAT";
        case EventKind::PrivacyOn: return "PRIVACY_ON";
        case EventKind::PrivacyOff: return "PRIVACY_OFF";
        case EventKind::Gap: return "GAP";
        case EventKind::MotionSummary: return "MOTION_SUMMARY";
    }
    return "UNKNOWN";
}

inline std::string format_authenticated_event_log(
    const std::string& logical_id, const NodeMessage& message,
    const EventKey& key, AckClass ack, const char* send_status) {
    return "Authenticated event logical=" + logical_id +
        " session=" + std::to_string(key.session_id) +
        " seq=" + std::to_string(key.sequence) +
        " sensor=" + event_log_sensor_name(message.sensor_type) +
        " event=" + event_log_kind_name(message.event_type) +
        " event_id=" + key.str() +
        " room=" + message.location +
        " ack=" + std::to_string(static_cast<int>(ack)) +
        " send=" + (send_status != nullptr ? send_status : "UNKNOWN");
}

}  // namespace gs::hub
