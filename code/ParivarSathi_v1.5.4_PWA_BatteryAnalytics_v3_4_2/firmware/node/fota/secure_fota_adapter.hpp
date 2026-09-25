#pragma once

#include "firmware/common/transport/fota_secure_wire.hpp"
#include "firmware/node/fota/fota_receiver.hpp"

#include <cstdint>
#include <array>
#include <string_view>

namespace gs::node::fota_receiver {

// Converts authenticated v2 plaintext into the existing bounded OTA receiver.
// The caller must authenticate the source and AEAD envelope before process().
// This class owns no transport keys and never accepts raw radio bytes.
class SecureFotaAdapter {
public:
    SecureFotaAdapter(Receiver& receiver, std::string_view board)
        : receiver_(receiver), board_(board) {}

    bool process(const gs::fota::secure_wire::Message& message,
                 std::uint64_t authenticated_session, std::uint64_t now_ms);
    void poll(std::uint64_t now_ms);
    bool active() const { return active_; }
    std::uint32_t transfer_id() const { return transfer_id_; }
    std::uint64_t authenticated_session() const { return authenticated_session_; }

private:
    Receiver& receiver_;
    std::string_view board_;
    bool active_{false};
    std::uint32_t transfer_id_{0};
    std::uint64_t authenticated_session_{0};
    std::uint32_t image_size_{0};
    std::uint32_t image_crc32_{0};
    std::array<std::uint8_t, 32> image_sha256_{};
    std::array<char, gs::fota::secure_wire::kMaxClaimBytes> version_{};
    std::uint8_t version_size_{0};
};

}  // namespace gs::node::fota_receiver
