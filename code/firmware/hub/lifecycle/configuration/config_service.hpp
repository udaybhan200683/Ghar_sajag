// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H07 Hub lifecycle/config
// @requirements F02, F03, F04, F10, E06, E07, E09, NFR-07
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// ConfigService maintains the active hub snapshot and rejects stale versions and invalid ordering.
// Production persistence must replace the whole snapshot atomically and retain the prior valid one after
// interruption. Report both desired and applied versions to avoid hiding an offline hub.

#pragma once

#include "gs/domain.hpp"

#include <optional>
#include <string>

namespace gs::hub {

struct HomeConfigResult {
    bool applied{false};
    std::string reason;
    std::uint32_t applied_version{0};
};

class ConfigService {
public:
    HomeConfigResult apply(const HomeConfig& desired);
    const std::optional<HomeConfig>& active() const { return active_; }

private:
    std::optional<HomeConfig> active_;
};

}  // namespace gs::hub
