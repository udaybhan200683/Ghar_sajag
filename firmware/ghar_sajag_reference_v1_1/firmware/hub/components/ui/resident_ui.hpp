#pragma once

#include "gs/domain.hpp"

#include <cstdint>
#include <optional>
#include <string>

namespace gs::hub {

enum class ResidentAction { Ok, CallFamily, PrivacyEnabled, PrivacyDisabled };

struct Feedback {
    std::string code;
    std::string display_text;
    bool audible_prompt{false};
};

class ResidentUi {
public:
    DomainEvent make_action(ResidentAction action, const std::string& hub_id,
                            std::uint64_t session_id, std::uint64_t sequence,
                            EpochSeconds now, bool is_test = false) const;
    Feedback feedback_for(ResidentAction action, bool remote_available) const;
};

}  // namespace gs::hub
