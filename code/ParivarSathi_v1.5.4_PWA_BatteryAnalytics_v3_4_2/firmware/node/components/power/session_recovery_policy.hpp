#pragma once

#include <algorithm>
#include <cstdint>
#include <optional>

namespace gs::node {

// Pure scheduling decisions used by the existing radio owner. No radio or NVS
// operation occurs here, so the same boundaries can be exercised on the host.
struct SessionRecoveryPolicy {
    static constexpr std::int64_t contact_timeout_ms = 430000;
    static constexpr std::int64_t v2_fallback_ms = 30000;
    static constexpr std::int64_t initial_ambiguity_window_ms = 180000;
    static constexpr std::int64_t maximum_ambiguity_window_ms = 3600000;

    static bool idle_expired(bool negotiated, std::int64_t now,
                             std::int64_t last_contact) {
        return negotiated && last_contact >= 0 && now >= last_contact &&
               now - last_contact >= contact_timeout_ms;
    }

    static bool health_ack_matches(bool negotiated,
                                   std::optional<std::uint64_t> outstanding,
                                   std::uint64_t received) {
        return negotiated && outstanding.has_value() && received != 0 &&
               *outstanding == received;
    }

    static bool active_expired(bool negotiated, std::int64_t now,
                               std::int64_t first_attempt,
                               unsigned completed_attempts,
                               std::int64_t last_contact) {
        return negotiated && first_attempt >= 0 && now >= first_attempt &&
               completed_attempts >= 3 && now - first_attempt >= 10000 &&
               last_contact <= first_attempt;
    }

    static bool may_fallback(bool pinned, bool authenticated_challenge,
                             std::uint8_t version, std::int64_t elapsed_ms) {
        return !pinned && !authenticated_challenge && version == 2 &&
               elapsed_ms >= v2_fallback_ms;
    }

    static bool ambiguity_expired(std::int64_t now, std::int64_t first_final,
                                   unsigned final_transmissions,
                                   std::int64_t window_ms) {
        return first_final >= 0 && now >= first_final &&
               final_transmissions >= 4 && now - first_final >= window_ms;
    }

    static std::int64_t next_ambiguity_window(std::int64_t current_ms) {
        return std::min(current_ms * 2, maximum_ambiguity_window_ms);
    }

    static std::int64_t retry_delay(unsigned attempt, std::uint64_t session) {
        constexpr std::int64_t delays[] = {1500, 3000, 10000, 20000, 40000, 60000};
        return delays[std::min<unsigned>(attempt, 5)] +
               static_cast<std::int64_t>((session * 37U + attempt * 17U) % 101U);
    }
};

}  // namespace gs::node
