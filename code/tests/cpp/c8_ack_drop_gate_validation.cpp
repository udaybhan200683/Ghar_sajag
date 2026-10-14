#include "firmware/hub/target/esp32/hil_c8_ack_drop_gate.hpp"

#include <atomic>
#include <iostream>
#include <stdexcept>
#include <thread>

namespace {
int checks = 0;

void check(bool condition, const char* message) {
    ++checks;
    if (!condition) throw std::runtime_error(message);
}

void test_default_and_single_use() {
    gs::hub::target::C8AckDropGate gate;
    check(gs::hub::target::C8AckDropGate::eligible(true, true, true, true, true),
          "eligible gate requires durable effect and authoritative open-admission key proof");
    check(!gs::hub::target::C8AckDropGate::eligible(false, true, true, true, true) &&
          !gs::hub::target::C8AckDropGate::eligible(true, false, true, true, true) &&
          !gs::hub::target::C8AckDropGate::eligible(true, true, false, true, true) &&
          !gs::hub::target::C8AckDropGate::eligible(true, true, true, false, true) &&
          !gs::hub::target::C8AckDropGate::eligible(true, true, true, true, false),
          "each missing durability or admission proof must fail closed to normal ACK");
    check(gate.decide(10U, true) == gs::hub::target::C8AckDropDecision::NotArmed,
          "gate must default disabled");
    check(gate.arm(100U), "first bounded arm must succeed");
    check(!gate.arm(101U), "second arm during the active window must fail");
    check(gate.decide(102U, false) == gs::hub::target::C8AckDropDecision::Ineligible,
          "ineligible event must retain the armed gate");
    check(gate.decide(103U, true) == gs::hub::target::C8AckDropDecision::SuppressOneAck,
          "first eligible event must consume one suppression");
    check(gate.decide(104U, true) == gs::hub::target::C8AckDropDecision::NotArmed,
          "one-shot must not suppress a second acknowledgement");
}

void test_expiry_and_rearm() {
    gs::hub::target::C8AckDropGate gate;
    check(gate.arm(500U), "gate must arm before expiry test");
    check(gate.decide(500U + gs::hub::target::C8AckDropGate::kWindowMs, true) ==
              gs::hub::target::C8AckDropDecision::Expired,
          "expiry boundary must send the ordinary ACK");
    check(gate.decide(500U + gs::hub::target::C8AckDropGate::kWindowMs + 1U, true) ==
              gs::hub::target::C8AckDropDecision::NotArmed,
          "expired gate must be cleared");
    check(gate.arm(40000U), "an expired gate may be rearmed");
    check(gate.decide(40001U, true) == gs::hub::target::C8AckDropDecision::SuppressOneAck,
          "rearmed gate must still suppress exactly one eligible ACK");
    check(!gate.arm(UINT64_MAX - 5U), "deadline overflow must be rejected");
}

void test_concurrent_consume_is_single_use() {
    gs::hub::target::C8AckDropGate gate;
    check(gate.arm(900U), "gate must arm before concurrent consume");
    std::atomic<bool> start{false};
    std::atomic<int> suppressions{0};
    const auto consume = [&]() {
        while (!start.load(std::memory_order_acquire)) std::this_thread::yield();
        if (gate.decide(901U, true) ==
            gs::hub::target::C8AckDropDecision::SuppressOneAck) {
            suppressions.fetch_add(1, std::memory_order_relaxed);
        }
    };
    std::thread first(consume);
    std::thread second(consume);
    start.store(true, std::memory_order_release);
    first.join();
    second.join();
    check(suppressions.load(std::memory_order_relaxed) == 1,
          "racing eligible events must consume only one suppression");
}
}  // namespace

int main() {
    try {
        test_default_and_single_use();
        test_expiry_and_rearm();
        test_concurrent_consume_is_single_use();
        std::cout << "C8 ACK-drop gate PASS checks=" << checks << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "C8 ACK-drop gate FAIL: " << error.what() << '\n';
        return 1;
    }
}
