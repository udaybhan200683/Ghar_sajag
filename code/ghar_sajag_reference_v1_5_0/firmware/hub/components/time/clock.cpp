// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H03 Hub time
// @requirements F04, F08, E03, E06
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Use estimate only with a monotonic value from the same continuity epoch as the anchor. A wall-time
// correction is not a reason to jump a monotonic timeout. An expired or missing anchor prevents absence
// inference until trusted time is restored; the reference is not itself a network time client.

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

// @requirements F04, F08, E03, E06
// Advance a trusted anchor using elapsed time and uncertainty; do not treat a missing anchor as a
// valid date.
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

// @requirements F04, F08, E03, E06
// Gate absence inference on time trust and maximum uncertainty, rather than the existence of any wall-
// clock value.
bool TrustedClock::valid_for_absence(Milliseconds monotonic_ms, std::uint32_t max_uncertainty_s) const {
    GS_TRACE(gs::log::Category::Hub, "H03", "valid_for_absence.enter", "-");
    const auto value = estimate(monotonic_ms);
    return value.trust == TimeTrust::Trusted && value.latest - value.earliest <= 2 * static_cast<EpochSeconds>(max_uncertainty_s);
}

}  // namespace gs::hub
