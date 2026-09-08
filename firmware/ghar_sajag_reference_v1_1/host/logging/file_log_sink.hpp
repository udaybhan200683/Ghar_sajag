#pragma once
#include "gs/logging.hpp"
#include <cstdio>
#include <cstddef>

namespace gs::host {
class FileLogSink final : public log::Sink {
public:
    FileLogSink(const char* path, std::size_t max_bytes = 131072,
                unsigned retained_files = 2) noexcept;
    ~FileLogSink() override;
    FileLogSink(const FileLogSink&) = delete;
    FileLogSink& operator=(const FileLogSink&) = delete;
    bool ready() const noexcept { return file_ != nullptr; }
    void write(const char* record, std::size_t length) noexcept override;
private:
    bool open_append() noexcept;
    void rotate() noexcept;
    const char* path_;
    std::size_t max_bytes_;
    unsigned retained_files_;
    std::size_t bytes_{0};
    std::FILE* file_{nullptr};
};
}  // namespace gs::host

