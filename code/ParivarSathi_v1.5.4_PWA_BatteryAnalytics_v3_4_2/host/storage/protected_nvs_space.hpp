#pragma once
#include <cstddef>
#include <vector>

namespace gs::host::storage::native {
// ESP-IDF 6.0.3, 4096-byte pages, 126 32-byte entries and blob chunks of
// at most 4000 bytes. Single serialized writer; mounted/recovered partition.
// This is a sufficient workspace certificate, NOT a usable-byte estimator.
struct PublicationPlan {
    std::vector<std::size_t> blobs; // missing immutable objects, bank, head
    std::size_t control_manifest_bytes{};
    bool ordinary_admission{};
    std::size_t event_objects_after{}, reducer_objects_after{};
};
enum class SpaceOutcome {
    Ready, Committed, Duplicate, InsufficientProtectedSpace,
    MetadataPublicationFailure, IntegrityRecoveryFailure,
    RestartRequired, UnsupportedConfiguration, AdmissionLimit, InvalidRequest
};
struct Workspace {
    std::size_t operation_pages{}, control_pages{}, required_free_pages{};
};
// A partial initial tail can create one extra chunk/index page. Even if that
// tail is skipped, ceil(size/4000)+1 bounds all page activations per blob.
// Old chunks/index remain live until the new index exists. Their entries are
// never counted as free. Keep one further free page for NVS itself.
constexpr std::size_t blob_activation_bound(std::size_t bytes) {
    return (bytes+3999)/4000+1;
}
inline Workspace workspace(const PublicationPlan& p) {
    Workspace w;
    for(auto bytes:p.blobs)w.operation_pages+=blob_activation_bound(bytes);
    if(p.ordinary_admission)w.control_pages=blob_activation_bound(4124)+
        blob_activation_bound(p.control_manifest_bytes)+blob_activation_bound(86);
    w.required_free_pages=w.operation_pages+w.control_pages+1;
    return w;
}
// Worst owner prefix: header33 + six owner records646. No format change.
constexpr std::size_t control_manifest_bound(std::size_t rows) {
    return 6+3909+2+33*rows+32+28;
}
} // namespace
