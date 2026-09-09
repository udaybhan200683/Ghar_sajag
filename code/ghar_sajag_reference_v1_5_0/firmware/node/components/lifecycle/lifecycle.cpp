// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module N04 Node lifecycle
// @requirements F03, E07, E09
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Apply receives a complete proposed configuration and returns a reason rather than partially mutating
// fields. The service-window timer represents a limited maintenance opportunity. Neither a timer nor a
// node ID authenticates a provisioning party; the transport and credential adapter must supply that trust.

#include "lifecycle/lifecycle.hpp"
#include "gs/logging.hpp"

namespace gs::node {

ConfigApplyResult LifecycleService::apply(const NodeConfig& desired) {
    GS_TRACE(gs::log::Category::Node, "N04", "apply.enter", "-");
    if (desired.node_id.empty() || desired.location.empty()) return {false, "identity_or_location_missing"};
    if (!desired.pir_enabled && !desired.reed_enabled) return {false, "no_enabled_input"};
    if (desired.heartbeat_seconds < 15 || desired.heartbeat_seconds > 3600) return {false, "heartbeat_out_of_range"};
    if (active_ && desired.version <= active_->version) return {false, "version_not_newer"};
    active_ = desired;
    return {true, "applied"};
}

void LifecycleService::open_service_window(Milliseconds now_ms, Milliseconds duration_ms) {
    GS_TRACE(gs::log::Category::Node, "N04", "open_service_window.enter", "-");
    service_window_until_ms_ = now_ms + duration_ms;
}

bool LifecycleService::service_window_open(Milliseconds now_ms) const {
    GS_TRACE(gs::log::Category::Node, "N04", "service_window_open.enter", "-");
    return now_ms <= service_window_until_ms_;
}

}  // namespace gs::node
