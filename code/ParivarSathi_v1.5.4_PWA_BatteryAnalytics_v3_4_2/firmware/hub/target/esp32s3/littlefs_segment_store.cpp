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
constexpr char kCompletionPath[] = "/gsoutbox/completion.log";
constexpr char kCompletionPublicationPath[] = "/gsoutbox/completion.head";
constexpr char kCompletionPublicationTemporaryPath[] = "/gsoutbox/completion.head.new";
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

bool LittleFsSegmentStore::completion_size(bool& exists, std::uint32_t& bytes) {
    exists = false;
    bytes = 0;
    if (!mounted_) return false;
    struct stat info{};
    if (stat(kCompletionPath, &info) != 0) return errno == ENOENT;
    if (info.st_size < 0 || static_cast<std::uint64_t>(info.st_size) > UINT32_MAX)
        return false;
    exists = true;
    bytes = static_cast<std::uint32_t>(info.st_size);
    return true;
}

bool LittleFsSegmentStore::read_completion(std::uint32_t offset,
        std::uint8_t* output, std::size_t requested, std::size_t& actual) {
    actual = 0;
    if (!mounted_ || (requested != 0 && output == nullptr)) return false;
    FILE* file = std::fopen(kCompletionPath, "rb");
    if (file == nullptr) return false;
    const bool sought = std::fseek(file, static_cast<long>(offset), SEEK_SET) == 0;
    if (sought) actual = std::fread(output, 1, requested, file);
    const bool read_ok = sought && std::ferror(file) == 0;
    const bool close_ok = std::fclose(file) == 0;
    return read_ok && close_ok;
}

bool LittleFsSegmentStore::append_completion(const std::uint8_t* data,
                                               std::size_t length) {
    if (!mounted_ || (length != 0 && data == nullptr)) return false;
    FILE* file = std::fopen(kCompletionPath, "ab");
    if (file == nullptr) return false;
    const auto written = std::fwrite(data, 1, length, file);
    const bool flushed = std::fflush(file) == 0;
    const bool close_ok = std::fclose(file) == 0;
    return written == length && flushed && close_ok;
}

bool LittleFsSegmentStore::sync_completion() {
    if (!mounted_) return false;
    FILE* file = std::fopen(kCompletionPath, "r+");
    if (file == nullptr) return false;
    const bool synced = ::fsync(fileno(file)) == 0;
    const bool close_ok = std::fclose(file) == 0;
    return synced && close_ok;
}

bool LittleFsSegmentStore::truncate_completion(std::uint32_t bytes) {
    if (!mounted_) return false;
    FILE* file = std::fopen(kCompletionPath, "r+");
    if (file == nullptr) return bytes == 0 && errno == ENOENT;
    const bool truncated = ::ftruncate(fileno(file), static_cast<off_t>(bytes)) == 0;
    const bool synced = truncated && ::fsync(fileno(file)) == 0;
    const bool close_ok = std::fclose(file) == 0;
    return truncated && synced && close_ok;
}

bool LittleFsSegmentStore::read_completion_publication(security::Bytes& marker,
                                                        bool& found) {
    found = false;
    marker.clear();
    if (!mounted_) return false;
    struct stat info{};
    if (stat(kCompletionPublicationPath, &info) != 0) return errno == ENOENT;
    found = true;
    if (info.st_size <= 0 ||
        static_cast<std::uint64_t>(info.st_size) > kPublicationMaximumBytes) return true;
    FILE* file = std::fopen(kCompletionPublicationPath, "rb");
    if (file == nullptr) return false;
    marker.resize(static_cast<std::size_t>(info.st_size));
    const auto read = std::fread(marker.data(), 1, marker.size(), file);
    const bool read_ok = read == marker.size() && std::ferror(file) == 0;
    const bool close_ok = std::fclose(file) == 0;
    if (!read_ok || !close_ok) { marker.clear(); return false; }
    return true;
}

bool LittleFsSegmentStore::publish_completion_publication(
        const security::Bytes& marker) {
    if (!mounted_ || marker.empty() || marker.size() > kPublicationMaximumBytes)
        return false;
    FILE* file = std::fopen(kCompletionPublicationTemporaryPath, "wb");
    if (file == nullptr) return false;
    const auto written = std::fwrite(marker.data(), 1, marker.size(), file);
    const bool flushed = written == marker.size() && std::fflush(file) == 0;
    const bool synced = flushed && ::fsync(fileno(file)) == 0;
    const bool closed = std::fclose(file) == 0;
    if (!synced || !closed ||
        std::rename(kCompletionPublicationTemporaryPath,
                    kCompletionPublicationPath) != 0) return false;
    file = std::fopen(kCompletionPublicationPath, "r+");
    if (file == nullptr) return false;
    const bool publication_synced = ::fsync(fileno(file)) == 0;
    const bool publication_closed = std::fclose(file) == 0;
    return publication_synced && publication_closed;
}

namespace {
bool state_path(const char* name, char* path, std::size_t capacity) {
    if(std::strcmp(name,"identity.log")!=0 && std::strcmp(name,"identity.head")!=0 &&
       std::strcmp(name,"application.head")!=0)return false;
    const int n=std::snprintf(path,capacity,"/gsoutbox/%s",name);
    return n>0 && static_cast<std::size_t>(n)<capacity;
}
}
bool LittleFsSegmentStore::state_size(const char* name, bool& found, std::uint32_t& size) {
    found=false;size=0;char path[64];struct stat st{};
    if(!mounted_ || !state_path(name,path,sizeof(path)))return false;
    if(stat(path,&st)!=0)return errno==ENOENT;
    if(st.st_size<0 || static_cast<std::uint64_t>(st.st_size)>UINT32_MAX)return false;
    found=true;size=st.st_size;return true;
}
bool LittleFsSegmentStore::state_read(const char* name, std::uint32_t offset,
                                      std::uint8_t* out, std::size_t size) {
    char path[64];if(!mounted_ || !state_path(name,path,sizeof(path)))return false;
    FILE* file=std::fopen(path,"rb");if(!file)return false;
    const bool ok=std::fseek(file,offset,SEEK_SET)==0 && std::fread(out,1,size,file)==size &&
                  std::ferror(file)==0;
    return std::fclose(file)==0 && ok;
}
bool LittleFsSegmentStore::state_append_sync(const char* name, const security::Bytes& data) {
    char path[64];if(!mounted_ || !state_path(name,path,sizeof(path)))return false;
    FILE* file=std::fopen(path,"ab");if(!file)return false;
    const bool ok=std::fwrite(data.data(),1,data.size(),file)==data.size() &&
                  std::fflush(file)==0 && ::fsync(fileno(file))==0;
    return std::fclose(file)==0 && ok;
}
bool LittleFsSegmentStore::state_replace(const char* name, const security::Bytes& data) {
    char path[64],temporary[72];if(!mounted_ || !state_path(name,path,sizeof(path)))return false;
    std::snprintf(temporary,sizeof(temporary),"%s.new",path);
    FILE* file=std::fopen(temporary,"wb");if(!file)return false;
    const bool ok=std::fwrite(data.data(),1,data.size(),file)==data.size() &&
                  std::fflush(file)==0 && ::fsync(fileno(file))==0;
    const bool closed=std::fclose(file)==0;
    if(!ok || !closed || std::rename(temporary,path)!=0)return false;
    file=std::fopen(path,"r+");if(!file)return false;
    const bool synced=::fsync(fileno(file))==0;
    return std::fclose(file)==0 && synced;
}
bool LittleFsSegmentStore::state_truncate(const char* name, std::uint32_t size) {
    char path[64];if(!mounted_ || !state_path(name,path,sizeof(path)))return false;
    FILE* file=std::fopen(path,"r+");if(!file)return size==0 && errno==ENOENT;
    const bool ok=::ftruncate(fileno(file),size)==0 && ::fsync(fileno(file))==0;
    return std::fclose(file)==0 && ok;
}

}  // namespace gs::hub::storage::s3
