#include "firmware/common/security/nvs_association_blob_store.hpp"

#include "nvs.h"

namespace gs::security {

NvsBoundedSecurityBlobStore::NvsBoundedSecurityBlobStore(
    const char* storage_namespace, const char* key, std::size_t maximum_blob)
    : storage_namespace_(storage_namespace), key_(key), maximum_blob_(maximum_blob) {}

NvsAssociationBlobStore::NvsAssociationBlobStore()
    : NvsBoundedSecurityBlobStore("gs_assoc", "binding", 1024) {}

NvsRegistryBlobStore::NvsRegistryBlobStore()
    : NvsBoundedSecurityBlobStore("gs_registry", "snapshot", 8192) {}

NvsNodeRecoveryBlobStore::NvsNodeRecoveryBlobStore()
    : NvsBoundedSecurityBlobStore("gs_node_rec", "snapshot", 8192) {}

bool NvsBoundedSecurityBlobStore::read(Bytes& blob, bool& found) {
    found = false;
    blob.clear();
    nvs_handle_t handle = 0;
    const auto opened = nvs_open(storage_namespace_, NVS_READONLY, &handle);
    if (opened == ESP_ERR_NVS_NOT_FOUND) return true;
    if (opened != ESP_OK) return false;
    std::size_t length = 0;
    auto result = nvs_get_blob(handle, key_, nullptr, &length);
    if (result == ESP_ERR_NVS_NOT_FOUND) {
        nvs_close(handle);
        return true;
    }
    if (result != ESP_OK || length == 0 || length > maximum_blob_) {
        nvs_close(handle);
        return false;
    }
    blob.resize(length);
    result = nvs_get_blob(handle, key_, blob.data(), &length);
    nvs_close(handle);
    if (result != ESP_OK || length != blob.size()) {
        blob.clear();
        return false;
    }
    found = true;
    return true;
}

bool NvsBoundedSecurityBlobStore::write(const Bytes& blob) {
    if (blob.empty() || blob.size() > maximum_blob_) return false;
    nvs_handle_t handle = 0;
    if (nvs_open(storage_namespace_, NVS_READWRITE, &handle) != ESP_OK) return false;
    const bool committed = nvs_set_blob(handle, key_, blob.data(), blob.size()) == ESP_OK &&
                           nvs_commit(handle) == ESP_OK;
    nvs_close(handle);
    if (!committed) return false;
    Bytes verified;
    bool found = false;
    return read(verified, found) && found && verified == blob;
}

}  // namespace gs::security
