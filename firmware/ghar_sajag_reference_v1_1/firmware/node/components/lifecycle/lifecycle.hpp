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
