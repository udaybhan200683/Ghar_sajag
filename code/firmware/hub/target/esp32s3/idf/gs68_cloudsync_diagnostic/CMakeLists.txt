# ESP-IDF evaluates component requirements in a generated sub-CMake context
# where the top-level GS68_CLOUDSYNC_DIAGNOSTIC_ONLY option is not propagated.
# The root project selects this component only inside the isolated diagnostic
# branch and rejects all product/C8/legacy HIL combinations before project().
# Kconfig profile assertions live in app_main.cpp: ESP-IDF evaluates this file
# once in a requirements-only CMake context before sdkconfig is available.

set(GS_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../../../")
idf_component_register(
    SRCS
        "app_main.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32s3/https_backend_channel.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32s3/cloud_trust_provider.cpp"
    INCLUDE_DIRS
        "."
        "${GS_ROOT}"
        "${GS_ROOT}/firmware/common/shared/include"
        "${GS_ROOT}/firmware/hub"
        "${GS_ROOT}/firmware/hub/cloud_sync"
    REQUIRES app_update esp_driver_usb_serial_jtag esp_http_client esp_partition esp_psram esp_system esp_timer esp_hw_support mbedtls nvs_flash spi_flash
)
target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_17)
target_compile_definitions(${COMPONENT_LIB} PRIVATE
    GS68_TEST_ONLY_BUILD=1
    GS68_SOURCE_COMMIT="${GS68_SOURCE_COMMIT}"
    GS68_PROFILE_SHA256="${GS68_PROFILE_SHA256}")
