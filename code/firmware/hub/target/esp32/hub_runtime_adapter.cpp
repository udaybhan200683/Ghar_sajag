#include "gs/node_health_config.hpp"
#include "firmware/hub/target/esp32/hub_runtime_adapter.hpp"
#if GS_HIL_C8_ACK_DROP
#include "firmware/hub/target/esp32/hil_c8_ack_drop_gate.hpp"
#endif
#if GS_HIL_C8_ACK_HOLD
#include "firmware/hub/target/esp32/hil_c8_ack_hold_gate.hpp"
#endif

#include "firmware/common/transport/data_plane_codec.hpp"
#include "firmware/common/connectivity/esp_idf_india_wifi_country.hpp"
#include "firmware/common/connectivity/india_wifi_profile.hpp"
#include "firmware/common/security/target_identity_signer.hpp"
#include "firmware/hub/lifecycle/fota/hub_fota_guard.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/hub/runtime/hub_event_log.hpp"
#include "firmware/hub/storage/hub_durability_owner.hpp"
#include "firmware/hub/storage/durable_journal_slot_store.hpp"
#include "firmware/hub/target/esp32/nvs_durable_blob_store.hpp"
#include "firmware/hub/target/esp32/nvs_journal_slot_store.hpp"
#include "firmware/hub/target/esp32/nvs_store_inventory.hpp"
#include "firmware/hub/target/esp32/hub_target_config.hpp"
#include "firmware/hub/connectivity/wifi_station.hpp"
#if CONFIG_IDF_TARGET_ESP32S3
#include "firmware/hub/connectivity/wifi_reconnect_policy.hpp"
#include "firmware/hub/cloud_sync/cloud_sync.hpp"
#include "firmware/hub/cloud_sync/http_backend_transport.hpp"
#include "firmware/hub/target/esp32s3/cloud_trust_provider.hpp"
#include "firmware/hub/target/esp32s3/https_backend_channel.hpp"
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
#include "firmware/hub/target/esp32s3/gs40_test_only_runtime.hpp"
#include "firmware/hub/target/esp32s3/gs40_test_only_startup_policy.hpp"
#endif
#include "firmware/hub/storage/durable_event_outbox.hpp"
#include "firmware/hub/storage/outbox_journal_backend.hpp"
#include "firmware/hub/target/esp32s3/littlefs_segment_store.hpp"
#endif

#include "esp_event.h"
#include "esp_idf_version.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include <array>
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <memory>
#include <map>
#include <vector>

#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
#include "esp_timer.h"
#endif

namespace gs::hub::target {
namespace {
#if GS_HIL_C8_ACK_DROP && CONFIG_IDF_TARGET_ESP32S3
C8AckDropGate g_c8_ack_drop_gate;
#endif
#if GS_HIL_C8_ACK_HOLD && CONFIG_IDF_TARGET_ESP32S3
C8AckHoldGate g_c8_ack_hold_gate;
#endif

constexpr char kTag[] = "gs_hub_runtime";
constexpr UBaseType_t kDataQueueDepth = 16U;
constexpr UBaseType_t kControlQueueDepth = 8U;
constexpr UBaseType_t kHealthQueueDepth = 1U;
constexpr UBaseType_t kSecurityQueueDepth = 8U;
// ESP-IDF task stack sizes are bytes. The qualified Xtensa owner entry frame
// alone is 23456 bytes; recovery/checkpoint calls need additional stack.
// tests/test_hub_runtime_stack.py checks the actual target frame budgets.
constexpr std::uint32_t kSecureOwnerStackBytes = 81920;

#if CONFIG_IDF_TARGET_ESP32S3 && !GS_HIL_BUILD
constexpr std::uint32_t kCloudSyncRefreshMs = 5000U;
constexpr std::uint32_t kCloudSyncWorkerDelayMs = 5000U;
constexpr std::uint32_t kCloudSyncWorkerStackBytes = 8192U;
#if !defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) || !GS40_TEST_ONLY_CLOUDSYNC_BUILD
constexpr char kWifiReconnectTaskTag[] = "gs58_wifi_reconnect";
constexpr std::uint32_t kWifiReconnectTaskStackBytes = 3072U;
constexpr std::uint32_t kWifiReconnectPollMs = 250U;
connectivity::WifiReconnectPolicy g_wifi_reconnect_policy;
portMUX_TYPE g_wifi_reconnect_mux = portMUX_INITIALIZER_UNLOCKED;

std::uint64_t monotonic_ms_u64() {
    const auto elapsed = esp_timer_get_time();
    return elapsed <= 0 ? 0U : static_cast<std::uint64_t>(elapsed / 1000);
}

void station_event_handler(void*, esp_event_base_t event_base,
                           std::int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_CONNECTED) {
        const auto* connected = static_cast<const wifi_event_sta_connected_t*>(event_data);
        if (connected == nullptr ||
            !gs::connectivity::IndiaWifiProfileV1::allows_channel(connected->channel)) {
            ESP_LOGE(kTag, "WIFI_RADIO_UNSUPPORTED channel=%u profile=IN-V1",
                     connected == nullptr ? 0U :
                         static_cast<unsigned>(connected->channel));
            (void)esp_wifi_disconnect();
            return;
        }
        ESP_LOGI(kTag, "WIFI_RADIO_CHANNEL channel=%u profile=IN-V1",
                 static_cast<unsigned>(connected->channel));
    }
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        portENTER_CRITICAL(&g_wifi_reconnect_mux);
        g_wifi_reconnect_policy.on_disconnected(monotonic_ms_u64());
        portEXIT_CRITICAL(&g_wifi_reconnect_mux);
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        portENTER_CRITICAL(&g_wifi_reconnect_mux);
        g_wifi_reconnect_policy.on_connected();
        portEXIT_CRITICAL(&g_wifi_reconnect_mux);
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_LOST_IP) {
        portENTER_CRITICAL(&g_wifi_reconnect_mux);
        g_wifi_reconnect_policy.on_disconnected(monotonic_ms_u64());
        portEXIT_CRITICAL(&g_wifi_reconnect_mux);
    }
}

void wifi_reconnect_task(void*) {
    for (;;) {
        const auto now_ms = monotonic_ms_u64();
        portENTER_CRITICAL(&g_wifi_reconnect_mux);
        const bool attempt_due = g_wifi_reconnect_policy.take_due_attempt(now_ms);
        portEXIT_CRITICAL(&g_wifi_reconnect_mux);
        if (attempt_due) {
            const auto result = esp_wifi_connect();
            if (result != ESP_OK) {
                portENTER_CRITICAL(&g_wifi_reconnect_mux);
                g_wifi_reconnect_policy.on_attempt_failed(monotonic_ms_u64());
                portEXIT_CRITICAL(&g_wifi_reconnect_mux);
                ESP_LOGW(kTag, "Wi-Fi reconnect request failed: %s",
                         esp_err_to_name(result));
            }
        }
        vTaskDelay(pdMS_TO_TICKS(kWifiReconnectPollMs));
    }
}
#endif

class S3CloudRuntimeAuthorityProvider final : public CloudRuntimeAuthorityProvider {
public:
    S3CloudRuntimeAuthorityProvider(HubSecurityLink& security_link, HubRuntime& runtime,
                                    S3CloudTrustProvisioning& trust)
        : security_link_(security_link), runtime_(runtime), trust_(trust) {}

    bool current_binding(CloudAuthorityBinding& binding) override {
        return !security_link_.faulted() && trust_.current_binding(binding) &&
            !binding.home_id.empty() && !binding.hub_device_id.empty() &&
            binding.ownership_epoch != 0;
    }

    bool original_event_owned(const DomainEvent& event,
                              const CloudAuthorityBinding& binding) override {
        CloudAuthorityBinding current;
        transport::RetirementEnrollmentBinding enrollment{};
        std::uint32_t generation = 0;
        return current_binding(current) && current == binding &&
            security_link_.resolve_enrollment_binding(event.key.physical_device_id,
                event.key.source_id, enrollment) &&
            runtime_.cloud_event_enrollment_generation(event, generation) &&
            generation == enrollment.generation;
    }

    bool trusted_hub_time(Milliseconds monotonic_ms,
                          TrustedHubTimeSnapshot& time) override {
        return !security_link_.faulted() &&
            trust_.trusted_hub_time(monotonic_ms, time) && time.trusted &&
            time.monotonic_ms == monotonic_ms && time.boot_generation != 0 &&
            time.utc_now > 0;
    }

    bool active_nodes(const CloudAuthorityBinding& binding,
                      std::vector<CloudNodeEnrollment>& nodes) override {
        CloudAuthorityBinding current;
        if (security_link_.faulted() || !current_binding(current) ||
            !(current == binding)) return false;
        nodes.clear();
        nodes.reserve(HubSecurityLink::kInstalledCapacity);
        for (const auto& mac : security_link_.enrolled_macs()) {
            const auto* node = security_link_.ready_node(mac);
            if (node == nullptr || node->last_session == 0 ||
                !runtime_.node_profile_known(node->logical_id)) continue;
            transport::RetirementEnrollmentBinding enrollment{};
            if (!security_link_.resolve_enrollment_binding(node->device_id,
                    node->logical_id, enrollment)) continue;
            const auto profile = deployment::for_device(node->device_id);
            const auto runtime_lease = runtime_.node_offline_timeout_seconds(
                node->logical_id);
            if (!profile || !runtime_lease ||
                *runtime_lease != profile->offline_seconds) continue;
            std::string profile_id;
            if (profile->heartbeat_seconds == 300 && profile->offline_seconds == 910)
                profile_id = "configured";
            else if (profile->heartbeat_seconds == 60 && profile->offline_seconds == 190)
                profile_id = "legacy_60";
            else if (profile->heartbeat_seconds == 120 && profile->offline_seconds == 310)
                profile_id = "legacy_120";
            else continue;
            nodes.push_back({node->device_id, node->logical_id,
                enrollment.generation, node->last_session, std::move(profile_id),
                profile->heartbeat_seconds, profile->offline_seconds});
            if (nodes.size() > HubSecurityLink::kInstalledCapacity) return false;
        }
        return true;
    }
private:
    HubSecurityLink& security_link_;
    HubRuntime& runtime_;
    S3CloudTrustProvisioning& trust_;
};

struct CloudSyncTaskContext { CloudSyncWorker* worker{nullptr}; };

#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
class Gs40TestOnlyMonotonicClock final : public S3HubMonotonicClock {
public:
    Milliseconds now_ms() const override {
        return static_cast<Milliseconds>(esp_timer_get_time() / 1000);
    }
};

std::unique_ptr<Gs40TestOnlyRuntimeConfig> g_gs40_test_config;
std::unique_ptr<Gs40TestOnlyMonotonicClock> g_gs40_test_clock;
std::unique_ptr<NvsAuthenticatedTimeFloorStore> g_gs40_test_floor;
std::unique_ptr<Rsa3072Sha256TimeProofVerifier> g_gs40_test_time_verifier;
std::unique_ptr<S3AuthenticatedTimeRandomSource> g_gs40_test_random;
std::unique_ptr<AuthenticatedHubTimeProvider> g_gs40_test_time;
std::unique_ptr<Gs40TestOnlyMaterialSource> g_gs40_test_material;
std::unique_ptr<Gs40TestOnlyAuthorityLeaseVerifier> g_gs40_test_authority_verifier;

struct CloudAuthorityRefreshContext {
    Gs40TestOnlyMaterialSource* material{nullptr};
    AuthenticatedHubTimeProvider* time{nullptr};
    const S3HubMonotonicClock* clock{nullptr};
    AuthenticatedTimeRandomSource* random{nullptr};
    HttpsBackendChannel* channel{nullptr};
    Gs40TestOnlyAuthorityLeaseVerifier* verifier{nullptr};
    S3CloudTrustProvisioning* trust{nullptr};
    QueueHandle_t policy_queue{nullptr};
    QueueHandle_t acknowledgement_queue{nullptr};
};

struct Gs40TestOnlyConfigurationAck {
    std::uint32_t version{0};
    CloudAuthorityBinding authority;
};

void cloud_authority_refresh_task(void* opaque) {
    auto& context = *static_cast<CloudAuthorityRefreshContext*>(opaque);
    for (;;) {
        const bool refreshed =
            gs40_test_only_refresh_time(context.material->config(), *context.time) == ESP_OK &&
            gs40_test_only_refresh_authority(*context.material, *context.time,
                *context.clock, *context.random, *context.channel, *context.verifier);
        if (!refreshed) {
            context.material->invalidate();
            ESP_LOGE(kTag, "TEST_ONLY time/authority refresh failed; publication fenced");
        } else if (context.trust != nullptr && context.policy_queue != nullptr &&
                   context.acknowledgement_queue != nullptr) {
            CloudAuthorityBinding current;
            if (context.trust->current_binding(current)) {
                Gs40TestOnlyConfigurationAck* ack = nullptr;
                while (xQueueReceive(context.acknowledgement_queue, &ack, 0) == pdTRUE) {
                    std::unique_ptr<Gs40TestOnlyConfigurationAck> owned_ack(ack);
                    if (owned_ack && owned_ack->authority == current &&
                        !gs40_test_only_ack_household_config(
                            context.material->config(), current, owned_ack->version,
                            *context.channel)) {
                        ESP_LOGW(kTag, "TEST_ONLY applied-config acknowledgement remains pending");
                    }
                    ack = nullptr;
                }
                auto policy = std::make_unique<Gs40TestOnlyHouseholdPolicy>();
                const auto fetched = gs40_test_only_fetch_household_config(
                    context.material->config(), current, *context.channel, *policy);
                if (fetched == Gs40TestOnlyConfigSyncResult::PolicyReady) {
                    auto* pending = policy.release();
                    if (xQueueSend(context.policy_queue, &pending, 0) != pdTRUE) {
                        delete pending;
                        ESP_LOGW(kTag, "TEST_ONLY desired config queue full; will retry");
                    }
                } else if (fetched == Gs40TestOnlyConfigSyncResult::Rejected) {
                    ESP_LOGW(kTag, "TEST_ONLY desired config rejected; last checkpoint remains active");
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(15000));
    }
}
#endif

bool cloud_route_available() {
    wifi_ap_record_t ap{};
    // Association and a local route permit a CloudSync attempt; they do not
    // establish Internet, cloud authentication, COMMITTED, or monitoring.
    if (esp_wifi_sta_get_ap_info(&ap) != ESP_OK ||
        !gs::connectivity::IndiaWifiProfileV1::allows_channel(ap.primary)) return false;
    auto* netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    if (netif == nullptr) return false;
    esp_netif_ip_info_t address{};
    return esp_netif_get_ip_info(netif, &address) == ESP_OK &&
        address.ip.addr != 0 && address.gw.addr != 0;
}

void cloud_node_health_task(void* opaque) {
    auto& context = *static_cast<CloudSyncTaskContext*>(opaque);
    if (context.worker == nullptr) {
        vTaskDelete(nullptr);
        return;
    }
    for (;;) {
        const auto now_ms = static_cast<Milliseconds>(esp_timer_get_time() / 1000);
        const bool route_available = cloud_route_available();
        // Durable Node events retain first priority. Current-state health and
        // Hub-owned derived decisions use their existing bounded channels
        // after the durable event batch has had its turn.
        const auto events = context.worker->run_once(route_available, now_ms, 4, false);
        if (events.state == CloudWorkerState::AuthorityChanged)
            ESP_LOGE(kTag, "Cloud event worker stopped after Hub/Home/epoch authority change");
        const auto result = context.worker->run_node_health_once(route_available, now_ms);
        if (result.state == CloudWorkerState::AuthorityChanged)
            ESP_LOGE(kTag, "Cloud NodeHealth stopped after Hub/Home/epoch authority change");
        const auto decisions = context.worker->run_hub_rule_decision_once(
            route_available, now_ms, 2);
        if (decisions.state == CloudWorkerState::AuthorityChanged)
            ESP_LOGE(kTag, "Hub rule publication stopped after authority change");
        vTaskDelay(pdMS_TO_TICKS(kCloudSyncWorkerDelayMs));
    }
}
#endif

#if CONFIG_IDF_TARGET_ESP32S3
struct OutboxNodeRetirementContext {
    HubSecurityLink* security_link{nullptr};
    const durable::RetirementSnapshot* snapshot{nullptr};
    HubRuntime* runtime{nullptr};
    storage::DurableEventOutbox* outbox{nullptr};
    std::uint32_t epoch{0};
    durable::ReportSnapshotReference reference{};
};

bool outbox_retirement_authority_current(void* opaque) {
    const auto& context = *static_cast<OutboxNodeRetirementContext*>(opaque);
    return context.runtime && context.outbox && context.runtime->durable_admission_open() &&
        context.outbox->replay_fence_matches(context.epoch, context.reference);
}

bool outbox_event_retired_by_node_report(void* opaque, std::uint64_t,
        const std::string& canonical_key, const security::Bytes& payload) {
    auto& context = *static_cast<OutboxNodeRetirementContext*>(opaque);
    if (context.security_link == nullptr || context.snapshot == nullptr) return false;
    DomainEvent event;
    if (!HubJournal::decode_event_payload(payload, event) ||
        event.key.str() != canonical_key || event.key.physical_device_id.empty()) return false;
    transport::RetirementEnrollmentBinding binding;
    if (!context.security_link->resolve_enrollment_binding(event.key.physical_device_id,
            event.key.source_id, binding)) return false;
    if (context.runtime == nullptr ||
        context.runtime->identity_retirement_eligibility(event, binding.slot,
            binding.generation, binding.digest) !=
                IdentityRetirementEligibility::EligibleWithDurableReplayFence) return false;
    return durable::retirement_proves_node_durable_retirement(
        *context.snapshot, binding.slot, binding.generation,
        event.key.session_id, event.key.sequence);
}
#endif

#if !CONFIG_IDF_TARGET_ESP32S3
durable::DurableJournalSlotStore::EnrollmentOwnerResolver registry_owner_resolver(
        HubSecurityLink& security_link) {
    return [&security_link](const std::string& physical_device_id,
            const std::string& claimed_logical_id,
            durable::DurableJournalSlotStore::EnrollmentOwner& owner) {
        transport::RetirementEnrollmentBinding binding;
        if (!security_link.resolve_enrollment_binding(physical_device_id,
                claimed_logical_id, binding)) return false;
        owner.slot = binding.slot;
        owner.generation = binding.generation;
        owner.owner_digest = binding.digest;
        return true;
    };
}
#endif

StaticQueue_t g_data_queue_state{};
StaticQueue_t g_control_queue_state{};
StaticQueue_t g_health_queue_state{};
StaticQueue_t g_security_queue_state{};
StaticQueue_t g_request_queue_state{};
#if !GS_HIL_BUILD
struct ReplacementRequest {
    std::string old_device_id;
    HubSecurityLink::ExpectedNode replacement;
};
StaticQueue_t g_removal_queue_state{};
alignas(std::string*) std::array<std::uint8_t, sizeof(std::string*)> g_removal_storage{};
QueueHandle_t g_removal_queue = nullptr;
StaticQueue_t g_replacement_queue_state{};
alignas(ReplacementRequest*) std::array<std::uint8_t, sizeof(ReplacementRequest*)> g_replacement_storage{};
QueueHandle_t g_replacement_queue = nullptr;
StaticQueue_t g_fota_command_queue_state{};
StaticQueue_t g_fota_result_queue_state{};
StaticQueue_t g_fota_ack_queue_state{};
alignas(FotaOwnerCommand*) std::array<std::uint8_t, sizeof(FotaOwnerCommand*)> g_fota_command_storage{};
alignas(FotaOwnerResult) std::array<std::uint8_t, sizeof(FotaOwnerResult)> g_fota_result_storage{};
alignas(FotaOwnerAck) std::array<std::uint8_t, sizeof(FotaOwnerAck)> g_fota_ack_storage{};
QueueHandle_t g_fota_command_queue = nullptr;
QueueHandle_t g_fota_result_queue = nullptr;
QueueHandle_t g_fota_ack_queue = nullptr;
std::atomic<std::uint32_t> g_fota_command_id{1};
#endif
StaticQueue_t g_security_send_queue_state{};
alignas(ReceivedFrame) std::array<std::uint8_t, kDataQueueDepth * sizeof(ReceivedFrame)> g_data_storage{};
alignas(ReceivedFrame) std::array<std::uint8_t, kControlQueueDepth * sizeof(ReceivedFrame)> g_control_storage{};
alignas(ReceivedFrame) std::array<std::uint8_t, kHealthQueueDepth * sizeof(ReceivedFrame)> g_health_storage{};
alignas(ReceivedFrame) std::array<std::uint8_t, kSecurityQueueDepth * sizeof(ReceivedFrame)> g_security_storage{};
alignas(HubSecurityLink::ExpectedNode*) std::array<std::uint8_t, sizeof(HubSecurityLink::ExpectedNode*)> g_request_storage{};
alignas(bool) std::array<std::uint8_t, sizeof(bool)> g_security_send_storage{};
QueueHandle_t g_data_queue = nullptr;
QueueHandle_t g_control_queue = nullptr;
QueueHandle_t g_health_queue = nullptr;
QueueHandle_t g_security_queue = nullptr;
QueueHandle_t g_request_queue = nullptr;
QueueHandle_t g_security_send_queue = nullptr;
FixtureCommissioningState g_fixture_commissioning_state{};
std::atomic<std::uint32_t> g_data_queue_drops{0};
std::atomic<std::uint32_t> g_control_queue_drops{0};
std::atomic<bool> g_control_plane_active{false};
#if GS_HIL_CONTROL
std::atomic<bool> g_hil_logical_online{true};
std::atomic<bool> g_hil_reboot_after_commit{false};
std::atomic<std::uint32_t> g_hil_processed{0};
std::atomic<std::uint32_t> g_hil_durable_ack{0};
std::atomic<std::uint32_t> g_hil_health_received{0};
#endif

#if GS_HIL_CONTROL
bool from_qualified_node(const std::uint8_t* mac) {
    return mac != nullptr &&
           std::memcmp(mac, kQualifiedNodeMac.data(), kQualifiedNodeMac.size()) == 0;
}
#endif

void receive_callback(const esp_now_recv_info_t* info, const std::uint8_t* data,
                      int length) {
#if GS_HIL_CONTROL
    if (!g_hil_logical_online.load(std::memory_order_acquire)) return;
#endif
    if (info == nullptr || data == nullptr ||
        length <= 0 || static_cast<std::size_t>(length) > kTargetEspNowPayloadMax) {
        return;
    }
#if GS_HIL_CONTROL
    if (!from_qualified_node(info->src_addr)) return;
#endif

#if GS_HIL_BUILD
    const auto frame_class = transport::classify_frame(data, static_cast<std::size_t>(length));
#endif
    QueueHandle_t destination = nullptr;
    if (length >= 3 && data[0] == 0x47 && data[1] == 0x53 && data[2] == 1) {
        destination = g_security_queue;
    } else if (length >= 3 && data[0] == 0x47 && data[1] == 0x53 && data[2] == 2) {
        destination = g_data_queue;
    }
#if GS_HIL_BUILD
    else if (frame_class == transport::FrameClass::NodeMessage &&
        static_cast<std::size_t>(length) <= transport::kMaxFrameBytes) {
        destination = g_data_queue;
    }
    else if (frame_class == transport::FrameClass::ControlFota) {
        destination = g_control_queue;
    }
    else if (frame_class == transport::FrameClass::NodeHealth &&
               static_cast<std::size_t>(length) <= transport::kMaxFrameBytes) {
        destination = g_health_queue;
    }
#endif
    else {
        return;
    }
    if (destination == nullptr) return;

    ReceivedFrame envelope;
    std::memcpy(envelope.source_mac.data(), info->src_addr, envelope.source_mac.size());
    envelope.size = static_cast<std::uint16_t>(length);
    if (info->rx_ctrl != nullptr) {
        envelope.transport_rssi = info->rx_ctrl->rssi;
        envelope.channel = info->rx_ctrl->channel;
    }
    std::memcpy(envelope.bytes.data(), data, envelope.size);
    if (destination == g_health_queue) {
        // Depth one deliberately keeps only the latest best-effort snapshot.
        (void)xQueueOverwrite(destination, &envelope);
    } else if (xQueueSend(destination, &envelope, 0) != pdTRUE) {
        // No durable ACK is emitted, so dropped data remains retained and is
        // retried. The owner reports the counter outside callback context.
        if (destination == g_data_queue) {
            g_data_queue_drops.fetch_add(1U, std::memory_order_relaxed);
        } else {
            g_control_queue_drops.fetch_add(1U, std::memory_order_relaxed);
        }
    }
}

#if ESP_IDF_VERSION_MAJOR >= 6
void send_callback(const esp_now_send_info_t*, esp_now_send_status_t status) {
#else
void send_callback(const std::uint8_t*, esp_now_send_status_t status) {
#endif
    if (g_security_send_queue != nullptr) {
        const bool delivered = status == ESP_NOW_SEND_SUCCESS;
        (void)xQueueOverwrite(g_security_send_queue, &delivered);
    }
}

const char* ack_reason(const ProcessResult& result) {
    switch (result.ack) {
        case AckClass::Durable:
            return result.state_changed ? "journal_committed" : "already_committed";
        case AckClass::ReceivedVolatile: return "received_volatile";
        case AckClass::DiscardedPolicy: return "discarded_policy";
        case AckClass::Rejected: return "journal_rejected";
    }
    return "unknown";
}

esp_err_t initialize_wifi() {
    esp_err_t result = esp_netif_init();
    if (result != ESP_OK && result != ESP_ERR_INVALID_STATE) return result;
    result = esp_event_loop_create_default();
    if (result != ESP_OK && result != ESP_ERR_INVALID_STATE) return result;
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    if (esp_netif_get_handle_from_ifkey("WIFI_STA_DEF") == nullptr &&
        esp_netif_create_default_wifi_sta() == nullptr) return ESP_ERR_NO_MEM;
#endif
    const wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT();
    if ((result = esp_wifi_init(&config)) != ESP_OK) return result;
    if ((result = esp_wifi_set_storage(WIFI_STORAGE_RAM)) != ESP_OK) return result;
#if CONFIG_IDF_TARGET_ESP32S3
    if ((result = gs::connectivity::configure_india_wifi_country()) != ESP_OK) {
        ESP_LOGE(kTag, "India Wi-Fi regulatory profile activation failed: %s",
                 esp_err_to_name(result));
        return result;
    }
#endif
    if ((result = esp_wifi_set_mode(WIFI_MODE_STA)) != ESP_OK) return result;
#if CONFIG_IDF_TARGET_ESP32S3 && \
    (!defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) || !GS40_TEST_ONLY_CLOUDSYNC_BUILD)
    if ((result = esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
            station_event_handler, nullptr)) != ESP_OK) return result;
    if ((result = esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
            station_event_handler, nullptr)) != ESP_OK) return result;
    if ((result = esp_event_handler_register(IP_EVENT, IP_EVENT_STA_LOST_IP,
            station_event_handler, nullptr)) != ESP_OK) return result;
#endif
    if ((result = esp_wifi_start()) != ESP_OK) return result;
    if ((result = esp_wifi_set_ps(WIFI_PS_NONE)) != ESP_OK) return result;
    if ((result = esp_wifi_set_channel(
            gs::connectivity::IndiaWifiProfileV1::first_2ghz_channel,
            WIFI_SECOND_CHAN_NONE)) != ESP_OK) return result;

    std::array<std::uint8_t, 6> actual_mac{};
    if ((result = esp_wifi_get_mac(WIFI_IF_STA, actual_mac.data())) != ESP_OK) return result;
#if CONFIG_IDF_TARGET_ESP32S3 && \
    (!defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) || !GS40_TEST_ONLY_CLOUDSYNC_BUILD)
    if (xTaskCreate(wifi_reconnect_task, kWifiReconnectTaskTag,
            kWifiReconnectTaskStackBytes, nullptr, 3, nullptr) != pdPASS)
        return ESP_ERR_NO_MEM;
#endif
#if GS_HIL_BUILD
    if (actual_mac != kQualifiedHubMac) {
        ESP_LOGE(kTag, "STA MAC does not match qualified Hub");
        return ESP_ERR_INVALID_STATE;
    }
#endif
    return ESP_OK;
}

esp_err_t initialize_esp_now() {
    esp_err_t result = esp_now_init();
    if (result != ESP_OK) return result;
    if ((result = esp_now_register_recv_cb(receive_callback)) != ESP_OK) return result;
    if ((result = esp_now_register_send_cb(send_callback)) != ESP_OK) return result;

#if GS_HIL_BUILD
    esp_now_peer_info_t peer{};
    std::memcpy(peer.peer_addr, kQualifiedNodeMac.data(), kQualifiedNodeMac.size());
    peer.channel = 0;
    peer.ifidx = WIFI_IF_STA;
    peer.encrypt = false;  // Production peer key management remains open.
    if (!esp_now_is_peer_exist(kQualifiedNodeMac.data())) {
        result = esp_now_add_peer(&peer);
    }
#endif
    return result;
}

#if GS_HIL_BUILD
void owner_task(void*) {
    HubRuntime runtime(32, 1024);
    std::uint64_t authorized_session = 0;
    std::uint8_t initial_channel = 0;
    wifi_second_chan_t initial_secondary_channel = WIFI_SECOND_CHAN_NONE;
    (void)esp_wifi_get_channel(&initial_channel, &initial_secondary_channel);
    ESP_LOGI(kTag, "HubRuntime owner started radio_channel=%u",
             static_cast<unsigned>(initial_channel));

    for (;;) {
        if (g_control_plane_active.load(std::memory_order_acquire)) {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        ReceivedFrame health_frame;
        if (xQueueReceive(g_health_queue, &health_frame, 0) == pdTRUE) {
            const auto health = transport::decode_node_health(
                health_frame.bytes.data(), health_frame.size);
            if (!health || health.value->node_id != kAuthorizedNodeId ||
                health_frame.source_mac != kQualifiedNodeMac) {
                ESP_LOGW(kTag, "Rejected malformed/unmapped NodeHealth error=%d RSSI=%d CH=%u",
                         static_cast<int>(health.error), health_frame.transport_rssi,
                         static_cast<unsigned>(health_frame.channel));
            } else {
                const NodeHealthSnapshot& value = *health.value;
#if GS_HIL_CONTROL
                g_hil_health_received.fetch_add(1U, std::memory_order_relaxed);
#endif
                ESP_LOGI(kTag,
                         "NodeHealth schema=%u session=%llu health_seq=%llu uptime_ms=%llu reset=%u pir_raw=%d pir_edges=%u pir_ok=%u pir_rejected=%u store_full=%u motion_drop=%u priority_rejected=%u sensing_live=%u runtime_live=%u retained=%u oldest_seq=%llu in_flight=%d tx=%u mac_ok=%u mac_fail=%u durable_ack=%u volatile_ack=%u retry=%u backoff=%u breadcrumb=%u error=%u heap=%u min_heap=%u maintenance=%d sleep_entries=%u timer_wakes=%u gpio_wakes=%u other_wakes=%u last_wake=%s requested_ms=%u elapsed_ms=%u RSSI=%d CH=%u",
                         static_cast<unsigned>(value.schema),
                         static_cast<unsigned long long>(value.session_id),
                         static_cast<unsigned long long>(value.health_sequence),
                         static_cast<unsigned long long>(value.uptime_ms),
                         static_cast<unsigned>(value.reset_reason), value.raw_pir_level,
                         static_cast<unsigned>(value.raw_pir_edges),
                         static_cast<unsigned>(value.accepted_pir),
                         static_cast<unsigned>(value.rejected_pir),
                         static_cast<unsigned>(value.store_full),
                         static_cast<unsigned>(value.dropped_motion),
                         static_cast<unsigned>(value.priority_rejected),
                         static_cast<unsigned>(value.sensing_liveness),
                         static_cast<unsigned>(value.runtime_liveness),
                         static_cast<unsigned>(value.retained_count),
                         static_cast<unsigned long long>(value.oldest_sequence),
                         value.radio_in_flight, static_cast<unsigned>(value.tx_attempts),
                         static_cast<unsigned>(value.mac_success),
                         static_cast<unsigned>(value.mac_failure),
                         static_cast<unsigned>(value.durable_acks),
                         static_cast<unsigned>(value.volatile_acks),
                         static_cast<unsigned>(value.retries),
                         static_cast<unsigned>(value.periodic_backoff_entries),
                         static_cast<unsigned>(value.last_breadcrumb),
                         static_cast<unsigned>(value.last_error),
                         static_cast<unsigned>(value.free_heap),
                         static_cast<unsigned>(value.minimum_free_heap),
                         value.maintenance_active,
                         static_cast<unsigned>(value.light_sleep_entry_count),
                         static_cast<unsigned>(value.timer_wake_count),
                         static_cast<unsigned>(value.gpio_wake_count),
                         static_cast<unsigned>(value.other_wake_count),
                         node_health_sleep_wake_cause_name(value.last_wake_cause),
                         static_cast<unsigned>(value.last_sleep_requested_ms),
                         static_cast<unsigned>(value.last_sleep_elapsed_ms),
                         health_frame.transport_rssi,
                         static_cast<unsigned>(health_frame.channel));
            }
        }
        ReceivedFrame frame;
        if (xQueueReceive(g_data_queue, &frame, pdMS_TO_TICKS(200)) != pdTRUE) {
            const auto data_drops = g_data_queue_drops.exchange(0U, std::memory_order_relaxed);
            const auto control_drops = g_control_queue_drops.exchange(0U, std::memory_order_relaxed);
            if (data_drops != 0U || control_drops != 0U) {
                ESP_LOGW(kTag, "Callback queue drops DATA=%u CONTROL=%u",
                         static_cast<unsigned>(data_drops),
                         static_cast<unsigned>(control_drops));
            }
            continue;
        }
        const auto decoded = transport::decode_node_message(frame.bytes.data(), frame.size);
        if (!decoded) {
            ESP_LOGW(kTag, "Rejected malformed NodeMessage error=%d RSSI=%d CH=%u",
                     static_cast<int>(decoded.error), frame.transport_rssi,
                     static_cast<unsigned>(frame.channel));
            continue;
        }
        const NodeMessage& message = *decoded.value;
        if (message.node_id != kAuthorizedNodeId ||
            frame.source_mac != kQualifiedNodeMac) {
            ESP_LOGW(kTag, "Rejected unmapped node identity");
            continue;
        }
        if (authorized_session == 0 || message.session_id > authorized_session) {
            authorized_session = message.session_id;
            runtime.authorize_node(message.node_id, authorized_session, true);
            ESP_LOGI(kTag, "Authorized boot session=%llu",
                     static_cast<unsigned long long>(authorized_session));
        } else if (message.session_id != authorized_session) {
            ESP_LOGW(kTag, "Rejected stale session=%llu active=%llu",
                     static_cast<unsigned long long>(message.session_id),
                     static_cast<unsigned long long>(authorized_session));
            continue;
        }

        // No trusted SNTP/epoch source exists in HW-M1.3 target composition.
        // Zero preserves the existing untrusted-time semantics without
        // fabricating wall-clock time. Transport RSSI stays diagnostic-only.
        constexpr EpochSeconds hub_received_at = 0;
        if (!runtime.radio_message_callback(message, hub_received_at)) {
            ESP_LOGW(kTag, "HubRuntime admission rejected session=%llu seq=%llu RSSI=%d CH=%u",
                     static_cast<unsigned long long>(message.session_id),
                     static_cast<unsigned long long>(message.sequence_number),
                     frame.transport_rssi, static_cast<unsigned>(frame.channel));
            continue;
        }
        const auto processed = runtime.run_state_once();
        if (!processed) {
            ESP_LOGW(kTag, "HubRuntime had no admitted event to process");
            continue;
        }

        const auto ack = make_node_ack(processed->key, processed->ack,
                                       hub_received_at, ack_reason(*processed));
        const auto encoded_ack = transport::encode_node_ack(ack);
        if (!encoded_ack) {
            ESP_LOGE(kTag, "NodeAck encode failed error=%d", static_cast<int>(encoded_ack.error));
            continue;
        }
        const esp_err_t sent = esp_now_send(frame.source_mac.data(),
                                            encoded_ack.frame.bytes.data(),
                                            encoded_ack.frame.size);
        ESP_LOGI(kTag,
                 "Processed session=%llu seq=%llu app_ack=%d ack_send=%s RSSI=%d CH=%u",
                 static_cast<unsigned long long>(processed->key.session_id),
                 static_cast<unsigned long long>(processed->key.sequence),
                 static_cast<int>(processed->ack), esp_err_to_name(sent),
                 frame.transport_rssi, static_cast<unsigned>(frame.channel));
#if GS_HIL_CONTROL
        g_hil_processed.fetch_add(1U, std::memory_order_relaxed);
        if (processed->ack == AckClass::Durable) {
            g_hil_durable_ack.fetch_add(1U, std::memory_order_relaxed);
        }
#endif
    }
}
#endif

#if !GS_HIL_BUILD
bool add_runtime_peer(const HubSecurityLink::Mac& mac) {
    if (esp_now_is_peer_exist(mac.data())) return true;
    esp_now_peer_info_t peer{};
    std::memcpy(peer.peer_addr, mac.data(), mac.size());
    peer.channel = 0;
    peer.ifidx = WIFI_IF_STA;
    // Runtime frames carry their own authenticated encryption. Native
    // encrypted-peer capacity is below the installed-node requirement.
    peer.encrypt = false;
    return esp_now_add_peer(&peer) == ESP_OK;
}

bool send_security_message(const HubSecurityLink::Outbound& outbound) {
    if (!add_runtime_peer(outbound.destination)) return false;
    std::vector<security::wire::Packet> packets;
    std::uint32_t transaction = esp_random();
    if (transaction == 0) transaction = 1;
    if (!security::wire::fragment(outbound.message, transaction, packets)) return false;
    for (const auto& packet : packets) {
        (void)xQueueReset(g_security_send_queue);
        if (esp_now_send(outbound.destination.data(), packet.bytes.data(),
                         packet.size) != ESP_OK) return false;
        bool delivered = false;
        if (xQueueReceive(g_security_send_queue, &delivered,
                          pdMS_TO_TICKS(1000)) != pdTRUE || !delivered) return false;
    }
    return true;
}

void secure_owner_task(void*) {
    ESP_LOGI(kTag, "GS40 config=%s heartbeat=%u offline=%u", deployment::sha256,
             deployment::policy.heartbeat_seconds, deployment::policy.offline_seconds);
    HubSecurityLink security_link;
    HubSecurityLink::Mac physical_mac{};
    if (esp_wifi_get_mac(WIFI_IF_STA, physical_mac.data()) != ESP_OK) {
        ESP_LOGE(kTag, "Hub security bootstrap failed closed");
        vTaskDelete(nullptr);
        return;
    }
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    if (!g_gs40_test_material ||
        !security_link.initialize(physical_mac,
            g_gs40_test_material->config().fixture_home_id)) {
#else
    if (!security_link.initialize(physical_mac)) {
#endif
        ESP_LOGE(kTag, "Hub security bootstrap failed closed");
        vTaskDelete(nullptr);
        return;
    }
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    if (!g_gs40_test_material ||
        !gs40_test_only_hub_id_matches_runtime(
            g_gs40_test_material->config().permanent_hub_id,
            security_link.hub_id())) {
        ESP_LOGE(kTag, "TEST_ONLY configured Hub identity does not match physical Hub; startup refused");
        vTaskDelete(nullptr);
        return;
    }
#endif
    for (const auto& mac : security_link.enrolled_macs()) {
        if (!add_runtime_peer(mac)) {
            ESP_LOGE(kTag, "Could not restore enrolled ESP-NOW peer");
            vTaskDelete(nullptr);
            return;
        }
    }
    // Recover the durable owner before constructing an event runtime. It owns
    // the authoritative epoch and both durable repositories for this task's
    // lifetime. No target global may retain references to these objects.
    NvsDurableBlobStore durable_blobs;
    NvsStoreInventory durable_inventory;
    if (!durable_blobs.initialize()) {
        ESP_LOGE(kTag, "Durable NVS provider initialization failed closed");
        vTaskDelete(nullptr);
        return;
    }
    security::Key32 durable_key{};
    auto& commissioning_crypto = security_link.commissioning_crypto();
    if (!security_link.durable_storage_key(durable_key)) {
        commissioning_crypto.secure_zero(durable_key.data(), durable_key.size());
        ESP_LOGE(kTag, "Durable storage key derivation failed closed");
        vTaskDelete(nullptr);
        return;
    }
    const auto owner_freshness = [&]() {
        switch (security_link.installation_freshness()) {
            case SecurityFreshness::FreshInstallation:
                return durable::InstallationFreshness::FreshInstallation;
            case SecurityFreshness::ExistingInstallation:
                return durable::InstallationFreshness::ExistingInstallation;
            case SecurityFreshness::Ambiguous:
                return durable::InstallationFreshness::Ambiguous;
        }
        return durable::InstallationFreshness::Ambiguous;
    }();
    durable::HubDurabilityOwner durability_owner(
        durable_blobs, durable_inventory, commissioning_crypto,
        durable_key, owner_freshness);
    commissioning_crypto.secure_zero(durable_key.data(), durable_key.size());
    std::array<std::uint8_t,32> activated_table_digest{};
    const bool registry_activated =
        security_link.authenticated_enrollment_table_digest(activated_table_digest);
    const auto durability_state = durability_owner.recover(
        registry_activated ? &activated_table_digest : nullptr);
    commissioning_crypto.secure_zero(activated_table_digest.data(),
                                     activated_table_digest.size());
    const bool migration_required =
        durability_state == durable::DurabilityOwnerState::MigrationRequired;
    if ((!migration_required && durability_state != durable::DurabilityOwnerState::Ready) ||
        (migration_required && !durability_owner.migration_epoch()) ||
        (!migration_required && (!durability_owner.epoch() || *durability_owner.epoch() == 0 ||
          durability_owner.durable_store() == nullptr ||
          durability_owner.retirement_repository() == nullptr))) {
        ESP_LOGE(kTag, "Durability owner unavailable state=%u error=%u; admission closed",
                 static_cast<unsigned>(durability_state),
                 static_cast<unsigned>(durability_owner.error()));
        vTaskDelete(nullptr);
        return;
    }

#if GS_HIL_CONTROL
    if (!migration_required) {
        const auto* state = durability_owner.recovery_state();
        ESP_LOGI(kTag, "HIL_DURABILITY owner=Ready epoch=%u generation=%llu native=%d migration=NONE",
                 *durability_owner.epoch(),
                 static_cast<unsigned long long>(state->checkpoint_generation),
                 state->checkpoint.fresh_registry_domain);
    }
#endif

    // Upgrade old e/c journal slots into the authenticated durable owner before
    // allowing the runtime to attach. Source slots stay present until the copy
    // has been checkpointed and verified.
    NvsJournalSlotStore legacy_store;
    if (migration_required) {
#if CONFIG_IDF_TARGET_ESP32S3
        // The S3 outbox has a separately versioned publication format. Never
        // report the old NVS migration complete while leaving those recovered
        // event bodies outside the active replay path.
        ESP_LOGE(kTag, "Legacy slot migration to S3 outbox is unsupported; admission closed");
        vTaskDelete(nullptr);
        return;
#else
        HubJournal legacy_journal(128);
        security::Key32 journal_key{};
        if (!security_link.event_journal_key(journal_key)) {
            ESP_LOGE(kTag, "Event journal key unavailable for migration; admission closed");
            vTaskDelete(nullptr);
            return;
        }
        durable::DurableJournalSlotStore migration_store(
            durability_owner, commissioning_crypto, journal_key,
            registry_owner_resolver(security_link));
        const bool legacy_ready = legacy_store.initialize() &&
            security_link.attach_event_journal(legacy_journal, legacy_store);
        commissioning_crypto.secure_zero(journal_key.data(), journal_key.size());
        if (!legacy_ready || !durable::migrate_legacy_journal(
                legacy_journal, legacy_store, migration_store) ||
            durability_owner.recover() != durable::DurabilityOwnerState::Ready) {
            ESP_LOGE(kTag, "Legacy Hub journal migration failed closed");
            vTaskDelete(nullptr);
            return;
        }
#endif
    }

    const auto authoritative_epoch = durability_owner.epoch();
    if (!authoritative_epoch || *authoritative_epoch == 0 ||
        durability_owner.durable_store() == nullptr ||
        durability_owner.retirement_repository() == nullptr) {
        ESP_LOGE(kTag, "Durability owner not Ready after migration; admission closed");
        vTaskDelete(nullptr);
        return;
    }

    security::Key32 journal_key{};
    if (!security_link.event_journal_key(journal_key)) {
        ESP_LOGE(kTag, "Event journal key unavailable; admission closed");
        vTaskDelete(nullptr);
        return;
    }
#if CONFIG_IDF_TARGET_ESP32S3
    // Explicit S3 backend selection. Mount never formats and a missing
    // gs_outbox partition is fatal; this source path has no volatile/NVS
    // fallback that could issue a false Durable ACK.
    storage::s3::LittleFsSegmentStore outbox_storage;
    if (!outbox_storage.mount()) {
        commissioning_crypto.secure_zero(journal_key.data(), journal_key.size());
        ESP_LOGE(kTag, "gs_outbox LittleFS partition unavailable; admission closed");
        vTaskDelete(nullptr);
        return;
    }
    storage::OutboxLimits limits;
    // 2 MiB bodies + 1 MiB identities + 512 KiB completions + 128 KiB
    // checkpoint COW + 384 KiB filesystem overhead in the 4 MiB candidate.
    limits.segment_bytes=128U*1024U;
#if defined(CONFIG_GS_OUTBOX_BODY_RETIREMENT_ENABLED) && \
    CONFIG_GS_OUTBOX_BODY_RETIREMENT_ENABLED
    limits.body_retirement_enabled = true;
#endif
    storage::RuntimeStateStore runtime_state(outbox_storage,commissioning_crypto,journal_key);
    storage::DurableEventOutbox durable_outbox(
        outbox_storage, commissioning_crypto, journal_key,limits);
    commissioning_crypto.secure_zero(journal_key.data(), journal_key.size());
    storage::OutboxJournalBackend event_backend(durable_outbox);
    HubRuntime runtime(32, 0);
    runtime.bind_runtime_state(runtime_state);
    runtime.bind_durability_owner(durability_owner);
    const auto resolve_initial_owner=[](void* context,const DomainEvent& event,
            storage::IdentityOwnerEvidence& owner) {
        auto& link=*static_cast<HubSecurityLink*>(context);
        transport::RetirementEnrollmentBinding binding;
        if (!link.resolve_enrollment_binding(event.key.physical_device_id,
                event.key.source_id,binding)) return false;
        owner.enrollment_slot=binding.slot;
        owner.enrollment_generation=binding.generation;
        owner.binding_digest=binding.digest;
        return true;
    };
    if (!runtime.recover_native_outbox(durable_outbox,resolve_initial_owner,&security_link) ||
        !runtime.journal().attach_backend(event_backend)) {
        ESP_LOGE(kTag, "S3 authenticated native event recovery failed; admission closed");
        vTaskDelete(nullptr);
        return;
    }
#else
    durable::DurableJournalSlotStore journal_store(
        durability_owner, commissioning_crypto, journal_key,
        registry_owner_resolver(security_link));
    commissioning_crypto.secure_zero(journal_key.data(), journal_key.size());
    HubRuntime runtime(32, 128);
#endif
    runtime.bind_durability_owner(durability_owner);
#if !CONFIG_IDF_TARGET_ESP32S3
    // Admission is still closed; let the lower-priority idle task run between
    // complete authenticated slot reads. taskYIELD alone cannot release CPU1
    // to IDLE1 while this higher-priority owner remains ready.
    const bool journal_attached = security_link.attach_event_journal(
        runtime.journal(), journal_store, [] { vTaskDelay(1); });
#else
    const bool journal_attached = runtime.journal().persistent();
#endif
    if (!journal_attached) {
        ESP_LOGE(kTag, "Hub durable event store unavailable; refusing event admission");
        vTaskDelete(nullptr);
        return;
    }
#if CONFIG_IDF_TARGET_ESP32S3
    // Reconcile the selected NVS retirement bank into the authenticated
    // LittleFS lifecycle root before any event admission can open.
    {
        auto* report_repository = durability_owner.retirement_repository();
        auto* durable_store = durability_owner.durable_store();
        const auto* recovered = durability_owner.recovery_state();
        if (recovered != nullptr && recovered->checkpoint.report_snapshot) {
            const auto reconciliation = report_repository == nullptr || durable_store == nullptr
                ? ReplayFenceReconcileResult{ReplayFenceReconcileStage::DependenciesUnavailable}
                : runtime.reconcile_selected_replay_fence(*recovered,
                    *report_repository, runtime_state, *authoritative_epoch,
                    durable_outbox);
            if (!reconciliation.succeeded()) {
                const char* result = "RECONCILIATION_FAILED";
                if (reconciliation.stage == ReplayFenceReconcileStage::OutboxPublication)
                    result = storage::replay_fence_publish_result_name(reconciliation.publication);
                else if (reconciliation.stage == ReplayFenceReconcileStage::RuntimeBinding)
                    result = hub::replay_fence_bind_result_name(reconciliation.binding);
                else if (reconciliation.stage == ReplayFenceReconcileStage::SnapshotReferenceMissing)
                    result = "SELECTED_REFERENCE_MISSING";
                else if (reconciliation.stage == ReplayFenceReconcileStage::SnapshotReload)
                    result = "SNAPSHOT_READ_OR_AUTHENTICATION_FAILED";
                else if (reconciliation.stage == ReplayFenceReconcileStage::ReducerCheckpointReload)
                    result = "REDUCER_CHECKPOINT_READ_OR_AUTHENTICATION_FAILED";
                else if (reconciliation.stage == ReplayFenceReconcileStage::ReducerCheckpointMissing)
                    result = "REDUCER_CHECKPOINT_MISSING";
                else if (reconciliation.stage == ReplayFenceReconcileStage::DependenciesUnavailable)
                    result = "RETIREMENT_STORAGE_OWNER_UNAVAILABLE";
                ESP_LOGE(kTag,
                    "S3 replay fence failed stage=%s result=%s path=BOOT admission=CLOSED report_ack=NONE",
                    replay_fence_reconcile_stage_id(reconciliation.stage), result);
                vTaskDelete(nullptr);
                return;
            }
        }
    }
#endif
    // Compacted identity generations require the recovered owner fence during
    // replay. Bind it before restoring; admission remains closed on any failure.
    if (!runtime.restore_from_journal()) {
        ESP_LOGE(kTag, "Hub durable event replay unavailable; refusing event admission");
        vTaskDelete(nullptr);
        return;
    }
#if GS_HIL_CONTROL
    ESP_LOGI(kTag, "HIL_JOURNAL_RECOVERED records=%u", static_cast<unsigned>(runtime.journal().size()));
#endif

#if CONFIG_IDF_TARGET_ESP32S3
    // Separate the owner-thread capture from HTTPS I/O. Until GS-109 supplies
    // an approved permanent Hub/Home/epoch and trusted-time provider, the
    // runtime authority and TLS identity adapters below remain fail closed.
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    if (!g_gs40_test_material || !g_gs40_test_time || !g_gs40_test_clock ||
        !g_gs40_test_random || !g_gs40_test_authority_verifier) {
        ESP_LOGE(kTag, "TEST_ONLY bootstrap state unavailable; CloudSync stays fail closed");
        vTaskDelete(nullptr);
        return;
    }
    Gs40TestOnlyMaterialSource* test_material = g_gs40_test_material.get();
    Gs40TestOnlyMonotonicClock* test_clock = g_gs40_test_clock.get();
    AuthenticatedHubTimeProvider* test_time = g_gs40_test_time.get();
    S3AuthenticatedTimeRandomSource* test_random = g_gs40_test_random.get();
    Gs40TestOnlyAuthorityLeaseVerifier* test_lease_verifier = g_gs40_test_authority_verifier.get();
    Gs40TestOnlyCloudComposition cloud_composition(*test_material, *test_time, *test_clock);
    auto& bootstrap_channel = cloud_composition.bootstrap_channel;
    QueueHandle_t config_policy_queue = xQueueCreate(
        1, sizeof(Gs40TestOnlyHouseholdPolicy*));
    QueueHandle_t config_acknowledgement_queue = xQueueCreate(
        4, sizeof(Gs40TestOnlyConfigurationAck*));
    if (config_policy_queue == nullptr || config_acknowledgement_queue == nullptr) {
        if (config_policy_queue != nullptr) vQueueDelete(config_policy_queue);
        if (config_acknowledgement_queue != nullptr) vQueueDelete(config_acknowledgement_queue);
        ESP_LOGE(kTag, "TEST_ONLY household configuration queues unavailable; owner remains closed");
        vTaskDelete(nullptr);
        return;
    }
    CloudAuthorityRefreshContext refresh_context{test_material, test_time,
        test_clock, test_random, &bootstrap_channel, test_lease_verifier,
        &cloud_composition.trust, config_policy_queue, config_acknowledgement_queue};
    if (!gs40_test_only_refresh_authority(*test_material, *test_time, *test_clock,
            *test_random, bootstrap_channel, *test_lease_verifier)) {
        ESP_LOGE(kTag, "TEST_ONLY authority bootstrap unavailable; publication remains fenced");
    }
    auto& cloud_trust = cloud_composition.trust;
#else
    UnprovisionedS3CloudTrust cloud_trust;
#endif
    S3CloudRuntimeAuthorityProvider cloud_authority(
        security_link, runtime, cloud_trust);
    CloudRuntimeAuthoritySource cloud_authority_source(cloud_authority);
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    auto& cloud_channel = cloud_composition.cloud_channel;
    bool test_activity_home_ready = false;
    CloudAuthorityBinding initial_rule_binding;
    if (cloud_trust.current_binding(initial_rule_binding)) {
        const auto configuration_sync = gs40_test_only_sync_household_config(
            test_material->config(), initial_rule_binding, runtime, cloud_channel);
        test_activity_home_ready =
            configuration_sync == Gs40TestOnlyConfigSyncResult::Applied ||
            configuration_sync == Gs40TestOnlyConfigSyncResult::AppliedAckPending;
        if (!test_activity_home_ready &&
            runtime.has_home_activity_configuration(initial_rule_binding)) {
            // An authenticated configuration already in the checkpoint is the
            // last valid policy. A temporary backend or acknowledgement outage
            // cannot replace it with the signed bootstrap default.
            test_activity_home_ready = true;
        } else if (!test_activity_home_ready &&
                   (configuration_sync == Gs40TestOnlyConfigSyncResult::Unavailable ||
                    configuration_sync == Gs40TestOnlyConfigSyncResult::NoDesired) &&
                   gs40_test_only_apply_activity_home(test_material->config(),
                                                       initial_rule_binding, runtime)) {
            test_activity_home_ready = true;
        }
        if (configuration_sync == Gs40TestOnlyConfigSyncResult::Rejected)
            ESP_LOGE(kTag, "TEST_ONLY desired household policy rejected; last valid checkpoint preserved");
        if (test_activity_home_ready) {
        TrustedHubTimeSnapshot initial_time;
        const auto initial_now_ms = static_cast<Milliseconds>(esp_timer_get_time() / 1000);
        std::uint16_t initial_local_minute = 0;
        if (cloud_trust.trusted_hub_time(initial_now_ms, initial_time) &&
            initial_time.trusted && initial_time.monotonic_ms == initial_now_ms &&
            initial_time.boot_generation != 0 && initial_time.utc_now > 0 &&
            gs40_test_only_local_minute(test_material->config(), runtime,
                                        initial_time.utc_now, initial_local_minute) &&
            !runtime.activity_state().monitoring_started_at) {
            runtime.start_activity_monitor(initial_time.utc_now);
            if (!runtime.durable_admission_open()) test_activity_home_ready = false;
        }
        }
    }
    if (!test_activity_home_ready)
        ESP_LOGW(kTag, "TEST_ONLY deterministic activity rules disabled: signed Home config, current lease or trusted time unavailable");
#endif
#if !defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) || !GS40_TEST_ONLY_CLOUDSYNC_BUILD
    HttpsBackendChannel cloud_channel("", "", cloud_trust);
#endif
    HttpBackendTransport cloud_transport(cloud_channel);
    CloudSyncWorker cloud_worker(runtime.journal(), runtime,
                                 cloud_authority_source, cloud_transport);
    CloudSyncTaskContext cloud_task_context{&cloud_worker};
    TaskHandle_t cloud_task_handle = nullptr;
    if (xTaskCreate(cloud_node_health_task, "gs_hub_cloud_health",
            kCloudSyncWorkerStackBytes, &cloud_task_context, 3,
            &cloud_task_handle) != pdPASS) {
        ESP_LOGE(kTag, "Cloud NodeHealth worker unavailable; cloud publication disabled");
        cloud_task_handle = nullptr;
    } else {
        ESP_LOGI(kTag,
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
            "TEST_ONLY authenticated Cloud NodeHealth scheduler started; publication requires current authority lease");
        TaskHandle_t refresh_task_handle = nullptr;
        if (xTaskCreate(cloud_authority_refresh_task, "gs40_test_authority",
                6144, &refresh_context, 4, &refresh_task_handle) != pdPASS) {
            ESP_LOGE(kTag, "TEST_ONLY authority refresh task unavailable; CloudSync remains fail closed");
            g_gs40_test_material->invalidate();
        }
#else
            "Cloud NodeHealth scheduler started; commercial identity/time remain unprovisioned and disabled");
#endif
    }
    std::uint64_t next_cloud_refresh_ms = 0;
    std::uint64_t next_rule_evaluation_ms = 0;
#endif

    std::map<HubSecurityLink::Mac, std::uint64_t> authorized;
    std::map<HubSecurityLink::Mac, std::pair<std::uint64_t, std::uint32_t>> epoch_confirmed;
    struct RetirementRxState {
        std::uint64_t transport_session{0};
        transport::RetirementReportReassembler reassembler;
    };
    std::map<HubSecurityLink::Mac, RetirementRxState> retirement_rx;
    std::map<HubSecurityLink::Mac, bool> reported_liveness;
    std::uint64_t next_liveness_check_ms = 0;
    const auto advertise_storage_epoch = [&](const HubSecurityLink::Mac& mac) {
        const auto* node = security_link.ready_node(mac);
        auto* frames = security_link.frames_for(mac);
        const auto epoch = runtime.authoritative_storage_epoch();
        if (durability_owner.state() != durable::DurabilityOwnerState::Ready ||
            !epoch || *epoch == 0 || node == nullptr || frames == nullptr ||
            node->last_session == 0) return;
        const auto confirmed = epoch_confirmed.find(mac);
        if (confirmed != epoch_confirmed.end() &&
            confirmed->second.first == node->last_session &&
            confirmed->second.second == *epoch)
            return;
        const auto plain = transport::encode_hub_storage_epoch(*epoch);
        security::SecureFrame protected_epoch;
        if (!plain || !frames->seal(security::RuntimeDirection::Downlink,
                                    plain.frame, protected_epoch)) return;
        (void)esp_now_send(mac.data(), protected_epoch.bytes.data(),
                           protected_epoch.size);
    };
    hub::fota::HubFotaGuard fota_guard;
    std::uint64_t fota_last_activity_ms = 0;
    const auto active_fota_node = [&](const std::string& device_id)
        -> const EnrolledNode* {
        for (const auto& mac : security_link.enrolled_macs()) {
            const auto* node = security_link.ready_node(mac);
            if (node != nullptr && node->device_id == device_id) return node;
        }
        return nullptr;
    };
    const auto abort_fota = [&]() {
        if (!fota_guard.active()) return;
        fota_guard.abort();
        FotaOwnerAck stopped;
        stopped.aborted = true;
        (void)xQueueOverwrite(g_fota_ack_queue, &stopped);
    };
    ESP_LOGI(kTag, "Authenticated Hub owner started enrolled=%u storage_epoch=%u",
             static_cast<unsigned>(security_link.enrolled_macs().size()),
             static_cast<unsigned>(*runtime.authoritative_storage_epoch()));
#if GS_HIL_COMMISSIONING
    ESP_LOGI(kTag, "HIL_FIXTURE_HOME hub_id=%s home_id=%s",
             security_link.hub_id().c_str(), security_link.home_id().c_str());
#endif
#if GS_HIL_CONTROL
    ESP_LOGI(kTag, "HIL_STACK role=hub task=owner stage=startup minimum_free_bytes=%u",
             static_cast<unsigned>(uxTaskGetStackHighWaterMark(nullptr)));
#endif
    for (;;) {
        if (security_link.faulted()) {
            ESP_LOGE(kTag, "Hub security owner faulted; refusing event admission");
#if CONFIG_IDF_TARGET_ESP32S3
            if (cloud_task_handle != nullptr) vTaskDelete(cloud_task_handle);
#endif
            vTaskDelete(nullptr);
            return;
        }
        const auto now_ms = static_cast<std::uint64_t>(esp_timer_get_time() / 1000);
#if CONFIG_IDF_TARGET_ESP32S3
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
        Gs40TestOnlyHouseholdPolicy* pending_policy = nullptr;
        if (xQueueReceive(config_policy_queue, &pending_policy, 0) == pdTRUE) {
            std::unique_ptr<Gs40TestOnlyHouseholdPolicy> policy(pending_policy);
            CloudAuthorityBinding current_binding;
            if (policy && cloud_trust.current_binding(current_binding) &&
                current_binding == policy->authority &&
                gs40_test_only_apply_household_config(
                    test_material->config(), *policy, runtime)) {
                test_activity_home_ready = true;
                auto acknowledgement = std::make_unique<Gs40TestOnlyConfigurationAck>();
                acknowledgement->version = policy->home.version;
                acknowledgement->authority = policy->authority;
                auto* pending_acknowledgement = acknowledgement.release();
                if (xQueueSend(config_acknowledgement_queue,
                               &pending_acknowledgement, 0) != pdTRUE) {
                    delete pending_acknowledgement;
                    ESP_LOGW(kTag, "TEST_ONLY config checkpointed; acknowledgement queue full");
                }
            } else {
                ESP_LOGW(kTag, "TEST_ONLY desired policy no longer matches current Hub/Home/epoch; not applied");
            }
        }
        if (test_activity_home_ready && now_ms >= next_rule_evaluation_ms) {
            next_rule_evaluation_ms = now_ms + 5000U;
            TrustedHubTimeSnapshot trusted_time;
            CloudAuthorityBinding rule_binding;
            std::uint16_t local_minute = 0;
            if (cloud_trust.trusted_hub_time(static_cast<Milliseconds>(now_ms), trusted_time) &&
                trusted_time.trusted && trusted_time.monotonic_ms == now_ms &&
                trusted_time.boot_generation != 0 && trusted_time.utc_now > 0 &&
                cloud_trust.current_binding(rule_binding) &&
                rule_binding.home_id == test_material->config().activity_home_id &&
                gs40_test_only_local_minute(test_material->config(), runtime,
                                            trusted_time.utc_now, local_minute)) {
                (void)runtime.activity_timers(trusted_time.utc_now, local_minute, true,
                                              &rule_binding);
            }
        }
#endif
        if (cloud_task_handle != nullptr && now_ms >= next_cloud_refresh_ms) {
            next_cloud_refresh_ms = now_ms + kCloudSyncRefreshMs;
            if (!cloud_worker.refresh_node_health_snapshot(
                    static_cast<Milliseconds>(now_ms))) {
                // Missing identity, epoch, enrollment or trusted time remains
                // UNKNOWN; local Node admission and durable ACK continue.
            }
            (void)cloud_worker.refresh_hub_rule_decision_snapshot();
            std::vector<HubRuleDecisionReceipt> decision_receipts;
            if (cloud_worker.take_hub_rule_decision_receipts(decision_receipts)) {
                for (const auto& receipt : decision_receipts) {
                    const bool checkpointed = runtime.acknowledge_hub_rule_decision(receipt);
                    cloud_worker.finish_hub_rule_decision_receipt(receipt, checkpointed);
                    if (!checkpointed)
                        ESP_LOGE(kTag, "Hub decision COMMITTED receipt could not be checkpointed; exact intent remains pending");
                }
                (void)cloud_worker.refresh_hub_rule_decision_snapshot();
            }
        }
#endif
        if (const auto expired = security_link.expire_candidate(now_ms)) {
            (void)esp_now_del_peer(expired->data());
#if GS_HIL_COMMISSIONING
            g_fixture_commissioning_state.publish(FixtureCommissioningStatus::TimedOut);
#endif
            ESP_LOGI(kTag, "Expired uncommissioned peer removed");
        }
        if (fota_guard.active()) {
            const auto* current = active_fota_node(fota_guard.device_id());
            auto* frames = current == nullptr ? nullptr
                : security_link.frames_for(current->radio_mac);
            if (!fota_guard.current(current, frames)) {
                FotaOwnerAck stopped;
                stopped.aborted = true;
                (void)xQueueOverwrite(g_fota_ack_queue, &stopped);
            } else if (now_ms - fota_last_activity_ms >= 30000U) {
                ESP_LOGW(kTag, "Authenticated FOTA sender idle timeout");
                abort_fota();
            }
        }
        std::string* removal_request = nullptr;
        if (xQueueReceive(g_removal_queue, &removal_request, 0) == pdTRUE) {
            std::unique_ptr<std::string> device_id(removal_request);
            const auto removed = security_link.remove_node(*device_id);
            if (removed.access_stopped) {
                if (fota_guard.active() && fota_guard.device_id() == *device_id)
                    abort_fota();
                runtime.revoke_node(removed.logical_id);
                authorized.erase(removed.radio_mac);
                reported_liveness.erase(removed.radio_mac);
                const esp_err_t peer_result = esp_now_del_peer(removed.radio_mac.data());
                ESP_LOGI(kTag, "Node access stopped device=%s result=%d peer=%s",
                         device_id->c_str(), static_cast<int>(removed.result),
                         esp_err_to_name(peer_result));
            } else {
                ESP_LOGW(kTag, "Node removal rejected device=%s result=%d",
                         device_id->c_str(), static_cast<int>(removed.result));
            }
            if (security_link.faulted()) continue;
        }
        ReplacementRequest* replacement_request = nullptr;
        if (xQueueReceive(g_replacement_queue, &replacement_request, 0) == pdTRUE) {
            std::unique_ptr<ReplacementRequest> replacement(replacement_request);
            const auto outbound = security_link.begin_replacement(
                replacement->old_device_id, replacement->replacement, now_ms);
            if (outbound && send_security_message(*outbound))
                ESP_LOGI(kTag, "Exact-node replacement offer sent");
            else
                ESP_LOGW(kTag, "Exact-node replacement request rejected");
            std::fill(replacement->replacement.installer_code.begin(),
                      replacement->replacement.installer_code.end(), 0);
        }
        FotaOwnerCommand* fota_request = nullptr;
        if (xQueueReceive(g_fota_command_queue, &fota_request, 0) == pdTRUE) {
            std::unique_ptr<FotaOwnerCommand> command(fota_request);
            FotaOwnerResult result;
            result.command_id = command->command_id;
            if (now_ms <= command->deadline_ms) {
                if (command->action == FotaOwnerAction::Begin) {
                    const auto* node = active_fota_node(command->physical_device_id);
                    auto* frames = node == nullptr ? nullptr
                        : security_link.frames_for(node->radio_mac);
                    const auto encoded = gs::fota::secure_wire::encode(command->message);
                    result.accepted = command->message.type ==
                        gs::fota::secure_wire::Type::Begin && encoded &&
                        fota_guard.begin(node, frames, command->physical_device_id,
                                         command->message.transfer_id);
                    if (result.accepted) {
                        result.authenticated_session = fota_guard.session();
                        fota_last_activity_ms = now_ms;
                        (void)xQueueReset(g_fota_ack_queue);
                    }
                } else if (command->action == FotaOwnerAction::Send &&
                           fota_guard.active() &&
                           command->physical_device_id == fota_guard.device_id()) {
                    const auto* node = active_fota_node(fota_guard.device_id());
                    auto* frames = node == nullptr ? nullptr
                        : security_link.frames_for(node->radio_mac);
                    security::SecureFrame protected_packet;
                    if (fota_guard.seal(node, frames, command->message,
                                        protected_packet) &&
                        esp_now_send(fota_guard.radio_mac().data(),
                                     protected_packet.bytes.data(),
                                     protected_packet.size) == ESP_OK) {
                        result.accepted = true;
                        result.authenticated_session = fota_guard.session();
                        fota_last_activity_ms = now_ms;
                    } else {
                        abort_fota();
                    }
                } else if (command->action == FotaOwnerAction::Abort &&
                           fota_guard.active() &&
                           command->physical_device_id == fota_guard.device_id() &&
                           command->message.transfer_id == fota_guard.transfer_id()) {
                    abort_fota();
                    result.accepted = true;
                }
            }
            (void)xQueueOverwrite(g_fota_result_queue, &result);
        }
        HubSecurityLink::ExpectedNode* requested = nullptr;
        if (xQueueReceive(g_request_queue, &requested, 0) == pdTRUE) {
            std::unique_ptr<HubSecurityLink::ExpectedNode> exact(requested);
            const auto outbound = security_link.begin_commissioning(
                *exact, static_cast<std::uint64_t>(esp_timer_get_time() / 1000));
            if (outbound) {
#if GS_HIL_COMMISSIONING
                g_fixture_commissioning_state.publish(FixtureCommissioningStatus::OfferActive);
#endif
                if (send_security_message(*outbound))
                    ESP_LOGI(kTag, "Exact-node commissioning offer sent");
                else
                    ESP_LOGW(kTag, "Exact-node commissioning offer transmission failed");
            } else {
#if GS_HIL_COMMISSIONING
                g_fixture_commissioning_state.publish(FixtureCommissioningStatus::Rejected);
#endif
                ESP_LOGW(kTag, "Exact-node commissioning request rejected");
            }
            std::fill(exact->installer_code.begin(), exact->installer_code.end(), 0);
#if GS_HIL_CONTROL
            ESP_LOGI(kTag, "HIL_STACK role=hub task=owner stage=commissioning minimum_free_bytes=%u",
                     static_cast<unsigned>(uxTaskGetStackHighWaterMark(nullptr)));
#endif
        }
        ReceivedFrame control;
        if (xQueueReceive(g_security_queue, &control, pdMS_TO_TICKS(20)) == pdTRUE) {
            const auto outbound = security_link.accept(control.source_mac,
                control.bytes.data(), control.size,
                static_cast<std::uint64_t>(esp_timer_get_time() / 1000));
            if (const auto replaced = security_link.take_replaced_node()) {
                if (fota_guard.active() && fota_guard.radio_mac() == replaced->radio_mac)
                    abort_fota();
                runtime.revoke_node(replaced->logical_id);
                authorized.erase(replaced->radio_mac);
                reported_liveness.erase(replaced->radio_mac);
                const esp_err_t peer_result = esp_now_del_peer(replaced->radio_mac.data());
                ESP_LOGI(kTag, "Prior physical Node revoked after replacement peer=%s",
                         esp_err_to_name(peer_result));
            }
            if (outbound && !send_security_message(*outbound))
                ESP_LOGW(kTag, "Authenticated control reply delivery failed");
            if (const auto* node = security_link.ready_node(control.source_mac)) {
                const auto prior = authorized.find(control.source_mac);
                if (prior == authorized.end() || prior->second != node->last_session) {
#if GS_HIL_COMMISSIONING
                    if (g_fixture_commissioning_state.status() ==
                        FixtureCommissioningStatus::OfferActive)
                        g_fixture_commissioning_state.publish(
                            FixtureCommissioningStatus::AuthenticatedRejoin);
#endif
                    runtime.authorize_node(node->logical_id, node->last_session, true);
                    const auto profile = deployment::for_device(node->device_id);
                    runtime.set_node_offline_timeout(node->logical_id,
                        profile ? std::optional<std::uint32_t>{profile->offline_seconds} : std::nullopt);
                    (void)runtime.observe_authenticated_contact(
                        node->logical_id, node->last_session, now_ms);
                    authorized[control.source_mac] = node->last_session;
                    epoch_confirmed.erase(control.source_mac);
                    advertise_storage_epoch(control.source_mac);
                    ESP_LOGI(kTag, "Authenticated rejoin device=%s logical=%s session=%llu",
                             node->device_id.c_str(), node->logical_id.c_str(),
                             static_cast<unsigned long long>(node->last_session));
                }
            }
        }
        if (now_ms >= next_liveness_check_ms) {
            next_liveness_check_ms = now_ms + 1000U;
            for (const auto& [mac, session] : authorized) {
                const auto* node = security_link.ready_node(mac);
                if (node == nullptr || node->last_session != session) continue;
                const bool online = runtime.node_online(node->logical_id, now_ms);
                const auto prior = reported_liveness.find(mac);
                if (prior == reported_liveness.end() || prior->second != online) {
                    reported_liveness[mac] = online;
                    ESP_LOGI(kTag, "Node liveness logical=%s online=%d profile_known=%d session=%llu",
                             node->logical_id.c_str(), online, runtime.node_profile_known(node->logical_id),
                             static_cast<unsigned long long>(session));
                }
            }
        }
        ReceivedFrame frame;
        if (xQueueReceive(g_data_queue, &frame, 0) != pdTRUE) continue;
        const auto* node = security_link.ready_node(frame.source_mac);
        auto* frames = security_link.frames_for(frame.source_mac);
        if (node == nullptr || frames == nullptr) continue;
        security::SecureFrame protected_frame;
        protected_frame.size = frame.size;
        std::copy_n(frame.bytes.data(), frame.size, protected_frame.bytes.data());
        transport::EncodedFrame plain;
        if (!frames->open(security::RuntimeDirection::Uplink,
                          protected_frame, plain)) {
            ESP_LOGW(kTag, "Rejected unauthenticated/replayed runtime frame");
            continue;
        }
        advertise_storage_epoch(frame.source_mac);
        if (plain.size >= 2 && plain.bytes[0] == 'G' && plain.bytes[1] == 'F') {
            gs::fota::secure_wire::Message verified;
            if (fota_guard.admit_verified_ack(frame.source_mac, node, frames,
                                              plain, verified)) {
                (void)runtime.observe_authenticated_contact(
                    node->logical_id, node->last_session, now_ms);
                FotaOwnerAck forwarded;
                forwarded.message = verified;
                fota_last_activity_ms = now_ms;
                (void)xQueueOverwrite(g_fota_ack_queue, &forwarded);
            } else {
                ESP_LOGW(kTag, "Rejected mismatched authenticated FOTA ACK");
            }
            continue;
        }
        const auto classification = transport::classify_frame(plain.bytes.data(), plain.size);
        if (classification == transport::FrameClass::NodeRetirementFragment) {
            if (durability_owner.state() != durable::DurabilityOwnerState::Ready ||
                runtime.authoritative_storage_epoch().value_or(0) == 0) continue;
            auto& receive_state = retirement_rx[frame.source_mac];
            if (receive_state.transport_session != frames->session()) {
                receive_state.reassembler.reset();
                receive_state.transport_session = frames->session();
            }
            security::Key32 report_key{};
            transport::RetirementEnrollmentBinding enrollment{};
            if (!security_link.retirement_report_key(frame.source_mac, report_key) ||
                !security_link.retirement_enrollment_binding(frame.source_mac, enrollment)) {
                commissioning_crypto.secure_zero(report_key.data(), report_key.size());
                continue;
            }
            transport::NodeRetirementReportV1 report;
            security::Key32 report_hmac{};
            const auto assembly = receive_state.reassembler.accept(
                commissioning_crypto, report_key, plain, report, report_hmac);
            commissioning_crypto.secure_zero(report_key.data(), report_key.size());
            if (assembly == transport::RetirementAssemblyResult::Rejected)
                receive_state.reassembler.reset();
            if (assembly != transport::RetirementAssemblyResult::Complete) continue;

            auto* report_repository = durability_owner.retirement_repository();
            auto* durable_store = durability_owner.durable_store();
            const auto epoch = runtime.authoritative_storage_epoch();
            if (report_repository == nullptr || durable_store == nullptr ||
                !epoch || *epoch == 0 || report.epoch != *epoch) continue;
            durable::RecoveryState before;
            if (!durable_store->recover(before) || before.storage_epoch != *epoch) continue;
            durable::RetirementSnapshot current;
            if (before.checkpoint.report_snapshot) {
                if (!report_repository->load(*before.checkpoint.report_snapshot, current))
                    continue;
            } else {
                current.storage_epoch = *epoch;
                current.generation = 1;
            }
            durable::RetirementSnapshot candidate;
            const auto applied = report_repository->apply_authenticated_report(
                current, enrollment.digest, enrollment.slot, enrollment.generation,
                node->last_session, report, report_hmac, candidate);
            bool durable_report_ready = applied == durable::RetirementReportApply::Duplicate;
            if (applied == durable::RetirementReportApply::Prepared &&
                before.checkpoint_generation != UINT64_MAX) {
                std::uint8_t referenced_banks = before.recovery_report_bank_mask;
#if CONFIG_IDF_TARGET_ESP32S3
                if (!durable_outbox.retirement_report_bank_mask(before, referenced_banks))
                    continue;
#endif
                durable::RetirementSnapshotReference reference;
                if (report_repository->prepare_bank(candidate, referenced_banks,
                                                    reference)) {
                    auto next_checkpoint = before.checkpoint;
                    next_checkpoint.storage_epoch = *epoch;
                    next_checkpoint.generation = before.checkpoint_generation + 1U;
                    // Report metadata does not cover unarchived event tail:
                    // keep retained event/receipt identities and archive batching.
                    next_checkpoint.covered_ordinal = before.checkpoint.covered_ordinal;
                    next_checkpoint.report_snapshot = reference;
                    durable::RecoveryState verified_state;
                    durable::RetirementSnapshot verified_snapshot;
                    durable_report_ready = durable_store->checkpoint(next_checkpoint) &&
                        durable_store->recover(verified_state) &&
                        verified_state.checkpoint.report_snapshot.has_value() &&
                        verified_state.checkpoint.report_snapshot->bank == reference.bank &&
                        verified_state.checkpoint.report_snapshot->generation == reference.generation &&
                        verified_state.checkpoint.report_snapshot->digest == reference.digest &&
                        report_repository->load(reference, verified_snapshot);
                }
            }
            if (!durable_report_ready) continue;
#if CONFIG_IDF_TARGET_ESP32S3
            // NVS selection is the authority. Publish its exact reference in
            // LittleFS, then bind the in-memory gate before handling more data.
            {
                const auto reconciliation = runtime.reconcile_replay_fence(
                    *durable_store, *report_repository, runtime_state, *epoch,
                    durable_outbox);
                if (!reconciliation.succeeded()) {
                    const char* result = "RECONCILIATION_FAILED";
                    if (reconciliation.stage == ReplayFenceReconcileStage::SelectedStateReload)
                        result = "DURABLE_CHECKPOINT_RECOVERY_FAILED";
                    else if (reconciliation.stage == ReplayFenceReconcileStage::OutboxPublication)
                        result = storage::replay_fence_publish_result_name(reconciliation.publication);
                    else if (reconciliation.stage == ReplayFenceReconcileStage::RuntimeBinding)
                        result = replay_fence_bind_result_name(reconciliation.binding);
                    else if (reconciliation.stage == ReplayFenceReconcileStage::SnapshotReferenceMissing)
                        result = "SELECTED_REFERENCE_MISSING";
                    else if (reconciliation.stage == ReplayFenceReconcileStage::SnapshotReload)
                        result = "SNAPSHOT_READ_OR_AUTHENTICATION_FAILED";
                    else if (reconciliation.stage == ReplayFenceReconcileStage::ReducerCheckpointReload)
                        result = "REDUCER_CHECKPOINT_READ_OR_AUTHENTICATION_FAILED";
                    else if (reconciliation.stage == ReplayFenceReconcileStage::ReducerCheckpointMissing)
                        result = "REDUCER_CHECKPOINT_MISSING";
                    ESP_LOGE(kTag,
                        "S3 replay fence failed stage=%s result=%s path=%s admission=%s report_ack=withheld",
                        replay_fence_reconcile_stage_id(reconciliation.stage), result,
                        applied == durable::RetirementReportApply::Duplicate ? "DUPLICATE" : "PREPARED",
                        runtime.durable_admission_open() ? "PRIOR_FENCE_VALID" : "CLOSED");
                    continue;
                }
#if GS_HIL_COMMISSIONING
                ESP_LOGI(kTag,
                    "S3 replay fence healthy stage=%s path=%s admission=%s report_generation=%llu",
                    replay_fence_reconcile_stage_id(reconciliation.stage),
                    applied == durable::RetirementReportApply::Duplicate ? "DUPLICATE" : "PREPARED",
                    runtime.durable_admission_open() ? "OPEN" : "CLOSED",
                    static_cast<unsigned long long>(report.generation));
#endif
            }
            if (limits.body_retirement_enabled || durable_outbox.completion_reclamation_needed()) {
                // NVS publishes the authenticated Node snapshot first. The
                // LittleFS lifecycle root can only follow that selected,
                // recoverable report, so a crash between partitions is safe:
                // it leaves bodies retained until this join is retried.
                durable::RecoveryState selected_state;
                durable::RetirementSnapshot selected_snapshot;
                security::Bytes app_checkpoint;
                std::uint64_t checkpoint_boundary = 0;
                bool checkpoint_found = false;
                if (!durable_store->recover(selected_state) ||
                    !selected_state.checkpoint.report_snapshot ||
                    !report_repository->load(*selected_state.checkpoint.report_snapshot,
                                             selected_snapshot) ||
                    !runtime_state.load_checkpoint(app_checkpoint,
                        checkpoint_boundary, checkpoint_found) || !checkpoint_found) {
                    continue;
                }
                storage::RetirementAuthorization authorization;
                authorization.checkpoint_boundary = checkpoint_boundary;
                authorization.authenticated_report_generation =
                    selected_state.checkpoint.report_snapshot->generation;
                authorization.authenticated_report_digest =
                    selected_state.checkpoint.report_snapshot->digest;
                // No product post-sync retention interval or persistent
                // completion-time policy is approved yet. Host qualification
                // may explicitly satisfy this gate; firmware keeps deletion
                // disabled until that policy is implemented and qualified.
                authorization.post_sync_retention_satisfied = false;
                OutboxNodeRetirementContext retirement_context{
                    &security_link, &selected_snapshot, &runtime, &durable_outbox, *epoch,
                    *selected_state.checkpoint.report_snapshot};
                authorization.node_retired = outbox_event_retired_by_node_report;
                authorization.context = &retirement_context;
                authorization.authority_current = outbox_retirement_authority_current;
                // Reuse the selected Node proof and reducer checkpoint only when
                // the receipt stream cannot fit its maximum next receipt. Bodies
                // and exact identity evidence remain retained in production.
                if (durable_outbox.completion_reclamation_needed()) {
                    const auto metadata_reclaim = durable_outbox.reclaim_completion_metadata(authorization);
                    if (metadata_reclaim == storage::ReclaimResult::Reclaimed)
                        ESP_LOGI(kTag, "Reclaimed completion metadata with exact replay snapshot");
                }
                storage::BodyCompactionStats compaction_stats;
                const auto reclaim = durable_outbox.compact_event_bodies(authorization, compaction_stats);
                if (reclaim == storage::ReclaimResult::Reclaimed)
                    ESP_LOGI(kTag, "Retired synchronized outbox generation=%llu through=%llu",
                        static_cast<unsigned long long>(
                            authorization.authenticated_report_generation),
                        static_cast<unsigned long long>(authorization.checkpoint_boundary));
            }
#endif
            epoch_confirmed[frame.source_mac] = {node->last_session, report.epoch};
            transport::NodeRetirementAckV1 ack;
            ack.epoch = report.epoch;
            ack.generation = report.generation;
            ack.report_hmac = report_hmac;
            const auto encoded_ack = transport::encode_node_retirement_ack(ack);
            security::SecureFrame protected_ack;
            if (!encoded_ack || !frames->seal(security::RuntimeDirection::Downlink,
                                              encoded_ack.frame, protected_ack)) continue;
            const auto retirement_ack_sent = esp_now_send(
                frame.source_mac.data(), protected_ack.bytes.data(), protected_ack.size);
#if GS_HIL_COMMISSIONING
            ESP_LOGI(kTag, "Authenticated retirement ACK session=%llu generation=%llu send=%s",
                     static_cast<unsigned long long>(node->last_session),
                     static_cast<unsigned long long>(report.generation),
                     esp_err_to_name(retirement_ack_sent));
#endif
            continue;
        }
        if (classification == transport::FrameClass::NodeHealth) {
            const auto health = transport::decode_node_health(plain.bytes.data(), plain.size);
            const auto health_now_ms = static_cast<std::uint64_t>(esp_timer_get_time() / 1000);
            EpochSeconds health_received_at = 0;
            TrustedHubTimeSnapshot health_time;
            if (cloud_trust.trusted_hub_time(health_now_ms, health_time) &&
                health_time.trusted && health_time.monotonic_ms == health_now_ms &&
                health_time.boot_generation != 0 && health_time.utc_now > 0) {
                health_received_at = health_time.utc_now;
            }
            if (health && runtime.observe_authenticated_health(
                    *health.value, node->logical_id, node->last_session,
                    health_now_ms, health_received_at)) {
                if (!health.value->c8_ack_wait_trace) {
                ESP_LOGI(kTag, "Authenticated NodeHealth logical=%s session=%llu heap=%u min_heap=%u retained=%u sleep_entries=%u timer_wakes=%u gpio_wakes=%u other_wakes=%u last_wake=%s requested_ms=%u elapsed_ms=%u RSSI=%d",
                         node->logical_id.c_str(),
                         static_cast<unsigned long long>(node->last_session),
                         static_cast<unsigned>(health.value->free_heap),
                         static_cast<unsigned>(health.value->minimum_free_heap),
                         static_cast<unsigned>(health.value->retained_count),
                         static_cast<unsigned>(health.value->light_sleep_entry_count),
                         static_cast<unsigned>(health.value->timer_wake_count),
                         static_cast<unsigned>(health.value->gpio_wake_count),
                         static_cast<unsigned>(health.value->other_wake_count),
                         node_health_sleep_wake_cause_name(
                             health.value->last_wake_cause),
                         static_cast<unsigned>(health.value->last_sleep_requested_ms),
                         static_cast<unsigned>(health.value->last_sleep_elapsed_ms),
                         frame.transport_rssi);
                }
#if GS_HIL_COMMISSIONING
                if (!health.value->c8_ack_wait_trace) {
                ESP_LOGI(kTag,
                         "HIL_AUTH_HEALTH logical=%s session=%llu health_seq=%llu reset=%u pir_raw=%d pir_edges=%u pir_ok=%u pir_rejected=%u retained=%u oldest_seq=%llu tx=%u mac_ok=%u mac_fail=%u durable_ack=%u retry=%u maintenance=%d sleep_entries=%u timer_wakes=%u gpio_wakes=%u other_wakes=%u last_wake=%s",
                         node->logical_id.c_str(),
                         static_cast<unsigned long long>(node->last_session),
                         static_cast<unsigned long long>(health.value->health_sequence),
                         static_cast<unsigned>(health.value->reset_reason),
                         health.value->raw_pir_level,
                         static_cast<unsigned>(health.value->raw_pir_edges),
                         static_cast<unsigned>(health.value->accepted_pir),
                         static_cast<unsigned>(health.value->rejected_pir),
                         static_cast<unsigned>(health.value->retained_count),
                         static_cast<unsigned long long>(health.value->oldest_sequence),
                         static_cast<unsigned>(health.value->tx_attempts),
                         static_cast<unsigned>(health.value->mac_success),
                         static_cast<unsigned>(health.value->mac_failure),
                         static_cast<unsigned>(health.value->durable_acks),
                         static_cast<unsigned>(health.value->retries),
                         health.value->maintenance_active,
                         static_cast<unsigned>(health.value->light_sleep_entry_count),
                         static_cast<unsigned>(health.value->timer_wake_count),
                         static_cast<unsigned>(health.value->gpio_wake_count),
                         static_cast<unsigned>(health.value->other_wake_count),
                         node_health_sleep_wake_cause_name(health.value->last_wake_cause));
                if (health.value->c8_physical_sleep_trace) {
                    const auto& trace = *health.value->c8_physical_sleep_trace;
                    const char* restore_result =
                        trace.last_radio_restore_result == 1U ? "OK" :
                        trace.last_radio_restore_result == 2U ? "FAIL" : "UNKNOWN";
                    ESP_LOGI(kTag,
                             "HIL_C8_SLEEP_TRACE schema=1 logical=%s session=%llu health_seq=%llu uptime_ms=%llu gpio4_now=%d high_episodes=%u high_total_ms=%u high_max_ms=%u sleep_inhibited_high=%u entry_race_abort_high=%u sleep_entries_gpio4_high=%u last_entry_gpio4_high=%d last_wake_gpio4_high=%d wake_cause=%s radio_restore=%s owner_resumed=%d",
                             node->logical_id.c_str(),
                             static_cast<unsigned long long>(node->last_session),
                             static_cast<unsigned long long>(health.value->health_sequence),
                             static_cast<unsigned long long>(health.value->uptime_ms),
                             health.value->raw_pir_level,
                             static_cast<unsigned>(trace.pir_high_episodes),
                             static_cast<unsigned>(trace.pir_high_total_ms),
                             static_cast<unsigned>(trace.pir_high_max_episode_ms),
                             static_cast<unsigned>(trace.sleep_decisions_inhibited_pir_high),
                             static_cast<unsigned>(trace.entry_races_aborted_pir_high),
                             static_cast<unsigned>(trace.sleep_entries_with_gpio4_high),
                             trace.last_sleep_entry_gpio4_high,
                             trace.last_wake_gpio4_high,
                             node_health_sleep_wake_cause_name(health.value->last_wake_cause),
                             restore_result, trace.last_owner_resumed);
                }
                }
#endif
                if (health.value->c8_ack_wait_trace) {
                    const auto& trace = *health.value->c8_ack_wait_trace;
                    ESP_LOGI(kTag,
                             "C8_ACK_TRACE schema=1 logical=%s transport_session=%llu health_seq=%llu uptime_ms=%llu reset=%u boot_generation=%u key_session=%llu key_sequence=%llu events=%u overflow=%u missing=%u complete=%d interval_open=%d sleep_inhibit_decisions=%u sleep_inhibitor_mask=0x%08lx sleep_entries_during_wait=%u post_ack_sleep_eligible=%u post_ack_sleep_entries=%u flags=0x%04x RSSI=%d",
                             node->logical_id.c_str(),
                             static_cast<unsigned long long>(health.value->session_id),
                             static_cast<unsigned long long>(health.value->health_sequence),
                             static_cast<unsigned long long>(health.value->uptime_ms),
                             static_cast<unsigned>(health.value->reset_reason),
                             static_cast<unsigned>(trace.boot_generation),
                             static_cast<unsigned long long>(trace.event_key_session_id),
                             static_cast<unsigned long long>(trace.event_key_sequence),
                             static_cast<unsigned>(trace.event_count),
                             static_cast<unsigned>(trace.overflow_count),
                             static_cast<unsigned>(trace.missing_intervals),
                             trace.evidence_complete, trace.interval_open,
                             static_cast<unsigned>(trace.sleep_inhibit_decisions),
                             static_cast<unsigned long>(trace.sleep_inhibitor_mask),
                             static_cast<unsigned>(trace.sleep_entries_during_ack_wait),
                             static_cast<unsigned>(trace.post_ack_sleep_eligible_count),
                             static_cast<unsigned>(trace.post_ack_sleep_entries),
                             static_cast<unsigned>(trace.flags), frame.transport_rssi);
                    for (std::size_t i = 0; i < trace.event_count; ++i) {
                        const auto& event = trace.events[i];
                        ESP_LOGI(kTag,
                                 "C8_ACK_TRACE_EVENT logical=%s key_session=%llu key_sequence=%llu ordinal=%u uptime_ms=%u kind=%u value=0x%08lx",
                                 node->logical_id.c_str(),
                                 static_cast<unsigned long long>(trace.event_key_session_id),
                                 static_cast<unsigned long long>(trace.event_key_sequence),
                                 static_cast<unsigned>(i),
                                 static_cast<unsigned>(event.uptime_ms),
                                 static_cast<unsigned>(event.kind),
                                 static_cast<unsigned long>(event.value));
                    }
                    for (std::size_t i = 0; i < trace.sleep_reason_count; ++i) {
                        ESP_LOGI(kTag,
                                 "C8_ACK_TRACE_REASON logical=%s key_session=%llu key_sequence=%llu slot=%u inhibitors=0x%08lx",
                                 node->logical_id.c_str(),
                                 static_cast<unsigned long long>(trace.event_key_session_id),
                                 static_cast<unsigned long long>(trace.event_key_sequence),
                                 static_cast<unsigned>(i),
                                 static_cast<unsigned long>(trace.sleep_reason_masks[i]));
                    }
                }
                if (security_link.health_ack_supported(frame.source_mac)) {
                    const auto encoded_ack = transport::encode_node_health_ack(
                        health.value->health_sequence);
                    security::SecureFrame protected_ack;
                    if (encoded_ack && frames->seal(security::RuntimeDirection::Downlink,
                                                    encoded_ack.frame, protected_ack))
                        (void)esp_now_send(frame.source_mac.data(),
                                           protected_ack.bytes.data(), protected_ack.size);
                }
            } else {
                ESP_LOGW(kTag, "Rejected stale/mismatched authenticated NodeHealth");
            }
            continue;
        }
        if (classification != transport::FrameClass::NodeMessage) continue;
        const auto decoded = transport::decode_node_message(plain.bytes.data(), plain.size);
        if (!decoded || decoded.value->node_id != node->logical_id) continue;
        transport::RetirementEnrollmentBinding event_owner{};
        if (!security_link.retirement_enrollment_binding(frame.source_mac, event_owner)) continue;
        EpochSeconds hub_received_at = 0;
        std::optional<std::uint16_t> local_minute;
        CloudAuthorityBinding rule_binding;
        const CloudAuthorityBinding* decision_authority = nullptr;
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
        TrustedHubTimeSnapshot trusted_time;
        const auto event_now_ms = static_cast<Milliseconds>(esp_timer_get_time() / 1000);
        if (cloud_trust.trusted_hub_time(event_now_ms, trusted_time) &&
            trusted_time.trusted && trusted_time.monotonic_ms == event_now_ms &&
            trusted_time.boot_generation != 0 && trusted_time.utc_now > 0) {
            hub_received_at = trusted_time.utc_now;
            std::uint16_t household_minute = 0;
            if (test_activity_home_ready && cloud_trust.current_binding(rule_binding) &&
                rule_binding.home_id == test_material->config().activity_home_id &&
                gs40_test_only_local_minute(test_material->config(), runtime,
                                            trusted_time.utc_now, household_minute)) {
                local_minute = household_minute;
                decision_authority = &rule_binding;
            }
        }
#endif
        if (!runtime.authenticated_radio_message_callback(
                *decoded.value, node->logical_id, node->device_id,
                node->last_session, hub_received_at,
                static_cast<std::uint64_t>(esp_timer_get_time() / 1000),
                event_owner.slot, event_owner.generation, event_owner.digest)) continue;
        const auto processed = runtime.run_state_once(local_minute, decision_authority);
        if (!processed) continue;
#if (GS_HIL_COMMISSIONING || GS_HIL_C8_ACK_HOLD || GS_HIL_SIGNED_FOTA) && CONFIG_IDF_TARGET_ESP32S3
        bool key_found = false;
        const auto key_lookup = durable_outbox.contains(processed->key.str(), key_found);
        ESP_LOGI(kTag,
                 "HIL_AUTH_EVENT event_id=%s state_changed=%d records=%u outbox_lookup=%u outbox_found=%d admission=%s",
                 processed->key.str().c_str(), processed->state_changed,
                 static_cast<unsigned>(runtime.journal().size()),
                 static_cast<unsigned>(key_lookup), key_found,
                 runtime.durable_admission_open() ? "OPEN" : "CLOSED");
#endif
#if GS_HIL_C8_ACK_DROP && CONFIG_IDF_TARGET_ESP32S3
        const bool c8_ack_drop_eligible = C8AckDropGate::eligible(
            processed->ack == AckClass::Durable, processed->state_changed,
            key_lookup == storage::IdentityLookup::Found, key_found,
            runtime.durable_admission_open());
        const auto c8_ack_drop = g_c8_ack_drop_gate.decide(
            static_cast<std::uint64_t>(esp_timer_get_time() / 1000),
            c8_ack_drop_eligible);
        if (c8_ack_drop == C8AckDropDecision::SuppressOneAck) {
            ESP_LOGW(kTag,
                     "HIL_C8_ACK_DROP event_id=%s durable=YES state_changed=1 outbox_found=1 admission=OPEN ack_sent=NO",
                     processed->key.str().c_str());
            continue;
        }
        if (c8_ack_drop == C8AckDropDecision::Expired) {
            ESP_LOGW(kTag, "HIL_C8_ACK_DROP_EXPIRED ack_sent=NORMAL");
        }
#endif
#if GS_HIL_C8_ACK_HOLD && CONFIG_IDF_TARGET_ESP32S3
        const auto hold_decision = g_c8_ack_hold_gate.decide(
            static_cast<std::uint64_t>(esp_timer_get_time() / 1000),
            processed->key.str(), processed->ack == AckClass::Durable,
            processed->state_changed,
            key_lookup == storage::IdentityLookup::Found && key_found,
            runtime.durable_admission_open());
        if (hold_decision == C8AckHoldDecision::CapturedAndHeld ||
            hold_decision == C8AckHoldDecision::SameKeyHeld) {
            const auto held = g_c8_ack_hold_gate.snapshot(
                static_cast<std::uint64_t>(esp_timer_get_time() / 1000));
            ESP_LOGW(kTag,
                "HIL_C8_ACK_HOLD event_id=%s decision=%s durable=YES state_changed=%d outbox_found=1 logical_effects=%u held_attempts=%u ack_sent=NO",
                processed->key.str().c_str(),
                hold_decision == C8AckHoldDecision::CapturedAndHeld ? "CAPTURE" : "SAME_KEY",
                processed->state_changed,
                static_cast<unsigned>(held.logical_effects),
                static_cast<unsigned>(held.held_attempts));
            continue;
        }
        if (hold_decision == C8AckHoldDecision::WatchdogExpired ||
            hold_decision == C8AckHoldDecision::Released) {
            ESP_LOGI(kTag, "HIL_C8_ACK_HOLD event_id=%s decision=%s ack_sent=NORMAL",
                processed->key.str().c_str(),
                hold_decision == C8AckHoldDecision::Released ? "RELEASED" : "WATCHDOG");
        }
#endif
#if GS_HIL_CONTROL
        ESP_LOGI(kTag, "HIL_EVENT_RESULT event_id=%s ack=%u state_changed=%d records=%u",
                 processed->key.str().c_str(), static_cast<unsigned>(processed->ack),
                 processed->state_changed, static_cast<unsigned>(runtime.journal().size()));
        // Explicit one-shot fault injection after verified durable commit.
        // No false ACK: reboot with the application ACK deliberately unsent.
        if (processed->ack == AckClass::Durable && processed->state_changed &&
            g_hil_reboot_after_commit.exchange(false, std::memory_order_acq_rel)) {
            ESP_LOGI(kTag, "HIL_LOST_ACK_REBOOT event_id=%s durable=YES ack_sent=NO records=%u",
                     processed->key.str().c_str(), static_cast<unsigned>(runtime.journal().size()));
            std::fflush(stdout);
            vTaskDelay(pdMS_TO_TICKS(50));
            esp_restart();
        }
#endif
        const auto ack = make_node_ack(processed->key, processed->ack,
                                       hub_received_at, ack_reason(*processed));
        const auto encoded = transport::encode_node_ack(ack);
        security::SecureFrame protected_ack;
        if (!encoded || !frames->seal(security::RuntimeDirection::Downlink,
                                      encoded.frame, protected_ack)) continue;
        const auto sent = esp_now_send(frame.source_mac.data(),
                                       protected_ack.bytes.data(), protected_ack.size);
        const auto event_log = format_authenticated_event_log(
            node->logical_id, *decoded.value, processed->key, processed->ack,
            esp_err_to_name(sent));
        ESP_LOGI(kTag, "%s", event_log.c_str());
    }
}
#endif

}  // namespace

QueueHandle_t control_plane_queue() {
    return g_control_queue;
}

void set_control_plane_active(bool active) {
    g_control_plane_active.store(active, std::memory_order_release);
}

#if GS_HIL_C8_ACK_DROP && CONFIG_IDF_TARGET_ESP32S3
bool arm_c8_ack_drop_fixture() {
    const auto now_ms = static_cast<std::uint64_t>(esp_timer_get_time() / 1000);
    return g_c8_ack_drop_gate.arm(now_ms);
}
#endif

#if GS_HIL_C8_ACK_HOLD && CONFIG_IDF_TARGET_ESP32S3
bool arm_c8_ack_hold_fixture() {
    return g_c8_ack_hold_gate.arm(static_cast<std::uint64_t>(esp_timer_get_time() / 1000));
}

bool release_c8_ack_hold_fixture() {
    return g_c8_ack_hold_gate.release(static_cast<std::uint64_t>(esp_timer_get_time() / 1000));
}

bool cancel_c8_ack_hold_fixture() {
    return g_c8_ack_hold_gate.cancel(static_cast<std::uint64_t>(esp_timer_get_time() / 1000));
}

void log_c8_ack_hold_fixture() {
    const auto state = g_c8_ack_hold_gate.snapshot(
        static_cast<std::uint64_t>(esp_timer_get_time() / 1000));
    ESP_LOGI(kTag,
        "HIL_C8_ACK_HOLD_STATUS state=%u event_id=%s committed_ms=%llu ended_ms=%llu held_attempts=%u duplicate_deliveries=%u logical_effects=%u",
        static_cast<unsigned>(state.state), state.key.c_str(),
        static_cast<unsigned long long>(state.committed_at_ms),
        static_cast<unsigned long long>(state.ended_at_ms),
        static_cast<unsigned>(state.held_attempts),
        static_cast<unsigned>(state.duplicate_deliveries),
        static_cast<unsigned>(state.logical_effects));
}
#endif

bool request_node_commissioning(HubSecurityLink::ExpectedNode exact) {
#if GS_HIL_COMMISSIONING
    if (!g_fixture_commissioning_state.try_reserve_request()) {
        std::fill(exact.installer_code.begin(), exact.installer_code.end(), 0);
        return false;
    }
#endif
    if (g_request_queue == nullptr) {
        std::fill(exact.installer_code.begin(), exact.installer_code.end(), 0);
#if GS_HIL_COMMISSIONING
        g_fixture_commissioning_state.publish(FixtureCommissioningStatus::Rejected);
#endif
        return false;
    }
    auto candidate = std::make_unique<HubSecurityLink::ExpectedNode>(std::move(exact));
    auto* pointer = candidate.get();
    if (xQueueSend(g_request_queue, &pointer, 0) != pdTRUE) {
        std::fill(candidate->installer_code.begin(), candidate->installer_code.end(), 0);
#if GS_HIL_COMMISSIONING
        g_fixture_commissioning_state.publish(FixtureCommissioningStatus::Rejected);
#endif
        return false;
    }
    candidate.release();
    return true;
}

FixtureCommissioningStatus fixture_commissioning_status() {
    return g_fixture_commissioning_state.status();
}

bool request_node_replacement(const std::string& old_physical_device_id,
                              HubSecurityLink::ExpectedNode replacement) {
#if GS_HIL_BUILD
    (void)old_physical_device_id;
    (void)replacement;
    return false;
#else
    if (g_replacement_queue == nullptr || old_physical_device_id.empty() ||
        old_physical_device_id.size() > 64) return false;
    auto request = std::make_unique<ReplacementRequest>(
        ReplacementRequest{old_physical_device_id, std::move(replacement)});
    auto* pointer = request.get();
    if (xQueueSend(g_replacement_queue, &pointer, 0) != pdTRUE) return false;
    request.release();
    return true;
#endif
}

bool request_node_removal(const std::string& physical_device_id) {
#if GS_HIL_BUILD
    (void)physical_device_id;
    return false;
#else
    if (g_removal_queue == nullptr || physical_device_id.empty() ||
        physical_device_id.size() > 64) return false;
    auto request = std::make_unique<std::string>(physical_device_id);
    auto* pointer = request.get();
    if (xQueueSend(g_removal_queue, &pointer, 0) != pdTRUE) return false;
    request.release();
    return true;
#endif
}

#if !GS_HIL_BUILD
bool submit_fota_owner_command(FotaOwnerCommand command, FotaOwnerResult& result) {
    if (g_fota_command_queue == nullptr || g_fota_result_queue == nullptr ||
        command.physical_device_id.empty() || command.physical_device_id.size() > 64 ||
        command.message.transfer_id == 0) return false;
    command.command_id = g_fota_command_id.fetch_add(1U, std::memory_order_relaxed);
    if (command.command_id == 0) return false;
    command.deadline_ms = static_cast<std::uint64_t>(esp_timer_get_time() / 1000) + 1000U;
    auto owned = std::make_unique<FotaOwnerCommand>(std::move(command));
    const auto expected_id = owned->command_id;
    auto* pointer = owned.get();
    if (xQueueSend(g_fota_command_queue, &pointer, 0) != pdTRUE) return false;
    owned.release();
    const TickType_t started = xTaskGetTickCount();
    const TickType_t deadline = pdMS_TO_TICKS(1500);
    while (xTaskGetTickCount() - started < deadline) {
        FotaOwnerResult reply;
        const TickType_t remaining = deadline - (xTaskGetTickCount() - started);
        if (xQueueReceive(g_fota_result_queue, &reply, remaining) != pdTRUE) return false;
        if (reply.command_id == expected_id) {
            result = reply;
            return reply.accepted;
        }
    }
    return false;
}

bool wait_fota_owner_ack(FotaOwnerAck& ack, std::uint32_t timeout_ms) {
    return g_fota_ack_queue != nullptr &&
           xQueueReceive(g_fota_ack_queue, &ack, pdMS_TO_TICKS(timeout_ms)) == pdTRUE;
}
#endif

#if GS_HIL_CONTROL
void hil_reboot_after_next_durable_commit() {
    g_hil_reboot_after_commit.store(true, std::memory_order_release);
}

void hil_set_logical_online(bool online) {
    g_hil_logical_online.store(online, std::memory_order_release);
    ESP_LOGI(kTag, "HIL hub logical state online=%d", online);
}

void hil_log_state() {
    ESP_LOGI(kTag,
             "HIL_STATE role=hub online=%d processed=%u durable_ack=%u health=%u data_queue=%u heap=%u min_heap=%u",
             g_hil_logical_online.load(std::memory_order_acquire),
             static_cast<unsigned>(g_hil_processed.load(std::memory_order_acquire)),
             static_cast<unsigned>(g_hil_durable_ack.load(std::memory_order_acquire)),
             static_cast<unsigned>(g_hil_health_received.load(std::memory_order_acquire)),
             static_cast<unsigned>(uxQueueMessagesWaiting(g_data_queue)),
             static_cast<unsigned>(esp_get_free_heap_size()),
             static_cast<unsigned>(esp_get_minimum_free_heap_size()));
}

void hil_log_test_identity() {
    static security::TargetIdentitySigner identity("hub", 0x7001);
    static bool identity_ready = identity.initialize();
    security::P256PublicKey public_key{};
    std::array<std::uint8_t, 6> mac{};
    if (!identity_ready || !identity.public_key("hub", public_key) ||
        esp_wifi_get_mac(WIFI_IF_STA, mac.data()) != ESP_OK) {
        ESP_LOGE(kTag, "HIL_ERROR command=GET_TEST_IDENTITY reason=identity_unavailable");
        return;
    }
    char key_hex[public_key.size() * 2 + 1]{};
    constexpr char hex[] = "0123456789abcdef";
    for (std::size_t i = 0; i < public_key.size(); ++i) {
        key_hex[2 * i] = hex[public_key[i] >> 4];
        key_hex[2 * i + 1] = hex[public_key[i] & 0x0f];
    }
    ESP_LOGI(kTag,
             "HIL_TEST_IDENTITY profile=TEST_ONLY hub_id=hub-%02x%02x%02x%02x%02x%02x public_key=%s",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5], key_hex);
    ESP_LOGI(kTag, "HIL_OK command=GET_TEST_IDENTITY");
}
#endif

esp_err_t start_runtime_adapter() {
    esp_err_t result = nvs_flash_init();
    if (result != ESP_OK) return result;
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    g_gs40_test_config = std::make_unique<Gs40TestOnlyRuntimeConfig>();
    if ((result = gs40_test_only_receive_config(*g_gs40_test_config)) != ESP_OK) {
        ESP_LOGE(kTag, "TEST_ONLY authenticated configuration unavailable; startup refused: %s",
                 esp_err_to_name(result));
        return result;
    }
#endif
    g_data_queue = xQueueCreateStatic(kDataQueueDepth, sizeof(ReceivedFrame),
                                      g_data_storage.data(), &g_data_queue_state);
    g_control_queue = xQueueCreateStatic(kControlQueueDepth, sizeof(ReceivedFrame),
                                         g_control_storage.data(), &g_control_queue_state);
    g_health_queue = xQueueCreateStatic(kHealthQueueDepth, sizeof(ReceivedFrame),
                                        g_health_storage.data(), &g_health_queue_state);
    g_security_queue = xQueueCreateStatic(kSecurityQueueDepth, sizeof(ReceivedFrame),
                                          g_security_storage.data(), &g_security_queue_state);
    g_request_queue = xQueueCreateStatic(1U, sizeof(HubSecurityLink::ExpectedNode*),
                                         g_request_storage.data(), &g_request_queue_state);
#if !GS_HIL_BUILD
    g_removal_queue = xQueueCreateStatic(1U, sizeof(std::string*),
        g_removal_storage.data(), &g_removal_queue_state);
    g_replacement_queue = xQueueCreateStatic(1U, sizeof(ReplacementRequest*),
        g_replacement_storage.data(), &g_replacement_queue_state);
    g_fota_command_queue = xQueueCreateStatic(1U, sizeof(FotaOwnerCommand*),
        g_fota_command_storage.data(), &g_fota_command_queue_state);
    g_fota_result_queue = xQueueCreateStatic(1U, sizeof(FotaOwnerResult),
        g_fota_result_storage.data(), &g_fota_result_queue_state);
    g_fota_ack_queue = xQueueCreateStatic(1U, sizeof(FotaOwnerAck),
        g_fota_ack_storage.data(), &g_fota_ack_queue_state);
#endif
    g_security_send_queue = xQueueCreateStatic(1U, sizeof(bool),
        g_security_send_storage.data(), &g_security_send_queue_state);
    if (g_data_queue == nullptr || g_control_queue == nullptr || g_health_queue == nullptr ||
        g_security_queue == nullptr || g_request_queue == nullptr ||
        g_security_send_queue == nullptr
#if !GS_HIL_BUILD
        || g_removal_queue == nullptr || g_replacement_queue == nullptr ||
        g_fota_command_queue == nullptr || g_fota_result_queue == nullptr ||
        g_fota_ack_queue == nullptr
#endif
        ) {
        return ESP_ERR_NO_MEM;
    }
    if ((result = initialize_wifi()) != ESP_OK) return result;
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    if ((result = gs40_test_only_connect_wifi(*g_gs40_test_config)) != ESP_OK) {
        ESP_LOGW(kTag, "TEST_ONLY CloudSync route unavailable at boot; local Hub startup continues: %s",
                 esp_err_to_name(result));
    }
    const bool fixture_station_connected = result == ESP_OK;
    g_gs40_test_clock = std::make_unique<Gs40TestOnlyMonotonicClock>();
    g_gs40_test_floor = std::make_unique<NvsAuthenticatedTimeFloorStore>("gs40_time");
    g_gs40_test_random = std::make_unique<S3AuthenticatedTimeRandomSource>();
    g_gs40_test_time_verifier = std::make_unique<Rsa3072Sha256TimeProofVerifier>(
        g_gs40_test_config->time_public_key_der);
    const AuthenticatedTimeBootstrapPolicy time_policy{
        30000, 60000, 300};
    g_gs40_test_time = std::make_unique<AuthenticatedHubTimeProvider>(
        *g_gs40_test_floor, *g_gs40_test_time_verifier,
        *g_gs40_test_random, *g_gs40_test_clock, time_policy);
    const auto time_result = gs40_test_only_bootstrap_time(*g_gs40_test_config,
        *g_gs40_test_floor, *g_gs40_test_time);
    const bool fixture_signed_time_ready = time_result == ESP_OK;
    if (!fixture_signed_time_ready) {
        ESP_LOGW(kTag, "TEST_ONLY signed-time bootstrap unavailable; local Hub starts and CloudSync stays fenced: %s",
                 esp_err_to_name(time_result));
    }
    g_gs40_test_authority_verifier = std::make_unique<Gs40TestOnlyAuthorityLeaseVerifier>(
        g_gs40_test_config->authority_public_key_der);
    g_gs40_test_material = std::make_unique<Gs40TestOnlyMaterialSource>(
        std::move(*g_gs40_test_config), *g_gs40_test_time, *g_gs40_test_clock);
    g_gs40_test_config.reset();
    if (!gs40_test_only_local_hub_start_allowed(true, true))
        return ESP_ERR_INVALID_STATE;
    if (!gs40_test_only_cloud_bootstrap_ready(
            true, fixture_station_connected, fixture_signed_time_ready)) {
        ESP_LOGW(kTag, "TEST_ONLY CloudSync deferred until authenticated station and signed time are ready");
    }
#endif
    if ((result = initialize_esp_now()) != ESP_OK) return result;
#if GS_HIL_BUILD
    if (xTaskCreate(owner_task, "gs_hub_owner", 8192, nullptr, 8, nullptr) != pdPASS) {
#else
    if (xTaskCreate(secure_owner_task, "gs_hub_owner", kSecureOwnerStackBytes, nullptr, 8, nullptr) != pdPASS) {
#endif
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

}  // namespace gs::hub::target

namespace gs::hub::target {
void notify_wifi_credentials_ready_internal() {
#if CONFIG_IDF_TARGET_ESP32S3 && \
    (!defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) || !GS40_TEST_ONLY_CLOUDSYNC_BUILD)
    portENTER_CRITICAL(&g_wifi_reconnect_mux);
    g_wifi_reconnect_policy.on_credentials_ready(monotonic_ms_u64());
    portEXIT_CRITICAL(&g_wifi_reconnect_mux);
#endif
}
}  // namespace gs::hub::target

namespace gs::hub::connectivity {
void notify_s3_wifi_credentials_ready() {
    gs::hub::target::notify_wifi_credentials_ready_internal();
}
}  // namespace gs::hub::connectivity
