idf_component_register(SRCS "probe.cpp" REQUIRES nvs_flash PRIV_REQUIRES spi_flash)

target_link_options(${COMPONENT_LIB} INTERFACE "-Wl,--wrap=esp_partition_write" "-Wl,--wrap=esp_partition_write_raw" "-Wl,--wrap=esp_partition_erase_range" "-Wl,--wrap=mkstemp")
