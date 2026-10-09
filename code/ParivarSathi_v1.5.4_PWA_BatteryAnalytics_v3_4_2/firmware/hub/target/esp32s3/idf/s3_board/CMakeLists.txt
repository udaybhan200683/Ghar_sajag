# Configuration-only dependency: initialize PSRAM through native ESP-IDF startup.
# Keep the original Hub app_main and all shared processing unchanged.
idf_component_register(INCLUDE_DIRS "." REQUIRES esp_psram)
