// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module S05 Diagnostics facade and sinks
// @requirements AI08, E10, NFR-05, NFR-09
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The atomic sink pointer only makes pointer publication atomic; it does not make sink lifetime or writes
// thread-safe. The host file sink performs synchronous I/O and rotation. Production should enqueue fixed
// records to one writer, reserve error capacity and expose drops; this future writer is not in the current
// source.

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
    // @requirements AI08, E10, NFR-05, NFR-09
    // Perform host file output synchronously; target firmware needs a single-owner bounded asynchronous
    // writer.
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

