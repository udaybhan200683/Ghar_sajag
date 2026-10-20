#pragma once

#include <cstdint>
#include <optional>

namespace gs::connectivity {

// The R1 pilot is India-only. Keep this profile in common firmware code so
// both radio targets derive their regulatory country and channel range from
// the same versioned definition.
struct IndiaWifiProfileV1 {
    static constexpr std::uint8_t version = 1;
    static constexpr char country_code[] = "IN";
    static constexpr std::uint8_t first_2ghz_channel = 1;
    static constexpr std::uint8_t last_2ghz_channel = 13;
    static constexpr std::uint8_t channel_count =
        last_2ghz_channel - first_2ghz_channel + 1U;

    static constexpr bool allows_channel(std::uint8_t channel) {
        return channel >= first_2ghz_channel && channel <= last_2ghz_channel;
    }

    static constexpr std::uint8_t next_channel(std::uint8_t channel) {
        return !allows_channel(channel) || channel == last_2ghz_channel
            ? first_2ghz_channel
            : static_cast<std::uint8_t>(channel + 1U);
    }

    // Api provides static success plus set_country_code(code, ieee80211d)
    // and get_country_code(buffer). This keeps the exact production operation
    // host-testable without replacing or emulating ESP-IDF's radio driver.
    template <typename Api>
    static bool configure_country(Api& api) {
        if (api.set_country_code(country_code, false) != Api::success) return false;
        char active_country[3]{};
        return api.get_country_code(active_country) == Api::success &&
               active_country[0] == country_code[0] &&
               active_country[1] == country_code[1];
    }
};

// Advances only when the existing bounded rejoin scheduler sends a Hello.
// An authenticated challenge pins its observed channel through Final/ACK
// retries. A new session remembers the prior successful channel in RAM only.
class IndiaWifiChannelDiscovery {
public:
    std::optional<std::uint8_t> next_rejoin_hello_channel() {
        if (candidate_pinned_) return candidate_channel_;
        candidate_channel_ = next_channel_;
        next_channel_ = IndiaWifiProfileV1::next_channel(next_channel_);
        return candidate_channel_;
    }

    void begin_rejoin() {
        if (!search_active_) {
            next_channel_ = last_authenticated_channel_ != 0
                ? last_authenticated_channel_
                : IndiaWifiProfileV1::first_2ghz_channel;
            search_active_ = true;
        }
        candidate_pinned_ = false;
        candidate_channel_ = 0;
    }

    bool pin_authenticated_challenge(std::uint8_t channel) {
        if (!IndiaWifiProfileV1::allows_channel(channel)) return false;
        candidate_channel_ = channel;
        candidate_pinned_ = true;
        return true;
    }

    bool complete_authenticated_session(std::uint8_t channel) {
        if (!IndiaWifiProfileV1::allows_channel(channel)) return false;
        last_authenticated_channel_ = channel;
        candidate_channel_ = channel;
        candidate_pinned_ = false;
        search_active_ = false;
        next_channel_ = channel;
        return true;
    }

    std::uint8_t current_channel() const {
        if (candidate_channel_ != 0) return candidate_channel_;
        if (last_authenticated_channel_ != 0) return last_authenticated_channel_;
        return IndiaWifiProfileV1::first_2ghz_channel;
    }

    std::uint8_t last_authenticated_channel() const {
        return last_authenticated_channel_;
    }
    bool candidate_pinned() const { return candidate_pinned_; }

private:
    std::uint8_t next_channel_{IndiaWifiProfileV1::first_2ghz_channel};
    std::uint8_t candidate_channel_{0};
    std::uint8_t last_authenticated_channel_{0};
    bool search_active_{true};
    bool candidate_pinned_{false};
};

}  // namespace gs::connectivity
