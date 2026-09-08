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

