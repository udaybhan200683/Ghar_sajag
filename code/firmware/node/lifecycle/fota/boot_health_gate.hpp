#pragma once

#include <cstdint>

namespace gs::node::fota {

struct BootHealthObservation {
    bool owner_started{false};
    bool sensing_ready{false};
    bool post_sensing_radio_confirmed{false};
    bool maintenance_active{false};
    std::uint32_t post_sensing_runtime_ticks{0};
    std::uint32_t minimum_free_heap{0};
};

enum class BootHealthDecision { Wait, Validate, Rollback };

// A pending OTA image must prove local sensing/runtime health and a fresh
// post-sensing MAC delivery before the bootloader rollback is cancelled.
// This does not prove Hub application admission or firmware authenticity.
inline constexpr std::uint64_t kBootHealthDeadlineMs = 90000;
inline constexpr std::uint32_t kBootHealthMinHeapBytes = 8192;

BootHealthDecision evaluate_boot_health(const BootHealthObservation& observation,
                                        std::uint64_t elapsed_ms);

}  // namespace gs::node::fota
