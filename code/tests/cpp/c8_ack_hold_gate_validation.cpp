#include "firmware/hub/target/esp32/hil_c8_ack_hold_gate.hpp"

#include <atomic>
#include <iostream>
#include <stdexcept>
#include <thread>

namespace {
using Gate = gs::hub::target::C8AckHoldGate;
using Decision = gs::hub::target::C8AckHoldDecision;
using State = Gate::Snapshot::State;
int checks = 0;

void require(bool condition, const char* message) {
    ++checks;
    if (!condition) throw std::runtime_error(message);
}

void hold_release_exact_key() {
    Gate gate;
    require(gate.decide(1, "K", true, true, true, true) == Decision::Normal,
            "default must not hold an ACK");
    require(gate.arm(100), "arm before event");
    require(!gate.arm(101), "cannot rearm an active fixture");
    require(gate.decide(102, "bad", true, false, true, true) == Decision::Normal,
            "duplicate cannot capture an unbound key");
    require(gate.decide(103, "bad", true, true, false, true) == Decision::Normal,
            "non-durable key cannot capture");
    require(gate.decide(104, "K", true, true, true, true) == Decision::CapturedAndHeld,
            "authenticated durable first effect captures K");
    require(gate.decide(105, "other", true, true, true, true) == Decision::Normal,
            "unrelated key ACK must flow normally");
    require(gate.decide(106, "K", true, false, true, true) == Decision::SameKeyHeld,
            "duplicate K ACK must remain held");
    require(gate.decide(107, "K", false, false, true, true) == Decision::Normal,
            "volatile ACK must not be held");
    require(gate.decide(108, "K", true, false, false, true) == Decision::Normal,
            "lost durable lookup must fail to normal processing");
    const auto during = gate.snapshot(109);
    require(during.key == "K" && during.state == State::Holding &&
            during.held_attempts == 2 && during.duplicate_deliveries == 1 &&
            during.logical_effects == 1, "exact-key ledger must retain one effect");
    require(!gate.release(104 + Gate::kHoldMs - 1), "early release must reject");
    require(gate.release(104 + Gate::kHoldMs), "controlled release after hold");
    require(gate.decide(104 + Gate::kHoldMs + 1, "K", true, false, true, true) ==
            Decision::Released, "next exact-key retry gets normal authenticated ACK");
    require(gate.snapshot(104 + Gate::kHoldMs + 2).logical_effects == 1,
            "released replay must not invent a second logical effect");
}

void watchdog_cancel_reboot() {
    Gate gate;
    require(gate.arm(100), "arm watchdog case");
    require(gate.decide(101, "K", true, true, true, true) == Decision::CapturedAndHeld,
            "capture watchdog case");
    require(gate.decide(101 + Gate::kWatchdogMs - 1, "K", true, false, true, true) ==
            Decision::SameKeyHeld, "hold remains active before watchdog");
    require(gate.decide(101 + Gate::kWatchdogMs, "K", true, false, true, true) ==
            Decision::WatchdogExpired, "watchdog restores normal ACK path");
    require(gate.snapshot(101 + Gate::kWatchdogMs).state == State::Expired,
            "watchdog status is visible");
    require(gate.arm(20000), "explicit rearm after expiry");
    require(gate.cancel(20001), "cancel disarms before event");
    require(gate.decide(20002, "K2", true, true, true, true) == Decision::Normal,
            "cancelled fixture cannot suppress");
    require(gate.arm(30000), "rearm after cancel");
    require(gate.decide(30001, "K3", true, true, true, true) == Decision::CapturedAndHeld,
            "capture before cancellation");
    require(gate.cancel(30002), "cancel active hold on operator abort");
    require(gate.decide(30003, "K3", true, false, true, true) == Decision::Normal,
            "abort cleanup restores ACK path");
    Gate rebooted;
    require(rebooted.decide(30004, "K3", true, false, true, true) == Decision::Normal,
            "Hub reboot must default to normal ACK path");
    Gate precommit;
    require(precommit.arm(10), "arm precommit timeout");
    require(precommit.decide(10 + Gate::kArmWindowMs, "K", true, true, true, true) ==
            Decision::Normal, "expired arm cannot capture an unrelated later event");
}

void concurrent_key_isolation() {
    Gate gate;
    require(gate.arm(100), "arm concurrent case");
    std::atomic<int> captured{0};
    auto consume = [&]() {
        if (gate.decide(101, "K", true, true, true, true) ==
            Decision::CapturedAndHeld) captured.fetch_add(1);
    };
    std::thread a(consume), b(consume);
    a.join(); b.join();
    require(captured == 1, "only one first effect may capture K");
    require(gate.snapshot(102).logical_effects == 2,
            "duplicate state_changed=1 is visible as an anomalous second effect");
    require(gate.decide(103, "other", true, false, true, true) == Decision::Normal,
            "unrelated retry remains untouched");
}
}  // namespace

int main() {
    try {
        hold_release_exact_key();
        watchdog_cancel_reboot();
        concurrent_key_isolation();
        std::cout << "C8 ACK-hold gate PASS checks=" << checks << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "C8 ACK-hold gate FAIL: " << error.what() << '\n';
        return 1;
    }
}
