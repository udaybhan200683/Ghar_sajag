#pragma once

#include <atomic>
#include <cstdint>

namespace gs::hub::target {

enum class C8AckDropDecision : std::uint8_t {
    NotArmed,
    Ineligible,
    Expired,
    SuppressOneAck,
};

// Bounded cross-task gate for the isolated GS-114 S3 fixture profile. The UART
// owner arms it; the authenticated Hub event owner consumes it only after the
// exact EventKey is found in the durable outbox. A duplicate therefore gets a
// normal ACK after this one-shot is consumed.
class C8AckDropGate {
public:
    static constexpr std::uint64_t kWindowMs = 30000U;

    static constexpr bool eligible(bool durable_ack, bool state_changed,
                                   bool outbox_lookup_succeeded,
                                   bool exact_key_found, bool admission_open) noexcept {
        return durable_ack && state_changed && outbox_lookup_succeeded &&
               exact_key_found && admission_open;
    }

    bool arm(std::uint64_t now_ms) {
        if (now_ms > UINT64_MAX - kWindowMs) return false;
        const auto replacement = now_ms + kWindowMs;
        auto observed = deadline_ms_.load(std::memory_order_acquire);
        for (;;) {
            if (observed != 0U && observed > now_ms) return false;
            if (deadline_ms_.compare_exchange_weak(
                    observed, replacement, std::memory_order_acq_rel,
                    std::memory_order_acquire)) return true;
        }
    }

    C8AckDropDecision decide(std::uint64_t now_ms, bool eligible) {
        auto observed = deadline_ms_.load(std::memory_order_acquire);
        for (;;) {
            if (observed == 0U) return C8AckDropDecision::NotArmed;
            if (now_ms >= observed) {
                if (deadline_ms_.compare_exchange_weak(
                        observed, 0U, std::memory_order_acq_rel,
                        std::memory_order_acquire)) return C8AckDropDecision::Expired;
                continue;
            }
            if (!eligible) return C8AckDropDecision::Ineligible;
            if (deadline_ms_.compare_exchange_weak(
                    observed, 0U, std::memory_order_acq_rel,
                    std::memory_order_acquire)) return C8AckDropDecision::SuppressOneAck;
        }
    }

private:
    std::atomic<std::uint64_t> deadline_ms_{0U};
};

}  // namespace gs::hub::target
