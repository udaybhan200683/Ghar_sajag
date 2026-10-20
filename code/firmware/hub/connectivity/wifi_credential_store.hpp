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
// custody. replace_atomically must preserve the previous complete record if
// it returns CommitRejected. The provider owns encoding and partition details.
class WifiCredentialStoreBackend {
public:
    virtual ~WifiCredentialStoreBackend() = default;
    virtual WifiCredentialProtection protection() const = 0;
    virtual WifiCredentialStoreResult load(WifiCredentialRecord& record) = 0;
    virtual WifiCredentialStoreResult replace_atomically(
        const WifiCredentialRecord& record) = 0;
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

    WifiCredentialStoreResult replace(
        const WifiCredentialRecord& record) {
        if (!protected_backend())
            return WifiCredentialStoreResult::ProtectedStorageUnavailable;
        if (!record.valid()) return WifiCredentialStoreResult::InvalidRecord;
        return backend_.replace_atomically(record);
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
