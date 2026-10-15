#pragma once

#include <cstdint>
#include <mutex>
#include <string>

namespace gs::hub::target {

enum class C8AckHoldDecision : std::uint8_t {
    Normal,
    CapturedAndHeld,
    SameKeyHeld,
    Released,
    WatchdogExpired,
};

// Isolated GS-114 fixture only. The Hub owner invokes decide() after authenticated
// durable processing and exact-key outbox lookup, before constructing an ACK.
// No ACK frame is cached: release permits the normal fresh authenticated ACK on
// the next exact-key retry. Unrelated keys always retain the production path.
class C8AckHoldGate {
public:
    static constexpr std::uint64_t kArmWindowMs = 30000;
    static constexpr std::uint64_t kHoldMs = 12000;
    static constexpr std::uint64_t kWatchdogMs = 15000;

    struct Snapshot {
        enum class State : std::uint8_t { Disarmed, Armed, Holding, Released, Expired, Cancelled };
        State state{State::Disarmed};
        std::string key;
        std::uint64_t committed_at_ms{0};
        std::uint64_t ended_at_ms{0};
        std::uint32_t held_attempts{0};
        std::uint32_t duplicate_deliveries{0};
        std::uint32_t logical_effects{0};
    };

    bool arm(std::uint64_t now_ms) {
        std::lock_guard<std::mutex> guard(mu_);
        expire_locked(now_ms);
        if (state_.state == Snapshot::State::Armed ||
            state_.state == Snapshot::State::Holding ||
            now_ms > UINT64_MAX - kArmWindowMs) return false;
        state_ = {};
        state_.state = Snapshot::State::Armed;
        armed_until_ms_ = now_ms + kArmWindowMs;
        return true;
    }

    C8AckHoldDecision decide(std::uint64_t now_ms, const std::string& key,
                             bool durable_ack, bool state_changed,
                             bool exact_key_durable, bool admission_open) {
        std::lock_guard<std::mutex> guard(mu_);
        const auto expired = expire_locked(now_ms);
        if (state_.state == Snapshot::State::Armed) {
            if (!durable_ack || !state_changed || !exact_key_durable ||
                !admission_open || key.empty() ||
                now_ms > UINT64_MAX - kWatchdogMs) return C8AckHoldDecision::Normal;
            state_.state = Snapshot::State::Holding;
            state_.key = key;
            state_.committed_at_ms = now_ms;
            state_.logical_effects = 1;
            state_.held_attempts = 1;
            return C8AckHoldDecision::CapturedAndHeld;
        }
        if (state_.key != key || key.empty()) return C8AckHoldDecision::Normal;
        if (state_.state == Snapshot::State::Holding && durable_ack &&
            exact_key_durable && admission_open) {
            ++state_.held_attempts;
            if (!state_changed) ++state_.duplicate_deliveries;
            else ++state_.logical_effects;
            return C8AckHoldDecision::SameKeyHeld;
        }
        if (expired) return C8AckHoldDecision::WatchdogExpired;
        return state_.state == Snapshot::State::Released
            ? C8AckHoldDecision::Released : C8AckHoldDecision::Normal;
    }

    bool release(std::uint64_t now_ms) {
        std::lock_guard<std::mutex> guard(mu_);
        expire_locked(now_ms);
        if (state_.state != Snapshot::State::Holding ||
            now_ms - state_.committed_at_ms < kHoldMs) return false;
        state_.state = Snapshot::State::Released;
        state_.ended_at_ms = now_ms;
        return true;
    }

    bool cancel(std::uint64_t now_ms) {
        std::lock_guard<std::mutex> guard(mu_);
        expire_locked(now_ms);
        if (state_.state != Snapshot::State::Armed &&
            state_.state != Snapshot::State::Holding) return false;
        state_.state = Snapshot::State::Cancelled;
        state_.ended_at_ms = now_ms;
        return true;
    }

    Snapshot snapshot(std::uint64_t now_ms) {
        std::lock_guard<std::mutex> guard(mu_);
        expire_locked(now_ms);
        return state_;
    }

private:
    bool expire_locked(std::uint64_t now_ms) {
        if ((state_.state == Snapshot::State::Armed && now_ms >= armed_until_ms_) ||
            (state_.state == Snapshot::State::Holding &&
             now_ms - state_.committed_at_ms >= kWatchdogMs)) {
            state_.state = Snapshot::State::Expired;
            state_.ended_at_ms = now_ms;
            return true;
        }
        return false;
    }

    std::mutex mu_;
    Snapshot state_{};
    std::uint64_t armed_until_ms_{0};
};

}  // namespace gs::hub::target
