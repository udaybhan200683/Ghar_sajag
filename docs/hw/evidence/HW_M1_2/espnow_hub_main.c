#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#include "esp_err.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_wifi.h"
#include "nvs_flash.h"

#define ESPNOW_CHANNEL      1
#define RX_QUEUE_LEN        32
#define RX_DATA_MAX_LEN     128

static const char *TAG = "HW_M1_HUB";

typedef struct {
    uint8_t src_mac[6];
    int len;
    int8_t rssi;
    uint8_t channel;
    uint8_t data[RX_DATA_MAX_LEN + 1];
} rx_event_t;

static QueueHandle_t rx_queue = NULL;
static uint32_t rx_count = 0;
static uint32_t queue_drop_count = 0;


/*
 * ESP-NOW receive callback.
 *
 * ESP-IDF 5.1+ provides receive radio information through:
 *
 *     recv_info->rx_ctrl
 *
 * including RSSI.
 *
 * Keep this callback short because it runs in the Wi-Fi task.
 */
static void espnow_recv_cb(const esp_now_recv_info_t *recv_info,
                           const uint8_t *data,
                           int data_len)
{
    if (recv_info == NULL ||
        recv_info->src_addr == NULL ||
        data == NULL ||
        data_len <= 0) {
        return;
    }

    rx_event_t event = {0};

    memcpy(event.src_mac,
           recv_info->src_addr,
           sizeof(event.src_mac));

    /*
     * Copy RSSI/channel now.
     *
     * recv_info is only valid during this callback, therefore
     * we must not pass its pointer to another task.
     */
    if (recv_info->rx_ctrl != NULL) {
        event.rssi = recv_info->rx_ctrl->rssi;
        event.channel = recv_info->rx_ctrl->channel;
    } else {
        event.rssi = -127;
        event.channel = 0;
    }

    event.len = data_len;

    if (event.len > RX_DATA_MAX_LEN) {
        event.len = RX_DATA_MAX_LEN;
    }

    memcpy(event.data, data, event.len);

    /*
     * Null terminate so text payloads can safely be displayed.
     */
    event.data[event.len] = '\0';

    /*
     * Never block the Wi-Fi task.
     */
    if (xQueueSend(rx_queue, &event, 0) != pdTRUE) {
        queue_drop_count++;
    }
}


/*
 * Current Ghar Sajag node messages are ASCII:
 *
 * NODE=1,SEQ=34,EVENT=MOTION
 *
 * Reject control/binary characters so old ESP-NOW test packets
 * cannot produce garbage through our application logger.
 */
static bool payload_is_printable(const uint8_t *data, int len)
{
    if (data == NULL || len <= 0) {
        return false;
    }

    for (int i = 0; i < len; i++) {
        if (data[i] < 32 || data[i] > 126) {
            return false;
        }
    }

    return true;
}


/*
 * RX processing task.
 *
 * All application logging happens here rather than inside
 * the Wi-Fi callback.
 */
static void rx_task(void *arg)
{
    (void)arg;

    rx_event_t event;

    while (true) {

        if (xQueueReceive(rx_queue,
                          &event,
                          portMAX_DELAY) != pdTRUE) {
            continue;
        }

        rx_count++;

        if (payload_is_printable(event.data, event.len)) {

            ESP_LOGI(
                TAG,
                "RX#%lu | "
                "SRC=%02X:%02X:%02X:%02X:%02X:%02X | "
                "RSSI=%d dBm | CH=%u | "
                "len=%d | DATA=%.*s",
                (unsigned long)rx_count,
                event.src_mac[0],
                event.src_mac[1],
                event.src_mac[2],
                event.src_mac[3],
                event.src_mac[4],
                event.src_mac[5],
                event.rssi,
                event.channel,
                event.len,
                event.len,
                (const char *)event.data
            );

        } else {

            ESP_LOGW(
                TAG,
                "RX#%lu | "
                "SRC=%02X:%02X:%02X:%02X:%02X:%02X | "
                "RSSI=%d dBm | CH=%u | "
                "len=%d | NON-TEXT PACKET",
                (unsigned long)rx_count,
                event.src_mac[0],
                event.src_mac[1],
                event.src_mac[2],
                event.src_mac[3],
                event.src_mac[4],
                event.src_mac[5],
                event.rssi,
                event.channel,
                event.len
            );
        }

        if (queue_drop_count > 0) {

            ESP_LOGW(
                TAG,
                "RX queue drops=%lu",
                (unsigned long)queue_drop_count
            );
        }
    }
}


/*
 * Initialize Wi-Fi for ESP-NOW operation.
 */
static void wifi_init(void)
{
    ESP_ERROR_CHECK(esp_netif_init());

    esp_err_t event_ret =
        esp_event_loop_create_default();

    /*
     * This allows the code to survive if the default event loop
     * already exists for some reason.
     */
    if (event_ret != ESP_OK &&
        event_ret != ESP_ERR_INVALID_STATE) {

        ESP_ERROR_CHECK(event_ret);
    }

    wifi_init_config_t cfg =
        WIFI_INIT_CONFIG_DEFAULT();

    ESP_ERROR_CHECK(
        esp_wifi_init(&cfg)
    );

    ESP_ERROR_CHECK(
        esp_wifi_set_storage(WIFI_STORAGE_RAM)
    );

    ESP_ERROR_CHECK(
        esp_wifi_set_mode(WIFI_MODE_STA)
    );

    ESP_ERROR_CHECK(
        esp_wifi_start()
    );

    /*
     * HW-M1 current RF test baseline.
     *
     * Hub and C3 must be on the same channel.
     */
    ESP_ERROR_CHECK(
        esp_wifi_set_channel(
            ESPNOW_CHANNEL,
            WIFI_SECOND_CHAN_NONE
        )
    );

    /*
     * Disable Wi-Fi power save for hardware qualification.
     */
    ESP_ERROR_CHECK(
        esp_wifi_set_ps(WIFI_PS_NONE)
    );
}


/*
 * Initialize NVS.
 */
static void nvs_init(void)
{
    esp_err_t ret = nvs_flash_init();

    if (ret == ESP_ERR_NVS_NO_FREE_PAGES ||
        ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {

        ESP_ERROR_CHECK(
            nvs_flash_erase()
        );

        ESP_ERROR_CHECK(
            nvs_flash_init()
        );

    } else {

        ESP_ERROR_CHECK(ret);
    }
}


void app_main(void)
{
    /*
     * NVS must be initialized before Wi-Fi.
     */
    nvs_init();


    /*
     * Create application receive queue before ESP-NOW callback
     * registration so there is never a callback with no queue.
     */
    rx_queue = xQueueCreate(
        RX_QUEUE_LEN,
        sizeof(rx_event_t)
    );

    if (rx_queue == NULL) {

        ESP_LOGE(
            TAG,
            "Failed to create ESP-NOW RX queue"
        );

        return;
    }


    /*
     * Initialize Wi-Fi and lock it to the current ESP-NOW channel.
     */
    wifi_init();


    /*
     * Initialize ESP-NOW.
     */
    ESP_ERROR_CHECK(
        esp_now_init()
    );


    /*
     * Register receive callback.
     */
    ESP_ERROR_CHECK(
        esp_now_register_recv_cb(
            espnow_recv_cb
        )
    );


    /*
     * Read Hub STA MAC address.
     */
    uint8_t hub_mac[6] = {0};

    ESP_ERROR_CHECK(
        esp_wifi_get_mac(
            WIFI_IF_STA,
            hub_mac
        )
    );


    /*
     * Verify the Wi-Fi driver is actually operating on the
     * channel we requested.
     */
    uint8_t actual_channel = 0;

    wifi_second_chan_t secondary_channel =
        WIFI_SECOND_CHAN_NONE;

    ESP_ERROR_CHECK(
        esp_wifi_get_channel(
            &actual_channel,
            &secondary_channel
        )
    );


    ESP_LOGI(
        TAG,
        "========================================"
    );

    ESP_LOGI(
        TAG,
        "Ghar Sajag HW-M1.2 ESP-NOW HUB"
    );

    ESP_LOGI(
        TAG,
        "RSSI measurement enabled"
    );

    ESP_LOGI(
        TAG,
        "Configured channel : %d",
        ESPNOW_CHANNEL
    );

    ESP_LOGI(
        TAG,
        "Actual Wi-Fi channel: %u",
        actual_channel
    );

    ESP_LOGI(
        TAG,
        "HUB MAC : %02X:%02X:%02X:%02X:%02X:%02X",
        hub_mac[0],
        hub_mac[1],
        hub_mac[2],
        hub_mac[3],
        hub_mac[4],
        hub_mac[5]
    );

    ESP_LOGI(
        TAG,
        "Waiting for C3 node..."
    );

    ESP_LOGI(
        TAG,
        "========================================"
    );


    /*
     * Process packets outside the Wi-Fi callback.
     */
    BaseType_t task_result = xTaskCreate(
        rx_task,
        "espnow_rx_task",
        4096,
        NULL,
        5,
        NULL
    );

    if (task_result != pdPASS) {

        ESP_LOGE(
            TAG,
            "Failed to create ESP-NOW RX task"
        );

        return;
    }
}
