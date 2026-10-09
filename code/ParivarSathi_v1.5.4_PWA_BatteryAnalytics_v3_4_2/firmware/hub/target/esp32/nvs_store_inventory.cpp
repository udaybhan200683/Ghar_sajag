#include "nvs_store_inventory.hpp"

#include "nvs_durable_key_codec.hpp"
#include "nvs.h"
#include "nvs_flash.h"

#include <cstring>

namespace gs::hub::target {
namespace {
#if CONFIG_IDF_TARGET_ESP32S3
constexpr const char* kPartition = "gs_state";
#else
constexpr const char* kPartition = "gs_journal";
#endif
constexpr const char* kOwnedNamespace = "events";

std::size_t max_length(DurablePhysicalKeyKind kind) {
    using K = DurablePhysicalKeyKind;
    switch (kind) {
        case K::Checkpoint: return 4549;
        case K::Selector: return 64;
        case K::Transition: return 1332;
        case K::EffectChunk: return 1260;
        case K::EvidenceChunk: return 320;
        case K::Bitmap: return 384;
        case K::RetirementBank: return 6096;
        case K::LegacyEvent: return 284;
        case K::LegacyCompletion: return 32;
        case K::MigrationMetadata: return 218;
    }
    return 0;
}
bool looks_known_family(const char* key) {
    return std::strncmp(key,"cp",2)==0 || std::strncmp(key,"sel",3)==0 ||
           std::strncmp(key,"tr",2)==0 || std::strncmp(key,"ef",2)==0 ||
           std::strncmp(key,"ev",2)==0 || std::strncmp(key,"bm",2)==0 ||
           std::strncmp(key,"ret",3)==0 || std::strncmp(key,"mig",3)==0 ||
           key[0]=='e' || key[0]=='c';
}
}

durable::InventorySnapshot NvsStoreInventory::scan() {
    durable::InventorySnapshot out;
    out.status = durable::InventoryStatus::Empty;
    const auto init = nvs_flash_init_partition(kPartition);
    if (init != ESP_OK && init != ESP_ERR_NVS_NO_FREE_PAGES && init != ESP_ERR_NVS_NEW_VERSION_FOUND) {
        out.status = durable::InventoryStatus::ScanFailure; return out;
    }
    // Do not erase on no-free-pages or version mismatch; that is evidence, not permission.
    if (init != ESP_OK) { out.status = durable::InventoryStatus::ScanFailure; return out; }
    nvs_iterator_t it = nullptr;
    auto rc = nvs_entry_find(kPartition, nullptr, NVS_TYPE_ANY, &it);
    if (rc == ESP_ERR_NVS_NOT_FOUND) return out;
    if (rc != ESP_OK) { out.status = durable::InventoryStatus::ScanFailure; return out; }
    bool current = false, legacy = false;
    while (it != nullptr) {
        nvs_entry_info_t info{};
        if (nvs_entry_info(it, &info) != ESP_OK) {
            nvs_release_iterator(it); out.status = durable::InventoryStatus::ScanFailure; return out;
        }
        if (std::strcmp(info.namespace_name, kOwnedNamespace) != 0) {
            nvs_release_iterator(it); out.status = durable::InventoryStatus::UnknownOrphanRecord; return out;
        }
        if (info.type != NVS_TYPE_BLOB) {
            nvs_release_iterator(it); out.status = durable::InventoryStatus::MalformedRecord; return out;
        }
        DurablePhysicalKeyRecord record;
        const std::string physical(info.key);
        if (!durable_physical_key_record(physical, record)) {
            const auto status = looks_known_family(info.key) ? durable::InventoryStatus::MalformedRecord
                                                            : durable::InventoryStatus::UnknownOrphanRecord;
            nvs_release_iterator(it); out.status = status; return out;
        }
        if (out.count == out.records.size()) {
            nvs_release_iterator(it); out.status = durable::InventoryStatus::LimitExceeded; return out;
        }
        nvs_handle_t handle = 0;
        rc = nvs_open_from_partition(kPartition, kOwnedNamespace, NVS_READONLY, &handle);
        if (rc != ESP_OK) { nvs_release_iterator(it); out.status = durable::InventoryStatus::ScanFailure; return out; }
        std::size_t length = 0;
        rc = nvs_get_blob(handle, info.key, nullptr, &length);
        nvs_close(handle);
        if (rc != ESP_OK || length == 0 || length > max_length(record.kind)) {
            nvs_release_iterator(it); out.status = rc == ESP_OK ? durable::InventoryStatus::MalformedRecord
                                                                : durable::InventoryStatus::ScanFailure; return out;
        }
        const auto numeric_kind = static_cast<std::uint8_t>(record.kind);
        out.records[out.count++] = {static_cast<durable::InventoryRecord::Kind>(numeric_kind), record.id};
        const bool is_legacy = record.kind == DurablePhysicalKeyKind::LegacyEvent ||
                               record.kind == DurablePhysicalKeyKind::LegacyCompletion;
        legacy = legacy || is_legacy; current = current || !is_legacy;
        rc = nvs_entry_next(&it);
        if (rc != ESP_OK && rc != ESP_ERR_NVS_NOT_FOUND) {
            if (it) nvs_release_iterator(it);
            out.status = durable::InventoryStatus::ScanFailure; return out;
        }
    }
    out.status = current && legacy ? durable::InventoryStatus::KnownMixedRecords
                : legacy ? durable::InventoryStatus::KnownLegacyRecords
                : current ? durable::InventoryStatus::KnownCurrentRecords
                : durable::InventoryStatus::Empty;
    return out;
}

}  // namespace gs::hub::target
