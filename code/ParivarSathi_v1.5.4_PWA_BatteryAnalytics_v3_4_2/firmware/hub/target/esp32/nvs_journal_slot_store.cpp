#include "nvs_journal_slot_store.hpp"

#include <cstdio>

#include "nvs.h"
#include "nvs_flash.h"

namespace gs::hub::target {
namespace {
constexpr const char* kPartition = "gs_journal";
constexpr const char* kNamespace = "events";
constexpr std::size_t kCapacity = 128;
constexpr std::size_t kMaximumBlob = 12 + 256 + 16;

void slot_key(std::size_t slot, char (&key)[8]) {
    std::snprintf(key, sizeof(key), "e%03u", static_cast<unsigned>(slot));
}
}  // namespace

bool NvsJournalSlotStore::initialize() {
    if (initialized_) return true;
    // Do not erase/reformat on NVS errors: that could discard accepted events.
    initialized_ = nvs_flash_init_partition(kPartition) == ESP_OK;
    return initialized_;
}

bool NvsJournalSlotStore::read(std::size_t slot, security::Bytes& blob, bool& found) {
    blob.clear();
    found = false;
    if (!initialized_ || slot >= kCapacity) return false;
    char key[8]{};
    slot_key(slot, key);
    nvs_handle_t handle = 0;
    const auto opened = nvs_open_from_partition(kPartition, kNamespace,
                                                NVS_READONLY, &handle);
    if (opened == ESP_ERR_NVS_NOT_FOUND) return true;
    if (opened != ESP_OK) return false;
    std::size_t length = 0;
    auto result = nvs_get_blob(handle, key, nullptr, &length);
    if (result == ESP_ERR_NVS_NOT_FOUND) {
        nvs_close(handle);
        return true;
    }
    if (result != ESP_OK || length < 12 + 16 || length > kMaximumBlob) {
        nvs_close(handle);
        return false;
    }
    blob.resize(length);
    result = nvs_get_blob(handle, key, blob.data(), &length);
    nvs_close(handle);
    if (result != ESP_OK || length != blob.size()) {
        blob.clear();
        return false;
    }
    found = true;
    return true;
}

bool NvsJournalSlotStore::write(std::size_t slot, const security::Bytes& blob) {
    if (!initialized_ || slot >= kCapacity || blob.size() < 12 + 16 ||
        blob.size() > kMaximumBlob) return false;
    // Slots are append-only until a separately qualified retirement floor and
    // backend application receipt allow reclamation.
    security::Bytes prior;
    bool found = false;
    if (!read(slot, prior, found) || found) return false;
    char key[8]{};
    slot_key(slot, key);
    nvs_handle_t handle = 0;
    if (nvs_open_from_partition(kPartition, kNamespace, NVS_READWRITE,
                                &handle) != ESP_OK) return false;
    const bool committed = nvs_set_blob(handle, key, blob.data(), blob.size()) == ESP_OK &&
                           nvs_commit(handle) == ESP_OK;
    nvs_close(handle);
    if (!committed) return false;
    security::Bytes verified;
    return read(slot, verified, found) && found && verified == blob;
}

}  // namespace gs::hub::target
