#include "firmware/common/security/psa_commissioning_crypto.hpp"
#include "firmware/common/security/target_identity_signer.hpp"
#include "esp_app_desc.h"
#include "esp_mac.h"
#include "esp_ota_ops.h"
#include "esp_partition.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs.h"
#include "nvs_flash.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#if GS_FACTORY_HUB
#include "firmware/hub/components/storage/hub_durability_owner.hpp"
#include "firmware/hub/components/registry/registry_persistence.hpp"
#include "firmware/hub/target/esp32/nvs_durable_blob_store.hpp"
#include "firmware/hub/target/esp32/nvs_store_inventory.hpp"
#else
#include "firmware/common/security/association_persistence.hpp"
#include "firmware/node/target/esp32c3/zero_length_aead_qualification.hpp"
#include "firmware/common/security/nvs_association_blob_store.hpp"
#include "firmware/node/components/storage/node_recovery_persistence.hpp"
#endif

namespace {
constexpr char tag[] = "gs_dev_fresh_init";
// Exact ESP32 initializer ELF: six simultaneous genesis frames total 37424
// bytes, excluding deeper provider/PSA/RTOS frames. This is an initializer-only
// stack budget, not a change to production owner tasks or journal capacity.
constexpr std::uint32_t kHubInitializerStackBytes = 65536;
constexpr std::uint32_t kNodeInitializerStackBytes = 20480;
#if GS_FACTORY_HUB
constexpr char role[] = "hub";
#else
constexpr char role[] = "node";
#endif
using namespace gs;
void require(bool condition, const char* stage) {
    if (!condition) throw std::runtime_error(stage);
}
void esp_check(esp_err_t result, const char* stage) {
    if (result != ESP_OK) {
        ESP_LOGE(tag, "FACTORY_ERROR stage=%s esp=%s code=%d", stage, esp_err_to_name(result), result);
        throw std::runtime_error(stage);
    }
}
security::Bytes read_blob(const char* ns, const char* key, std::size_t expected) {
    nvs_handle_t h{}; esp_check(nvs_open(ns, NVS_READONLY, &h), "preserved_namespace");
    security::Bytes value(expected); std::size_t n = value.size();
    const auto result = nvs_get_blob(h, key, value.data(), &n); nvs_close(h);
    esp_check(result, "preserved_record_read"); require(n == expected, "preserved_record_length");
    return value;
}
void erase_key(const char* ns, const char* key) {
    nvs_handle_t h{}; const auto opened = nvs_open(ns, NVS_READWRITE, &h);
    esp_check(opened, "installation_namespace_open");
    const auto result = nvs_erase_key(h, key);
    if (result != ESP_OK && result != ESP_ERR_NVS_NOT_FOUND) { nvs_close(h); esp_check(result, "installation_key_erase"); }
    const auto committed = nvs_commit(h); nvs_close(h); esp_check(committed, "installation_key_erase_commit");
}
#if GS_FACTORY_HUB
void write_blob(const char* ns, const char* key, const security::Bytes& value) {
    nvs_handle_t h{}; esp_check(nvs_open(ns, NVS_READWRITE, &h), "installation_namespace_open");
    const auto written = nvs_set_blob(h, key, value.data(), value.size());
    const auto committed = written == ESP_OK ? nvs_commit(h) : written; nvs_close(h);
    esp_check(committed, "installation_key_write_commit");
    auto verified = read_blob(ns, key, value.size());
    require(verified == value, "installation_key_readback");
    std::fill(verified.begin(), verified.end(), 0);
}
#endif
std::string hex(const std::uint8_t* bytes, std::size_t n) {
    constexpr char alphabet[] = "0123456789abcdef"; std::string out;
    for (std::size_t i=0;i<n;++i) { out += alphabet[bytes[i] >> 4]; out += alphabet[bytes[i] & 15]; }
    return out;
}
void initialize(const std::array<std::uint8_t,6>& mac) {
    // No automatic erase fallback for normal NVS, even in this explicit image.
    esp_check(nvs_flash_init(), "normal_nvs_init");
    auto identity_before = read_blob("gs_dev_ident", "private_p256", 32);
    security::TargetIdentitySigner signer(role, GS_FACTORY_HUB ? 0x7001 : 0x7002);
    require(signer.initialize(), "existing_identity_initialize");
    security::PsaCommissioningCrypto crypto(signer); require(crypto.ready(), "psa_ready");
#if GS_FACTORY_HUB
    const auto* partition = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, "gs_journal");
    require(partition && partition->address == 0x3e0000 && partition->size == 0x20000,
            "journal_partition_allowlist");
    security::Key32 wrap{}, journal_key{}, durable_key{};
    security::Bytes home(16), wrap_blob(32);
    require(crypto.random_bytes(wrap.data(),wrap.size()) && crypto.random_bytes(home.data(),home.size()), "installation_rng");
    require(std::any_of(wrap.begin(),wrap.end(),[](auto b){return b!=0;}) &&
            std::any_of(home.begin(),home.end(),[](auto b){return b!=0;}), "installation_rng_nonzero");
    std::copy(wrap.begin(),wrap.end(),wrap_blob.begin());
    const auto home_id = "home-" + hex(home.data(),home.size());
    const auto hub_id = "hub-" + hex(mac.data(),mac.size());
    security::Bytes salt(home_id.begin(),home_id.end()); salt.insert(salt.end(),hub_id.begin(),hub_id.end());
    auto context = [](const char* text) { return security::Bytes(text,text+std::strlen(text)); };
    require(crypto.hkdf_sha256(wrap,salt,context("GharSajag/HubJournal/v1"),journal_key) &&
            crypto.hkdf_sha256(journal_key,salt,context("GharSajag/HubDurableStorage/v1"),durable_key), "durability_key_derivation");
    esp_check(esp_partition_erase_range(partition,0,partition->size), "explicit_development_journal_initialize");
    erase_key("gs_registry","snapshot");
    write_blob("gs_security","wrap_key",wrap_blob); write_blob("gs_home","id",home);
    hub::target::NvsDurableBlobStore blobs; hub::target::NvsStoreInventory inventory;
    require(blobs.initialize(), "durable_provider_initialize");
    require(inventory.scan().status == hub::durable::InventoryStatus::Empty, "empty_journal_verified");
    hub::durable::HubDurabilityOwner owner(blobs,inventory,crypto,durable_key,hub::durable::InstallationFreshness::FreshInstallation);
    require(owner.recover() == hub::durable::DurabilityOwnerState::Ready && owner.epoch() == 1 &&
            owner.recovery_state()->checkpoint_generation == 2 &&
            owner.recovery_state()->checkpoint.fresh_registry_domain, "native_genesis_verified");
    security::P256PublicKey public_key{}; require(signer.public_key(role,public_key), "preserved_public_identity");
    // Empty authenticated native registry; no legacy descriptors or migration markers.
    class RegistryBlob final : public security::SecurityBlobStore {
    public:
        bool read(security::Bytes& out,bool& found) override {
            found=false; nvs_handle_t h{}; const auto opened=nvs_open("gs_registry",NVS_READONLY,&h);
            if(opened==ESP_ERR_NVS_NOT_FOUND)return true;
            if(opened!=ESP_OK)return false;
            std::size_t n=0; auto r=nvs_get_blob(h,"snapshot",nullptr,&n);
            if(r==ESP_ERR_NVS_NOT_FOUND){nvs_close(h);return true;}
            if(r!=ESP_OK||n>8192){nvs_close(h);return false;}out.resize(n);
            r=nvs_get_blob(h,"snapshot",out.data(),&n);nvs_close(h);found=r==ESP_OK;return found;
        }
        bool write(const security::Bytes& b) override {write_blob("gs_registry","snapshot",b);return true;}
    } registry_blob;
    hub::HubRegistryRepository registry(crypto,registry_blob,wrap,home_id,hub_id,public_key,10,10);
    hub::HubRegistryState empty; empty.registry.home_id=home_id; empty.registry.hub_id=hub_id;
    require(registry.save(empty), "native_registry_save"); const auto loaded=registry.load();
    require(loaded.status==hub::HubRegistryLoadStatus::Ready && loaded.state &&
            loaded.state->registry.active.empty() && loaded.state->migration.phase==hub::RegistryMigrationPhase::FreshInstallation,
            "native_registry_verified");
    hub::durable::HubDurabilityOwner reboot(blobs,inventory,crypto,durable_key,hub::durable::InstallationFreshness::ExistingInstallation);
    require(reboot.recover()==hub::durable::DurabilityOwnerState::Ready,"normal_reboot_recovery_verified");
    const auto contents=inventory.scan();
    require(contents.status==hub::durable::InventoryStatus::KnownCurrentRecords && contents.count==4,"only_genesis_records");
    crypto.secure_zero(wrap.data(),wrap.size()); crypto.secure_zero(wrap_blob.data(),wrap_blob.size());
    crypto.secure_zero(journal_key.data(),journal_key.size()); crypto.secure_zero(durable_key.data(),durable_key.size());
    ESP_LOGI(tag,"FACTORY_STATE role=hub owner=Ready epoch=1 generation=2 registry=native-empty records=4 migration=NONE");
#else
    auto wrap_before=read_blob("gs_security","wrap_key",32);
    auto factory_before=read_blob("gs_factory","install_code",32);
    security::Key32 wrap{};std::copy(wrap_before.begin(),wrap_before.end(),wrap.begin());
    nvs_handle_t h{};esp_check(nvs_open("gs_node",NVS_READONLY,&h),"session_namespace");
    std::uint64_t session_before=0; const auto session_read=nvs_get_u64(h,"boot_session",&session_before);nvs_close(h);
    esp_check(session_read,"session_counter_read");require(session_before!=0,"session_counter_nonzero");
    security::NvsAssociationBlobStore association_store;
    security::AssociationRepository association(crypto,association_store,wrap);
    const auto old=association.load();
    require(old.status==security::AssociationStatus::Paired || old.status==security::AssociationStatus::Unpaired,
            "existing_association_valid");
    std::size_t discarded=0;
    security::NvsNodeRecoveryBlobStore recovery_store;
    if (old.status==security::AssociationStatus::Paired) {
        security::Key32 recovery_key{};
        const auto physical_id="c3-"+hex(mac.data(),mac.size());
        security::Bytes salt(physical_id.begin(),physical_id.end());
        constexpr char context[]="GharSajag/NodeRecovery/v1";
        require(crypto.hkdf_sha256(wrap,salt,security::Bytes(context,context+sizeof(context)-1),recovery_key),"recovery_key");
        node::NodeRecoveryRepository recovery(crypto,recovery_store,recovery_key,
            old.binding->home_id,old.binding->hub_id,old.binding->logical_id);
        const auto loaded=recovery.load();
        require(loaded.status==node::NodeRecoveryLoadStatus::Missing ||
                (loaded.status==node::NodeRecoveryLoadStatus::Ready && loaded.state),"archived_recovery_valid");
        if(loaded.state)discarded=loaded.state->retained.size();
        require(discarded==28 || loaded.status==node::NodeRecoveryLoadStatus::Missing,"expected_archived_development_count_28");
        crypto.secure_zero(recovery_key.data(),recovery_key.size());
    } else {
        security::Bytes ignored;bool found=false;
        require(recovery_store.read(ignored,found) && !found,"unpaired_must_have_no_old_recovery");
    }
    // Disposal is explicit and precedes unpairing so an interrupted reset can
    // retry using the still-valid old association. Never report a synthetic ACK.
    erase_key("gs_node_rec","snapshot");
    security::Bytes absent; bool found=false;
    require(recovery_store.read(absent,found) && !found,"recovery_disposal_verified");
    require(association.factory_reset(),"association_generation_reset");
    const auto unpaired=association.load();require(unpaired.status==security::AssociationStatus::Unpaired,"unpaired_readback");
    // Explicitly authorized DEVELOPMENT disposal; no ACK or event retirement protocol is fabricated.
    esp_check(nvs_open("gs_node",NVS_READONLY,&h),"session_verify_open");
    std::uint64_t session_after=0; const auto session_verify=nvs_get_u64(h,"boot_session",&session_after);nvs_close(h);
    esp_check(session_verify,"session_verify");require(session_after==session_before,"session_counter_preserved");
    require(read_blob("gs_security","wrap_key",32)==wrap_before &&
            read_blob("gs_factory","install_code",32)==factory_before,"node_factory_material_preserved");
    std::fill(wrap_before.begin(),wrap_before.end(),0);std::fill(factory_before.begin(),factory_before.end(),0);
    crypto.secure_zero(wrap.data(),wrap.size());
    ESP_LOGI(tag,"FACTORY_STATE role=node association=Unpaired recovery=ABSENT boot_session_preserved=YES development_events_discarded=%u",static_cast<unsigned>(discarded));
#endif
    auto identity_after=read_blob("gs_dev_ident","private_p256",32);
    require(identity_after==identity_before,"device_identity_preserved");
    std::fill(identity_before.begin(),identity_before.end(),0);std::fill(identity_after.begin(),identity_after.end(),0);
}
void run(void*) {
#if !GS_FACTORY_HUB
    // Run the accelerated-backend gate before accepting reset confirmation.
    if(!node::target::qualify_zero_length_aead()){
        ESP_LOGE(tag,"FACTORY_FAILED stage=empty_aead_target_gate normal_admission=OFF");
        vTaskDelete(nullptr);return;
    }
#endif
    std::array<std::uint8_t,6> mac{};esp_check(esp_read_mac(mac.data(),ESP_MAC_WIFI_STA),"read_device_mac");
    const auto device=std::string(role)+"-"+hex(mac.data(),mac.size());
    const auto confirmation="DEV_FRESH_RESET "+device+" FORENSICS_PRESERVED"
#if !GS_FACTORY_HUB
        " DISCARD_RETAINED=28"
#endif
        ;
    vTaskDelay(pdMS_TO_TICKS(2000));  // Allow app-only flasher to release/reopen the console.
    ESP_LOGI(tag,"FACTORY_READY role=%s device=%s confirm=%s",role,device.c_str(),confirmation.c_str());
    std::string line;
    for (;;) {
        const int c=std::fgetc(stdin);
        if(c==EOF){std::clearerr(stdin);vTaskDelay(pdMS_TO_TICKS(20));continue;}
        if(c=='\r')continue;
        if(c=='\n'){
            if(line!=confirmation){ESP_LOGW(tag,"FACTORY_REJECT confirmation_required");line.clear();continue;}
            try {initialize(mac);
                ESP_LOGI(tag,"FACTORY_STACK minimum_free_bytes=%u",static_cast<unsigned>(uxTaskGetStackHighWaterMark(nullptr)));
                ESP_LOGI(tag,"FACTORY_DONE role=%s identity_preserved=YES normal_admission=OFF",role);}
            catch(const std::exception& e){ESP_LOGE(tag,"FACTORY_FAILED stage=%s normal_admission=OFF explicit_retry_required=YES",e.what());}
            break;
        }
        if(line.size()<160)line+=char(c);else line.clear();
    }
    // Never reset automatically or start radio, event handling, or normal recovery again.
    vTaskDelete(nullptr);
}
}
extern "C" void app_main() {
    ESP_LOGI(tag,"DEVELOPMENT ONLY version=%s; no writes until exact confirmation",esp_app_get_description()->version);
    const auto stack_bytes = GS_FACTORY_HUB ? kHubInitializerStackBytes : kNodeInitializerStackBytes;
    ESP_LOGI(tag,"FACTORY_STACK configured_bytes=%u",static_cast<unsigned>(stack_bytes));
    // Allocation failure remains fail closed, before confirmation or NVS access.
    ESP_ERROR_CHECK(xTaskCreate(run,"dev_fresh_init",stack_bytes,nullptr,5,nullptr)==pdPASS?ESP_OK:ESP_ERR_NO_MEM);
}
