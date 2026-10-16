set(GS_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../../..")
include("${GS_ROOT}/firmware/common/node_health_config.cmake")
set(GS_NODE_SRCS
    "app_main.cpp"
    "fota_receiver.cpp"
)
if(GS_GS68_NODE_OBSERVER)
    list(APPEND GS_NODE_SRCS "${GS_ROOT}/firmware/node/target/esp32c3/gs68_node_observer.cpp")
endif()
if(GS_HIL_BUILD OR GS_HIL_CONTROL)
    list(APPEND GS_NODE_SRCS "hil_control.cpp"
        "${GS_ROOT}/firmware/node/target/esp32c3/zero_length_aead_qualification.cpp")
endif()

idf_component_register(
    SRCS
        ${GS_NODE_SRCS}
        "${GS_ROOT}/firmware/node/lifecycle/fota/fota_receiver.cpp"
        "${GS_ROOT}/firmware/node/lifecycle/fota/secure_fota_adapter.cpp"
        "${GS_ROOT}/firmware/common/transport/fota_secure_wire.cpp"
        "${GS_ROOT}/firmware/node/lifecycle/fota/boot_health_gate.cpp"
        "${GS_ROOT}/firmware/common/shared/src/logging.cpp"
        "${GS_ROOT}/firmware/common/transport/data_plane_codec.cpp"
        "${GS_ROOT}/firmware/common/transport/node_retirement_protocol.cpp"
        "${GS_ROOT}/firmware/common/transport/session_id.cpp"
        "${GS_ROOT}/firmware/common/security/psa_commissioning_crypto.cpp"
        "${GS_ROOT}/firmware/common/security/target_identity_signer.cpp"
        "${GS_ROOT}/firmware/common/security/target_wrapping_key.cpp"
        "${GS_ROOT}/firmware/common/security/commissioning_protocol.cpp"
        "${GS_ROOT}/firmware/common/security/commissioning_wire.cpp"
        "${GS_ROOT}/firmware/common/security/rejoin_protocol.cpp"
        "${GS_ROOT}/firmware/common/security/association_persistence.cpp"
        "${GS_ROOT}/firmware/common/security/nvs_association_blob_store.cpp"
        "${GS_ROOT}/firmware/common/security/runtime_frame_security.cpp"
        "${GS_ROOT}/firmware/node/sensing/sensing.cpp"
        "${GS_ROOT}/firmware/node/power/power.cpp"
        "${GS_ROOT}/firmware/node/communication/radio/node_radio.cpp"
        "${GS_ROOT}/firmware/node/storage/node_store.cpp"
        "${GS_ROOT}/firmware/node/storage/node_recovery_persistence.cpp"
        "${GS_ROOT}/firmware/node/runtime/node_runtime.cpp"
        "${GS_ROOT}/firmware/node/target/esp32c3/nvs_session_provider.cpp"
        "${GS_ROOT}/firmware/node/target/esp32c3/node_runtime_adapter.cpp"
        "${GS_ROOT}/firmware/node/target/esp32c3/node_security_link.cpp"
    INCLUDE_DIRS
        "${GS_NODE_HEALTH_GENERATED}"
        "."
        "${GS_ROOT}"
        "${GS_ROOT}/firmware/common/shared/include"
        "${GS_ROOT}/firmware/node"
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
        spi_flash
        mbedtls
)

target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_17)
target_compile_definitions(${COMPONENT_LIB} PRIVATE
    GS_HIL_BUILD=$<BOOL:${GS_HIL_BUILD}>
    GS_HIL_CONTROL=$<BOOL:${GS_HIL_CONTROL}>
    GS_HIL_FORCE_BOOT_HEALTH_FAIL=$<BOOL:${GS_HIL_FORCE_BOOT_HEALTH_FAIL}>
    GS_BAT_C8_PHYSICAL_WAKE=$<BOOL:${GS_BAT_C8_PHYSICAL_WAKE}>
    GS_BAT_C8_ACK_TRACE=$<BOOL:${GS_BAT_C8_ACK_TRACE}>
    GS_BAT_C8_FIXTURE_SECURITY=$<BOOL:${GS_BAT_C8_FIXTURE_SECURITY}>
    GS_GS68_NODE_OBSERVER=$<BOOL:${GS_GS68_NODE_OBSERVER}>
    GS68_NODE_SOURCE_COMMIT=\"${GS68_NODE_SOURCE_COMMIT}\"
    GS68_NODE_PROFILE_SHA256=\"${GS68_NODE_PROFILE_SHA256}\")
