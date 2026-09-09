// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module N01 Node sensing
// @requirements F05, F09
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The constructor selects motion or reed semantics. sample is called with a raw level and elapsed
// milliseconds. Keep GPIO inversion and electrical pull configuration in the adapter. Do not read a PIR
// high level at boot as a newly observed person. The debounce clock and sensor warm-up are different
// responsibilities.

#include "sensing/sensing.hpp"
#include "gs/logging.hpp"

namespace gs::node {

QualifiedInput::QualifiedInput(EventKind active_kind, std::optional<EventKind> inactive_kind,
                               Milliseconds debounce_ms, Milliseconds minimum_retrigger_ms)
    : active_kind_(active_kind),
      inactive_kind_(inactive_kind),
      debounce_ms_(debounce_ms),
      minimum_retrigger_ms_(minimum_retrigger_ms) {
    GS_TRACE(gs::log::Category::Node, "N01", "QualifiedInput.enter", "-");}

// @requirements F05, F09
// Qualify an electrical transition using debounce/retrigger clocks; the GPIO adapter supplies polarity
// and warm-up handling.
std::optional<EventKind> QualifiedInput::sample(bool raw_level, Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Node, "N01", "sample.enter", "-");
    if (!initialized_) {
        initialized_ = true;
        raw_level_ = raw_level;
        stable_level_ = raw_level;
        raw_since_ms_ = now_ms;
        return std::nullopt;
    }
    if (raw_level != raw_level_) {
        raw_level_ = raw_level;
        raw_since_ms_ = now_ms;
        return std::nullopt;
    }
    if (raw_level_ == stable_level_ || now_ms - raw_since_ms_ < debounce_ms_) return std::nullopt;

    stable_level_ = raw_level_;
    if (last_emit_ms_ >= 0 && now_ms - last_emit_ms_ < minimum_retrigger_ms_) return std::nullopt;
    if (stable_level_) {
        last_emit_ms_ = now_ms;
        return active_kind_;
    }
    if (inactive_kind_) {
        last_emit_ms_ = now_ms;
        return inactive_kind_;
    }
    return std::nullopt;
}

}  // namespace gs::node
