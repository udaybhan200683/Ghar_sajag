#include "nvs_durable_blob_store.hpp"

#include "nvs_durable_key_codec.hpp"
#include "storage/node_retirement_snapshot.hpp"
#include "nvs.h"
#include "nvs_flash.h"

#include <algorithm>
#include <cstring>
#include <mutex>

namespace gs::hub::target {
namespace {
#if CONFIG_IDF_TARGET_ESP32S3
// S3 candidate layouts keep small owner/checkpoint metadata separate from the
// LittleFS event outbox. The active development map still lacks gs_outbox and
// therefore fails closed at startup until an approved map is selected.
constexpr const char* kPartition = "gs_state";
#else
constexpr const char* kPartition = "gs_journal";
#endif
constexpr const char* kNamespace = "events";
std::mutex kJournalMutationMutex;

std::size_t maximum_for(const DurablePhysicalKeyRecord& r) {
    switch (r.kind) {
        case DurablePhysicalKeyKind::Checkpoint: return 4549;
        case DurablePhysicalKeyKind::Selector: return 64;
        case DurablePhysicalKeyKind::Transition: return 1332;
        case DurablePhysicalKeyKind::EffectChunk: return 1260;
        case DurablePhysicalKeyKind::EvidenceChunk: return 320;
        case DurablePhysicalKeyKind::Bitmap: return 384;
        case DurablePhysicalKeyKind::RetirementBank:
            return durable::kRetirementLegacyInspectionBytes;
        case DurablePhysicalKeyKind::LegacyEvent: return 284;
        case DurablePhysicalKeyKind::LegacyCompletion: return 32;
        case DurablePhysicalKeyKind::MigrationMetadata: return 218;
    }
    return 0;
}
std::size_t maximum_write_for(const DurablePhysicalKeyRecord& r) {
    return r.kind == DurablePhysicalKeyKind::RetirementBank
        ? durable::kRetirementSnapshotBankBytes : maximum_for(r);
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
    if (value.empty() || value.size() > maximum_write_for(record)) {
        last_error_ = NvsDurableError::CorruptValue; return false;
    }
    if (record.kind == DurablePhysicalKeyKind::LegacyEvent ||
        (record.kind == DurablePhysicalKeyKind::LegacyCompletion && !immutable)) {
        last_error_ = NvsDurableError::KeyMapping; return false;
    }
    if (!initialized_) { last_error_ = NvsDurableError::Io; return false; }
    std::lock_guard<std::mutex> mutation_lock(kJournalMutationMutex);
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

bool NvsDurableBlobStore::erase_if_equals(const std::string& logical,
                                          const security::Bytes& expected) {
    std::string key;
    DurablePhysicalKeyRecord record;
    if (!durable_logical_to_physical_key(logical, key) ||
        !durable_physical_key_record(key, record)) {
        last_error_ = NvsDurableError::KeyMapping;
        return false;
    }
    // Event archives and legacy completion markers are never migration scratch
    // objects. Their exact bytes must not make them eligible for this API.
    if (record.kind == DurablePhysicalKeyKind::LegacyEvent ||
        record.kind == DurablePhysicalKeyKind::LegacyCompletion || expected.empty() ||
        expected.size() > maximum_for(record)) {
        last_error_ = NvsDurableError::KeyMapping;
        return false;
    }
    if (!initialized_) {
        last_error_ = NvsDurableError::Io;
        return false;
    }

    std::lock_guard<std::mutex> mutation_lock(kJournalMutationMutex);
    nvs_handle_t handle = 0;
    auto rc = nvs_open_from_partition(kPartition, kNamespace, NVS_READWRITE, &handle);
    if (rc != ESP_OK) {
        if (rc == ESP_ERR_NVS_NOT_FOUND) {
            last_error_ = NvsDurableError::None;
            return true;
        }
        last_error_ = NvsDurableError::Io;
        return false;
    }
    std::size_t length = 0;
    rc = nvs_get_blob(handle, key.c_str(), nullptr, &length);
    if (rc == ESP_ERR_NVS_NOT_FOUND) {
        nvs_close(handle);
        last_error_ = NvsDurableError::None;
        return true;
    }
    if (rc != ESP_OK || length == 0 || length > maximum_for(record)) {
        nvs_close(handle);
        last_error_ = rc == ESP_OK ? NvsDurableError::CorruptValue : NvsDurableError::Io;
        return false;
    }
    security::Bytes current(length);
    rc = nvs_get_blob(handle, key.c_str(), current.data(), &length);
    if (rc != ESP_OK || length != current.size()) {
        nvs_close(handle);
        last_error_ = NvsDurableError::Io;
        return false;
    }
    if (current != expected) {
        nvs_close(handle);
        last_error_ = NvsDurableError::ConditionalMismatch;
        return false;
    }
    if (nvs_erase_key(handle, key.c_str()) != ESP_OK) {
        nvs_close(handle);
        last_error_ = NvsDurableError::Io;
        return false;
    }
    const auto commit_rc = nvs_commit(handle);
    nvs_close(handle);

    // Reopen after commit: reading the same handle could observe an uncommitted
    // erase from its cache and would not prove durable absence.
    nvs_handle_t verify = 0;
    rc = nvs_open_from_partition(kPartition, kNamespace, NVS_READONLY, &verify);
    if (rc != ESP_OK) {
        last_error_ = NvsDurableError::Io;
        return false;
    }
    std::size_t remaining = 0;
    rc = nvs_get_blob(verify, key.c_str(), nullptr, &remaining);
    if (rc == ESP_ERR_NVS_NOT_FOUND) {
        nvs_close(verify);
        if (commit_rc != ESP_OK) {
            last_error_ = NvsDurableError::PersistedButApiFailed;
            return false;
        }
        last_error_ = NvsDurableError::None;
        return true;
    }
    if (rc != ESP_OK || remaining == 0 || remaining > maximum_for(record)) {
        nvs_close(verify);
        last_error_ = rc == ESP_OK ? NvsDurableError::CorruptValue : NvsDurableError::Io;
        return false;
    }
    security::Bytes remaining_value(remaining);
    rc = nvs_get_blob(verify, key.c_str(), remaining_value.data(), &remaining);
    nvs_close(verify);
    if (rc != ESP_OK || remaining != remaining_value.size()) {
        last_error_ = NvsDurableError::Io;
        return false;
    }
    last_error_ = remaining_value == expected ? NvsDurableError::Io :
                                                NvsDurableError::ConditionalMismatch;
    return false;
}

}  // namespace gs::hub::target
