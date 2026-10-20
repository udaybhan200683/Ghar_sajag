#pragma once

#include <cstdint>

namespace gs::hub::connectivity {

// Rate-limits station reconnect attempts after link loss. This policy contains
// no credentials and never changes ESP-NOW/session state.
class WifiReconnectPolicy {
public:
    static constexpr std::uint64_t kInitialDelayMs = 1000;
    static constexpr std::uint64_t kMaximumDelayMs = 60000;

    // Schedule a retry after a disconnect or immediate retryable failure.
    // Repeated disconnect notifications do not postpone an already scheduled
    // retry.
    void on_disconnected(std::uint64_t now_ms);
    void on_attempt_failed(std::uint64_t now_ms);

    // A newly committed credential generation may request one immediate
    // connection attempt. The caller must only invoke this after secure-store
    // commit succeeds.
    void on_credentials_ready(std::uint64_t now_ms);

    // Returns true once when a scheduled attempt becomes due.
    bool take_due_attempt(std::uint64_t now_ms);

    // A received station IP address ends the retry sequence.
    void on_connected();

    bool scheduled() const { return scheduled_; }
    std::uint64_t retry_delay_ms() const;
    std::uint64_t next_attempt_ms() const { return next_attempt_ms_; }

private:
    void schedule(std::uint64_t now_ms, std::uint64_t delay_ms);

    std::uint8_t retry_stage_{0};
    bool scheduled_{false};
    bool credentials_ready_{false};
    std::uint64_t next_attempt_ms_{0};
};

}  // namespace gs::hub::connectivity
