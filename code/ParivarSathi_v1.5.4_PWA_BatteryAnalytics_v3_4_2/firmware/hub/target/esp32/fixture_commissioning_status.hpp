#pragma once

#include <atomic>
#include <cstdint>

namespace gs::hub::target {

enum class FixtureCommissioningStatus : std::uint8_t {
    Idle, Queued, OfferActive, Rejected, TimedOut, AuthenticatedRejoin
};

// One exact fixture enrollment per boot; requests are retriable after a
// rejected request or the bounded owner timeout, but never while one is live.
class FixtureCommissioningState {
public:
    bool try_reserve_request() {
        auto current = status_.load(std::memory_order_acquire);
        while (current == FixtureCommissioningStatus::Idle ||
               current == FixtureCommissioningStatus::Rejected ||
               current == FixtureCommissioningStatus::TimedOut) {
            if (status_.compare_exchange_weak(current, FixtureCommissioningStatus::Queued,
                    std::memory_order_acq_rel, std::memory_order_acquire)) return true;
        }
        return false;
    }

    void publish(FixtureCommissioningStatus status) {
        status_.store(status, std::memory_order_release);
    }

    FixtureCommissioningStatus status() const {
        return status_.load(std::memory_order_acquire);
    }

private:
    std::atomic<FixtureCommissioningStatus> status_{FixtureCommissioningStatus::Idle};
};

}  // namespace gs::hub::target
