#pragma once

namespace gs::node::target {

// HIL security controls do not imply physical wake capability. The explicit
// qualification option preserves the awake behavior of existing HIL images.
constexpr bool physical_wake_permitted(bool hil_build, bool hil_control,
                                       bool qualification_wake) {
    return !hil_build && (!hil_control || qualification_wake);
}

}  // namespace gs::node::target
