#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace gs::hub::connectivity {

struct WifiCredentialRecord {
    static constexpr std::size_t kSsidCapacity = 32;
    static constexpr std::size_t kPasswordCapacity = 64;

    std::array<std::uint8_t, kSsidCapacity> ssid{};
    std::array<std::uint8_t, kPasswordCapacity> password{};
    std::uint8_t ssid_size{0};
    std::uint8_t password_size{0};

    ~WifiCredentialRecord() { clear(); }

    bool valid() const {
        return ssid_size > 0 && ssid_size <= ssid.size() &&
               password_size <= password.size();
    }

    void clear() {
        volatile std::uint8_t* ssid_bytes = ssid.data();
        for (std::size_t i = 0; i < ssid.size(); ++i) ssid_bytes[i] = 0;
        volatile std::uint8_t* password_bytes = password.data();
        for (std::size_t i = 0; i < password.size(); ++i) password_bytes[i] = 0;
        ssid_size = 0;
        password_size = 0;
    }
};

enum class WifiCredentialProtection : std::uint8_t {
    Unavailable,
    PlaintextOnly,
    EncryptedWithVerifiedDeviceKey,
};

enum class WifiCredentialStoreResult : std::uint8_t {
    Ok,
    CandidateStaged,
    NotFound,
    InvalidRecord,
    CorruptRecord,
    ProtectedStorageUnavailable,
    CommitRejected,
    CommitOutcomeUnknown,
    IoError,
};

// A production provider must report EncryptedWithVerifiedDeviceKey only after
// it has verified encrypted-NVS availability and approved per-device key
// custody. stage_candidate must never change the active selector. Activation
// is an explicit second operation so onboarding can keep the previous working
// credential while association, Internet, cloud-authentication and current
// Home checks are performed by separately authorized runtime providers.
class WifiCredentialStoreBackend {
public:
    virtual ~WifiCredentialStoreBackend() = default;
    virtual WifiCredentialProtection protection() const = 0;
    virtual WifiCredentialStoreResult load(WifiCredentialRecord& record) = 0;
    virtual WifiCredentialStoreResult stage_candidate(
        const WifiCredentialRecord& record, std::uint32_t& generation) = 0;
    virtual WifiCredentialStoreResult load_candidate(
        std::uint32_t& generation, WifiCredentialRecord& record) = 0;
    // This storage primitive only commits a staged generation. Product code
    // must call it after its independent authorization/network readiness gate.
    virtual WifiCredentialStoreResult activate_candidate(
        std::uint32_t generation) = 0;
    virtual WifiCredentialStoreResult discard_candidate(
        std::uint32_t generation) = 0;
    virtual WifiCredentialStoreResult erase() = 0;
};

class WifiCredentialStore {
public:
    explicit WifiCredentialStore(WifiCredentialStoreBackend& backend)
        : backend_(backend) {}

    WifiCredentialStoreResult load(WifiCredentialRecord& record) {
        if (!protected_backend()) {
            clear(record);
            return WifiCredentialStoreResult::ProtectedStorageUnavailable;
        }
        const auto result = backend_.load(record);
        if (result == WifiCredentialStoreResult::Ok && !record.valid()) {
            clear(record);
            return WifiCredentialStoreResult::CorruptRecord;
        }
        if (result != WifiCredentialStoreResult::Ok) clear(record);
        return result;
    }

    WifiCredentialStoreResult stage_candidate(
        const WifiCredentialRecord& record, std::uint32_t& generation) {
        generation = 0;
        if (!protected_backend())
            return WifiCredentialStoreResult::ProtectedStorageUnavailable;
        if (!record.valid()) return WifiCredentialStoreResult::InvalidRecord;
        return backend_.stage_candidate(record, generation);
    }

    WifiCredentialStoreResult load_candidate(
        std::uint32_t& generation, WifiCredentialRecord& record) {
        generation = 0;
        clear(record);
        if (!protected_backend())
            return WifiCredentialStoreResult::ProtectedStorageUnavailable;
        const auto result = backend_.load_candidate(generation, record);
        if (result == WifiCredentialStoreResult::CandidateStaged && !record.valid()) {
            clear(record);
            generation = 0;
            return WifiCredentialStoreResult::CorruptRecord;
        }
        if (result != WifiCredentialStoreResult::CandidateStaged) {
            clear(record);
            generation = 0;
        }
        return result;
    }

    WifiCredentialStoreResult activate_candidate(std::uint32_t generation) {
        if (!protected_backend())
            return WifiCredentialStoreResult::ProtectedStorageUnavailable;
        if (generation == 0) return WifiCredentialStoreResult::InvalidRecord;
        return backend_.activate_candidate(generation);
    }

    WifiCredentialStoreResult discard_candidate(std::uint32_t generation) {
        if (!protected_backend())
            return WifiCredentialStoreResult::ProtectedStorageUnavailable;
        if (generation == 0) return WifiCredentialStoreResult::InvalidRecord;
        return backend_.discard_candidate(generation);
    }

    WifiCredentialStoreResult erase() {
        if (!protected_backend())
            return WifiCredentialStoreResult::ProtectedStorageUnavailable;
        return backend_.erase();
    }

    static void clear(WifiCredentialRecord& record) {
        record.clear();
    }

private:
    bool protected_backend() const {
        return backend_.protection() ==
            WifiCredentialProtection::EncryptedWithVerifiedDeviceKey;
    }

    WifiCredentialStoreBackend& backend_;
};

}  // namespace gs::hub::connectivity
