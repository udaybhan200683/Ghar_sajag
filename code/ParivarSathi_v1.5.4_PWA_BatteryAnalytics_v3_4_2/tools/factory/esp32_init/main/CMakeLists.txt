get_filename_component(GS_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../.." ABSOLUTE)
set(SOURCES app_main.cpp
    "${GS_ROOT}/firmware/common/security/psa_commissioning_crypto.cpp"
    "${GS_ROOT}/firmware/common/security/target_identity_signer.cpp")
if(GS_FACTORY_ROLE STREQUAL "hub")
    list(APPEND SOURCES
        "${GS_ROOT}/firmware/common/transport/data_plane_codec.cpp"
        "${GS_ROOT}/firmware/common/transport/node_retirement_protocol.cpp"
        "${GS_ROOT}/firmware/hub/components/storage/durable_transition.cpp"
        "${GS_ROOT}/firmware/hub/components/storage/node_retirement_snapshot.cpp"
        "${GS_ROOT}/firmware/hub/components/storage/hub_durability_owner.cpp"
        "${GS_ROOT}/firmware/hub/components/registry/node_registry.cpp"
        "${GS_ROOT}/firmware/hub/components/registry/registry_persistence.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32/nvs_durable_blob_store.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32/nvs_durable_key_codec.cpp"
        "${GS_ROOT}/firmware/hub/target/esp32/nvs_store_inventory.cpp")
    set(HUB 1)
else()
    list(APPEND SOURCES
        "${GS_ROOT}/firmware/common/security/association_persistence.cpp"
        "${GS_ROOT}/firmware/common/security/nvs_association_blob_store.cpp"
        "${GS_ROOT}/firmware/node/components/storage/node_recovery_persistence.cpp"
        "${GS_ROOT}/firmware/node/target/esp32c3/zero_length_aead_qualification.cpp"
        "${GS_ROOT}/firmware/node/runtime/node_runtime.cpp"
        "${GS_ROOT}/firmware/node/components/sensing/sensing.cpp"
        "${GS_ROOT}/firmware/node/components/power/power.cpp"
        "${GS_ROOT}/firmware/node/components/radio/node_radio.cpp"
        "${GS_ROOT}/firmware/node/components/storage/node_store.cpp"
        "${GS_ROOT}/shared/src/logging.cpp")
    set(HUB 0)
endif()
idf_component_register(SRCS ${SOURCES}
    INCLUDE_DIRS "${GS_ROOT}" "${GS_ROOT}/shared/include" "${GS_ROOT}/firmware/hub/components" "${GS_ROOT}/firmware/node/components"
    PRIV_REQUIRES nvs_flash mbedtls esp_partition app_update esp_hw_support)
target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_17)
# This standalone development image needs the existing development signer.
# It contains no normal runtime, HIL parser, radio or FOTA worker.
target_compile_definitions(${COMPONENT_LIB} PRIVATE GS_FACTORY_HUB=${HUB} GS_HIL_BUILD=0 GS_HIL_CONTROL=1)
