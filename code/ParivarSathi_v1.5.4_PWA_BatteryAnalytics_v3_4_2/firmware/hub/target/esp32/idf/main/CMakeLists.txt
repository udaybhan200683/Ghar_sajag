set(GS_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../../..")
set(GS_HUB_SRCS
    "app_main.cpp"
    "fota_sender.cpp"
)
if(GS_HIL_BUILD)
    list(APPEND GS_HUB_SRCS "hil_control.cpp")
endif()

if(NOT EXISTS "${CMAKE_CURRENT_LIST_DIR}/node_firmware.bin")
    message(FATAL_ERROR
        "Missing node_firmware.bin. Build the C3 product and copy its app binary here before configuring the Hub.")
endif()

idf_component_register(
    SRCS
        ${GS_HUB_SRCS}
        "${GS_ROOT}/shared/src/logging.cpp"
        "${GS_ROOT}/shared/src/rules.cpp"
        "${GS_ROOT}/firmware/common/transport/data_plane_codec.cpp"
        "${GS_ROOT}/firmware/hub/components/ingest/ingest.cpp"
        "${GS_ROOT}/firmware/hub/components/registry/node_registry.cpp"
        "${GS_ROOT}/firmware/hub/components/storage/journal.cpp"
        "${GS_ROOT}/firmware/hub/components/coverage/coverage.cpp"
        "${GS_ROOT}/firmware/hub/components/rules/routine_service.cpp"
        "${GS_ROOT}/firmware/hub/runtime/hub_runtime.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32/hub_runtime_adapter.cpp"
    INCLUDE_DIRS
        "."
        "${GS_ROOT}"
        "${GS_ROOT}/shared/include"
        "${GS_ROOT}/firmware/hub/components"
    PRIV_REQUIRES
        app_update
        esp_driver_gpio
        esp_event
        esp_hw_support
        esp_netif
        esp_system
        esp_wifi
        nvs_flash
    EMBED_FILES
        "node_firmware.bin"
)

target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_17)
target_compile_definitions(${COMPONENT_LIB} PRIVATE GS_HIL_BUILD=$<BOOL:${GS_HIL_BUILD}>)
