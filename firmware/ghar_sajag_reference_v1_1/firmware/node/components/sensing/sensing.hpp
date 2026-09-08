#pragma once

#include "gs/domain.hpp"

#include <optional>

namespace gs::node {

class QualifiedInput {
public:
    QualifiedInput(EventKind active_kind, std::optional<EventKind> inactive_kind,
                   Milliseconds debounce_ms, Milliseconds minimum_retrigger_ms);

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
