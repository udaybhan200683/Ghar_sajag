// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module N04 Node lifecycle
// @requirements F03, E07, E09
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Apply receives a complete proposed configuration and returns a reason rather than partially mutating
// fields. The service-window timer represents a limited maintenance opportunity. Neither a timer nor a
// node ID authenticates a provisioning party; the transport and credential adapter must supply that trust.

#pragma once

#include "gs/domain.hpp"

#include <optional>
#include <string>

namespace gs::node {

struct ConfigApplyResult {
    bool applied{false};
    std::string reason;
};

class LifecycleService {
public:
    ConfigApplyResult apply(const NodeConfig& desired);
    void open_service_window(Milliseconds now_ms, Milliseconds duration_ms = 120000);
    bool service_window_open(Milliseconds now_ms) const;
    const std::optional<NodeConfig>& active() const { return active_; }

private:
    std::optional<NodeConfig> active_;
    Milliseconds service_window_until_ms_{0};
};

}  // namespace gs::node
