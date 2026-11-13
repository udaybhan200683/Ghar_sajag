#pragma once

#include <array>
#include <cstddef>

namespace gs::node::target {

// Bounded line framing for the TEST_ONLY C3 console. An oversized line is
// rejected as a whole; its suffix must never be dispatched as a new command.
class HilCommandLine final {
public:
    static constexpr std::size_t kMaxCommandLength = 63;

    enum class Result {
        NeedMore,
        CommandReady,
        CommandTooLong,
        DiscardedLine,
    };

    Result push(char ch) noexcept {
        if (discarding_) {
            if (ch == '\n') {
                discarding_ = false;
                clear();
                return Result::DiscardedLine;
            }
            return Result::NeedMore;
        }
        if (ch == '\r') {
            return Result::NeedMore;
        }
        if (ch == '\n') {
            command_[length_] = '\0';
            return Result::CommandReady;
        }
        if (length_ < kMaxCommandLength) {
            command_[length_++] = ch;
            command_[length_] = '\0';
            return Result::NeedMore;
        }

        clear();
        discarding_ = true;
        return Result::CommandTooLong;
    }

    const char* command() const noexcept { return command_.data(); }

    void clear() noexcept {
        length_ = 0;
        command_[0] = '\0';
    }

private:
    std::array<char, kMaxCommandLength + 1> command_{};
    std::size_t length_{0};
    bool discarding_{false};
};

}  // namespace gs::node::target
