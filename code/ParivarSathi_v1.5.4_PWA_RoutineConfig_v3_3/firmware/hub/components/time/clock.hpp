// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H03 Hub time
// @requirements F04, F08, E03, E06
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Use estimate only with a monotonic value from the same continuity epoch as the anchor. A wall-time
// correction is not a reason to jump a monotonic timeout. An expired or missing anchor prevents absence
// inference until trusted time is restored; the reference is not itself a network time client.

#pragma once

#include "gs/domain.hpp"

#include <cstdint>
#include <optional>

namespace gs::hub {

enum class TimeTrust { Untrusted, Trusted, Expired };

struct TimeEstimate {
    EpochSeconds earliest{0};
    EpochSeconds latest{0};
    TimeTrust trust{TimeTrust::Untrusted};
};

class TrustedClock {
public:
    void anchor(EpochSeconds server_time, Milliseconds monotonic_ms, std::uint32_t uncertainty_s);
    // @requirements F04, F08, E03, E06
    // Advance a trusted anchor using elapsed time and uncertainty; do not treat a missing anchor as a
    // valid date.
    TimeEstimate estimate(Milliseconds monotonic_ms) const;
    // @requirements F04, F08, E03, E06
    // Gate absence inference on time trust and maximum uncertainty, rather than the existence of any wall-
    // clock value.
    bool valid_for_absence(Milliseconds monotonic_ms, std::uint32_t max_uncertainty_s = 60) const;

private:
    bool anchored_{false};
    EpochSeconds anchor_time_{0};
    Milliseconds anchor_monotonic_ms_{0};
    std::uint32_t anchor_uncertainty_s_{0};
    static constexpr EpochSeconds kMaxAnchorAgeSeconds = 72 * 60 * 60;
};

}  // namespace gs::hub
