// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H07 Hub lifecycle/config
// @requirements F02, F03, F04, F10, E06, E07, E09, NFR-07
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// ConfigService maintains the active hub snapshot and rejects stale versions and invalid ordering.
// Production persistence must replace the whole snapshot atomically and retain the prior valid one after
// interruption. Report both desired and applied versions to avoid hiding an offline hub.

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
