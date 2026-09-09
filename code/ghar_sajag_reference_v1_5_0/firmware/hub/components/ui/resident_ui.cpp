// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H06 Hub resident interface
// @requirements F02, F06, F07, F10, E03, AI05, NFR-02, NFR-10
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// ResidentUi creates semantic events and feedback values. The physical input adapter must separately
// debounce, distinguish buttons and enforce accessibility. feedback_for receives remote availability from
// the caller; that boolean is not proof that a notification was delivered to a person.

#include "ui/resident_ui.hpp"
#include "gs/logging.hpp"

namespace gs::hub {

// @requirements F02, F06, F07, F10, E03, AI05, NFR-02, NFR-10
// Build a resident semantic event; physical debounce and durable local feedback belong to the runtime
// adapter.
DomainEvent ResidentUi::make_action(ResidentAction action, const std::string& hub_id,
                                    std::uint64_t session_id, std::uint64_t sequence,
                                    EpochSeconds now, bool is_test) const {
    GS_TRACE(gs::log::Category::Hub, "H06", "make_action.enter", "-");
    EventKind kind = EventKind::OkPressed;
    if (action == ResidentAction::CallFamily) kind = EventKind::CallFamily;
    else if (action == ResidentAction::PrivacyEnabled) kind = EventKind::PrivacyOn;
    else if (action == ResidentAction::PrivacyDisabled) kind = EventKind::PrivacyOff;
    return DomainEvent{{hub_id, session_id, sequence}, kind, "hub", 0, now, now, 0, 0, is_test};
}

// @requirements F02, F06, F07, F10, E03, AI05, NFR-02, NFR-10
// Choose local wording from caller-supplied availability; remote availability does not mean human
// delivery.
Feedback ResidentUi::feedback_for(ResidentAction action, bool remote_available) const {
    GS_TRACE(gs::log::Category::Hub, "H06", "feedback_for.enter", "-");
    if (action == ResidentAction::PrivacyEnabled) return {"PRIVACY_ON", "Observation paused", true};
    if (action == ResidentAction::PrivacyDisabled) return {"PRIVACY_OFF", "Observation resumed", true};
    if (action == ResidentAction::Ok) return {"OK_SAVED", remote_available ? "I'm OK shared" : "I'm OK saved locally", true};
    return {"CALL_SAVED", remote_available ? "Family request accepted" : "Request saved; internet unavailable", true};
}

}  // namespace gs::hub
