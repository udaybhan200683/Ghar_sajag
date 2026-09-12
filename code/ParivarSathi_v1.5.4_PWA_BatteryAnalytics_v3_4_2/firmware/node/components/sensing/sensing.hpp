// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module N01 Node sensing
// @requirements F05, F09
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The constructor selects motion or reed semantics. sample is called with a raw level and elapsed
// milliseconds. Keep GPIO inversion and electrical pull configuration in the adapter. Do not read a PIR
// high level at boot as a newly observed person. The debounce clock and sensor warm-up are different
// responsibilities.

#pragma once

#include "gs/domain.hpp"

#include <optional>

namespace gs::node {

class QualifiedInput {
public:
    QualifiedInput(EventKind active_kind, std::optional<EventKind> inactive_kind,
                   Milliseconds debounce_ms, Milliseconds minimum_retrigger_ms);

    // @requirements F05, F09
    // Qualify an electrical transition using debounce/retrigger clocks; the GPIO adapter supplies polarity
    // and warm-up handling.
    std::optional<EventKind> sample(bool raw_level, Milliseconds now_ms);
    bool stable_level() const { return stable_level_; }

private:
    EventKind active_kind_;
    std::optional<EventKind> inactive_kind_;
    Milliseconds debounce_ms_;
    Milliseconds minimum_retrigger_ms_;
    bool initialized_{false};
    bool raw_level_{false};
    bool stable_level_{false};
    Milliseconds raw_since_ms_{0};
    Milliseconds last_emit_ms_{-1};
};

}  // namespace gs::node
