idf_component_register(SRCS "app_main.c" INCLUDE_DIRS "."
    PRIV_REQUIRES esp_psram esp_wifi esp_netif esp_event esp_system spi_flash esp_hw_support)
