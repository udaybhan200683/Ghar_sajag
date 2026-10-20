#pragma once

#include "firmware/hub/connectivity/wifi_onboarding.hpp"

#include <array>
#include <cstddef>
#include <cstdint>

namespace gs::hub::connectivity {

enum class WifiSetupOperation : std::uint8_t { InitialClaim, ChangeNetwork };

struct WifiSetupChallenge {
    static constexpr std::size_t kIdCapacity = 32;
    static constexpr std::size_t kNonceSize = 32;
    std::array<std::uint8_t, kIdCapacity> hub_id{};
    std::uint8_t hub_id_size{0};
    std::array<std::uint8_t, kIdCapacity> home_id{};
    std::uint8_t home_id_size{0};
    std::uint64_t ownership_epoch{0};
    WifiSetupOperation operation{WifiSetupOperation::InitialClaim};
    std::array<std::uint8_t, kNonceSize> nonce{};
    std::uint64_t boot_generation{0};
    // The authenticated Protocomm Security 2 session that carried this
    // challenge. It is covered by the GS-109 permit binding.
    std::uint64_t security2_session_id{0};
    // Hub monotonic milliseconds, never phone/server wall-clock time.
    std::uint64_t created_at_ms{0};
};

// Claims are returned only by the existing GS-109 permit verifier. The signed
// envelope format and its signer/key lifecycle stay owned by GS-109; this
// module does not define another permit protocol or trust root.
struct VerifiedGs109SetupPermit {
    WifiSetupChallenge binding{};
    std::uint64_t authority_generation{0};
    // Both timestamps are in the Hub's monotonic time domain. The verifier
    // must derive the deadline from the signed permit and cap it at
    // challenge.created_at_ms + kMaxPermitLifetimeMs; receipt time must not
    // extend the authority lease.
    std::uint64_t verified_at_ms{0};
    std::uint64_t expires_at_ms{0};
};

class Gs109SetupPermitVerifier {
public:
    virtual ~Gs109SetupPermitVerifier() = default;
    // The implementation must validate the existing GS-109 signature,
    // issuer/purpose, live Hub/Home/epoch ownership and revocation, and
    // atomically consume the one-use challenge permit before returning true.
    virtual bool verify_and_consume_one_use_permit(
        const std::uint8_t* permit, std::size_t permit_size,
        const WifiSetupChallenge& challenge, std::uint64_t now_ms,
        VerifiedGs109SetupPermit& verified) = 0;
};

// Implemented by the pinned Espressif Security 2 transport adapter. Its
// authenticated() result must come from the active Protocomm Security 2
// session, never from an advertisement, MAC, QR, caller header, or UI flag.
class WifiSecurity2Session {
public:
    virtual ~WifiSecurity2Session() = default;
    virtual bool authenticated() const = 0;
    virtual std::uint8_t security_version() const = 0;
    virtual std::uint64_t session_id() const = 0;
};

enum class WifiSetupPermitResult : std::uint8_t {
    Ok,
    InvalidInput,
    Security2Required,
    PermitRejected,
    BindingMismatch,
    AuthorityStale,
    Expired,
    Replay,
    Busy,
};

// Consumes a separately verified GS-109 permit and exposes the existing
// WifiSetupAuthority generation only while its exact Security 2 session,
// current ownership generation, boot binding and bounded lease remain valid.
class WifiSetupPermitGate final : public WifiSetupAuthority {
public:
    static constexpr std::uint64_t kMaxChallengeAgeMs = 30000;
    static constexpr std::uint64_t kMaxPermitLifetimeMs = 120000;
    static constexpr std::size_t kReplayEntries = 32;

    explicit WifiSetupPermitGate(WifiSetupAuthority& current_authority)
        : current_authority_(current_authority) {}

    WifiSetupPermitResult open(WifiSecurity2Session& session,
                               const WifiSetupChallenge& challenge,
                               const std::uint8_t* signed_permit,
                               std::size_t permit_size,
                               Gs109SetupPermitVerifier& verifier,
                               std::uint64_t now_ms);
    void close();
    std::uint64_t current_generation(std::uint64_t now_ms) const override;
    bool complete_setup_operation(std::uint64_t now_ms,
                                  std::uint64_t generation) override;

private:
    struct ReplayEntry {
        std::array<std::uint8_t, WifiSetupChallenge::kNonceSize> nonce{};
        std::uint64_t boot_generation{0};
        bool used{false};
    };

    bool valid_challenge(const WifiSetupChallenge& challenge,
                         std::uint64_t now_ms) const;
    bool was_consumed(const WifiSetupChallenge& challenge) const;
    void remember(const WifiSetupChallenge& challenge);

    WifiSetupAuthority& current_authority_;
    WifiSecurity2Session* session_{nullptr};
    std::uint64_t session_id_{0};
    std::uint64_t authority_generation_{0};
    std::uint64_t opened_at_ms_{0};
    std::uint64_t expires_at_ms_{0};
    std::array<ReplayEntry, kReplayEntries> replay_{};
    std::size_t replay_cursor_{0};
};

}  // namespace gs::hub::connectivity
