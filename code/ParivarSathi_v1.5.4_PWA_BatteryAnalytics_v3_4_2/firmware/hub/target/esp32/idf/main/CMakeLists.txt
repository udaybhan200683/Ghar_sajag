set(GS_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../../..")
include("${GS_ROOT}/firmware/common/node_health_config.cmake")
set(GS_HUB_SRCS
    "app_main.cpp"
    "fota_sender.cpp"
)
if(GS_HIL_BUILD OR GS_HIL_CONTROL)
    list(APPEND GS_HUB_SRCS "hil_control.cpp")
endif()

set(GS_TARGET_STORAGE_REQUIRES)
if(IDF_TARGET STREQUAL "esp32s3")
    list(APPEND GS_TARGET_STORAGE_REQUIRES s3_storage esp_http_client)
    list(APPEND GS_HUB_SRCS
        "${GS_ROOT}/firmware/hub/components/cloud/cloud_sync.cpp"
        "${GS_ROOT}/firmware/hub/components/cloud/http_backend_transport.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32s3/https_backend_channel.cpp")
endif()

set(GS_NODE_FIRMWARE_ASSET "${CMAKE_CURRENT_LIST_DIR}/node_firmware.bin" CACHE FILEPATH "Validated paired C3 app asset (basename node_firmware.bin)")
get_filename_component(GS_NODE_ASSET_NAME "${GS_NODE_FIRMWARE_ASSET}" NAME)
if(NOT GS_NODE_ASSET_NAME STREQUAL "node_firmware.bin")
    message(FATAL_ERROR "C3 asset basename must remain node_firmware.bin for existing embedded symbols")
endif()
if(NOT EXISTS "${GS_NODE_FIRMWARE_ASSET}")
    message(FATAL_ERROR
        "Missing node_firmware.bin. Build the C3 product and copy its app binary here before configuring the Hub.")
endif()

idf_component_register(
    SRCS
        ${GS_HUB_SRCS}
        "${GS_ROOT}/shared/src/logging.cpp"
        "${GS_ROOT}/shared/src/rules.cpp"
        "${GS_ROOT}/firmware/common/transport/data_plane_codec.cpp"
        "${GS_ROOT}/firmware/common/transport/node_retirement_protocol.cpp"
        "${GS_ROOT}/firmware/common/transport/fota_secure_wire.cpp"
        "${GS_ROOT}/firmware/common/security/psa_commissioning_crypto.cpp"
        "${GS_ROOT}/firmware/common/security/target_identity_signer.cpp"
        "${GS_ROOT}/firmware/common/security/target_wrapping_key.cpp"
        "${GS_ROOT}/firmware/common/security/commissioning_protocol.cpp"
        "${GS_ROOT}/firmware/common/security/commissioning_wire.cpp"
        "${GS_ROOT}/firmware/common/security/rejoin_protocol.cpp"
        "${GS_ROOT}/firmware/common/security/association_persistence.cpp"
        "${GS_ROOT}/firmware/common/security/nvs_association_blob_store.cpp"
        "${GS_ROOT}/firmware/common/security/runtime_frame_security.cpp"
        "${GS_ROOT}/firmware/hub/components/ingest/ingest.cpp"
        "${GS_ROOT}/firmware/hub/components/registry/node_registry.cpp"
        "${GS_ROOT}/firmware/hub/components/registry/registry_persistence.cpp"
        "${GS_ROOT}/firmware/hub/components/fota/hub_fota_guard.cpp"
        "${GS_ROOT}/firmware/hub/components/storage/journal.cpp"
        "${GS_ROOT}/firmware/hub/components/storage/durable_transition.cpp"
        "${GS_ROOT}/firmware/hub/components/storage/node_retirement_snapshot.cpp"
        "${GS_ROOT}/firmware/hub/components/storage/hub_durability_owner.cpp"
        "${GS_ROOT}/firmware/hub/components/storage/durable_journal_slot_store.cpp"
        "${GS_ROOT}/firmware/hub/components/coverage/coverage.cpp"
        "${GS_ROOT}/firmware/hub/components/rules/routine_service.cpp"
        "${GS_ROOT}/firmware/hub/runtime/hub_runtime.cpp"
        "${GS_ROOT}/firmware/hub/runtime/hub_checkpoint_codec.cpp"
        "${GS_ROOT}/firmware/hub/components/storage/runtime_state_store.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32/hub_runtime_adapter.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32/hub_security_link.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32/nvs_journal_slot_store.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32/nvs_durable_key_codec.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32/nvs_durable_blob_store.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32/nvs_store_inventory.cpp"
    INCLUDE_DIRS
        "${GS_NODE_HEALTH_GENERATED}"
        "."
        "${GS_ROOT}"
        "${GS_ROOT}/shared/include"
        "${GS_ROOT}/firmware/hub/components"
        "${GS_ROOT}/firmware/node/components"
    PRIV_REQUIRES
        app_update
        esp_driver_gpio
        esp_event
        esp_hw_support
        esp_netif
        esp_system
        esp_timer
        esp_wifi
        nvs_flash
        mbedtls
        ${GS_TARGET_STORAGE_REQUIRES}
    EMBED_FILES
        "${GS_NODE_FIRMWARE_ASSET}"
)

target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_17)
target_compile_definitions(${COMPONENT_LIB} PRIVATE
    GS_HIL_BUILD=$<BOOL:${GS_HIL_BUILD}>
    GS_HIL_CONTROL=$<BOOL:${GS_HIL_CONTROL}>)
