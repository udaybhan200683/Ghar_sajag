// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H07 Hub lifecycle/config
// @requirements F02, F03, F04, F10, E06, E07, E09, NFR-07
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// ConfigService maintains the active hub snapshot and rejects stale versions and invalid ordering.
// Production persistence must replace the whole snapshot atomically and retain the prior valid one after
// interruption. Report both desired and applied versions to avoid hiding an offline hub.

#include "lifecycle/configuration/config_service.hpp"
#include "gs/logging.hpp"

#include <algorithm>
#include <set>

namespace gs::hub {

HomeConfigResult ConfigService::apply(const HomeConfig& desired) {
    GS_TRACE(gs::log::Category::Hub, "H07", "apply.enter", "-");
    if (desired.home_id.empty() || desired.timezone.empty()) return {false, "home_or_timezone_missing", active_ ? active_->version : 0};
    if (desired.morning.enabled &&
        (desired.morning.start_at >= desired.morning.end_at || desired.morning.end_at > desired.morning.grace_end_at)) {
        return {false, "invalid_window_boundaries", active_ ? active_->version : 0};
    }
    const auto& rules = desired.activity_rules;
    if (rules.morning_steps.size() > 24 ||
        (rules.morning_sequence_strict_order && rules.morning_steps.empty())) {
        return {false, "invalid_morning_steps", active_ ? active_->version : 0};
    }
    if (!rules.morning_steps.empty()) {
        std::set<std::string> locations;
        bool required_enabled = false;
        for (const auto& step : rules.morning_steps) {
            if (step.location.empty() || step.location.size() > 32 ||
                !locations.insert(step.location).second ||
                !std::all_of(step.location.begin(), step.location.end(), [](unsigned char ch) {
                    return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
                           (ch >= '0' && ch <= '9') || ch == '-' || ch == '_';
                })) {
                return {false, "invalid_morning_steps", active_ ? active_->version : 0};
            }
            required_enabled = required_enabled || (step.enabled && step.required);
        }
        if (!required_enabled)
            return {false, "morning_required_step_missing", active_ ? active_->version : 0};
    }
    if (rules.quiet_start_minute >= 24U * 60U || rules.quiet_end_minute >= 24U * 60U ||
        rules.daytime_start_minute >= 24U * 60U || rules.daytime_end_minute >= 24U * 60U ||
        rules.door_open_timeout_seconds < 30 || rules.door_open_timeout_seconds > 86400 ||
        rules.daytime_inactivity_seconds < 300 || rules.daytime_inactivity_seconds > 86400) {
        return {false, "invalid_activity_rules", active_ ? active_->version : 0};
    }
    if (active_ && desired.version <= active_->version) return {false, "version_not_newer", active_->version};
    active_ = desired;
    return {true, "applied", desired.version};
}

}  // namespace gs::hub
