set(GS_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../../..")
set(GS_NODE_SRCS
    "app_main.cpp"
    "fota_receiver.cpp"
)
if(GS_HIL_BUILD)
    list(APPEND GS_NODE_SRCS "hil_control.cpp")
endif()

idf_component_register(
    SRCS
        ${GS_NODE_SRCS}
        "${GS_ROOT}/firmware/node/fota/fota_receiver.cpp"
        "${GS_ROOT}/shared/src/logging.cpp"
        "${GS_ROOT}/firmware/common/transport/data_plane_codec.cpp"
        "${GS_ROOT}/firmware/common/transport/session_id.cpp"
        "${GS_ROOT}/firmware/node/components/sensing/sensing.cpp"
        "${GS_ROOT}/firmware/node/components/radio/node_radio.cpp"
        "${GS_ROOT}/firmware/node/components/storage/node_store.cpp"
        "${GS_ROOT}/firmware/node/runtime/node_runtime.cpp"
        "${GS_ROOT}/firmware/node/target/esp32c3/nvs_session_provider.cpp"
        "${GS_ROOT}/firmware/node/target/esp32c3/node_runtime_adapter.cpp"
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
)

target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_17)
target_compile_definitions(${COMPONENT_LIB} PRIVATE GS_HIL_BUILD=$<BOOL:${GS_HIL_BUILD}>)
