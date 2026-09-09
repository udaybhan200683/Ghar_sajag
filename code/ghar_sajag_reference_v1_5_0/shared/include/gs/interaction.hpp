// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H09 Interaction controller
// @requirements AI01, AI02, AI03, AI04, AI05, AI08, NFR-04, NFR-07
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Controller owns state, current ID and start timestamp and borrows Provider by reference. Provider must
// outlive Controller, return promptly and never reenter it from start/cancel. A single owner serializes
// begin, complete, tick and cancel. start failure leaves Failed although begin returns Accepted; callers
// must inspect state.

#pragma once
#include "gs/product.hpp"
#include "gs/logging.hpp"
#include <cstdint>
#include <limits>

namespace gs::interaction {
enum class State { Idle, Waiting, Ready, Failed };
enum class Result { Accepted, Disabled, NoConsent, Offline, Busy, Exhausted };
// The adapter must return promptly. Network/audio work belongs in its worker.
// Completion is delivered to Controller on its owning task, never concurrently.
struct Provider {
    virtual ~Provider() = default;
    virtual bool start(std::uint64_t id) noexcept = 0;
    // @requirements AI01, AI02, AI03, AI04, AI05, AI08, NFR-04, NFR-07
    // Return to Idle. Provider cancellation is called only while Waiting; a future coordinator must also
    // stop Ready-state playback.
    virtual void cancel(std::uint64_t id) noexcept = 0;
};
class Controller {
public:
    explicit Controller(Provider& provider) noexcept : provider_(provider) {}
    // @requirements AI01, AI02, AI03, AI04, AI05, AI08, NFR-04, NFR-07
    // Admit at most one AI session. Accepted means admission occurred; immediate provider failure still
    // leaves state Failed.
    Result begin(std::uint64_t now_ms, bool consent, bool online) noexcept {
        if constexpr (!Product::ai) return Result::Disabled;
        if (!consent) return Result::NoConsent;
        if (!online) return Result::Offline;
        if (state_ == State::Waiting) return Result::Busy;
        if (id_ == std::numeric_limits<std::uint64_t>::max()) return Result::Exhausted;
        ++id_;
        started_ = now_ms;
        state_ = State::Waiting;
        GS_TRACE(log::Category::Hub, "interaction", "begin", "-");
        if (!provider_.start(id_)) {
            state_ = State::Failed;
            GS_ERROR(log::Category::Hub, "interaction", "provider_start_failed", "-");
        }
        return Result::Accepted;
    }
    // @requirements AI01, AI02, AI03, AI04, AI05, AI08, NFR-04, NFR-07
    // Accept only the active Waiting request ID; reject duplicate, cancelled and late completions.
    bool complete(std::uint64_t id, bool success) noexcept {
        if (state_ != State::Waiting || id != id_) return false;
        state_ = success ? State::Ready : State::Failed;
        if (!success) GS_ERROR(log::Category::Hub, "interaction", "provider_failed", "-");
        GS_TRACE(log::Category::Hub, "interaction", "complete", "-");
        return true;
    }
    // @requirements AI01, AI02, AI03, AI04, AI05, AI08, NFR-04, NFR-07
    // Expire a waiting session using elapsed monotonic time; the owning scheduler must call this even
    // during network stalls.
    void tick(std::uint64_t now_ms) noexcept {
        if (state_ == State::Waiting && now_ms - started_ >= timeout_ms) {
            state_ = State::Failed;
            provider_.cancel(id_);
            GS_ERROR(log::Category::Hub, "interaction", "timeout", "-");
        }
    }
    // Use for resident cancel, consent revocation, or monitoring prompt priority.
    // @requirements AI01, AI02, AI03, AI04, AI05, AI08, NFR-04, NFR-07
    // Return to Idle. Provider cancellation is called only while Waiting; a future coordinator must also
    // stop Ready-state playback.
    void cancel() noexcept {
        const bool waiting = state_ == State::Waiting;
        state_ = State::Idle;
        if (waiting) provider_.cancel(id_);
        GS_TRACE(log::Category::Hub, "interaction", "cancel", "-");
    }
    State state() const noexcept { return state_; }
    std::uint64_t id() const noexcept { return id_; }
    static constexpr std::uint64_t timeout_ms = 30000;
private:
    Provider& provider_;
    State state_{State::Idle};
    std::uint64_t id_{0};
    std::uint64_t started_{0};
};
}
