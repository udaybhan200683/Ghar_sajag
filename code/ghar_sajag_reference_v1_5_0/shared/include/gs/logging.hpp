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

#include <cstddef>
#include <cstdint>

// Set to 1 only in development builds. At 0, trace call sites compile out.
#ifndef GS_ENABLE_TRACE
#define GS_ENABLE_TRACE 0
#endif

namespace gs::log {

enum class Category : std::uint8_t {
    System, Node, Hub, Rules, Storage, Radio, Security, Backend, App, Test
};

class Sink {
public:
    virtual ~Sink() = default;
    // @requirements AI08, E10, NFR-05, NFR-09
    // Perform host file output synchronously; target firmware needs a single-owner bounded asynchronous
    // writer.
    virtual void write(const char* record, std::size_t length) noexcept = 0;
};

void set_sink(Sink* sink) noexcept;
void error(Category category, const char* module, const char* event,
           const char* detail = "-") noexcept;
void trace(Category category, const char* module, const char* event,
           const char* detail = "-") noexcept;
const char* category_name(Category category) noexcept;

}  // namespace gs::log

#define GS_ERROR(category, module, event, detail) \
    ::gs::log::error((category), (module), (event), (detail))

#if GS_ENABLE_TRACE
#define GS_TRACE(category, module, event, detail) \
    ::gs::log::trace((category), (module), (event), (detail))
#else
#define GS_TRACE(category, module, event, detail) do { (void)sizeof(category); } while (false)
#endif

