#include "nvs_durable_blob_store.hpp"

#include "nvs_durable_key_codec.hpp"
#include "nvs.h"
#include "nvs_flash.h"

#include <algorithm>
#include <cstring>

namespace gs::hub::target {
namespace {
constexpr const char* kPartition = "gs_journal";
constexpr const char* kNamespace = "events";

std::size_t maximum_for(const DurablePhysicalKeyRecord& r) {
    switch (r.kind) {
        case DurablePhysicalKeyKind::Checkpoint: return 4514;
        case DurablePhysicalKeyKind::Selector: return 64;
        case DurablePhysicalKeyKind::Transition: return 1332;
        case DurablePhysicalKeyKind::EffectChunk: return 1260;
        case DurablePhysicalKeyKind::EvidenceChunk: return 320;
        case DurablePhysicalKeyKind::Bitmap: return 384;
        case DurablePhysicalKeyKind::RetirementBank: return 6096;
        case DurablePhysicalKeyKind::LegacyEvent: return 284;
        case DurablePhysicalKeyKind::LegacyCompletion: return 32;
        case DurablePhysicalKeyKind::MigrationMetadata: return 512;
    }
    return 0;
}
}

bool NvsDurableBlobStore::initialize() {
    if (initialized_) return true;
    // Deliberately never erase: an NVS error may indicate the only durable history.
    initialized_ = nvs_flash_init_partition(kPartition) == ESP_OK;
    last_error_ = initialized_ ? NvsDurableError::None : NvsDurableError::Io;
    return initialized_;
}

bool NvsDurableBlobStore::read(const std::string& logical, security::Bytes& value,
                               bool& found) {
    value.clear(); found = false;
    std::string key;
    DurablePhysicalKeyRecord record;
    if (!durable_logical_to_physical_key(logical, key) ||
        !durable_physical_key_record(key, record)) {
        last_error_ = NvsDurableError::KeyMapping; return false;
    }
    if (!initialized_) { last_error_ = NvsDurableError::Io; return false; }
    nvs_handle_t handle = 0;
    auto rc = nvs_open_from_partition(kPartition, kNamespace, NVS_READONLY, &handle);
    if (rc == ESP_ERR_NVS_NOT_FOUND) { last_error_ = NvsDurableError::NotFound; return true; }
    if (rc != ESP_OK) { last_error_ = NvsDurableError::Io; return false; }
    std::size_t length = 0;
    rc = nvs_get_blob(handle, key.c_str(), nullptr, &length);
    if (rc == ESP_ERR_NVS_NOT_FOUND) {
        nvs_close(handle); last_error_ = NvsDurableError::NotFound; return true;
    }
    if (rc != ESP_OK) {
        nvs_close(handle); last_error_ = NvsDurableError::Io; return false;
    }
    if (length == 0 || length > maximum_for(record)) {
        nvs_close(handle); last_error_ = NvsDurableError::CorruptValue; return false;
    }
    value.resize(length);
    rc = nvs_get_blob(handle, key.c_str(), value.data(), &length);
    nvs_close(handle);
    if (rc != ESP_OK || length != value.size()) {
        value.clear(); last_error_ = rc == ESP_OK ? NvsDurableError::CorruptValue : NvsDurableError::Io;
        return false;
    }
    found = true; last_error_ = NvsDurableError::None; return true;
}

bool NvsDurableBlobStore::write_immutable(const std::string& k,
                                          const security::Bytes& v) {
    return write(k, v, true);
}
bool NvsDurableBlobStore::replace(const std::string& k, const security::Bytes& v) {
    return write(k, v, false);
}

bool NvsDurableBlobStore::write(const std::string& logical,
                                const security::Bytes& value, bool immutable) {
    std::string key;
    DurablePhysicalKeyRecord record;
    if (!durable_logical_to_physical_key(logical, key) ||
        !durable_physical_key_record(key, record)) {
        last_error_ = NvsDurableError::KeyMapping; return false;
    }
    if (value.empty() || value.size() > maximum_for(record)) {
        last_error_ = NvsDurableError::CorruptValue; return false;
    }
    if (record.kind == DurablePhysicalKeyKind::LegacyEvent ||
        record.kind == DurablePhysicalKeyKind::LegacyCompletion) {
        last_error_ = NvsDurableError::KeyMapping; return false;
    }
    if (!initialized_) { last_error_ = NvsDurableError::Io; return false; }
    nvs_handle_t handle = 0;
    auto rc = nvs_open_from_partition(kPartition, kNamespace, NVS_READWRITE, &handle);
    if (rc != ESP_OK) { last_error_ = NvsDurableError::Io; return false; }
    std::size_t old_length = 0;
    rc = nvs_get_blob(handle, key.c_str(), nullptr, &old_length);
    if (immutable && rc == ESP_OK) {
        nvs_close(handle); last_error_ = NvsDurableError::ImmutableCollision; return false;
    }
    if (rc != ESP_OK && rc != ESP_ERR_NVS_NOT_FOUND) {
        nvs_close(handle); last_error_ = NvsDurableError::Io; return false;
    }
    if (nvs_set_blob(handle, key.c_str(), value.data(), value.size()) != ESP_OK) {
        nvs_close(handle); last_error_ = NvsDurableError::Io; return false;
    }
    rc = nvs_commit(handle);
    if (rc != ESP_OK) {
        // The commit API may fail after flash has accepted data; exact readback
        // decides whether persistence occurred, while preserving that distinction.
        std::size_t check_length = 0;
        auto read_rc = nvs_get_blob(handle, key.c_str(), nullptr, &check_length);
        bool persisted = read_rc == ESP_OK && check_length == value.size();
        security::Bytes check(persisted ? check_length : 0);
        if (persisted) persisted = nvs_get_blob(handle, key.c_str(), check.data(), &check_length) == ESP_OK &&
                                   check_length == value.size() && check == value;
        nvs_close(handle);
        last_error_ = persisted ? NvsDurableError::PersistedButApiFailed : NvsDurableError::Io;
        return false;
    }
    security::Bytes check(value.size());
    std::size_t check_length = check.size();
    rc = nvs_get_blob(handle, key.c_str(), check.data(), &check_length);
    nvs_close(handle);
    if (rc != ESP_OK || check_length != value.size() || check != value) {
        last_error_ = NvsDurableError::Io; return false;
    }
    last_error_ = NvsDurableError::None; return true;
}

}  // namespace gs::hub::target
