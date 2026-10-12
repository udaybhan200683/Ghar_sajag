#pragma once
#include <cstdint>
namespace gs {
struct NodeHealthPolicy {
    std::uint32_t heartbeat_seconds{300};
    std::uint32_t offline_seconds{910};
    constexpr bool valid() const {
        return heartbeat_seconds >= 15 && heartbeat_seconds <= 3600 &&
               offline_seconds == 3 * heartbeat_seconds + 10;
    }
    static constexpr NodeHealthPolicy configured(std::uint32_t interval) {
        return {interval, 3 * interval + 10};
    }
};
} // namespace gs
