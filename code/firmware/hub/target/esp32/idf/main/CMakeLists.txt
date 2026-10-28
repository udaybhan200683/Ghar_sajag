set(GS_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../../..")
include("${GS_ROOT}/firmware/common/node_health_config.cmake")
set(GS_HUB_SRCS
    "app_main.cpp"
    "fota_sender.cpp"
)
if(GS_HIL_BUILD OR GS_HIL_CONTROL)
    list(APPEND GS_HUB_SRCS "hil_control.cpp")
endif()
if(GS_HIL_COMMISSIONING OR GS_HIL_C8_ACK_HOLD OR GS_HIL_SIGNED_FOTA)
    if(NOT IDF_TARGET STREQUAL "esp32s3" OR GS_HIL_BUILD OR GS_HIL_CONTROL)
        message(FATAL_ERROR "S3 fixture controls are limited to the isolated secure S3 profile")
    endif()
    list(APPEND GS_HUB_SRCS "fixture_commissioning_control.cpp")
endif()

set(GS_TARGET_STORAGE_REQUIRES)
set(GS_TARGET_INCLUDE_DIRS)
if(IDF_TARGET STREQUAL "esp32s3")
    if(GS40_TEST_ONLY_CLOUDSYNC AND CONFIG_ESP_TLS_USE_DS_PERIPHERAL)
        message(FATAL_ERROR "GS-40 TEST_ONLY software-key profile requires CONFIG_ESP_TLS_USE_DS_PERIPHERAL=n")
    endif()
    list(APPEND GS_TARGET_STORAGE_REQUIRES s3_storage esp_http_client)
    list(APPEND GS_HUB_SRCS
        "${GS_ROOT}/firmware/hub/cloud_sync/cloud_sync.cpp"
        "${GS_ROOT}/firmware/hub/cloud_sync/http_backend_transport.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32s3/cloud_trust_provider.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32s3/https_backend_channel.cpp")
    list(APPEND GS_HUB_SRCS
        "${GS_ROOT}/firmware/hub/target/esp32s3/esp_idf_wifi_setup_scanner.cpp")
    list(APPEND GS_HUB_SRCS
        "${GS_ROOT}/firmware/hub/connectivity/wifi_credential_slots.cpp"
        "${GS_ROOT}/firmware/hub/connectivity/wifi_setup_permit_gate.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32s3/esp_idf_encrypted_wifi_credential_slots.cpp")
    if(GS40_TEST_ONLY_CLOUDSYNC)
        list(APPEND GS_HUB_SRCS
            "${GS_ROOT}/firmware/hub/target/esp32s3/gs40_test_only_bootstrap.cpp"
            "${GS_ROOT}/firmware/hub/target/esp32s3/gs40_test_only_runtime.cpp"
            "${GS_ROOT}/firmware/hub/lifecycle/configuration/config_service.cpp")
        list(APPEND GS_TARGET_STORAGE_REQUIRES lwip cjson)
        # ESP-IDF 6.0.3's split USB Serial/JTAG component may not propagate
        # this legacy driver include directory through the aliased dependency.
        # Keep the header visible only in the explicit TEST_ONLY composition.
        list(APPEND GS_TARGET_INCLUDE_DIRS
            "${IDF_PATH}/components/esp_driver_usb_serial_jtag/include")
    endif()
endif()

if(DEFINED ENV{GS_NODE_FIRMWARE_ASSET})
    set(GS_NODE_FIRMWARE_ASSET "$ENV{GS_NODE_FIRMWARE_ASSET}" CACHE FILEPATH
        "Validated paired C3 app asset (basename node_firmware.bin)" FORCE)
else()
    set(GS_NODE_FIRMWARE_ASSET "${CMAKE_CURRENT_LIST_DIR}/node_firmware.bin" CACHE FILEPATH
        "Validated paired C3 app asset (basename node_firmware.bin)")
endif()
get_filename_component(GS_NODE_ASSET_NAME "${GS_NODE_FIRMWARE_ASSET}" NAME)
if(NOT GS_NODE_ASSET_NAME STREQUAL "node_firmware.bin")
    message(FATAL_ERROR "C3 asset basename must remain node_firmware.bin for existing embedded symbols")
endif()
if(NOT EXISTS "${GS_NODE_FIRMWARE_ASSET}")
    message(FATAL_ERROR
        "Missing node_firmware.bin. Build the C3 product and copy its app binary here before configuring the Hub.")
endif()

set(GS_HUB_EMBED_FILES "${GS_NODE_FIRMWARE_ASSET}")
if(GS40_TEST_ONLY_CLOUDSYNC)
    # ESP-IDF derives embedded linker symbols from the input basename. Copy
    # the external TEST_ONLY public root to a stable component-build filename
    # so symbols do not depend on the caller's temporary path or filename.
    set(GS40_TEST_ONLY_CONFIG_ROOT_EMBED_FILE
        "${CMAKE_CURRENT_BINARY_DIR}/gs40_test_config_root.der")
    configure_file("${GS40_TEST_ONLY_CONFIG_ROOT_DER}"
        "${GS40_TEST_ONLY_CONFIG_ROOT_EMBED_FILE}" COPYONLY)
    list(APPEND GS_HUB_EMBED_FILES "${GS40_TEST_ONLY_CONFIG_ROOT_EMBED_FILE}")
endif()

idf_component_register(
    SRCS
        ${GS_HUB_SRCS}
        "${GS_ROOT}/firmware/common/shared/src/logging.cpp"
        "${GS_ROOT}/firmware/common/shared/src/rules.cpp"
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
        "${GS_ROOT}/firmware/hub/event_processing/ingest/ingest.cpp"
        "${GS_ROOT}/firmware/hub/commissioning/registry/node_registry.cpp"
        "${GS_ROOT}/firmware/hub/commissioning/registry/registry_persistence.cpp"
        "${GS_ROOT}/firmware/hub/lifecycle/fota/hub_fota_guard.cpp"
        "${GS_ROOT}/firmware/hub/storage/journal.cpp"
        "${GS_ROOT}/firmware/hub/storage/durable_transition.cpp"
        "${GS_ROOT}/firmware/hub/storage/node_retirement_snapshot.cpp"
        "${GS_ROOT}/firmware/hub/storage/hub_durability_owner.cpp"
        "${GS_ROOT}/firmware/hub/storage/durable_journal_slot_store.cpp"
        "${GS_ROOT}/firmware/hub/event_processing/coverage/coverage.cpp"
        "${GS_ROOT}/firmware/hub/routines/routine_service.cpp"
        "${GS_ROOT}/firmware/hub/runtime/hub_runtime.cpp"
        "${GS_ROOT}/firmware/hub/runtime/hub_checkpoint_codec.cpp"
        "${GS_ROOT}/firmware/hub/connectivity/wifi_reconnect_policy.cpp"
        "${GS_ROOT}/firmware/hub/connectivity/wifi_onboarding.cpp"
        "${GS_ROOT}/firmware/hub/storage/runtime_state_store.cpp"
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
        "${GS_ROOT}/firmware/common/shared/include"
        "${GS_ROOT}/firmware/hub"
        "${GS_ROOT}/firmware/node"
        ${GS_TARGET_INCLUDE_DIRS}
    PRIV_REQUIRES
        app_update
        esp_driver_gpio
        # UART is an existing product console transport and is also the
        # identified GS-117 fixture's signed-envelope receive path.
        esp_driver_uart
        esp_event
        efuse
        esp_hw_support
        esp_partition
        esp_netif
        bootloader_support
        esp_system
        esp_timer
        esp_wifi
        nvs_flash
        mbedtls
        ${GS_TARGET_STORAGE_REQUIRES}
    EMBED_FILES ${GS_HUB_EMBED_FILES}
)

target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_17)
target_compile_definitions(${COMPONENT_LIB} PRIVATE
    GS40_TEST_ONLY_CLOUDSYNC_BUILD=$<BOOL:${GS40_TEST_ONLY_CLOUDSYNC}>
    GS_HIL_BUILD=$<BOOL:${GS_HIL_BUILD}>
    GS_HIL_CONTROL=$<BOOL:${GS_HIL_CONTROL}>
    GS_HIL_COMMISSIONING=$<BOOL:${GS_HIL_COMMISSIONING}>
    GS_HIL_C8_ACK_DROP=$<BOOL:${GS_HIL_C8_ACK_DROP}>
    GS_HIL_C8_ACK_HOLD=$<BOOL:${GS_HIL_C8_ACK_HOLD}>
    GS_HIL_SIGNED_FOTA=$<BOOL:${GS_HIL_SIGNED_FOTA}>)
