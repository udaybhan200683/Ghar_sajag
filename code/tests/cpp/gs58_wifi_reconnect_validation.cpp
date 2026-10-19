#include "firmware/hub/connectivity/wifi_reconnect_policy.hpp"

#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace {
int checks = 0;

void check(bool condition, const std::string& message) {
    ++checks;
    if (!condition) throw std::runtime_error(message);
}

void test_bounded_retry_and_success_reset() {
    gs::hub::connectivity::WifiReconnectPolicy policy;
    policy.on_credentials_ready(0);
    check(policy.take_due_attempt(0),
          "secure credential readiness permits initial station attempt");
    policy.on_disconnected(100);
    check(policy.scheduled(), "disconnect must schedule reconnect");
    check(policy.next_attempt_ms() == 1100,
          "first reconnect must wait one second");
    check(policy.retry_delay_ms() == 2000,
          "next reconnect delay advances after link loss");
    check(!policy.take_due_attempt(1099),
          "reconnect must not run before its deadline");
    check(policy.take_due_attempt(1100),
          "reconnect runs at its deadline");
    check(!policy.take_due_attempt(1100),
          "a due reconnect may be claimed only once");

    policy.on_attempt_failed(1100);
    check(policy.next_attempt_ms() == 3100,
          "failed reconnect request must use the next two-second delay");
    policy.on_disconnected(1200);
    check(policy.next_attempt_ms() == 3100,
          "duplicate disconnect notification must not postpone a retry");

    for (std::uint64_t now = 4000; policy.retry_delay_ms() < 60000; now += 61000) {
        policy.on_disconnected(now);
        check(policy.take_due_attempt(policy.next_attempt_ms()),
              "scheduled bounded-backoff attempt is available");
        policy.on_attempt_failed(now);
    }
    check(policy.retry_delay_ms() == 60000,
          "retry delay must stop growing at its cap");
    const auto pending = policy.next_attempt_ms();
    check(policy.take_due_attempt(pending),
          "a capped retry remains claimable at its deadline");
    policy.on_disconnected(pending);
    check(policy.next_attempt_ms() == pending + 60000,
          "retry interval remains capped after repeated outages");

    policy.on_connected();
    check(!policy.scheduled(), "connected state cancels retry");
    check(policy.retry_delay_ms() == 1000,
          "connected state resets retry stage");
}

void test_ready_credentials_request_immediate_attempt() {
    gs::hub::connectivity::WifiReconnectPolicy policy;
    policy.on_disconnected(0);
    check(!policy.scheduled(),
          "disconnect without committed credentials must not reconnect");
    policy.on_credentials_ready(42);
    check(policy.next_attempt_ms() == 42,
          "committed credentials request immediate station attempt");
    check(policy.take_due_attempt(42),
          "immediate credential retry is available exactly once");
}

void test_uncredentialed_attempt_failure_is_ignored() {
    gs::hub::connectivity::WifiReconnectPolicy policy;
    policy.on_attempt_failed(10);
    check(!policy.scheduled(),
          "driver failure without committed credentials must not schedule retries");
}

void test_deadline_saturates() {
    gs::hub::connectivity::WifiReconnectPolicy policy;
    policy.on_credentials_ready(0);
    check(policy.take_due_attempt(0),
          "secure credential readiness permits station attempt before deadline test");
    const auto now = std::numeric_limits<std::uint64_t>::max() - 500;
    policy.on_disconnected(now);
    check(policy.next_attempt_ms() == std::numeric_limits<std::uint64_t>::max(),
          "retry deadline addition must saturate");
    check(!policy.take_due_attempt(now),
          "saturated retry deadline is not immediately due");
}
}

int main() {
    try {
        test_bounded_retry_and_success_reset();
        test_ready_credentials_request_immediate_attempt();
        test_uncredentialed_attempt_failure_is_ignored();
        test_deadline_saturates();
        std::cout << "GS-58 Wi-Fi reconnect checks=" << checks << " PASS\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "GS-58 Wi-Fi reconnect FAIL: " << error.what() << '\n';
        return 1;
    }
}
