#include <stdio.h>
#include <string.h>
#include <stdbool.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "driver/gpio.h"

#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_wifi.h"
#include "nvs_flash.h"

#define PIR_GPIO          GPIO_NUM_4
#define LED_GPIO          GPIO_NUM_8

#define LED_ON            0
#define LED_OFF           1

#define ESPNOW_CHANNEL      1

#define POLL_MS            20
#define VALID_HIGH_MS      150

static const char *TAG = "GS_NODE";

static const uint8_t HUB_MAC[6] = {
    0x5C, 0x01, 0x3B, 0xBE, 0xB9, 0xF8
};

static uint32_t motion_sequence = 0;

static void blink_led(int count)
{
    for (int i = 0; i < count; i++) {
        gpio_set_level(LED_GPIO, LED_ON);
        vTaskDelay(pdMS_TO_TICKS(120));

        gpio_set_level(LED_GPIO, LED_OFF);
        vTaskDelay(pdMS_TO_TICKS(120));
    }
}

static void send_cb(const esp_now_send_info_t *info,
                    esp_now_send_status_t status)
{
    (void)info;

    if (status == ESP_NOW_SEND_SUCCESS) {
        ESP_LOGI(TAG, "DELIVERY SUCCESS");
    } else {
        ESP_LOGW(TAG, "DELIVERY FAILED");
    }
}

static void init_wifi_espnow(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();

    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_start());

    /*
     * Runtime cap: API uses units of 0.25 dBm.
     * 40 = 10 dBm.
     */
    ESP_ERROR_CHECK(esp_wifi_set_max_tx_power(40));

    ESP_ERROR_CHECK(
        esp_wifi_set_channel(
            ESPNOW_CHANNEL,
            WIFI_SECOND_CHAN_NONE
        )
    );

    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));

    ESP_ERROR_CHECK(esp_now_init());
    ESP_ERROR_CHECK(esp_now_register_send_cb(send_cb));

    esp_now_peer_info_t peer = {0};

    memcpy(peer.peer_addr, HUB_MAC, 6);
    peer.channel = 0;
    peer.ifidx = WIFI_IF_STA;
    peer.encrypt = false;

    ESP_ERROR_CHECK(esp_now_add_peer(&peer));

    uint8_t mac[6];
    uint8_t channel;
    wifi_second_chan_t secondary;
    int8_t tx_power;

    ESP_ERROR_CHECK(
        esp_wifi_get_mac(WIFI_IF_STA, mac)
    );

    ESP_ERROR_CHECK(
        esp_wifi_get_channel(&channel, &secondary)
    );

    ESP_ERROR_CHECK(
        esp_wifi_get_max_tx_power(&tx_power)
    );

    ESP_LOGI(TAG,
             "NODE MAC: %02X:%02X:%02X:%02X:%02X:%02X",
             mac[0], mac[1], mac[2],
             mac[3], mac[4], mac[5]);

    ESP_LOGI(TAG,
             "HUB MAC : %02X:%02X:%02X:%02X:%02X:%02X",
             HUB_MAC[0], HUB_MAC[1], HUB_MAC[2],
             HUB_MAC[3], HUB_MAC[4], HUB_MAC[5]);

    ESP_LOGI(TAG, "Channel : %u", channel);
    ESP_LOGI(TAG, "TX power: %.2f dBm", tx_power / 4.0);
}

static void send_motion_event(void)
{
    char message[64];

    motion_sequence++;

    snprintf(
        message,
        sizeof(message),
        "NODE=1,SEQ=%lu,EVENT=MOTION",
        (unsigned long)motion_sequence
    );

    esp_err_t err = esp_now_send(
        HUB_MAC,
        (const uint8_t *)message,
        strlen(message)
    );

    if (err == ESP_OK) {
        ESP_LOGI(TAG, "TX: %s", message);
    } else {
        ESP_LOGE(TAG,
                 "Send error: %s",
                 esp_err_to_name(err));
    }
}

void app_main(void)
{
    esp_err_t ret = nvs_flash_init();

    if (ret == ESP_ERR_NVS_NO_FREE_PAGES ||
        ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {

        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    } else {
        ESP_ERROR_CHECK(ret);
    }

    gpio_config_t led_cfg = {
        .pin_bit_mask = (1ULL << LED_GPIO),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };

    ESP_ERROR_CHECK(gpio_config(&led_cfg));
    gpio_set_level(LED_GPIO, LED_OFF);

    gpio_config_t pir_cfg = {
        .pin_bit_mask = (1ULL << PIR_GPIO),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE
    };

    ESP_ERROR_CHECK(gpio_config(&pir_cfg));

    init_wifi_espnow();

    ESP_LOGI(TAG, "Ghar Sajag PIR node starting");
    ESP_LOGI(TAG, "PIR GPIO: 4");
    ESP_LOGI(TAG, "Waiting 10 seconds for PIR stabilization");

    vTaskDelay(pdMS_TO_TICKS(10000));

    ESP_LOGI(TAG, "NODE READY");

    int high_time_ms = 0;
    bool motion_active = false;

    while (true) {

        int pir = gpio_get_level(PIR_GPIO);

        if (pir) {

            if (high_time_ms < VALID_HIGH_MS) {
                high_time_ms += POLL_MS;
            }

            if (!motion_active &&
                high_time_ms >= VALID_HIGH_MS) {

                motion_active = true;

                ESP_LOGI(TAG, "MOTION DETECTED");

                send_motion_event();
                blink_led(3);
            }

        } else {

            high_time_ms = 0;

            if (motion_active) {
                motion_active = false;
                ESP_LOGI(TAG, "MOTION CLEARED");
            }
        }

        vTaskDelay(pdMS_TO_TICKS(POLL_MS));
    }
}
