#include "firmware/hub/connectivity/wifi_setup_permit_gate.hpp"

#include <algorithm>
#include <iostream>
#include <stdexcept>

namespace {
using namespace gs::hub::connectivity;
unsigned checks = 0;
void expect(bool ok, const char* label) {
    ++checks;
    if (!ok) throw std::runtime_error(label);
}

class CurrentAuthority final : public WifiSetupAuthority {
public:
    std::uint64_t generation{5};
    std::uint64_t current_generation(std::uint64_t) const override { return generation; }
};

class Session final : public WifiSecurity2Session {
public:
    bool is_authenticated{true};
    std::uint8_t version{2};
    std::uint64_t id{10};
    bool authenticated() const override { return is_authenticated; }
    std::uint8_t security_version() const override { return version; }
    std::uint64_t session_id() const override { return id; }
};

class PermitVerifier final : public Gs109SetupPermitVerifier {
public:
    bool accept{true};
    VerifiedGs109SetupPermit output{};
    bool verify_and_consume_one_use_permit(const std::uint8_t* permit, std::size_t size,
                                           const WifiSetupChallenge& challenge,
                                           std::uint64_t now,
                                           VerifiedGs109SetupPermit& verified) override {
        if (!accept || permit == nullptr || size != 3 || permit[0] != 'G' ||
            permit[1] != 'S' || permit[2] != '1') return false;
        verified = output;
        if (verified.binding.hub_id_size == 0) verified.binding = challenge;
        if (verified.verified_at_ms == 0) verified.verified_at_ms = now;
        return true;
    }
};

WifiSetupChallenge challenge(std::uint64_t created = 1000) {
    WifiSetupChallenge value;
    value.hub_id[0] = 'H'; value.hub_id_size = 1;
    value.home_id[0] = 'A'; value.home_id_size = 1;
    value.ownership_epoch = 3;
    value.operation = WifiSetupOperation::InitialClaim;
    value.nonce[0] = 0x91;
    value.boot_generation = 8;
    value.security2_session_id = 10;
    value.created_at_ms = created;
    return value;
}

void set_valid(PermitVerifier& verifier, const WifiSetupChallenge& input,
               std::uint64_t generation = 5, std::uint64_t expiry = 2000) {
    verifier.output.binding = input;
    verifier.output.authority_generation = generation;
    verifier.output.verified_at_ms = input.created_at_ms;
    verifier.output.expires_at_ms = expiry;
}

void test_security2_binding_expiry_and_revocation() {
    CurrentAuthority authority;
    WifiSetupPermitGate gate(authority);
    Session session;
    PermitVerifier verifier;
    const std::uint8_t permit[] = {'G', 'S', '1'};
    auto input = challenge();
    set_valid(verifier, input);
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::Ok, "Security 2 and verified current permit open session");
    expect(gate.current_generation(1006) == 5, "current session exposes authority generation");
    Session competing;
    competing.id = 11;
    expect(gate.open(competing, input, permit, sizeof(permit), verifier, 1007) ==
           WifiSetupPermitResult::Busy, "parallel setup session is rejected");
    authority.generation = 6;
    expect(gate.current_generation(1008) == 0, "ownership/revocation generation change fences session");
    gate.close();
    authority.generation = 5;
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1009) ==
           WifiSetupPermitResult::Replay, "consumed nonce cannot reopen after close");

    auto new_input = challenge(1010);
    new_input.nonce[0] = 0x92;
    set_valid(verifier, new_input, 5, 1110);
    expect(gate.open(session, new_input, permit, sizeof(permit), verifier, 1011) ==
           WifiSetupPermitResult::Ok, "fresh challenge opens bounded change session");
    expect(gate.current_generation(1110) == 0, "permit expires at the exclusive deadline");
    session.is_authenticated = false;
    expect(gate.current_generation(1012) == 0, "closed Security 2 transport immediately fences access");
    gate.close();
    session.is_authenticated = true;

    session.id = 11;
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::BindingMismatch,
           "permit cannot be moved to a different Security 2 session");
    session.id = 10;
    auto final_input = challenge(1020);
    final_input.nonce[0] = 0x93;
    set_valid(verifier, final_input, 5, 1120);
    expect(gate.open(session, final_input, permit, sizeof(permit), verifier, 1021) ==
           WifiSetupPermitResult::Ok, "new one-use setup permit can open after expiry");
    expect(gate.complete_setup_operation(1022, 5) && gate.current_generation(1022) == 0,
           "successful setup consumes its permit session");
    expect(gate.open(session, final_input, permit, sizeof(permit), verifier, 1023) ==
           WifiSetupPermitResult::Replay, "completed setup permit cannot be reused");
}

void test_rejects_wrong_security_and_claim_binding() {
    CurrentAuthority authority;
    WifiSetupPermitGate gate(authority);
    Session session;
    PermitVerifier verifier;
    const std::uint8_t permit[] = {'G', 'S', '1'};
    auto input = challenge();
    set_valid(verifier, input);

    session.version = 1;
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::Security2Required, "Security 1 downgrade is rejected");
    session.version = 2;
    session.is_authenticated = false;
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::Security2Required, "unauthenticated transport is rejected");
    session.is_authenticated = true;

    verifier.output.binding = input;
    verifier.output.binding.hub_id[0] = 'X';
    verifier.output.authority_generation = 5;
    verifier.output.verified_at_ms = 1001;
    verifier.output.expires_at_ms = 1100;
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::BindingMismatch, "wrong permanent Hub binding is rejected");
    verifier.output.binding = input;
    verifier.output.binding.home_id[0] = 'B';
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::BindingMismatch, "wrong Home binding is rejected");
    verifier.output.binding = input;
    verifier.output.binding.ownership_epoch++;
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::BindingMismatch, "wrong ownership epoch is rejected");
    verifier.output.binding = input;
    verifier.output.binding.operation = WifiSetupOperation::ChangeNetwork;
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::BindingMismatch, "initial claim/change-network substitution is rejected");
    verifier.output.binding = input;
    verifier.output.binding.boot_generation++;
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::BindingMismatch, "stale boot generation is rejected");
    verifier.output.binding = input;
    verifier.output.binding.nonce[0]++;
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::BindingMismatch, "nonce substitution is rejected");
    verifier.output.binding = input;
    verifier.output.binding.hub_id_size = 0xff;
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::BindingMismatch,
           "malformed verifier identity length is rejected without out-of-bounds comparison");
}

void test_rejects_invalid_time_generation_and_input() {
    CurrentAuthority authority;
    WifiSetupPermitGate gate(authority);
    Session session;
    PermitVerifier verifier;
    const std::uint8_t permit[] = {'G', 'S', '1'};
    auto input = challenge();
    set_valid(verifier, input, 5, 2000);
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 31001) ==
           WifiSetupPermitResult::InvalidInput, "stale challenge is rejected");
    input = challenge();
    input.boot_generation = 0;
    set_valid(verifier, input);
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::InvalidInput, "zero boot generation is rejected");
    input = challenge();
    input.nonce.fill(0);
    set_valid(verifier, input);
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::InvalidInput, "zero challenge nonce is rejected");
    input = challenge();
    set_valid(verifier, input, 4, 2000);
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::AuthorityStale, "old authority generation is rejected");
    set_valid(verifier, input, 5, 1005);
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::Expired, "expired permit is rejected");
    set_valid(verifier, input, 5, 300000);
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::Expired, "overlong permit lifetime is rejected");
    auto delayed = challenge(2000);
    delayed.nonce[0] = 0xa4;
    set_valid(verifier, delayed, 5, 122001);
    verifier.output.verified_at_ms = 2029;
    expect(gate.open(session, delayed, permit, sizeof(permit), verifier, 2029) ==
           WifiSetupPermitResult::Expired,
           "permit deadline cannot be extended from delayed receipt time");
    verifier.accept = false;
    expect(gate.open(session, input, permit, sizeof(permit), verifier, 1005) ==
           WifiSetupPermitResult::PermitRejected, "failed GS-109 verification is rejected");
    verifier.accept = true;
    expect(gate.open(session, input, permit, 0, verifier, 1005) ==
           WifiSetupPermitResult::InvalidInput, "empty permit envelope is rejected");
}
}  // namespace

int main() {
    try {
        test_security2_binding_expiry_and_revocation();
        test_rejects_wrong_security_and_claim_binding();
        test_rejects_invalid_time_generation_and_input();
        std::cout << "GS-58 setup permit checks=" << checks << " PASS\n";
    } catch (const std::exception& error) {
        std::cerr << "GS-58 setup permit FAIL: " << error.what() << '\n';
        return 1;
    }
}
