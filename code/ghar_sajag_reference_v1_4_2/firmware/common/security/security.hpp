// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module S03 Firmware security/update
// @requirements F03, E08, E09, NFR-06
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// CredentialRegistry keeps credential references and UpdatePolicy delegates authenticity to a verifier.
// The reference tests can replace that verifier. Production cryptographic verification, secret protection,
// revocation transport and bootloader enforcement must be proved separately.

#pragma once

#include "gs/ports.hpp"

#include <map>
#include <optional>
#include <string>

namespace gs::security {

struct DeviceCredential {
    std::string device_id;
    std::string key_reference;
    std::uint32_t version{0};
};

class CredentialRegistry {
public:
    bool install(const DeviceCredential& credential);
    bool revoke(const std::string& device_id);
    std::optional<DeviceCredential> get(const std::string& device_id) const;

private:
    std::map<std::string, DeviceCredential> credentials_;
};

struct UpdateManifest {
    std::string board_profile;
    std::uint32_t firmware_version{0};
    std::string image_sha256;
    std::string signature;
};

struct UpdateValidation {
    bool accepted{false};
    std::string reason;
};

class UpdatePolicy {
public:
    explicit UpdatePolicy(const SignatureVerifier& verifier);
    UpdateValidation validate(const UpdateManifest& manifest,
                              const std::string& expected_board,
                              std::uint32_t running_version) const;

private:
    const SignatureVerifier& verifier_;
};

}  // namespace gs::security
