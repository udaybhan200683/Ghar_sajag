#pragma once

#include <cstdint>
#include <optional>

namespace gs::node::target {

// Returns a session only after the incremented boot counter is committed to
// NVS. Failure is intentional and prevents reuse of an uncommitted identity.
std::optional<std::uint64_t> allocate_nvs_session_id();

}  // namespace gs::node::target
