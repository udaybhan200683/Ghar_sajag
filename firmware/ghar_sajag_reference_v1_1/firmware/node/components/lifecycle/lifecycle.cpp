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
