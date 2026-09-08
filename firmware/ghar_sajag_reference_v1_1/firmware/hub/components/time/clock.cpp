#include "time/clock.hpp"
#include "gs/logging.hpp"

#include <algorithm>

namespace gs::hub {

void TrustedClock::anchor(EpochSeconds server_time, Milliseconds monotonic_ms, std::uint32_t uncertainty_s) {
    GS_TRACE(gs::log::Category::Hub, "H03", "anchor.enter", "-");
    anchored_ = true;
    anchor_time_ = server_time;
    anchor_monotonic_ms_ = monotonic_ms;
    anchor_uncertainty_s_ = uncertainty_s;
}

TimeEstimate TrustedClock::estimate(Milliseconds monotonic_ms) const {
    GS_TRACE(gs::log::Category::Hub, "H03", "estimate.enter", "-");
    if (!anchored_ || monotonic_ms < anchor_monotonic_ms_) return {};
    const auto elapsed_s = (monotonic_ms - anchor_monotonic_ms_) / 1000;
    const auto center = anchor_time_ + elapsed_s;
    const auto drift = elapsed_s / 10000;  // conservative 100 ppm host policy
    const auto uncertainty = static_cast<EpochSeconds>(anchor_uncertainty_s_) + drift;
    TimeEstimate result{center - uncertainty, center + uncertainty, TimeTrust::Trusted};
    if (elapsed_s > kMaxAnchorAgeSeconds) result.trust = TimeTrust::Expired;
    return result;
}

bool TrustedClock::valid_for_absence(Milliseconds monotonic_ms, std::uint32_t max_uncertainty_s) const {
    GS_TRACE(gs::log::Category::Hub, "H03", "valid_for_absence.enter", "-");
    const auto value = estimate(monotonic_ms);
    return value.trust == TimeTrust::Trusted && value.latest - value.earliest <= 2 * static_cast<EpochSeconds>(max_uncertainty_s);
}

}  // namespace gs::hub
