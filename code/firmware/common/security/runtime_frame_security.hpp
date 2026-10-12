#pragma once

#include "firmware/common/security/commissioning_protocol.hpp"
#include "firmware/common/transport/data_plane_codec.hpp"

#include <array>
#include <cstddef>
#include <cstdint>

namespace gs::security {

// Fits the ESP-NOW v1 250-byte payload budget. A 224-byte data-plane frame
// may be too large after authentication; seal rejects it explicitly.
constexpr std::size_t kMaximumSecureFrameBytes = 250;
constexpr std::size_t kSecureFrameOverhead = 28;

enum class RuntimeDirection : std::uint8_t { Uplink = 1, Downlink = 2 };

struct SecureFrame {
    std::array<std::uint8_t, kMaximumSecureFrameBytes> bytes{};
    std::size_t size{0};
};

// Session establishment is a separate authenticated protocol step. Callers
// must supply a fresh authenticated salt and monotonically progressed session
// after commissioning or rejoin. This class never accepts a session rollback
// within one instance. No plaintext is exposed before AEAD verification.
class RuntimeFrameSecurity {
public:
    RuntimeFrameSecurity(CommissioningCrypto& crypto, const CommissioningBinding& binding);
    ~RuntimeFrameSecurity();
    RuntimeFrameSecurity(const RuntimeFrameSecurity&) = delete;
    RuntimeFrameSecurity& operator=(const RuntimeFrameSecurity&) = delete;
    bool start(std::uint64_t session, const Key32& authenticated_salt);
    bool seal(RuntimeDirection direction, const transport::EncodedFrame& plain,
              SecureFrame& output);
    bool open(RuntimeDirection expected_direction, const SecureFrame& input,
              transport::EncodedFrame& plain);
    std::uint64_t session() const { return session_; }
    std::uint64_t rejected_frames() const { return rejected_frames_; }

private:
    struct DirectionState {
        Key32 key{};
        std::uint64_t next_send{1};
        std::uint64_t highest_received{0};
        std::uint64_t received_window{0};
    };
    DirectionState& state(RuntimeDirection direction);
    Bytes associated_data(const std::uint8_t* header) const;
    CommissioningCrypto& crypto_;
    CommissioningBinding binding_;
    DirectionState uplink_{};
    DirectionState downlink_{};
    std::uint64_t session_{0};
    std::uint64_t rejected_frames_{0};
};

}  // namespace gs::security
