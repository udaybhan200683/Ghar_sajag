#pragma once

#include "storage/durable_event_outbox.hpp"
#include "storage/runtime_state_store.hpp"

#include <cstddef>
#include <cstdint>

namespace gs::hub::storage::s3 {

// ESP-IDF LittleFS VFS adapter. It never formats on mount failure. Callers must
// use the reviewed `gs_outbox` partition and keep this writer serialized.
class LittleFsSegmentStore final : public SegmentStore, public RuntimeStateFiles {
public:
    bool mount();
    bool mounted() const { return mounted_; }

    std::uint64_t partition_capacity_bytes() const override { return total_bytes_; }
    bool segment_size(std::uint16_t segment, bool& exists,
                      std::uint32_t& bytes) override;
    bool read(std::uint16_t segment, std::uint32_t offset,
              std::uint8_t* output, std::size_t requested,
              std::size_t& actual) override;
    bool append(std::uint16_t segment, const std::uint8_t* data,
                std::size_t length) override;
    bool sync(std::uint16_t segment) override;
    bool read_publication(security::Bytes& marker, bool& found) override;
    bool publish_publication(const security::Bytes& marker) override;
    bool read_lifecycle_root(security::Bytes& marker, bool& found) override;
    bool publish_lifecycle_root(const security::Bytes& marker) override;
    bool remove_segment(std::uint16_t segment) override;
    bool filesystem_usage(std::uint64_t& total, std::uint64_t& used) override;
    bool completion_size(bool& exists, std::uint32_t& bytes) override;
    bool read_completion(std::uint32_t offset, std::uint8_t* output,
                         std::size_t requested, std::size_t& actual) override;
    bool append_completion(const std::uint8_t* data, std::size_t length) override;
    bool sync_completion() override;
    bool truncate_completion(std::uint32_t bytes) override;
    bool read_completion_publication(security::Bytes& marker, bool& found) override;
    bool publish_completion_publication(const security::Bytes& marker) override;

    bool state_size(const char* name, bool& found, std::uint32_t& size) override;
    bool state_read(const char* name, std::uint32_t offset, std::uint8_t* out, std::size_t size) override;
    bool state_append_sync(const char* name, const security::Bytes& data) override;
    bool state_replace(const char* name, const security::Bytes& data) override;
    bool state_truncate(const char* name, std::uint32_t size) override;
    bool state_capacity(std::uint64_t& total, std::uint64_t& used) override;
    bool state_remove(const char* name) override;
    bool state_sync(const char* name) override;
private:
    bool path_for(std::uint16_t segment, char* path, std::size_t capacity) const;

    std::uint64_t total_bytes_{0};
    bool mounted_{false};
};

}  // namespace gs::hub::storage::s3
