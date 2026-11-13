#include "firmware/node/target/esp32c3/idf/main/hil_command_line.hpp"

#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

namespace {
using gs::node::target::HilCommandLine;

void feed(HilCommandLine& parser, const std::string& input,
          std::vector<std::string>& commands, unsigned& too_long,
          unsigned& discarded) {
    for (char ch : input) {
        switch (parser.push(ch)) {
            case HilCommandLine::Result::NeedMore:
                break;
            case HilCommandLine::Result::CommandReady:
                commands.emplace_back(parser.command());
                parser.clear();
                break;
            case HilCommandLine::Result::CommandTooLong:
                ++too_long;
                break;
            case HilCommandLine::Result::DiscardedLine:
                ++discarded;
                break;
        }
    }
}

void require(bool condition, const char* message, unsigned& checks) {
    ++checks;
    if (!condition) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(1);
    }
}
}  // namespace

int main() {
    unsigned checks = 0;
    unsigned too_long = 0;
    unsigned discarded = 0;
    std::vector<std::string> commands;
    HilCommandLine parser;

    // The parser must buffer fragmented input and dispatch only at LF.
    feed(parser, "GET_", commands, too_long, discarded);
    require(commands.empty(), "fragment dispatched before line terminator", checks);
    feed(parser, "STATE\r\nGET_STATE\n", commands, too_long, discarded);
    require(commands.size() == 2 && commands[0] == "GET_STATE" &&
                commands[1] == "GET_STATE",
            "fragmented LF and CRLF commands were not preserved", checks);

    // Match the observed overflow/suffix pattern, then prove the next complete
    // valid command is handled normally.
    const std::string oversized(64, 'X');
    feed(parser, oversized + "STATE\nGET_STATE\n", commands, too_long, discarded);
    require(too_long == 1 && discarded == 1,
            "oversized input did not reject exactly one complete line", checks);
    require(commands.size() == 3 && commands.back() == "GET_STATE",
            "oversized suffix was dispatched or parser failed to recover", checks);

    // The maximum permitted payload remains accepted, and malformed input
    // split over multiple serial reads still recovers at its newline.
    const std::string boundary(HilCommandLine::kMaxCommandLength, 'A');
    feed(parser, boundary + "\n", commands, too_long, discarded);
    require(commands.size() == 4 && commands.back() == boundary,
            "63-character command boundary changed", checks);
    feed(parser, std::string(63, 'B'), commands, too_long, discarded);
    feed(parser, "Bbad-suffix\r\nGET_STATE\n", commands, too_long, discarded);
    require(too_long == 2 && discarded == 2,
            "fragmented oversized command was not rejected once", checks);
    require(commands.size() == 5 && commands.back() == "GET_STATE",
            "parser did not recover after fragmented oversized line", checks);

    std::cout << "C3 HIL command parser PASS checks=" << checks << '\n';
    return 0;
}
