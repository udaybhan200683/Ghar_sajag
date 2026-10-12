#include "esp_chip_info.h"
#include "esp_event.h"
#include "esp_flash.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_psram.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdint.h>

static void memory_log(const char *stage) {
    ESP_LOGI("gs_s3_diag", "MEMORY stage=%s internal_free=%u internal_min=%u internal_largest=%u psram_size=%u psram_free=%u",
        stage, (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
        (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
        (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
        (unsigned)esp_psram_get_size(), (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
}

void app_main(void) {
    esp_chip_info_t chip = {0};
    esp_chip_info(&chip);
    uint32_t flash = 0;
    ESP_ERROR_CHECK(esp_flash_get_size(NULL, &flash));
    ESP_ERROR_CHECK(chip.model == CHIP_ESP32S3 && flash == 16U * 1024U * 1024U
        && esp_psram_is_initialized() && esp_psram_get_size() == 8U * 1024U * 1024U
        ? ESP_OK : ESP_ERR_INVALID_STATE);
    ESP_LOGI("gs_s3_diag", "IDENTITY chip=ESP32-S3 revision=%u flash=%lu psram=%u",
        (unsigned)chip.revision, (unsigned long)flash, (unsigned)esp_psram_get_size());
    memory_log("boot");
    uint32_t *scratch = heap_caps_malloc(65536, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    ESP_ERROR_CHECK(scratch != NULL ? ESP_OK : ESP_ERR_NO_MEM);
    for (unsigned i = 0; i < 65536 / sizeof(*scratch); ++i) scratch[i] = 0xa5a50000U ^ i;
    for (unsigned i = 0; i < 65536 / sizeof(*scratch); ++i)
        ESP_ERROR_CHECK(scratch[i] == (0xa5a50000U ^ i) ? ESP_OK : ESP_FAIL);
    heap_caps_free(scratch);
    ESP_LOGI("gs_s3_diag", "PSRAM_SCRATCH=PASS bytes=65536 startup_memtest=enabled");
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT();
    config.nvs_enable = false;
    ESP_ERROR_CHECK(esp_wifi_init(&config));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_LOGI("gs_s3_diag", "WIFI_INIT=PASS mode=STA no_association no_persistent_configuration");
    ESP_ERROR_CHECK(esp_now_init());
    ESP_LOGI("gs_s3_diag", "ESPNOW_INIT=PASS no_peers no_application_transmissions");
    memory_log("radio_ready");
    for (unsigned cycle = 1; cycle <= 6; ++cycle) {
        vTaskDelay(pdMS_TO_TICKS(10000));
        ESP_LOGI("gs_s3_diag", "ALIVE cycle=%u main_stack_min=%u", cycle,
            (unsigned)uxTaskGetStackHighWaterMark(NULL));
        memory_log("alive");
    }
    ESP_LOGI("gs_s3_diag", "DIAGNOSTIC_COMPLETE=PASS physical_R1_qualification=PENDING");
}
