#pragma once

#include <cstdint>
#include <optional>
#include <string>

namespace gs::node::target {

// Returns a session only after the incremented boot counter is committed to
// NVS. Failure is intentional and prevents reuse of an uncommitted identity.
std::optional<std::uint64_t> allocate_nvs_session_id();
std::optional<bool> health_ack_pinned_for_hub(const std::string& hub_id);
bool pin_health_ack_for_hub(const std::string& hub_id);

}  // namespace gs::node::target
