set(GS_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../../..")
set(GS_NODE_SRCS
    "app_main.cpp"
    "fota_receiver.cpp"
)
if(GS_HIL_BUILD OR GS_HIL_CONTROL)
    list(APPEND GS_NODE_SRCS "hil_control.cpp")
endif()

idf_component_register(
    SRCS
        ${GS_NODE_SRCS}
        "${GS_ROOT}/firmware/node/fota/fota_receiver.cpp"
        "${GS_ROOT}/firmware/node/fota/secure_fota_adapter.cpp"
        "${GS_ROOT}/firmware/common/transport/fota_secure_wire.cpp"
        "${GS_ROOT}/firmware/node/fota/boot_health_gate.cpp"
        "${GS_ROOT}/shared/src/logging.cpp"
        "${GS_ROOT}/firmware/common/transport/data_plane_codec.cpp"
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
        "${GS_ROOT}/firmware/node/components/sensing/sensing.cpp"
        "${GS_ROOT}/firmware/node/components/power/power.cpp"
        "${GS_ROOT}/firmware/node/components/radio/node_radio.cpp"
        "${GS_ROOT}/firmware/node/components/storage/node_store.cpp"
        "${GS_ROOT}/firmware/node/components/storage/node_recovery_persistence.cpp"
        "${GS_ROOT}/firmware/node/runtime/node_runtime.cpp"
        "${GS_ROOT}/firmware/node/target/esp32c3/nvs_session_provider.cpp"
        "${GS_ROOT}/firmware/node/target/esp32c3/node_runtime_adapter.cpp"
        "${GS_ROOT}/firmware/node/target/esp32c3/node_security_link.cpp"
    INCLUDE_DIRS
        "."
        "${GS_ROOT}"
        "${GS_ROOT}/shared/include"
        "${GS_ROOT}/firmware/node/components"
    PRIV_REQUIRES
        app_update
        esp_driver_gpio
        esp_event
        esp_netif
        esp_system
        esp_timer
        esp_wifi
        nvs_flash
        mbedtls
)

target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_17)
target_compile_definitions(${COMPONENT_LIB} PRIVATE
    GS_HIL_BUILD=$<BOOL:${GS_HIL_BUILD}>
    GS_HIL_CONTROL=$<BOOL:${GS_HIL_CONTROL}>)
