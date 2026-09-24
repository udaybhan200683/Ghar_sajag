#include "firmware/node/fota/boot_health_gate.hpp"

namespace gs::node::fota {

BootHealthDecision evaluate_boot_health(const BootHealthObservation& observation,
                                        std::uint64_t elapsed_ms) {
    if (elapsed_ms >= kBootHealthDeadlineMs) return BootHealthDecision::Rollback;
    if (observation.owner_started && observation.sensing_ready &&
        observation.post_sensing_radio_confirmed && !observation.maintenance_active &&
        observation.post_sensing_runtime_ticks >= 2U &&
        observation.minimum_free_heap >= kBootHealthMinHeapBytes) {
        return BootHealthDecision::Validate;
    }
    return BootHealthDecision::Wait;
}

}  // namespace gs::node::fota
