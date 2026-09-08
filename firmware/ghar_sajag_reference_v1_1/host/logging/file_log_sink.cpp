#include "file_log_sink.hpp"
#include <cstdio>
#include <cstring>

namespace gs::host {
FileLogSink::FileLogSink(const char* path, std::size_t max_bytes, unsigned retained_files) noexcept
    : path_(path), max_bytes_(max_bytes), retained_files_(retained_files) { open_append(); }
FileLogSink::~FileLogSink() { if (file_) std::fclose(file_); }

bool FileLogSink::open_append() noexcept {
    file_ = std::fopen(path_, "ab+");
    if (!file_) return false;
    if (std::fseek(file_, 0, SEEK_END) != 0) { std::fclose(file_); file_ = nullptr; return false; }
    const long end = std::ftell(file_);
    if (end < 0) { std::fclose(file_); file_ = nullptr; return false; }
    bytes_ = static_cast<std::size_t>(end);
    return true;
}

void FileLogSink::rotate() noexcept {
    if (file_) { std::fclose(file_); file_ = nullptr; }
    char old_name[320]; char new_name[320];
    for (unsigned i = retained_files_; i > 0; --i) {
        if (i == 1) std::snprintf(old_name, sizeof(old_name), "%s", path_);
        else std::snprintf(old_name, sizeof(old_name), "%s.%u", path_, i - 1);
        std::snprintf(new_name, sizeof(new_name), "%s.%u", path_, i);
        std::rename(old_name, new_name);
    }
    bytes_ = 0; open_append();
}

void FileLogSink::write(const char* record, std::size_t length) noexcept {
    if (!file_ || !record || length == 0) return;
    if (max_bytes_ > 0 && bytes_ + length > max_bytes_) rotate();
    if (!file_) return;
    const std::size_t actual = std::fwrite(record, 1, length, file_);
    bytes_ += actual;
    if (record[0] == 'l' && std::strstr(record, "level=ERROR") == record) std::fflush(file_);
}
}  // namespace gs::host
