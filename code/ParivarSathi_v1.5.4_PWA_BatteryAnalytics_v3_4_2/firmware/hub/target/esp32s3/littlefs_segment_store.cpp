#include "littlefs_segment_store.hpp"

#include "esp_littlefs.h"

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <sys/stat.h>
#include <unistd.h>

namespace gs::hub::storage::s3 {
namespace {
constexpr char kMountPath[] = "/gsoutbox";
constexpr char kPartitionLabel[] = "gs_outbox";
constexpr char kPublicationPath[] = "/gsoutbox/head";
constexpr char kPublicationTemporaryPath[] = "/gsoutbox/head.new";
constexpr std::size_t kPathCapacity = 32;
constexpr std::size_t kPublicationMaximumBytes = 128;
}

bool LittleFsSegmentStore::mount() {
    if (mounted_) return true;
    esp_vfs_littlefs_conf_t config{};
    config.base_path = kMountPath;
    config.partition_label = kPartitionLabel;
    config.format_if_mount_failed = false;
    config.read_only = false;
    config.dont_mount = false;
    config.grow_on_mount = false;
    if (esp_vfs_littlefs_register(&config) != ESP_OK) return false;
    std::size_t total = 0;
    std::size_t used = 0;
    if (esp_littlefs_info(kPartitionLabel, &total, &used) != ESP_OK || total == 0 ||
        used > total) {
        (void)esp_vfs_littlefs_unregister(kPartitionLabel);
        return false;
    }
    total_bytes_ = total;
    mounted_ = true;
    return true;
}

bool LittleFsSegmentStore::path_for(std::uint16_t segment, char* path,
                                    std::size_t capacity) const {
    if (!mounted_ || path == nullptr || capacity < kPathCapacity) return false;
    const int written = std::snprintf(path, capacity, "%s/s%03u.log", kMountPath,
                                      static_cast<unsigned>(segment));
    return written > 0 && static_cast<std::size_t>(written) < capacity;
}

bool LittleFsSegmentStore::segment_size(std::uint16_t segment, bool& exists,
                                        std::uint32_t& bytes) {
    exists = false;
    bytes = 0;
    char path[kPathCapacity]{};
    if (!path_for(segment, path, sizeof(path))) return false;
    struct stat info{};
    if (stat(path, &info) != 0) return errno == ENOENT;
    if (info.st_size < 0 || static_cast<std::uint64_t>(info.st_size) > UINT32_MAX)
        return false;
    exists = true;
    bytes = static_cast<std::uint32_t>(info.st_size);
    return true;
}

bool LittleFsSegmentStore::read(std::uint16_t segment, std::uint32_t offset,
                                std::uint8_t* output, std::size_t requested,
                                std::size_t& actual) {
    actual = 0;
    if (requested != 0 && output == nullptr) return false;
    char path[kPathCapacity]{};
    if (!path_for(segment, path, sizeof(path))) return false;
    FILE* file = std::fopen(path, "rb");
    if (file == nullptr) return false;
    const bool sought = std::fseek(file, static_cast<long>(offset), SEEK_SET) == 0;
    if (sought) actual = std::fread(output, 1, requested, file);
    const bool read_ok = sought && (!std::ferror(file));
    const bool close_ok = std::fclose(file) == 0;
    return read_ok && close_ok;
}

bool LittleFsSegmentStore::append(std::uint16_t segment, const std::uint8_t* data,
                                  std::size_t length) {
    if (length != 0 && data == nullptr) return false;
    char path[kPathCapacity]{};
    if (!path_for(segment, path, sizeof(path))) return false;
    FILE* file = std::fopen(path, "ab");
    if (file == nullptr) return false;
    const auto written = std::fwrite(data, 1, length, file);
    const bool flushed = std::fflush(file) == 0;
    const bool close_ok = std::fclose(file) == 0;
    return written == length && flushed && close_ok;
}

bool LittleFsSegmentStore::sync(std::uint16_t segment) {
    char path[kPathCapacity]{};
    if (!path_for(segment, path, sizeof(path))) return false;
    FILE* file = std::fopen(path, "r+");
    if (file == nullptr) return false;
    const bool synced = ::fsync(fileno(file)) == 0;
    const bool close_ok = std::fclose(file) == 0;
    return synced && close_ok;
}

bool LittleFsSegmentStore::read_publication(security::Bytes& marker, bool& found) {
    found = false;
    marker.clear();
    if (!mounted_) return false;
    struct stat info{};
    if (stat(kPublicationPath, &info) != 0) return errno == ENOENT;
    found = true;
    if (info.st_size <= 0 ||
        static_cast<std::uint64_t>(info.st_size) > kPublicationMaximumBytes)
        return true;  // Present but malformed: core recovery fails closed.
    FILE* file = std::fopen(kPublicationPath, "rb");
    if (file == nullptr) return false;
    marker.resize(static_cast<std::size_t>(info.st_size));
    const auto read = std::fread(marker.data(), 1, marker.size(), file);
    const bool read_ok = read == marker.size() && std::ferror(file) == 0;
    const bool close_ok = std::fclose(file) == 0;
    if (!read_ok || !close_ok) {
        marker.clear();
        return false;
    }
    return true;
}

bool LittleFsSegmentStore::publish_publication(const security::Bytes& marker) {
    if (!mounted_ || marker.empty() || marker.size() > kPublicationMaximumBytes)
        return false;
    FILE* file = std::fopen(kPublicationTemporaryPath, "wb");
    if (file == nullptr) return false;
    const auto written = std::fwrite(marker.data(), 1, marker.size(), file);
    const bool flushed = written == marker.size() && std::fflush(file) == 0;
    const bool synced = flushed && ::fsync(fileno(file)) == 0;
    const bool closed = std::fclose(file) == 0;
    if (!synced || !closed) return false;

    // LittleFS metadata operations are power-loss consistent. The rename makes
    // either the previous complete marker or this complete marker visible;
    // the caller still verifies the exact marker by reading it back.
    if (std::rename(kPublicationTemporaryPath, kPublicationPath) != 0) return false;
    file = std::fopen(kPublicationPath, "r+");
    if (file == nullptr) return false;
    const bool publication_synced = ::fsync(fileno(file)) == 0;
    const bool publication_closed = std::fclose(file) == 0;
    return publication_synced && publication_closed;
}

}  // namespace gs::hub::storage::s3
