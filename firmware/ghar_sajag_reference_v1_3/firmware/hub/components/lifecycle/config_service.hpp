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
