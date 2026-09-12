// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H06 Hub resident interface
// @requirements F02, F06, F07, F10, E03, AI05, NFR-02, NFR-10
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// ResidentUi creates semantic events and feedback values. The physical input adapter must separately
// debounce, distinguish buttons and enforce accessibility. feedback_for receives remote availability from
// the caller; that boolean is not proof that a notification was delivered to a person.

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
    // @requirements F02, F06, F07, F10, E03, AI05, NFR-02, NFR-10
    // Build a resident semantic event; physical debounce and durable local feedback belong to the runtime
    // adapter.
    DomainEvent make_action(ResidentAction action, const std::string& hub_id,
                            std::uint64_t session_id, std::uint64_t sequence,
                            EpochSeconds now, bool is_test = false) const;
    // @requirements F02, F06, F07, F10, E03, AI05, NFR-02, NFR-10
    // Choose local wording from caller-supplied availability; remote availability does not mean human
    // delivery.
    Feedback feedback_for(ResidentAction action, bool remote_available) const;
};

}  // namespace gs::hub
