#include "gs/logging.hpp"

#include <atomic>
#include <cstdio>
#include <cstring>

namespace gs::log {
namespace {
std::atomic<Sink*> active_sink{nullptr};

void emit(const char* level, Category category, const char* module,
          const char* event, const char* detail) noexcept {
    Sink* const sink = active_sink.load(std::memory_order_acquire);
    if (sink == nullptr) return;
    char record[384];
    const int written = std::snprintf(record, sizeof(record),
        "level=%s category=%s module=%s event=%s detail=%s\n",
        level, category_name(category), module ? module : "?",
        event ? event : "?", detail ? detail : "-");
    if (written <= 0) return;
    std::size_t length = static_cast<std::size_t>(written);
    if (length >= sizeof(record)) {
        record[sizeof(record) - 2] = '\n';
        record[sizeof(record) - 1] = '\0';
        length = sizeof(record) - 1;
    }
    sink->write(record, length);
}
}  // namespace

void set_sink(Sink* sink) noexcept { active_sink.store(sink, std::memory_order_release); }

const char* category_name(Category category) noexcept {
    switch (category) {
        case Category::System: return "SYSTEM"; case Category::Node: return "NODE";
        case Category::Hub: return "HUB"; case Category::Rules: return "RULES";
        case Category::Storage: return "STORAGE"; case Category::Radio: return "RADIO";
        case Category::Security: return "SECURITY"; case Category::Backend: return "BACKEND";
        case Category::App: return "APP"; case Category::Test: return "TEST";
    }
    return "UNKNOWN";
}

void error(Category c, const char* m, const char* e, const char* d) noexcept { emit("ERROR", c, m, e, d); }
void trace(Category c, const char* m, const char* e, const char* d) noexcept { emit("TRACE", c, m, e, d); }
}  // namespace gs::log

