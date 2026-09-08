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
    TimeEstimate estimate(Milliseconds monotonic_ms) const;
    bool valid_for_absence(Milliseconds monotonic_ms, std::uint32_t max_uncertainty_s = 60) const;

private:
    bool anchored_{false};
    EpochSeconds anchor_time_{0};
    Milliseconds anchor_monotonic_ms_{0};
    std::uint32_t anchor_uncertainty_s_{0};
    static constexpr EpochSeconds kMaxAnchorAgeSeconds = 72 * 60 * 60;
};

}  // namespace gs::hub
