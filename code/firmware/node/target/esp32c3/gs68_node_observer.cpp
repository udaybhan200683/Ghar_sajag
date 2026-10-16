#include "firmware/node/target/esp32c3/gs68_node_observer.hpp"

#include "esp_app_desc.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_ota_ops.h"
#include "esp_partition.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/portmacro.h"
#include "freertos/task.h"
#include "gs/gs68_diag_protocol.hpp"

#include <array>
#include <cinttypes>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string_view>

#if !defined(GS_GS68_NODE_OBSERVER) || GS_GS68_NODE_OBSERVER != 1
#error "GS-68 C3 observer must be selected only by its diagnostic profile"
#endif
#if GS_HIL_CONTROL || GS_HIL_BUILD
#error "GS-68 C3 observer excludes legacy HIL injection and reset controls"
#endif
#ifndef GS68_NODE_SOURCE_COMMIT
#define GS68_NODE_SOURCE_COMMIT "UNBOUND"
#endif
#ifndef GS68_NODE_PROFILE_SHA256
#define GS68_NODE_PROFILE_SHA256 "UNBOUND"
#endif

namespace gs::node::target::gs68 {
namespace {
constexpr char kTag[] = "gs68_c3_observer";
constexpr std::size_t kTraceCapacity = 6;
constexpr std::size_t kIdentifierCapacity = 48;
constexpr std::size_t kOutputCapacity = 4096;
portMUX_TYPE g_observer_mux = portMUX_INITIALIZER_UNLOCKED;

struct KeyRecord {
    bool present{false};
    char physical_device_id[kIdentifierCapacity]{};
    char source_id[kIdentifierCapacity]{};
    std::uint64_t session_id{0};
    std::uint64_t sequence{0};
};

struct TraceRecord {
    char type[12]{};
    KeyRecord key{};
    std::uint32_t attempt{0};
    std::int32_t ack_class{-1};
    bool authenticated{false};
    bool matched_pending{false};
    bool retired{false};
    bool durable{false};
};

struct ObserverState {
    char node_id[kIdentifierCapacity]{};
    char hub_id[kIdentifierCapacity]{};
    char physical_device_id[kIdentifierCapacity]{};
    std::uint64_t boot_generation{0};
    std::uint32_t reset_reason{0};
    std::uint32_t retained_count{0};
    std::uint32_t pending_count{0};
    std::uint32_t retry_count{0};
    bool runtime_snapshot_seen{false};
    bool hub_authenticated{false};
    bool hub_outage{false};
    KeyRecord oldest_pending_key{};
    KeyRecord last_transmit_key{};
    KeyRecord last_ack_key{};
    std::uint32_t last_transmit_attempt{0};
    std::array<TraceRecord, kTraceCapacity> trace{};
    std::size_t trace_next{0};
    std::size_t trace_count{0};
};

ObserverState g_state{};
char g_running_image_sha256[65]{};

bool safe_identifier(const char* value) {
    if (value == nullptr || value[0] == '\0') return false;
    for (const unsigned char ch : std::string_view(value)) {
        if (!((ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') ||
              (ch >= '0' && ch <= '9') || ch == '-' || ch == '_' || ch == '.' || ch == ':'))
            return false;
    }
    return true;
}

void copy_identifier(char* output, std::size_t capacity, const char* value) {
    output[0] = '\0';
    if (!safe_identifier(value)) return;
    const auto size = std::strlen(value);
    if (size >= capacity) return;
    std::memcpy(output, value, size + 1);
}

KeyRecord make_key(const gs::EventKey& key, const char* physical_device_id) {
    KeyRecord record{};
    if (key.session_id == 0 || key.sequence == 0 || !safe_identifier(key.source_id.c_str()))
        return record;
    copy_identifier(record.source_id, sizeof(record.source_id), key.source_id.c_str());
    copy_identifier(record.physical_device_id, sizeof(record.physical_device_id), physical_device_id);
    if (record.source_id[0] == '\0' || record.physical_device_id[0] == '\0') return {};
    record.present = true;
    record.session_id = key.session_id;
    record.sequence = key.sequence;
    return record;
}

void push_trace(const TraceRecord& record) {
    g_state.trace[g_state.trace_next] = record;
    g_state.trace_next = (g_state.trace_next + 1U) % g_state.trace.size();
    if (g_state.trace_count < g_state.trace.size()) ++g_state.trace_count;
}

void append_key(char* output, std::size_t capacity, const KeyRecord& key) {
    if (!key.present) {
        std::snprintf(output, capacity, "null");
        return;
    }
    std::snprintf(output, capacity,
        "{\"physical_device_id\":\"%s\",\"source_id\":\"%s\",\"session_id\":\"%" PRIu64 "\",\"sequence\":\"%" PRIu64 "\"}",
        key.physical_device_id, key.source_id, key.session_id, key.sequence);
}

const char* ack_name(std::int32_t value) {
    switch (value) {
        case 0: return "DURABLE";
        case 1: return "RECEIVED_VOLATILE";
        case 2: return "DISCARDED_POLICY";
        case 3: return "REJECTED";
        default: return "NONE";
    }
}

ObserverState copy_state() {
    ObserverState copy{};
    portENTER_CRITICAL(&g_observer_mux);
    copy = g_state;
    portEXIT_CRITICAL(&g_observer_mux);
    return copy;
}

bool append_text(char*& cursor, std::size_t& remaining, const char* format, ...) {
    if (remaining == 0) return false;
    va_list args;
    va_start(args, format);
    const int written = std::vsnprintf(cursor, remaining, format, args);
    va_end(args);
    if (written < 0 || static_cast<std::size_t>(written) >= remaining) return false;
    cursor += written;
    remaining -= static_cast<std::size_t>(written);
    return true;
}

void emit_line(const char* buffer, std::size_t size) {
    (void)std::fwrite(buffer, 1, size, stdout);
    (void)std::fflush(stdout);
}

void emit_ready() {
    const auto* app = esp_app_get_description();
    esp_chip_info_t chip{};
    esp_chip_info(&chip);
    std::array<std::uint8_t, 32> image_hash{};
    const auto* running = esp_ota_get_running_partition();
    const bool image_hash_valid = running != nullptr &&
        esp_partition_get_sha256(running, image_hash.data()) == ESP_OK;
    char image_hex[65]{};
    if (image_hash_valid) {
        for (std::size_t i = 0; i < image_hash.size(); ++i)
            std::snprintf(image_hex + i * 2, sizeof(image_hex) - i * 2, "%02x", image_hash[i]);
    }
    std::memcpy(g_running_image_sha256, image_hex, sizeof(g_running_image_sha256));
    std::array<std::uint8_t, 6> mac{};
    const auto mac_status = esp_read_mac(mac.data(), ESP_MAC_WIFI_STA);
    std::uint32_t flash_bytes = 0;
    const auto flash_status = esp_flash_get_physical_size(nullptr, &flash_bytes);
    const auto boot_state = copy_state();
    char output[1024]{};
    const int size = std::snprintf(output, sizeof(output),
        "GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"ready\",\"role\":\"c3\","
        "\"source_commit\":\"%s\",\"profile_sha256\":\"%s\",\"project_version\":\"%s\","
        "\"boot_generation_source\":\"durable_node_session_allocator\","
        "\"idf_version\":\"%s\",\"chip_model\":\"ESP32-C3\",\"chip_revision\":%u,"
        "\"mac_status\":%d,\"mac_address\":\"%02x:%02x:%02x:%02x:%02x:%02x\","
        "\"flash_status\":%d,\"flash_bytes\":%u,\"psram_bytes\":%u,"
        "\"running_image_sha256\":\"%s\",\"boot_generation\":\"%" PRIu64 "\",\"reset_reason\":%" PRIu32 ","
        "\"observer_profile\":\"TEST_ONLY_READ_ONLY\",\"control_surface\":\"OBSERVE_ONLY\","
        "\"internet_status\":\"NOT_OBSERVED_BY_NODE\",\"physical\":\"NOT_RUN\"}\n",
        GS68_NODE_SOURCE_COMMIT, GS68_NODE_PROFILE_SHA256,
        app != nullptr ? app->version : "unknown", app != nullptr ? app->idf_ver : "unknown",
        static_cast<unsigned>(chip.revision), static_cast<int>(mac_status),
        mac[0], mac[1], mac[2], mac[3], mac[4], mac[5],
        static_cast<int>(flash_status), static_cast<unsigned>(flash_bytes),
        0U, image_hash_valid ? image_hex : "",
        boot_state.boot_generation, boot_state.reset_reason);
    if (size > 0 && static_cast<std::size_t>(size) < sizeof(output))
        emit_line(output, static_cast<std::size_t>(size));
}

void emit_observation(const gs::diagnostic::TargetCommand& command) {
    const auto state = copy_state();
    char oldest[256]{}, tx[256]{}, ack[256]{};
    append_key(oldest, sizeof(oldest), state.oldest_pending_key);
    append_key(tx, sizeof(tx), state.last_transmit_key);
    append_key(ack, sizeof(ack), state.last_ack_key);
    TraceRecord last_ack{};
    bool has_ack = false;
    for (std::size_t i = 0; i < state.trace_count; ++i) {
        const auto index = (state.trace_next + kTraceCapacity - 1U - i) % kTraceCapacity;
        if (std::strcmp(state.trace[index].type, "ACK") == 0) {
            last_ack = state.trace[index];
            has_ack = true;
            break;
        }
    }
    static char output[kOutputCapacity]{};
    std::memset(output, 0, sizeof(output));
    char* cursor = output;
    std::size_t remaining = sizeof(output);
    bool ok = append_text(cursor, remaining,
        "GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"node_observation\","
        "\"role\":\"c3\",\"case_id\":\"%s\",\"challenge_nonce\":\"%s\","
        "\"source_commit\":\"%s\",\"profile_sha256\":\"%s\","
        "\"running_image_sha256\":\"%s\","
        "\"boot_generation_source\":\"durable_node_session_allocator\","
        "\"node_id\":\"%s\",\"hub_id\":\"%s\",\"physical_device_id\":\"%s\","
        "\"boot_generation\":\"%" PRIu64 "\",\"reset_reason\":%" PRIu32 ","
        "\"runtime_snapshot_seen\":%s,\"hub_authenticated\":%s,\"hub_link_state\":\"%s\","
        "\"hub_outage_profile\":%s,\"internet_status\":\"NOT_OBSERVED_BY_NODE\","
        "\"retained_event_count\":%" PRIu32 ",\"pending_event_count\":%" PRIu32 ",\"retry_count\":%" PRIu32 ","
        "\"oldest_pending_event_key\":%s,\"last_transmit_event_key\":%s,"
        "\"last_transmit_attempt\":%" PRIu32 ",\"last_ack_event_key\":%s,"
        "\"last_ack_class\":\"%s\",\"last_ack_authenticated\":%s,"
        "\"last_ack_matched_pending\":%s,\"last_ack_retired\":%s,\"last_ack_durable\":%s,"
        "\"trace\":[",
        command.case_id, command.challenge_nonce, GS68_NODE_SOURCE_COMMIT,
        GS68_NODE_PROFILE_SHA256, g_running_image_sha256,
        state.node_id, state.hub_id, state.physical_device_id,
        state.boot_generation, state.reset_reason,
        state.runtime_snapshot_seen ? "true" : "false",
        state.hub_authenticated ? "true" : "false",
        state.hub_authenticated ? "AUTHENTICATED" : "UNAVAILABLE_OR_REJOINING",
        state.hub_outage ? "true" : "false", state.retained_count,
        state.pending_count, state.retry_count, oldest, tx,
        state.last_transmit_attempt, ack, ack_name(has_ack ? last_ack.ack_class : -1),
        has_ack && last_ack.authenticated ? "true" : "false",
        has_ack && last_ack.matched_pending ? "true" : "false",
        has_ack && last_ack.retired ? "true" : "false",
        has_ack && last_ack.durable ? "true" : "false");
    for (std::size_t i = 0; ok && i < state.trace_count; ++i) {
        const auto index = (state.trace_next + kTraceCapacity - state.trace_count + i) % kTraceCapacity;
        const auto& item = state.trace[index];
        char key[256]{};
        append_key(key, sizeof(key), item.key);
        ok = append_text(cursor, remaining,
            "%s{\"type\":\"%s\",\"event_key\":%s,\"attempt\":%" PRIu32 ","
            "\"ack_class\":\"%s\",\"authenticated\":%s,\"matched_pending\":%s,"
            "\"retired\":%s,\"durable\":%s}",
            i == 0 ? "" : ",", item.type, key, item.attempt,
            ack_name(item.ack_class), item.authenticated ? "true" : "false",
            item.matched_pending ? "true" : "false", item.retired ? "true" : "false",
            item.durable ? "true" : "false");
    }
    ok = ok && append_text(cursor, remaining,
        "],\"free_heap\":%u,\"largest_free_block\":%u,\"physical\":\"NOT_RUN\"}\n",
        static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_8BIT)),
        static_cast<unsigned>(heap_caps_get_largest_free_block(MALLOC_CAP_8BIT)));
    if (ok) emit_line(output, static_cast<std::size_t>(cursor - output));
    else {
        static constexpr char error[] =
            "GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"capture_error\","
            "\"reason\":\"bounded_observation_overflow\",\"physical\":\"NOT_RUN\"}\n";
        emit_line(error, sizeof(error) - 1);
    }
}

void emit_command_error(const char* reason) {
    char output[256]{};
    const int size = std::snprintf(output, sizeof(output),
        "GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"command_result\","
        "\"case_id\":\"GS68-PHY-000\",\"case_outcome\":\"BLOCKED\","
        "\"reason\":\"%s\",\"physical\":\"NOT_RUN\"}\n", reason);
    if (size > 0 && static_cast<std::size_t>(size) < sizeof(output))
        emit_line(output, static_cast<std::size_t>(size));
}

void diagnostic_task(void*) {
    emit_ready();
    char line[gs::diagnostic::kTargetCommandMaxBytes + 2]{};
    std::size_t used = 0;
    bool overflow = false;
    for (;;) {
        const int value = std::fgetc(stdin);
        if (value == EOF) {
            clearerr(stdin);
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        const char ch = static_cast<char>(value);
        if (ch == '\r') continue;
        if (ch == '\n') {
            if (overflow) emit_command_error("oversized_command");
            else {
                gs::diagnostic::TargetCommand command{};
                const auto result = gs::diagnostic::parse_target_command(line, used, command);
                if (result != gs::diagnostic::TargetCommandError::Ok)
                    emit_command_error("invalid_or_oversized_command");
                else if (std::strcmp(command.operation, "PING") == 0)
                    emit_observation(command);
                else if (std::strcmp(command.operation, "OBSERVE") == 0)
                    emit_observation(command);
                else emit_command_error("operation_not_supported");
            }
            std::memset(line, 0, sizeof(line));
            used = 0;
            overflow = false;
            continue;
        }
        if (overflow) continue;
        if (used >= gs::diagnostic::kTargetCommandMaxBytes) {
            overflow = true;
            continue;
        }
        line[used++] = ch;
    }
}
}  // namespace

void start_node_observer() {
    if (xTaskCreate(diagnostic_task, "gs68_c3_observe", 8192, nullptr, 4, nullptr) != pdPASS)
        ESP_LOGE(kTag, "observer task could not start; product runtime remains unchanged");
}

void publish_runtime_state(const char* node_id, const char* hub_id,
                           const char* physical_device_id,
                           std::uint64_t boot_generation,
                           std::uint32_t reset_reason,
                           bool hub_authenticated, bool hub_outage,
                           std::uint32_t retained_count,
                           std::uint32_t pending_count,
                           std::uint32_t retry_count,
                           const gs::EventKey* oldest_pending_key) {
    portENTER_CRITICAL(&g_observer_mux);
    copy_identifier(g_state.node_id, sizeof(g_state.node_id), node_id);
    copy_identifier(g_state.hub_id, sizeof(g_state.hub_id), hub_id);
    copy_identifier(g_state.physical_device_id, sizeof(g_state.physical_device_id), physical_device_id);
    g_state.boot_generation = boot_generation;
    g_state.reset_reason = reset_reason;
    g_state.hub_authenticated = hub_authenticated;
    g_state.hub_outage = hub_outage;
    g_state.retained_count = retained_count;
    g_state.pending_count = pending_count;
    g_state.retry_count = retry_count;
    g_state.runtime_snapshot_seen = true;
    g_state.oldest_pending_key = oldest_pending_key == nullptr
        ? KeyRecord{} : make_key(*oldest_pending_key, physical_device_id);
    portEXIT_CRITICAL(&g_observer_mux);
}

void publish_event_admitted(const gs::EventKey& key, const char* physical_device_id) {
    portENTER_CRITICAL(&g_observer_mux);
    TraceRecord item{};
    std::snprintf(item.type, sizeof(item.type), "ADMITTED");
    item.key = make_key(key, physical_device_id);
    push_trace(item);
    portEXIT_CRITICAL(&g_observer_mux);
}

void publish_transmission_attempt(const gs::EventKey& key,
                                  const char* physical_device_id) {
    portENTER_CRITICAL(&g_observer_mux);
    const auto record = make_key(key, physical_device_id);
    if (record.present && g_state.last_transmit_key.present &&
        std::strcmp(record.physical_device_id, g_state.last_transmit_key.physical_device_id) == 0 &&
        std::strcmp(record.source_id, g_state.last_transmit_key.source_id) == 0 &&
        record.session_id == g_state.last_transmit_key.session_id &&
        record.sequence == g_state.last_transmit_key.sequence) {
        ++g_state.last_transmit_attempt;
    } else {
        g_state.last_transmit_attempt = 1;
    }
    g_state.last_transmit_key = record;
    TraceRecord item{};
    std::snprintf(item.type, sizeof(item.type), "TX");
    item.key = record;
    item.attempt = g_state.last_transmit_attempt;
    push_trace(item);
    portEXIT_CRITICAL(&g_observer_mux);
}

void publish_hub_ack(const gs::EventKey& key, const char* physical_device_id,
                     gs::AckClass ack_class, bool authenticated,
                     bool matched_pending, bool retired, bool durable) {
    portENTER_CRITICAL(&g_observer_mux);
    const auto record = make_key(key, physical_device_id);
    g_state.last_ack_key = record;
    TraceRecord item{};
    std::snprintf(item.type, sizeof(item.type), "ACK");
    item.key = record;
    item.ack_class = static_cast<std::int32_t>(ack_class);
    item.authenticated = authenticated;
    item.matched_pending = matched_pending;
    item.retired = retired;
    item.durable = durable;
    push_trace(item);
    portEXIT_CRITICAL(&g_observer_mux);
}

}  // namespace gs::node::target::gs68
