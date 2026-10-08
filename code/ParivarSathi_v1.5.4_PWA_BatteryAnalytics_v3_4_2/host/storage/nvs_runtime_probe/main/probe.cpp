// Host-only ESP-IDF Linux NVS runtime probe. Length-matched dummy values;
// no production codec, authenticated root protocol, or product policy.
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_partition.h"
#include "esp_private/partition_linux.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <vector>

#define REQUIRE(expression) do { if (!(expression)) { \
    std::fprintf(stderr, "PROBE_FAIL %s:%d: %s\n", __FILE__, __LINE__, #expression); \
    std::abort(); \
} } while (0)

namespace {
constexpr char part_name[] = "life";
constexpr unsigned page_bytes = 4096;
constexpr unsigned pages = 32;
struct Media {
    unsigned allocated = 0;
    unsigned live = 0;
    unsigned erased = 0;
    unsigned written = 0;
};
Media inspect(const esp_partition_t* part) {
    Media m{};
    std::array<std::uint8_t, page_bytes> raw{};
    for (unsigned p = 0; p < pages; ++p) {
        REQUIRE(esp_partition_read(part, p * page_bytes, raw.data(), raw.size()) == ESP_OK);
        if (std::all_of(raw.begin(), raw.end(), [](auto b) { return b == 0xff; })) continue;
        ++m.allocated;
        for (unsigned e = 0; e < 126; ++e) {
            const unsigned state = (raw[32 + e / 4] >> ((e % 4) * 2)) & 3;
            m.live += state == 2;
            m.erased += state == 0;
        }
        m.written += 126;
    }
    return m;
}
esp_err_t put(nvs_handle_t handle, const char* prefix, unsigned index, unsigned size, unsigned generation) {
    char key[16];
    std::snprintf(key, sizeof(key), "%s%u", prefix, index);
    std::vector<std::uint8_t> value(size, static_cast<std::uint8_t>(generation + index));
    if (size >= 4) std::memcpy(value.data(), &generation, 4);
    auto rc = nvs_set_blob(handle, key, value.data(), value.size());
    if (rc == ESP_OK) rc = nvs_commit(handle);
    return rc;
}
void metric(const char* phase, unsigned iteration, const esp_partition_t* part) {
    const auto m = inspect(part);
    nvs_stats_t stats{};
    REQUIRE(nvs_get_stats(part_name, &stats) == ESP_OK);
    size_t min_erase = static_cast<size_t>(-1), max_erase = 0;
    const size_t first = part->address / ESP_PARTITION_EMULATED_SECTOR_SIZE;
    for (unsigned p = 0; p < pages; ++p) {
        const size_t count = esp_partition_get_sector_erase_count(first + p);
        min_erase = std::min(min_erase, count);
        max_erase = std::max(max_erase, count);
    }
    std::printf("NVS_RUNTIME phase=%s iteration=%u allocated_pages=%u free_erased_pages=%u live_entries=%u erased_entries=%u stats_used=%zu stats_free=%zu write_bytes=%zu erase_ops=%zu min_sector_erases=%zu max_sector_erases=%zu\n",
                phase, iteration, m.allocated, pages - m.allocated, m.live, m.erased,
                stats.used_entries, stats.free_entries, esp_partition_get_write_bytes(), esp_partition_get_erase_ops(), min_erase, max_erase);
}
}

int main(int argc, char** argv) {
    const unsigned segment_count = argc > 1 ? static_cast<unsigned>(std::strtoul(argv[1], nullptr, 10)) : 7;
    const unsigned cycle_count = argc > 2 ? static_cast<unsigned>(std::strtoul(argv[2], nullptr, 10)) : 100;
    const unsigned saturation_limit = argc > 3 ? static_cast<unsigned>(std::strtoul(argv[3], nullptr, 10)) : 20;
    const bool promotion = argc > 4 && std::strcmp(argv[4], "promotion") == 0;
    const bool fault = argc > 4 && std::strcmp(argv[4], "fault") == 0;
    const unsigned hot_count = promotion && argc > 5 ? static_cast<unsigned>(std::strtoul(argv[5], nullptr, 10)) : 32;
    REQUIRE(hot_count <= 192);
    REQUIRE(segment_count >= 5 && segment_count <= 9);
    const auto* part = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, part_name);
    REQUIRE(part != nullptr);
    REQUIRE(part->size == pages * page_bytes);
    REQUIRE(esp_partition_erase_range(part, 0, part->size) == ESP_OK);
    esp_partition_clear_stats();
    REQUIRE(nvs_flash_init_partition(part_name) == ESP_OK);
    nvs_handle_t handle{};
    REQUIRE(nvs_open_from_partition(part_name, "life", NVS_READWRITE, &handle) == ESP_OK);
    for (unsigned i = 0; i < 6; ++i) REQUIRE(put(handle, "cert", i, 4079, 0) == ESP_OK);
    for (unsigned i = 0; i < 3; ++i) REQUIRE(put(handle, "ret", i, 3485, 0) == ESP_OK);
    for (unsigned i = 0; i < 3; ++i) REQUIRE(put(handle, "state", i, 6144, 0) == ESP_OK);
    for (unsigned i = 0; i < 2; ++i) REQUIRE(put(handle, "root", i, 512, 0) == ESP_OK);
    for (unsigned i = 0; i < 2; ++i) REQUIRE(put(handle, "meta", i, 4096, 0) == ESP_OK);
    for (unsigned i = 0; i < 2; ++i) REQUIRE(put(handle, "crit", i, 4096, 0) == ESP_OK);
    for (unsigned i = 0; i < segment_count; ++i) REQUIRE(put(handle, "seg", i, 4096, 0) == ESP_OK);
    metric("fresh", 0, part);
    for (unsigned cycle = 1; cycle <= cycle_count; ++cycle) {
        const auto a = put(handle, "tail", 0, 124, cycle);
        const auto b = a == ESP_OK ? put(handle, "seg", (cycle - 1) % segment_count, 4096, cycle) : a;
        const auto c = b == ESP_OK ? nvs_erase_key(handle, "tail0") : b;
        const auto d = c == ESP_OK ? nvs_commit(handle) : c;
        const auto e = d == ESP_OK ? put(handle, "ret", (cycle - 1) % 3, 3485, cycle) : d;
        const auto f = e == ESP_OK ? put(handle, "state", (cycle - 1) % 3, 6144, cycle) : e;
        const auto g = f == ESP_OK ? put(handle, "meta", (cycle - 1) % 2, 4096, cycle) : f;
        const auto h = g == ESP_OK ? put(handle, "root", (cycle - 1) % 2, 512, cycle) : g;
        if (h != ESP_OK) {
            std::printf("NVS_RUNTIME_STOP cycle=%u error=%s stage=%c\n", cycle, esp_err_to_name(h),
                        a != ESP_OK ? 'a' : b != ESP_OK ? 'b' : c != ESP_OK ? 'c' :
                        d != ESP_OK ? 'd' : e != ESP_OK ? 'e' : f != ESP_OK ? 'f' :
                        g != ESP_OK ? 'g' : 'h');
            metric("stop", cycle, part);
            break;
        }
        if (cycle == 1 || cycle == cycle_count || cycle % 1000 == 0) metric("churn", cycle, part);
    }
    if (fault) {
        const size_t cut = argc > 5 ? std::strtoul(argv[5], nullptr, 10) : 0;
        std::vector<std::uint8_t> report(3485);
        size_t length = report.size();
        REQUIRE(nvs_get_blob(handle, "ret0", report.data(), &length) == ESP_OK);
        REQUIRE(length == report.size());
        std::uint32_t old_generation = 0;
        std::memcpy(&old_generation, report.data(), 4);
        const std::uint32_t new_generation = cycle_count + 77;
        esp_partition_fail_after(cut, ESP_PARTITION_FAIL_AFTER_MODE_BOTH);
        const auto write = put(handle, "ret", 0, 3485, new_generation);
        esp_partition_fail_after(static_cast<size_t>(-1), ESP_PARTITION_FAIL_AFTER_MODE_BOTH);
        nvs_close(handle);
        REQUIRE(nvs_flash_deinit_partition(part_name) == ESP_OK);
        const auto recovery = nvs_flash_init_partition(part_name);
        REQUIRE(recovery == ESP_OK);
        REQUIRE(nvs_open_from_partition(part_name, "life", NVS_READONLY, &handle) == ESP_OK);
        length = report.size();
        const auto read = nvs_get_blob(handle, "ret0", report.data(), &length);
        if (read != ESP_OK) {
            std::printf("NVS_RUNTIME_FAULT_READ_FAIL cut=%zu write=%s read=%s length=%zu\n",
                        cut, esp_err_to_name(write), esp_err_to_name(read), length);
            metric("fault_read_fail", cycle_count, part);
        }
        REQUIRE(read == ESP_OK);
        REQUIRE(length == report.size());
        std::uint32_t recovered = 0;
        std::memcpy(&recovered, report.data(), 4);
        REQUIRE(recovered == old_generation || recovered == new_generation);
        std::printf("NVS_RUNTIME_FAULT cut=%zu write=%s old=%u new=%u recovered=%u\n",
                    cut, esp_err_to_name(write), old_generation, new_generation, recovered);
        metric("after_recovery", cycle_count, part);
        nvs_close(handle);
        REQUIRE(nvs_flash_deinit_partition(part_name) == ESP_OK);
        return 0;
    }
    if (promotion) {
        if (hot_count > 32) {
            // Replace 192 of the 384 exact certificates with full HOT bodies.
            // This releases three 64-key blocks before adding the bodies.
            for (unsigned i = 0; i < 3; ++i) {
                char key[16];
                std::snprintf(key, sizeof(key), "cert%u", i);
                REQUIRE(nvs_erase_key(handle, key) == ESP_OK);
            }
            REQUIRE(nvs_commit(handle) == ESP_OK);
            metric("certs_released", cycle_count, part);
        }
        unsigned admitted = 0;
        esp_err_t rc = ESP_OK;
        for (; admitted < hot_count; ++admitted) {
            rc = put(handle, "hot", admitted, 124, cycle_count + admitted + 1);
            if (rc != ESP_OK) break;
        }
        std::printf("NVS_RUNTIME_PROMOTION hot_admitted=%u hot_result=%s\n", admitted, esp_err_to_name(rc));
        metric("hot_peak", cycle_count, part);
        const auto seal = admitted == hot_count ? put(handle, "seg", 0, 4096, cycle_count + 50) : rc;
        std::printf("NVS_RUNTIME_PROMOTION seal_result=%s\n", esp_err_to_name(seal));
        metric("seal_peak", cycle_count, part);
        if (seal == ESP_OK) {
            for (unsigned i = 0; i < hot_count; ++i) {
                char key[16];
                std::snprintf(key, sizeof(key), "hot%u", i);
                REQUIRE(nvs_erase_key(handle, key) == ESP_OK);
            }
            REQUIRE(nvs_commit(handle) == ESP_OK);
            metric("after_hot_retire", cycle_count, part);
        }
    } else if (segment_count == 9) {
        unsigned failed_segment = saturation_limit;
        for (unsigned next = 9; next < saturation_limit; ++next) {
            const auto append = put(handle, "seg", next, 4096, cycle_count + next);
            std::printf("NVS_RUNTIME_SATURATION append_segment=%u result=%s\n", next, esp_err_to_name(append));
            if (append != ESP_OK) { failed_segment = next; break; }
        }
        metric("after_append_attempt", cycle_count, part);
        const auto report = put(handle, "ret", 0, 3485, cycle_count + 31);
        const auto root = report == ESP_OK ? put(handle, "root", 0, 512, cycle_count + 32) : report;
        std::printf("NVS_RUNTIME_SATURATION report_before_reclaim=%s root_after_report=%s\n",
                    esp_err_to_name(report), esp_err_to_name(root));
        metric("after_report_attempt", cycle_count, part);
        const auto erase = nvs_erase_key(handle, "seg0");
        const auto commit = erase == ESP_OK ? nvs_commit(handle) : erase;
        std::printf("NVS_RUNTIME_SATURATION erase_old=%s commit=%s\n", esp_err_to_name(erase), esp_err_to_name(commit));
        const auto retry = commit == ESP_OK ? put(handle, "seg", failed_segment, 4096, cycle_count + 30) : commit;
        std::printf("NVS_RUNTIME_SATURATION append_after_erase=%s\n", esp_err_to_name(retry));
        metric("after_reclaim", cycle_count, part);
    }
    nvs_close(handle);
    REQUIRE(nvs_flash_deinit_partition(part_name) == ESP_OK);
    return 0;
}
