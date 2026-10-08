get_filename_component(GS_HOST_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../.." ABSOLUTE)
idf_component_register(SRCS "probe.cpp"
    "${GS_HOST_ROOT}/host/storage/native_transaction.cpp"
    "${GS_HOST_ROOT}/host/storage/compact_nvs_representation.cpp"
    "${GS_HOST_ROOT}/host/security/openssl_commissioning_crypto.cpp"
    "${GS_HOST_ROOT}/firmware/common/transport/data_plane_codec.cpp"
    "${GS_HOST_ROOT}/firmware/common/transport/node_retirement_protocol.cpp"
    "${GS_HOST_ROOT}/firmware/hub/components/storage/durable_transition.cpp"
    "${GS_HOST_ROOT}/firmware/hub/components/storage/node_retirement_snapshot.cpp"
    INCLUDE_DIRS "${GS_HOST_ROOT}" "${GS_HOST_ROOT}/shared/include"
    "${GS_HOST_ROOT}/firmware/node/components" "${GS_HOST_ROOT}/firmware/hub/components"
    REQUIRES nvs_flash PRIV_REQUIRES spi_flash)
target_link_libraries(${COMPONENT_LIB} PUBLIC crypto)
target_compile_options(${COMPONENT_LIB} PRIVATE -DGS_ENABLE_TRACE=0)

target_link_options(${COMPONENT_LIB} INTERFACE "-Wl,--wrap=esp_partition_write" "-Wl,--wrap=esp_partition_write_raw" "-Wl,--wrap=esp_partition_erase_range" "-Wl,--wrap=mkstemp")
