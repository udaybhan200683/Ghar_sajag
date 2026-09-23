#include "firmware/common/security/nvs_association_blob_store.hpp"

#include "nvs.h"

namespace gs::security {
namespace {
constexpr const char* kNamespace = "gs_assoc";
constexpr const char* kKey = "binding";
constexpr std::size_t kMaximumBlob = 1024;
}

bool NvsAssociationBlobStore::read(Bytes& blob, bool& found) {
    found = false;
    blob.clear();
    nvs_handle_t handle = 0;
    const auto opened = nvs_open(kNamespace, NVS_READONLY, &handle);
    if (opened == ESP_ERR_NVS_NOT_FOUND) return true;
    if (opened != ESP_OK) return false;
    std::size_t length = 0;
    auto result = nvs_get_blob(handle, kKey, nullptr, &length);
    if (result == ESP_ERR_NVS_NOT_FOUND) {
        nvs_close(handle);
        return true;
    }
    if (result != ESP_OK || length == 0 || length > kMaximumBlob) {
        nvs_close(handle);
        return false;
    }
    blob.resize(length);
    result = nvs_get_blob(handle, kKey, blob.data(), &length);
    nvs_close(handle);
    if (result != ESP_OK || length != blob.size()) {
        blob.clear();
        return false;
    }
    found = true;
    return true;
}

bool NvsAssociationBlobStore::write(const Bytes& blob) {
    if (blob.empty() || blob.size() > kMaximumBlob) return false;
    nvs_handle_t handle = 0;
    if (nvs_open(kNamespace, NVS_READWRITE, &handle) != ESP_OK) return false;
    const bool committed = nvs_set_blob(handle, kKey, blob.data(), blob.size()) == ESP_OK &&
                           nvs_commit(handle) == ESP_OK;
    nvs_close(handle);
    if (!committed) return false;
    Bytes verified;
    bool found = false;
    return read(verified, found) && found && verified == blob;
}

}  // namespace gs::security
