// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H04 Hub coverage
// @requirements F08, E01, E03
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// CoverageTracker owns contact and fault state for required nodes. Optional nodes should not invalidate
// unrelated routines. Its current/reasons methods describe the present moment; they do not reconstruct
// whether the entire morning was observable. Store interval history before making that stronger claim.

#include "coverage/coverage.hpp"
#include "gs/logging.hpp"

namespace gs::hub {

CoverageTracker::CoverageTracker(EpochSeconds lease_seconds) : lease_seconds_(lease_seconds) {
    GS_TRACE(gs::log::Category::Hub, "H04", "CoverageTracker.enter", "-");}

void CoverageTracker::require_node(const std::string& node_id) {
    GS_TRACE(gs::log::Category::Hub, "H04", "require_node.enter", "-");
    required_nodes_.insert(node_id);
}

void CoverageTracker::forget_node(const std::string& node_id) {
    required_nodes_.erase(node_id);
    health_.erase(node_id);
}

// @requirements F08, E01, E03
// Refresh contact telemetry; a heartbeat must not erase an explicit sensor fault.
void CoverageTracker::observe(const std::string& node_id, EpochSeconds at, std::uint16_t battery_mv) {
    GS_TRACE(gs::log::Category::Hub, "H04", "observe.enter", "-");
    auto& value = health_[node_id];
    value.last_contact = at;
    value.battery_mv = battery_mv;
}

void CoverageTracker::set_sensor_fault(const std::string& node_id, bool fault) {
    GS_TRACE(gs::log::Category::Hub, "H04", "set_sensor_fault.enter", "-");
    health_[node_id].sensor_fault = fault;
}

// @requirements F08, E01, E03
// Calculate present required-node coverage; this is not full-window coverage history (G03).
CoverageState CoverageTracker::current(EpochSeconds now) const {
    GS_TRACE(gs::log::Category::Hub, "H04", "current.enter", "-");
    for (const auto& node : required_nodes_) {
        const auto it = health_.find(node);
        if (it == health_.end() || it->second.last_contact == 0 || now - it->second.last_contact > lease_seconds_) {
            return CoverageState::Unknown;
        }
        if (it->second.sensor_fault) return CoverageState::Fault;
    }
    return CoverageState::Covered;
}

std::vector<std::string> CoverageTracker::reasons(EpochSeconds now) const {
    GS_TRACE(gs::log::Category::Hub, "H04", "reasons.enter", "-");
    std::vector<std::string> result;
    for (const auto& node : required_nodes_) {
        const auto it = health_.find(node);
        if (it == health_.end() || it->second.last_contact == 0) result.push_back(node + ":never_seen");
        else if (now - it->second.last_contact > lease_seconds_) result.push_back(node + ":lease_expired");
        else if (it->second.sensor_fault) result.push_back(node + ":sensor_fault");
    }
    return result;
}

}  // namespace gs::hub
