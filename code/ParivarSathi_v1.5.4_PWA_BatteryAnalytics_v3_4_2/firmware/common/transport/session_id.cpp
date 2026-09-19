#include "firmware/common/transport/session_id.hpp"

#include <limits>

namespace gs::transport {

std::optional<std::uint64_t> next_boot_session(SessionCounterStore& store) {
    std::uint64_t current = 0;
    bool found = false;
    if (!store.load(current, found)) return std::nullopt;
    if (!found) current = 0;
    if (current == std::numeric_limits<std::uint64_t>::max()) return std::nullopt;
    const auto next = current + 1U;
    if (!store.save(next)) return std::nullopt;
    return next;
}

}  // namespace gs::transport
