// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module T01 Simulation/CI
// @requirements E08, E10, V01, AI01, AI03, NFR-08
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The Makefile builds host C++17 and runs Python/JavaScript tests plus simulator fixtures. Tests prove
// their asserted paths, not every SRD criterion. Keep a clean command transcript and attach additional
// scenario tests as requirements are integrated.

#include "gs/interaction.hpp"
#include <cassert>
#include <iostream>
using namespace gs::interaction;
struct Fake final : Provider {
    int starts{0}; int cancels{0}; bool available{true};
    bool start(std::uint64_t) noexcept override { ++starts; return available; }
    // @requirements E08, E10, V01, AI01, AI03, NFR-08
    // Return to Idle. Provider cancellation is called only while Waiting; a future coordinator must also
    // stop Ready-state playback.
    void cancel(std::uint64_t) noexcept override { ++cancels; }
};
int main() {
    Fake p;
    Controller c(p);
    if constexpr (!gs::Product::ai) {
        assert(c.begin(0, true, true) == Result::Disabled);
        assert(p.starts == 0);
        assert(!c.complete(0, true));
    } else {
        assert(c.begin(0, false, true) == Result::NoConsent);
        assert(c.begin(0, true, false) == Result::Offline);
        assert(p.starts == 0);
        assert(c.begin(100, true, true) == Result::Accepted);
        const auto first = c.id();
        assert(c.begin(101, true, true) == Result::Busy);
        assert(!c.complete(first + 1, true));
        c.tick(30099); assert(c.state() == State::Waiting);
        c.tick(30100); assert(c.state() == State::Failed);
        assert(p.cancels == 1);
        assert(!c.complete(first, true));
        assert(c.begin(31000, true, true) == Result::Accepted);
        assert(!c.complete(first, true));
        assert(c.complete(c.id(), true));
        assert(c.state() == State::Ready);
        assert(!c.complete(c.id(), true));
        c.begin(32000, true, true); c.cancel();
        assert(p.cancels == 2 && c.state() == State::Idle);
        assert(!c.complete(c.id(), true));
        p.available = false;
        c.begin(33000, true, true); assert(c.state() == State::Failed);
        p.available = true;
        c.begin(34000, true, true);
        assert(c.complete(c.id(), false));
        assert(c.state() == State::Failed);
    }
    std::cout << gs::Product::name << " product tests passed; controller bytes=" << sizeof(Controller) << '\n';
}
