#include "wifi_reconnect_policy.hpp"

#include <limits>

namespace gs::hub::connectivity {
namespace {
constexpr std::uint64_t kRetryDelaysMs[] = {
    1000, 2000, 4000, 8000, 16000, 30000, 60000};
constexpr std::uint8_t kMaximumRetryStage =
    static_cast<std::uint8_t>(sizeof(kRetryDelaysMs) / sizeof(kRetryDelaysMs[0]) - 1);
}

std::uint64_t WifiReconnectPolicy::retry_delay_ms() const {
    const auto stage = retry_stage_ > kMaximumRetryStage
        ? kMaximumRetryStage : retry_stage_;
    return kRetryDelaysMs[stage];
}

void WifiReconnectPolicy::schedule(std::uint64_t now_ms,
                                   std::uint64_t delay_ms) {
    next_attempt_ms_ = now_ms > std::numeric_limits<std::uint64_t>::max() - delay_ms
        ? std::numeric_limits<std::uint64_t>::max() : now_ms + delay_ms;
    scheduled_ = true;
}

void WifiReconnectPolicy::on_disconnected(std::uint64_t now_ms) {
    if (credentials_ready_ && !scheduled_) {
        schedule(now_ms, retry_delay_ms());
        if (retry_stage_ < kMaximumRetryStage) ++retry_stage_;
    }
}

void WifiReconnectPolicy::on_attempt_failed(std::uint64_t now_ms) {
    if (!credentials_ready_) return;
    schedule(now_ms, retry_delay_ms());
    if (retry_stage_ < kMaximumRetryStage) ++retry_stage_;
}

void WifiReconnectPolicy::on_credentials_ready(std::uint64_t now_ms) {
    credentials_ready_ = true;
    retry_stage_ = 0;
    schedule(now_ms, 0);
}

bool WifiReconnectPolicy::take_due_attempt(std::uint64_t now_ms) {
    if (!scheduled_ || now_ms < next_attempt_ms_) return false;
    scheduled_ = false;
    return true;
}

void WifiReconnectPolicy::on_connected() {
    retry_stage_ = 0;
    scheduled_ = false;
    next_attempt_ms_ = 0;
}

}  // namespace gs::hub::connectivity
