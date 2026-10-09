// Host-only ESP-IDF Linux NVS runtime probe. Length-matched dummy values;
// no production codec, authenticated root protocol, or product policy.
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_partition.h"
#include "spi_flash_mmap.h"
#include "esp_private/partition_linux.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <vector>
#include <unistd.h>

#define REQUIRE(expression) do { if (!(expression)) { \
    std::fprintf(stderr, "PROBE_FAIL %s:%d: %s\n", __FILE__, __LINE__, #expression); \
    std::abort(); \
} } while (0)

extern "C" int __real_mkstemp(char*);
extern "C" int __wrap_mkstemp(char* path) {
    auto fd=__real_mkstemp(path);
    if(fd>=0) std::fprintf(stderr,"EMULATOR_IMAGE=%s\n",path);
    return fd;
}
namespace diag {
bool active = false, frozen = false, latch = false, verbose = false;
// New compact tests terminate the child immediately at a cut. No SDK cleanup,
// read, commit, or application operation runs on a supposedly powered-off device.
bool hard_stop = false;
size_t units = 0, calls = 0, entry_writes = 0, logical_bytes = 0;
const esp_partition_t* part = nullptr;
unsigned peak_live=0, peak_pages=0;
void observe() {
    if (!active || std::getenv("GS_PEAK") == nullptr) return;
    std::array<std::uint8_t,4096> raw{};unsigned live=0,used=0;
    for(unsigned p=0;p<part->size/4096;++p) {
        esp_partition_read(part,p*4096,raw.data(),raw.size());
        if(std::all_of(raw.begin(),raw.end(),[](auto b){return b==255;}))continue;
        ++used;for(unsigned e=0;e<126;++e) live+=((raw[32+e/4]>>((e%4)*2))&3)==2;
    }
    peak_live=std::max(peak_live,live);peak_pages=std::max(peak_pages,used);
}
void dump(const char* phase) {
    std::array<std::uint8_t, 4096> raw{};
    for (unsigned p = 0; p < part->size / 4096; ++p) {
        esp_partition_read(part, p * 4096, raw.data(), raw.size());
        for (unsigned e = 0; e < 126; ++e) {
            auto* it = raw.data() + 64 + e * 32;
            if (std::memcmp(it + 8, "ret0\0", 5) != 0) continue;
            unsigned st = (raw[32 + e / 4] >> ((e % 4) * 2)) & 3;
            unsigned sz = 0; std::memcpy(&sz, it + 24, it[1] == 0x48 ? 4 : 2);
            std::printf("ITEM phase=%s page=%u entry=%u state=%u type=%02x span=%u chunk=%u size=%u count=%u start=%u\n",
                phase,p,e,st,it[1],it[2],it[3],sz,it[28],it[29]);
        }
    }
}
}
extern "C" esp_err_t __real_esp_partition_write_raw(const esp_partition_t*, size_t, const void*, size_t);
extern "C" esp_err_t __real_esp_partition_write(const esp_partition_t*, size_t, const void*, size_t);
extern "C" esp_err_t __real_esp_partition_erase_range(const esp_partition_t*, size_t, size_t);
extern "C" esp_err_t __wrap_esp_partition_write(const esp_partition_t* p, size_t o, const void* d, size_t n) {
    if (diag::active && diag::frozen) {
        if (diag::verbose) std::printf("IO BLOCKED write offset=%zu size=%zu\n",o,n);
        return ESP_ERR_FLASH_OP_FAIL;
    }
    auto rc = __real_esp_partition_write(p,o,d,n);
    if(diag::hard_stop && rc!=ESP_OK){std::printf("COMPACT_POWER_CUT operation=write offset=%zu bytes=%zu\n",o,n);_exit(77);}
    if (rc == ESP_OK && o % 4096 >= 64) diag::entry_writes += (n + 31)/32;
    if (diag::active) {
        diag::units += n/4; ++diag::calls;
        if (diag::verbose) std::printf("IO write call=%zu units=%zu offset=%zu size=%zu result=%s\n",diag::calls,diag::units,o,n,esp_err_to_name(rc));
        if (rc != ESP_OK) { diag::dump("first_failure"); diag::frozen = diag::latch; }
    }
    diag::observe();
    return rc;
}
extern "C" esp_err_t __wrap_esp_partition_write_raw(const esp_partition_t* p, size_t o, const void* d, size_t n) {
    if (diag::active && diag::frozen) {
        if (diag::verbose) std::printf("IO BLOCKED write offset=%zu size=%zu\n",o,n);
        return ESP_ERR_FLASH_OP_FAIL;
    }
    if (diag::active && diag::verbose && o%4096==0 && n>=4) {
        std::uint32_t state=0;std::memcpy(&state,d,4);
        std::printf("PAGE_TRANSITION page=%zu state=%08x\n",o/4096,state);
    }
    auto rc = __real_esp_partition_write_raw(p,o,d,n);
    if(diag::hard_stop && rc!=ESP_OK){std::printf("COMPACT_POWER_CUT operation=raw_write offset=%zu bytes=%zu\n",o,n);_exit(77);}
    if (rc == ESP_OK && o % 4096 >= 64) diag::entry_writes += (n + 31)/32;
    if (diag::active) {
        diag::units += n/4; ++diag::calls;
        if (diag::verbose) std::printf("IO rawwrite call=%zu units=%zu offset=%zu size=%zu result=%s\n",diag::calls,diag::units,o,n,esp_err_to_name(rc));
        if (rc != ESP_OK) { diag::dump("first_failure"); diag::frozen = diag::latch; }
    }
    diag::observe();
    return rc;
}
extern "C" esp_err_t __wrap_esp_partition_erase_range(const esp_partition_t* p,size_t o,size_t n) {
    if (diag::active && diag::frozen) return ESP_ERR_FLASH_OP_FAIL;
    auto rc=__real_esp_partition_erase_range(p,o,n);
    if(diag::hard_stop && rc!=ESP_OK){std::printf("COMPACT_POWER_CUT operation=erase offset=%zu bytes=%zu\n",o,n);_exit(77);}
    if (diag::active) {
        diag::units += n/4096; ++diag::calls;
        if (diag::verbose) std::printf("IO erase call=%zu units=%zu offset=%zu size=%zu result=%s\n",diag::calls,diag::units,o,n,esp_err_to_name(rc));
        if (rc != ESP_OK) { diag::dump("first_failure"); diag::frozen=diag::latch; }
    }
    diag::observe();
    return rc;
}
namespace {
constexpr char part_name[] = "life";
constexpr unsigned page_bytes = 4096;
unsigned pages = 32;
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
    if (diag::active && diag::verbose) std::printf("API nvs_set_blob key=%s bytes=%u generation=%u\n",key,size,generation);
    auto rc = nvs_set_blob(handle, key, value.data(), value.size());
    if (rc == ESP_OK) {
        if (diag::active && diag::verbose) std::printf("API nvs_commit key=%s\n",key);
        rc = nvs_commit(handle);
    }
    if (rc == ESP_OK) diag::logical_bytes += size;
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

#include "offline_probe.hpp"
#include "compact_probe.hpp"
#include "workspace_48h_probe.hpp"

int main(int argc, char** argv) {
    setvbuf(stdout, nullptr, _IONBF, 0);
    if(argc>1 && std::strcmp(argv[1],"offline")==0) {
        if(const auto* size=std::getenv("GS_EMULATOR_FLASH_BYTES")) {
            const auto bytes=std::strtoul(size,nullptr,10);
            REQUIRE(bytes==4194304); // Capacity-only host mapping, no target I/O.
            esp_partition_get_file_mmap_ctrl_input()->flash_file_size=bytes;
        }
    }
    if(argc>1 && std::strcmp(argv[1],"compact")==0)return compact_probe(argc,argv);
    if(argc>1 && std::strcmp(argv[1],"workspace48")==0)return workspace_48h_probe(argc,argv);
    if(argc>1 && std::strcmp(argv[1],"offline")==0)return offline_probe(argc,argv);
    const unsigned segment_count = argc > 1 ? static_cast<unsigned>(std::strtoul(argv[1], nullptr, 10)) : 7;
    const unsigned cycle_count = argc > 2 ? static_cast<unsigned>(std::strtoul(argv[2], nullptr, 10)) : 100;
    const unsigned saturation_limit = argc > 3 ? static_cast<unsigned>(std::strtoul(argv[3], nullptr, 10)) : 20;
    const bool capacity = argc > 4 && std::strcmp(argv[4], "capacity") == 0;
    const bool promotion = capacity || (argc > 4 && std::strcmp(argv[4], "promotion") == 0);
    const bool schedule = argc > 4 && std::strcmp(argv[4], "schedule") == 0;
    const bool banks = argc > 4 && std::strcmp(argv[4], "banks") == 0;
    const bool fault = argc > 4 && std::strcmp(argv[4], "fault") == 0;
    const unsigned hot_count = promotion && argc > 5 ? static_cast<unsigned>(std::strtoul(argv[5], nullptr, 10)) : 32;
    REQUIRE(hot_count <= 192);
    REQUIRE(segment_count >= 3 && segment_count <= 9);
    const auto* original_part = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, part_name);
    REQUIRE(original_part != nullptr);
    auto synthetic_part = *original_part;
    if(const auto* size = std::getenv("GS_DIAG_PAGES")) {
        pages=std::strtoul(size,nullptr,10);REQUIRE(pages>=32 && pages<=64);
        synthetic_part.size=pages*page_bytes;
    }
    const auto* part=&synthetic_part;
    pages = part->size / page_bytes;
    diag::part = part;
    REQUIRE(esp_partition_erase_range(part, 0, part->size) == ESP_OK);
    esp_partition_clear_stats();
    REQUIRE(nvs_flash_init_partition_ptr(part) == ESP_OK);
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
    for (unsigned cycle = 1; cycle <= (schedule ? 0 : cycle_count); ++cycle) {
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
    if (schedule) {
        // Sensitivity fixture: each body commits before hypothetical ACK. No codec,
        // cloud service, authenticated owner ledger or real reducer is implemented.
        const auto wb=esp_partition_get_write_bytes(), eb=esp_partition_get_erase_ops();
        const auto iw=diag::entry_writes, lb=diag::logical_bytes;
        unsigned groups=0;
        for (unsigned i=0;i<cycle_count;++i) {
            REQUIRE(put(handle,"evt",i%32,36,i+1)==ESP_OK);
            // Event-driven durable backend receipt; intentionally individual, unbatched.
            REQUIRE(put(handle,"done",i%32,48,i+1)==ESP_OK);
            if ((i+1)%32==0 || i+1==cycle_count) {
                // Candidate report/state bank, root publication, then lawful release.
                REQUIRE(put(handle,"ret",(groups+1)%3,3485,i+1)==ESP_OK);
                REQUIRE(put(handle,"state",(groups+1)%3,6144,i+1)==ESP_OK);
                REQUIRE(put(handle,"seg",groups%segment_count,4096,i+1)==ESP_OK);
                REQUIRE(put(handle,"meta",groups%2,4096,i+1)==ESP_OK);
                REQUIRE(put(handle,"root",groups%2,512,i+1)==ESP_OK);
                for(unsigned j=0;j<(i%32+1);++j) {
                    char k[16];std::snprintf(k,sizeof(k),"evt%u",j);REQUIRE(nvs_erase_key(handle,k)==ESP_OK);
                    std::snprintf(k,sizeof(k),"done%u",j);REQUIRE(nvs_erase_key(handle,k)==ESP_OK);
                }
                REQUIRE(nvs_commit(handle)==ESP_OK);++groups;
            }
        }
        REQUIRE(put(handle,"daily",0,320,1)==ESP_OK);
        metric("schedule_day",cycle_count,part);
        size_t mx=0;for(unsigned p=0;p<pages;++p) mx=std::max(mx,esp_partition_get_sector_erase_count(part->address/4096+p));
        const auto logical=diag::logical_bytes-lb, programmed=esp_partition_get_write_bytes()-wb;
        std::printf("SCHEDULE records=%u groups=%u logical_bytes=%zu programmed_bytes=%zu amplification=%.6f entries_written=%zu page_erases=%zu max_sector_erases=%zu\n",
            cycle_count,groups,logical,programmed,double(programmed)/logical,diag::entry_writes-iw,esp_partition_get_erase_ops()-eb,mx);
        nvs_close(handle);REQUIRE(nvs_flash_deinit_partition(part_name)==ESP_OK);return 0;
    }
    if (argc > 4 && std::strcmp(argv[4], "progress") == 0) {
        // One targeted saturation/restart check, not a capacity matrix. Preserve
        // every existing dummy owner; never delete accepted data to make room.
        REQUIRE(segment_count == 9);
        for (unsigned i = 9; i < 12; ++i)
            REQUIRE(put(handle, "seg", i, 4096, cycle_count + i) == ESP_OK);
        struct Saved { std::array<char,16> key{}; std::vector<std::uint8_t> bytes; };
        std::vector<Saved> saved;
        for (const auto& family : std::array<std::pair<const char*,unsigned>,7>{{
                {"cert",6},{"ret",3},{"state",3},{"root",2},
                {"meta",2},{"crit",2},{"seg",12}}}) {
            for (unsigned i = 0; i < family.second; ++i) {
                Saved item;
                std::snprintf(item.key.data(), item.key.size(), "%s%u", family.first, i);
                size_t length = 0;
                REQUIRE(nvs_get_blob(handle,item.key.data(),nullptr,&length)==ESP_OK);
                item.bytes.resize(length);
                REQUIRE(nvs_get_blob(handle,item.key.data(),item.bytes.data(),&length)==ESP_OK);
                saved.push_back(std::move(item));
            }
        }
        for (unsigned attempt = 1; attempt <= 3; ++attempt) {
            auto rc = put(handle,"candidate",0,3485,cycle_count+77);
            if (rc == ESP_OK) rc = put(handle,"select",0,512,cycle_count+77);
            std::printf("PROTECTED_PROGRESS attempt=%u result=%s ack_allowed=0\n",
                        attempt,esp_err_to_name(rc));
            REQUIRE(rc == ESP_ERR_NVS_NOT_ENOUGH_SPACE);
        }
        nvs_close(handle);
        REQUIRE(nvs_flash_deinit_partition(part_name)==ESP_OK);
        REQUIRE(nvs_flash_init_partition_ptr(part)==ESP_OK);
        REQUIRE(nvs_open_from_partition(part_name,"life",NVS_READONLY,&handle)==ESP_OK);
        for (const auto& item : saved) {
            size_t length = item.bytes.size();
            std::vector<std::uint8_t> value(length);
            REQUIRE(nvs_get_blob(handle,item.key.data(),value.data(),&length)==ESP_OK);
            REQUIRE(length == item.bytes.size() && value == item.bytes);
        }
        std::printf("PROTECTED_PROGRESS_HOST_PASS preserved_blobs=%zu remount=PASS bounded_attempts=3 progress=BLOCKED\n",saved.size());
        metric("protected_progress_recovery",cycle_count,part);
        nvs_close(handle);
        REQUIRE(nvs_flash_deinit_partition(part_name)==ESP_OK);
        return 0;
    }
    if (fault || banks) {
        const size_t cut = argc > 5 ? std::strtoul(argv[5], nullptr, 10) : 0;
        std::vector<std::uint8_t> report(3485);
        size_t length = report.size();
        REQUIRE(nvs_get_blob(handle, "ret0", report.data(), &length) == ESP_OK);
        REQUIRE(length == report.size());
        std::uint32_t old_generation = 0;
        std::memcpy(&old_generation, report.data(), 4);
        const std::uint32_t new_generation = cycle_count + 77;
        if (banks) REQUIRE(put(handle, "pick", 0, 512, old_generation) == ESP_OK); // fresh old selector in this one-transition fixture
        diag::active = true;
        diag::latch = (banks && !(argc > 6 && std::strcmp(argv[6], "resume") == 0)) || (argc > 6 && std::strcmp(argv[6], "freeze") == 0);
        diag::verbose = std::getenv("GS_DIAG_TRACE") != nullptr;
        if (diag::verbose) diag::dump("before_cut");
        esp_partition_fail_after(cut, ESP_PARTITION_FAIL_AFTER_MODE_BOTH);
        auto write = put(handle, banks ? "r" : "ret", banks ? new_generation : 0, 3485, new_generation);
        if (banks && write == ESP_OK) {
            write = put(handle, "pick", 1, 512, new_generation);
            if (write == ESP_OK) {
                if (diag::verbose) std::printf("API nvs_erase_key key=ret0 after_new_selection\n");
                write = nvs_erase_key(handle, "ret0");
                if (write == ESP_OK) write = nvs_commit(handle);
            }
        }
        if (diag::verbose) diag::dump("after_api");
        diag::active = false;
        esp_partition_fail_after(static_cast<size_t>(-1), ESP_PARTITION_FAIL_AFTER_MODE_BOTH);
        nvs_close(handle);
        REQUIRE(nvs_flash_deinit_partition(part_name) == ESP_OK);
        if (diag::verbose) std::printf("API remount\n");
        std::printf("DIAG_OPERATION mode=%s calls=%zu units=%zu latch=%u\n",banks?"banks":"inplace",diag::calls,diag::units,diag::latch);
        const auto* recovery_cut = std::getenv("GS_RECOVERY_CUT");
        if (recovery_cut) {
            diag::active=true; diag::latch=true; diag::frozen=false;
            esp_partition_fail_after(std::strtoul(recovery_cut,nullptr,10),ESP_PARTITION_FAIL_AFTER_MODE_BOTH);
            auto rr=nvs_flash_init_partition_ptr(part);
            diag::active=false;
            esp_partition_fail_after(static_cast<size_t>(-1),ESP_PARTITION_FAIL_AFTER_MODE_BOTH);
            nvs_flash_deinit_partition(part_name);
            std::printf("RECOVERY_INTERRUPTION cut=%s result=%s reboot_again\n",recovery_cut,esp_err_to_name(rr));
        }
        const auto recovery = nvs_flash_init_partition_ptr(part);
        REQUIRE(recovery == ESP_OK);
        if (diag::verbose) diag::dump("after_remount");
        REQUIRE(nvs_open_from_partition(part_name, "life", NVS_READONLY, &handle) == ESP_OK);
        length = report.size();
        char selected[16] = "ret0";
        if (banks) {
            std::array<std::uint8_t,512> root{}; size_t rn=root.size();
            if (nvs_get_blob(handle,"pick1",root.data(),&rn)==ESP_OK && rn==root.size()) {
                std::uint32_t rg=0; std::memcpy(&rg,root.data(),4);
                REQUIRE(rg==new_generation && std::all_of(root.begin()+4,root.end(),[rg](auto b){return b==static_cast<std::uint8_t>(rg+1);}));
                if (rg==new_generation) std::snprintf(selected,sizeof(selected),"r%u",rg);
            }
        }
        if (diag::verbose) std::printf("API nvs_get_blob key=%s\n",selected);
        const auto read = nvs_get_blob(handle, selected, report.data(), &length);
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
        if (banks) {
            if (recovered==old_generation) {
                std::array<std::uint8_t,512> root{};size_t rn=root.size();
                REQUIRE(nvs_get_blob(handle,"pick0",root.data(),&rn)==ESP_OK && rn==root.size());
                std::uint32_t rg=0;std::memcpy(&rg,root.data(),4);REQUIRE(rg==old_generation);
                REQUIRE(std::all_of(root.begin()+4,root.end(),[rg](auto b){return b==static_cast<std::uint8_t>(rg);}));
            }
        }
        const auto fill=static_cast<std::uint8_t>(recovered + (banks && recovered==new_generation ? new_generation : 0));
        REQUIRE(std::all_of(report.begin()+4,report.end(),[fill](auto b){return b==fill;}));
        std::printf("NVS_RUNTIME_FAULT cut=%zu write=%s old=%u new=%u recovered=%u\n",
                    cut, esp_err_to_name(write), old_generation, new_generation, recovered);
        metric("after_recovery", cycle_count, part);
        nvs_close(handle);
        REQUIRE(nvs_flash_deinit_partition(part_name) == ESP_OK);
        return 0;
    }
    if (promotion) {
        diag::active=capacity;
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
            rc = put(handle, "hot", admitted, std::getenv("GS_HOT_BYTES") ? std::strtoul(std::getenv("GS_HOT_BYTES"),nullptr,10) : 124, cycle_count + admitted + 1);
            if (rc != ESP_OK) break;
        }
        std::printf("NVS_RUNTIME_PROMOTION hot_admitted=%u hot_result=%s\n", admitted, esp_err_to_name(rc));
        metric("hot_peak", cycle_count, part);
        const auto seal = admitted == hot_count ? put(handle, "seg", 0, 4096, cycle_count + 50) : rc;
        std::printf("NVS_RUNTIME_PROMOTION seal_result=%s\n", esp_err_to_name(seal));
        metric("seal_peak", cycle_count, part);
        if (capacity) {
            auto progress=seal;
            if(progress==ESP_OK) progress=put(handle,"candidate",0,3485,cycle_count+100);
            if(progress==ESP_OK) progress=put(handle,"select",0,512,cycle_count+100);
            if(progress==ESP_OK) progress=put(handle,"check",0,6144,cycle_count+100);
            if(progress==ESP_OK) progress=put(handle,"selstate",0,512,cycle_count+100);
            std::printf("CAPACITY pages=%u hot_bytes=%s admitted=%u progress=%s\n",pages,std::getenv("GS_HOT_BYTES")?std::getenv("GS_HOT_BYTES"):"124",admitted,esp_err_to_name(progress));
            metric("capacity_peak",cycle_count,part);
            std::printf("CAPACITY_IO_PEAK live_entries=%u allocated_pages=%u\n",diag::peak_live,diag::peak_pages);
            nvs_close(handle);REQUIRE(nvs_flash_deinit_partition(part_name)==ESP_OK);
            return progress==ESP_OK ? 0 : 2;
        }
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
        diag::active=true;
        const auto report = put(handle, "ret", 0, 3485, cycle_count + 31);
        const auto root = report == ESP_OK ? put(handle, "root", 0, 512, cycle_count + 32) : report;
        std::printf("NVS_RUNTIME_SATURATION report_before_reclaim=%s root_after_report=%s\n",
                    esp_err_to_name(report), esp_err_to_name(root));
        metric("after_report_attempt", cycle_count, part);
        std::printf("REPORT_IO_PEAK live_entries=%u allocated_pages=%u\n",diag::peak_live,diag::peak_pages);
        diag::active=false;
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
