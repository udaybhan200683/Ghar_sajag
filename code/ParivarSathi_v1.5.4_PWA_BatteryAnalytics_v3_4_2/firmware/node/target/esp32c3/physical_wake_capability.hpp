#pragma once

#include "gs/domain.hpp"

namespace gs::node::target {

// HIL security controls do not imply physical wake capability. The explicit
// qualification option preserves the awake behavior of existing HIL images.
constexpr bool physical_wake_permitted(bool hil_build, bool hil_control,
                                       bool qualification_wake) {
    return !hil_build && (!hil_control || qualification_wake);
}

// The old HIL-control profile requests an early first health record for the
// FOTA fixture. Physical battery qualification follows the product deadline.
constexpr Milliseconds initial_node_health_deadline(Milliseconds now_ms,
                                                     Milliseconds interval_ms,
                                                     bool hil_control,
                                                     bool qualification_wake) {
    return hil_control && !qualification_wake ? 1000 : now_ms + interval_ms;
}

}  // namespace gs::node::target
