set(GS_PRODUCT_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../../../")
get_filename_component(GS_PRODUCT_ROOT "${GS_PRODUCT_ROOT}" ABSOLUTE)

idf_component_register(
    SRCS
        "${GS_PRODUCT_ROOT}/firmware/hub/components/storage/durable_event_outbox.cpp"
        "${GS_PRODUCT_ROOT}/firmware/hub/target/esp32s3/littlefs_segment_store.cpp"
    INCLUDE_DIRS
        "${GS_PRODUCT_ROOT}"
        "${GS_PRODUCT_ROOT}/firmware/hub/components"
        "${GS_PRODUCT_ROOT}/firmware/common/security"
    PRIV_REQUIRES joltwallet__littlefs
)

target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_17)
