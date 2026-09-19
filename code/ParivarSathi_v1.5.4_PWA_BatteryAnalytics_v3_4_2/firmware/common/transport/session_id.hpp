#pragma once

#include <cstdint>
#include <optional>

namespace gs::transport {

class SessionCounterStore {
public:
    virtual ~SessionCounterStore() = default;
    virtual bool load(std::uint64_t& value, bool& found) = 0;
    virtual bool save(std::uint64_t value) = 0;
};

// Atomically from the caller's perspective, advance a persistent boot counter.
// The backing store is responsible for durable commit before save returns true.
// Failure is fail-closed: target composition must not start with a reused or
// uncommitted session identity.
std::optional<std::uint64_t> next_boot_session(SessionCounterStore& store);

}  // namespace gs::transport
