#include "security.hpp"
#include "gs/logging.hpp"

#include <algorithm>
#include <cctype>

namespace gs::security {

bool CredentialRegistry::install(const DeviceCredential& credential) {
    GS_TRACE(gs::log::Category::Security, "S01", "install.enter", "-");
    if (credential.device_id.empty() || credential.key_reference.empty() || credential.version == 0) {
        GS_ERROR(gs::log::Category::Security, "S01", "credential.rejected", "invalid_fields");
        return false;
    }
    const auto current = credentials_.find(credential.device_id);
    if (current != credentials_.end() && credential.version <= current->second.version) return false;
    credentials_[credential.device_id] = credential;
    return true;
}

bool CredentialRegistry::revoke(const std::string& device_id) {
    GS_TRACE(gs::log::Category::Security, "S01", "revoke.enter", "-");
    return credentials_.erase(device_id) == 1;
}

std::optional<DeviceCredential> CredentialRegistry::get(const std::string& device_id) const {
    GS_TRACE(gs::log::Category::Security, "S01", "get.enter", "-");
    const auto it = credentials_.find(device_id);
    if (it == credentials_.end()) return std::nullopt;
    return it->second;
}

UpdatePolicy::UpdatePolicy(const SignatureVerifier& verifier) : verifier_(verifier) {
    GS_TRACE(gs::log::Category::Security, "S01", "UpdatePolicy.enter", "-");}

UpdateValidation UpdatePolicy::validate(const UpdateManifest& manifest,
                                        const std::string& expected_board,
                                        std::uint32_t running_version) const {
    GS_TRACE(gs::log::Category::Security, "S01", "validate.enter", "-");
    if (manifest.board_profile != expected_board) return {false, "board_mismatch"};
    if (manifest.firmware_version <= running_version) return {false, "rollback_or_same_version"};
    if (manifest.image_sha256.size() != 64 ||
        !std::all_of(manifest.image_sha256.begin(), manifest.image_sha256.end(), [](unsigned char value) {
            return std::isxdigit(value) != 0;
        })) return {false, "invalid_sha256"};
    const auto payload = manifest.board_profile + ":" + std::to_string(manifest.firmware_version) + ":" + manifest.image_sha256;
    if (!verifier_.verify(payload, manifest.signature)) return {false, "signature_invalid"};
    return {true, "accepted"};
}

}  // namespace gs::security
