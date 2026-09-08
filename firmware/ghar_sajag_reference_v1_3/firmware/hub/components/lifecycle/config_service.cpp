#include "lifecycle/config_service.hpp"
#include "gs/logging.hpp"

namespace gs::hub {

HomeConfigResult ConfigService::apply(const HomeConfig& desired) {
    GS_TRACE(gs::log::Category::Hub, "H07", "apply.enter", "-");
    if (desired.home_id.empty() || desired.timezone.empty()) return {false, "home_or_timezone_missing", active_ ? active_->version : 0};
    if (desired.morning.enabled &&
        (desired.morning.start_at >= desired.morning.end_at || desired.morning.end_at > desired.morning.grace_end_at)) {
        return {false, "invalid_window_boundaries", active_ ? active_->version : 0};
    }
    if (active_ && desired.version <= active_->version) return {false, "version_not_newer", active_->version};
    active_ = desired;
    return {true, "applied", desired.version};
}

}  // namespace gs::hub
