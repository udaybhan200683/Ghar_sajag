#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#include "driver/gpio.h"

#include "esp_err.h"
#include "esp_event.h"
#include "esp_idf_version.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_wifi.h"

#include "nvs_flash.h"

#include "fota_protocol.h"


#define NODE_FW_VERSION            "HW-M1-FOTA-BOOTSTRAP-1"

#define PIR_GPIO                   GPIO_NUM_4
#define LED_GPIO                   GPIO_NUM_8

#define ESPNOW_CHANNEL             1

/*
 * esp_wifi_set_max_tx_power() uses 0.25 dBm units.
 * 40 = 10 dBm.
 *
 * Keep this at the RF setting already qualified on our C3.
 */
#define C3_TX_POWER_QDBM           40

#define PIR_STABILIZATION_MS       10000
#define PIR_POLL_MS                20
#define PIR_CONFIRM_HIGH_MS        150

#define FOTA_QUEUE_LEN             8

static const char *TAG = "GS_NODE";


/* ============================================================
 * Qualified Hub
 * ============================================================
 */

static const uint8_t HUB_MAC[6] = {
    0x5C, 0x01, 0x3B, 0xBE, 0xB9, 0xF8
};


/* ============================================================
 * FOTA RX Queue
 * ============================================================
 */

typedef struct {
    uint8_t src_mac[6];
    int8_t rssi;
    gs_fota_packet_t packet;
} fota_rx_event_t;

static QueueHandle_t g_fota_queue = NULL;


/* ============================================================
 * FOTA Runtime Context
 * ============================================================
 */

typedef struct {
    bool active;

    uint32_t session_id;
    uint32_t expected_seq;

    uint32_t expected_size;
    uint32_t expected_image_crc32;

    uint32_t bytes_written;

    /*
     * CRC is maintained internally before final XOR.
     */
    uint32_t running_crc;

    esp_ota_handle_t ota_handle;

    const esp_partition_t *update_partition;
} fota_context_t;

static fota_context_t g_fota = {0};

static volatile bool g_fota_active = false;


/* ============================================================
 * PIR Runtime
 * ============================================================
 */

static uint32_t g_motion_seq = 0;


/* ============================================================
 * CRC32
 * ============================================================
 */

static uint32_t crc32_update(uint32_t crc,
                             const uint8_t *data,
                             size_t len)
{
    while (len > 0) {

        crc ^= (uint32_t)(*data++);

        for (int bit = 0; bit < 8; bit++) {

            if ((crc & 1U) != 0U) {
                crc = (crc >> 1U) ^ 0xEDB88320U;
            } else {
                crc >>= 1U;
            }
        }

        len--;
    }

    return crc;
}


static uint32_t crc32_buffer(const uint8_t *data,
                             size_t len)
{
    uint32_t crc = 0xFFFFFFFFU;

    crc = crc32_update(crc, data, len);

    return crc ^ 0xFFFFFFFFU;
}


/* ============================================================
 * LED
 * ============================================================
 */

static void led_set(bool on)
{
    /*
     * Current C3 onboard LED is active-low.
     */
    gpio_set_level(
        LED_GPIO,
        on ? 0 : 1
    );
}


static void led_blink(uint32_t count)
{
    for (uint32_t i = 0; i < count; i++) {

        led_set(true);

        vTaskDelay(
            pdMS_TO_TICKS(80)
        );

        led_set(false);

        vTaskDelay(
            pdMS_TO_TICKS(80)
        );
    }
}


/* ============================================================
 * FOTA ACK
 * ============================================================
 */

static void send_fota_ack(int32_t status,
                          uint32_t ack_seq)
{
    gs_fota_ack_t ack = {0};

    ack.magic =
        GS_FOTA_MAGIC;

    ack.protocol_version =
        GS_FOTA_PROTOCOL_VERSION;

    ack.type =
        0x80;

    ack.session_id =
        g_fota.session_id;

    ack.ack_seq =
        ack_seq;

    ack.next_seq =
        g_fota.expected_seq;

    ack.status =
        status;

    ack.bytes_written =
        g_fota.bytes_written;


    esp_err_t err =
        esp_now_send(
            HUB_MAC,
            (const uint8_t *)&ack,
            sizeof(ack)
        );


    if (err != ESP_OK) {

        ESP_LOGE(
            TAG,
            "FOTA ACK send failed: %s",
            esp_err_to_name(err)
        );
    }
}


/* ============================================================
 * Reset / Abort FOTA Session
 * ============================================================
 */

static void fota_reset(bool abort_ota)
{
    if (abort_ota &&
        g_fota.active) {

        esp_err_t err =
            esp_ota_abort(
                g_fota.ota_handle
            );

        if (err != ESP_OK) {

            ESP_LOGW(
                TAG,
                "esp_ota_abort failed: %s",
                esp_err_to_name(err)
            );
        }
    }


    memset(
        &g_fota,
        0,
        sizeof(g_fota)
    );


    g_fota_active = false;
}


/* ============================================================
 * FOTA BEGIN
 * ============================================================
 */

static void handle_fota_begin(
    const gs_fota_packet_t *packet)
{
    ESP_LOGI(
        TAG,
        "FOTA BEGIN session=%lu size=%lu crc=0x%08lX",
        (unsigned long)packet->session_id,
        (unsigned long)packet->image_size,
        (unsigned long)packet->image_crc32
    );


    /*
     * Hub may retransmit BEGIN if READY ACK was lost.
     */
    if (g_fota.active &&
        g_fota.session_id ==
            packet->session_id) {

        ESP_LOGW(
            TAG,
            "Duplicate FOTA BEGIN - re-sending READY"
        );

        send_fota_ack(
            GS_FOTA_ACK_READY,
            0
        );

        return;
    }


    /*
     * New FOTA session replaces a stale one.
     */
    if (g_fota.active) {

        ESP_LOGW(
            TAG,
            "Aborting previous FOTA session"
        );

        fota_reset(true);
    }


    const esp_partition_t *partition =
        esp_ota_get_next_update_partition(
            NULL
        );


    if (partition == NULL) {

        ESP_LOGE(
            TAG,
            "No OTA update partition available"
        );

        g_fota.session_id =
            packet->session_id;

        send_fota_ack(
            GS_FOTA_ERR_OTA_BEGIN,
            0
        );

        fota_reset(false);

        return;
    }


    if (packet->image_size == 0 ||
        packet->image_size >
            partition->size) {

        ESP_LOGE(
            TAG,
            "Invalid OTA size=%lu partition-size=%lu",
            (unsigned long)packet->image_size,
            (unsigned long)partition->size
        );

        g_fota.session_id =
            packet->session_id;

        send_fota_ack(
            GS_FOTA_ERR_BAD_SIZE,
            0
        );

        fota_reset(false);

        return;
    }


    esp_ota_handle_t ota_handle = 0;


    esp_err_t err =
        esp_ota_begin(
            partition,
            packet->image_size,
            &ota_handle
        );


    if (err != ESP_OK) {

        ESP_LOGE(
            TAG,
            "esp_ota_begin failed: %s",
            esp_err_to_name(err)
        );

        g_fota.session_id =
            packet->session_id;

        send_fota_ack(
            GS_FOTA_ERR_OTA_BEGIN,
            0
        );

        fota_reset(false);

        return;
    }


    memset(
        &g_fota,
        0,
        sizeof(g_fota)
    );


    g_fota.active =
        true;

    g_fota.session_id =
        packet->session_id;

    g_fota.expected_seq =
        0;

    g_fota.expected_size =
        packet->image_size;

    g_fota.expected_image_crc32 =
        packet->image_crc32;

    g_fota.bytes_written =
        0;

    g_fota.running_crc =
        0xFFFFFFFFU;

    g_fota.ota_handle =
        ota_handle;

    g_fota.update_partition =
        partition;

    g_fota_active =
        true;


    ESP_LOGI(
        TAG,
        "FOTA target=%s offset=0x%08lX size=%lu",
        partition->label,
        (unsigned long)partition->address,
        (unsigned long)partition->size
    );


    send_fota_ack(
        GS_FOTA_ACK_READY,
        0
    );
}


/* ============================================================
 * FOTA DATA
 * ============================================================
 */

static void handle_fota_data(
    const gs_fota_packet_t *packet)
{
    if (!g_fota.active ||
        packet->session_id !=
            g_fota.session_id) {

        ESP_LOGE(
            TAG,
            "FOTA DATA: invalid session"
        );

        send_fota_ack(
            GS_FOTA_ERR_BAD_SESSION,
            packet->seq
        );

        return;
    }


    /*
     * Packet already written.
     *
     * This can happen when ACK is lost and Hub retries.
     */
    if (packet->seq <
        g_fota.expected_seq) {

        ESP_LOGW(
            TAG,
            "Duplicate FOTA DATA seq=%lu expected=%lu",
            (unsigned long)packet->seq,
            (unsigned long)g_fota.expected_seq
        );

        send_fota_ack(
            GS_FOTA_ACK_DUPLICATE,
            packet->seq
        );

        return;
    }


    if (packet->seq !=
        g_fota.expected_seq) {

        ESP_LOGE(
            TAG,
            "FOTA sequence error rx=%lu expected=%lu",
            (unsigned long)packet->seq,
            (unsigned long)g_fota.expected_seq
        );

        send_fota_ack(
            GS_FOTA_ERR_BAD_SEQ,
            packet->seq
        );

        return;
    }


    if (packet->payload_len == 0 ||
        packet->payload_len >
            GS_FOTA_CHUNK_SIZE) {

        ESP_LOGE(
            TAG,
            "Invalid FOTA payload length=%u",
            packet->payload_len
        );

        send_fota_ack(
            GS_FOTA_ERR_BAD_SIZE,
            packet->seq
        );

        return;
    }


    if ((g_fota.bytes_written +
         packet->payload_len) >
        g_fota.expected_size) {

        ESP_LOGE(
            TAG,
            "FOTA payload exceeds image size"
        );

        send_fota_ack(
            GS_FOTA_ERR_BAD_SIZE,
            packet->seq
        );

        return;
    }


    uint32_t calculated_crc =
        crc32_buffer(
            packet->payload,
            packet->payload_len
        );


    if (calculated_crc !=
        packet->payload_crc32) {

        ESP_LOGE(
            TAG,
            "Chunk CRC mismatch seq=%lu expected=0x%08lX calculated=0x%08lX",
            (unsigned long)packet->seq,
            (unsigned long)packet->payload_crc32,
            (unsigned long)calculated_crc
        );

        send_fota_ack(
            GS_FOTA_ERR_BAD_CRC,
            packet->seq
        );

        return;
    }


    esp_err_t err =
        esp_ota_write(
            g_fota.ota_handle,
            packet->payload,
            packet->payload_len
        );


    if (err != ESP_OK) {

        ESP_LOGE(
            TAG,
            "esp_ota_write failed seq=%lu: %s",
            (unsigned long)packet->seq,
            esp_err_to_name(err)
        );

        send_fota_ack(
            GS_FOTA_ERR_OTA_WRITE,
            packet->seq
        );

        fota_reset(true);

        return;
    }


    g_fota.running_crc =
        crc32_update(
            g_fota.running_crc,
            packet->payload,
            packet->payload_len
        );


    g_fota.bytes_written +=
        packet->payload_len;


    g_fota.expected_seq++;


    if ((packet->seq % 100U) == 0U ||
        g_fota.bytes_written ==
            g_fota.expected_size) {

        uint32_t percentage =
            (g_fota.bytes_written * 100U) /
            g_fota.expected_size;


        ESP_LOGI(
            TAG,
            "FOTA progress %lu/%lu bytes (%lu%%)",
            (unsigned long)g_fota.bytes_written,
            (unsigned long)g_fota.expected_size,
            (unsigned long)percentage
        );
    }


    send_fota_ack(
        GS_FOTA_ACK_DATA_OK,
        packet->seq
    );
}


/* ============================================================
 * FOTA END
 * ============================================================
 */

static void handle_fota_end(
    const gs_fota_packet_t *packet)
{
    if (!g_fota.active ||
        packet->session_id !=
            g_fota.session_id) {

        ESP_LOGE(
            TAG,
            "FOTA END: invalid session"
        );

        send_fota_ack(
            GS_FOTA_ERR_BAD_SESSION,
            packet->seq
        );

        return;
    }


    if (g_fota.bytes_written !=
        g_fota.expected_size) {

        ESP_LOGE(
            TAG,
            "FOTA size mismatch written=%lu expected=%lu",
            (unsigned long)g_fota.bytes_written,
            (unsigned long)g_fota.expected_size
        );

        send_fota_ack(
            GS_FOTA_ERR_BAD_SIZE,
            packet->seq
        );

        return;
    }


    uint32_t final_crc =
        g_fota.running_crc ^
        0xFFFFFFFFU;


    if (final_crc !=
        g_fota.expected_image_crc32) {

        ESP_LOGE(
            TAG,
            "Image CRC mismatch expected=0x%08lX actual=0x%08lX",
            (unsigned long)g_fota.expected_image_crc32,
            (unsigned long)final_crc
        );

        send_fota_ack(
            GS_FOTA_ERR_BAD_CRC,
            packet->seq
        );

        fota_reset(true);

        return;
    }


    esp_err_t err =
        esp_ota_end(
            g_fota.ota_handle
        );


    if (err != ESP_OK) {

        ESP_LOGE(
            TAG,
            "esp_ota_end failed: %s",
            esp_err_to_name(err)
        );

        send_fota_ack(
            GS_FOTA_ERR_OTA_END,
            packet->seq
        );

        fota_reset(false);

        return;
    }


    err =
        esp_ota_set_boot_partition(
            g_fota.update_partition
        );


    if (err != ESP_OK) {

        ESP_LOGE(
            TAG,
            "esp_ota_set_boot_partition failed: %s",
            esp_err_to_name(err)
        );

        send_fota_ack(
            GS_FOTA_ERR_SET_BOOT,
            packet->seq
        );

        fota_reset(false);

        return;
    }


    ESP_LOGI(
        TAG,
        "FOTA COMPLETE"
    );

    ESP_LOGI(
        TAG,
        "Next boot partition: %s",
        g_fota.update_partition->label
    );


    send_fota_ack(
        GS_FOTA_ACK_COMPLETE,
        packet->seq
    );


    /*
     * Allow final ESP-NOW ACK time to leave the radio.
     */
    vTaskDelay(
        pdMS_TO_TICKS(1000)
    );


    ESP_LOGI(
        TAG,
        "Rebooting into updated image"
    );


    esp_restart();
}


/* ============================================================
 * FOTA ABORT
 * ============================================================
 */

static void handle_fota_abort(
    const gs_fota_packet_t *packet)
{
    if (g_fota.active &&
        packet->session_id ==
            g_fota.session_id) {

        ESP_LOGW(
            TAG,
            "FOTA aborted by Hub"
        );

        fota_reset(true);
    }
}


/* ============================================================
 * FOTA Worker Task
 * ============================================================
 */

static void fota_task(void *arg)
{
    (void)arg;

    fota_rx_event_t event;


    while (true) {

        if (xQueueReceive(
                g_fota_queue,
                &event,
                portMAX_DELAY) != pdTRUE) {

            continue;
        }


        const gs_fota_packet_t *packet =
            &event.packet;


        if (packet->magic !=
                GS_FOTA_MAGIC ||
            packet->protocol_version !=
                GS_FOTA_PROTOCOL_VERSION) {

            continue;
        }


        ESP_LOGD(
            TAG,
            "FOTA RX type=%u seq=%lu RSSI=%d",
            packet->type,
            (unsigned long)packet->seq,
            event.rssi
        );


        switch (packet->type) {

            case GS_FOTA_MSG_BEGIN:

                handle_fota_begin(
                    packet
                );

                break;


            case GS_FOTA_MSG_DATA:

                handle_fota_data(
                    packet
                );

                break;


            case GS_FOTA_MSG_END:

                handle_fota_end(
                    packet
                );

                break;


            case GS_FOTA_MSG_ABORT:

                handle_fota_abort(
                    packet
                );

                break;


            default:

                ESP_LOGW(
                    TAG,
                    "Unknown FOTA message type=%u",
                    packet->type
                );

                break;
        }
    }
}


/* ============================================================
 * ESP-NOW Receive Callback
 * ============================================================
 */

static void espnow_recv_cb(
    const esp_now_recv_info_t *recv_info,
    const uint8_t *data,
    int data_len)
{
    if (recv_info == NULL ||
        recv_info->src_addr == NULL ||
        data == NULL) {

        return;
    }


    /*
     * Accept FOTA only from our Hub.
     */
    if (memcmp(
            recv_info->src_addr,
            HUB_MAC,
            sizeof(HUB_MAC)) != 0) {

        return;
    }


    /*
     * FOTA transport packets have fixed size.
     */
    if (data_len !=
        (int)sizeof(gs_fota_packet_t)) {

        return;
    }


    uint32_t magic = 0;


    memcpy(
        &magic,
        data,
        sizeof(magic)
    );


    if (magic != GS_FOTA_MAGIC) {
        return;
    }


    fota_rx_event_t event = {0};


    memcpy(
        event.src_mac,
        recv_info->src_addr,
        sizeof(event.src_mac)
    );


    if (recv_info->rx_ctrl != NULL) {

        event.rssi =
            recv_info->rx_ctrl->rssi;

    } else {

        event.rssi =
            -127;
    }


    memcpy(
        &event.packet,
        data,
        sizeof(event.packet)
    );


    /*
     * Never block the ESP-NOW/Wi-Fi callback.
     */
    if (xQueueSend(
            g_fota_queue,
            &event,
            0) != pdTRUE) {

        /*
         * The Hub sender will use stop-and-wait ACK flow,
         * therefore queue overflow should not occur normally.
         */
    }
}


/* ============================================================
 * ESP-NOW Send Callback
 * ============================================================
 */

#if ESP_IDF_VERSION_MAJOR >= 6

static void espnow_send_cb(
    const esp_now_send_info_t *tx_info,
    esp_now_send_status_t status)
{
    (void)tx_info;


    if (status ==
        ESP_NOW_SEND_SUCCESS) {

        ESP_LOGD(
            TAG,
            "ESP-NOW MAC delivery success"
        );

    } else {

        ESP_LOGW(
            TAG,
            "ESP-NOW MAC delivery failed"
        );
    }
}

#else

static void espnow_send_cb(
    const uint8_t *mac_addr,
    esp_now_send_status_t status)
{
    (void)mac_addr;


    if (status ==
        ESP_NOW_SEND_SUCCESS) {

        ESP_LOGD(
            TAG,
            "ESP-NOW MAC delivery success"
        );

    } else {

        ESP_LOGW(
            TAG,
            "ESP-NOW MAC delivery failed"
        );
    }
}

#endif


/* ============================================================
 * Motion Event
 * ============================================================
 */

static void send_motion_event(void)
{
    /*
     * Suppress normal RF traffic while transferring firmware.
     */
    if (g_fota_active) {

        ESP_LOGW(
            TAG,
            "Motion detected during FOTA - RF report suppressed"
        );

        return;
    }


    g_motion_seq++;


    char message[64];


    int len =
        snprintf(
            message,
            sizeof(message),
            "NODE=1,SEQ=%lu,EVENT=MOTION",
            (unsigned long)g_motion_seq
        );


    if (len <= 0 ||
        len >= (int)sizeof(message)) {

        ESP_LOGE(
            TAG,
            "Failed to build motion message"
        );

        return;
    }


    ESP_LOGI(
        TAG,
        "MOTION DETECTED"
    );


    ESP_LOGI(
        TAG,
        "TX: %s",
        message
    );


    esp_err_t err =
        esp_now_send(
            HUB_MAC,
            (const uint8_t *)message,
            (size_t)len
        );


    if (err != ESP_OK) {

        ESP_LOGE(
            TAG,
            "Motion TX failed: %s",
            esp_err_to_name(err)
        );
    }


    led_blink(3);
}


/* ============================================================
 * PIR Task
 * ============================================================
 */

static void pir_task(void *arg)
{
    (void)arg;


    ESP_LOGI(
        TAG,
        "PIR stabilizing for %d ms",
        PIR_STABILIZATION_MS
    );


    vTaskDelay(
        pdMS_TO_TICKS(
            PIR_STABILIZATION_MS
        )
    );


    ESP_LOGI(
        TAG,
        "PIR READY"
    );


    bool motion_active = false;

    uint32_t high_time_ms = 0;


    while (true) {

        int level =
            gpio_get_level(
                PIR_GPIO
            );


        if (level != 0) {

            if (!motion_active) {

                high_time_ms +=
                    PIR_POLL_MS;


                if (high_time_ms >=
                    PIR_CONFIRM_HIGH_MS) {

                    motion_active =
                        true;

                    send_motion_event();
                }
            }

        } else {

            if (motion_active) {

                ESP_LOGI(
                    TAG,
                    "MOTION CLEARED"
                );
            }


            motion_active =
                false;

            high_time_ms =
                0;
        }


        vTaskDelay(
            pdMS_TO_TICKS(
                PIR_POLL_MS
            )
        );
    }
}


/* ============================================================
 * GPIO
 * ============================================================
 */

static void gpio_init_node(void)
{
    gpio_config_t pir_cfg = {
        .pin_bit_mask =
            (1ULL << PIR_GPIO),

        .mode =
            GPIO_MODE_INPUT,

        .pull_up_en =
            GPIO_PULLUP_DISABLE,

        .pull_down_en =
            GPIO_PULLDOWN_ENABLE,

        .intr_type =
            GPIO_INTR_DISABLE
    };


    ESP_ERROR_CHECK(
        gpio_config(
            &pir_cfg
        )
    );


    gpio_config_t led_cfg = {
        .pin_bit_mask =
            (1ULL << LED_GPIO),

        .mode =
            GPIO_MODE_OUTPUT,

        .pull_up_en =
            GPIO_PULLUP_DISABLE,

        .pull_down_en =
            GPIO_PULLDOWN_DISABLE,

        .intr_type =
            GPIO_INTR_DISABLE
    };


    ESP_ERROR_CHECK(
        gpio_config(
            &led_cfg
        )
    );


    led_set(false);
}


/* ============================================================
 * NVS
 * ============================================================
 */

static void nvs_init_node(void)
{
    esp_err_t ret =
        nvs_flash_init();


    if (ret ==
            ESP_ERR_NVS_NO_FREE_PAGES ||
        ret ==
            ESP_ERR_NVS_NEW_VERSION_FOUND) {

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


/* ============================================================
 * Wi-Fi
 * ============================================================
 */

static void wifi_init_node(void)
{
    ESP_ERROR_CHECK(
        esp_netif_init()
    );


    esp_err_t event_ret =
        esp_event_loop_create_default();


    if (event_ret != ESP_OK &&
        event_ret !=
            ESP_ERR_INVALID_STATE) {

        ESP_ERROR_CHECK(
            event_ret
        );
    }


    wifi_init_config_t cfg =
        WIFI_INIT_CONFIG_DEFAULT();


    ESP_ERROR_CHECK(
        esp_wifi_init(
            &cfg
        )
    );


    ESP_ERROR_CHECK(
        esp_wifi_set_storage(
            WIFI_STORAGE_RAM
        )
    );


    ESP_ERROR_CHECK(
        esp_wifi_set_mode(
            WIFI_MODE_STA
        )
    );


    ESP_ERROR_CHECK(
        esp_wifi_start()
    );


    ESP_ERROR_CHECK(
        esp_wifi_set_ps(
            WIFI_PS_NONE
        )
    );


    ESP_ERROR_CHECK(
        esp_wifi_set_channel(
            ESPNOW_CHANNEL,
            WIFI_SECOND_CHAN_NONE
        )
    );


    ESP_ERROR_CHECK(
        esp_wifi_set_max_tx_power(
            C3_TX_POWER_QDBM
        )
    );
}


/* ============================================================
 * ESP-NOW
 * ============================================================
 */

static void espnow_init_node(void)
{
    ESP_ERROR_CHECK(
        esp_now_init()
    );


    ESP_ERROR_CHECK(
        esp_now_register_recv_cb(
            espnow_recv_cb
        )
    );


    ESP_ERROR_CHECK(
        esp_now_register_send_cb(
            espnow_send_cb
        )
    );


    esp_now_peer_info_t peer = {0};


    memcpy(
        peer.peer_addr,
        HUB_MAC,
        sizeof(HUB_MAC)
    );


    /*
     * 0 = use current Wi-Fi channel.
     */
    peer.channel =
        0;

    peer.ifidx =
        WIFI_IF_STA;

    peer.encrypt =
        false;


    if (!esp_now_is_peer_exist(
            HUB_MAC)) {

        ESP_ERROR_CHECK(
            esp_now_add_peer(
                &peer
            )
        );
    }
}


/* ============================================================
 * OTA Rollback Validation
 * ============================================================
 */

static void ota_validation_task(void *arg)
{
    (void)arg;


    const esp_partition_t *running =
        esp_ota_get_running_partition();


    esp_ota_img_states_t state;


    esp_err_t err =
        esp_ota_get_state_partition(
            running,
            &state
        );


    if (err == ESP_OK &&
        state ==
            ESP_OTA_IMG_PENDING_VERIFY) {

        ESP_LOGW(
            TAG,
            "OTA image pending validation"
        );


        /*
         * Basic application-health window.
         *
         * Later this will be upgraded to validate radio,
         * storage, sensor and Hub communication before
         * confirming the firmware.
         */
        vTaskDelay(
            pdMS_TO_TICKS(5000)
        );


        err =
            esp_ota_mark_app_valid_cancel_rollback();


        if (err == ESP_OK) {

            ESP_LOGI(
                TAG,
                "OTA image marked VALID"
            );

        } else {

            ESP_LOGE(
                TAG,
                "Could not mark OTA image valid: %s",
                esp_err_to_name(err)
            );
        }
    }


    vTaskDelete(NULL);
}


/* ============================================================
 * Application Entry
 * ============================================================
 */

void app_main(void)
{
    ESP_LOGI(
        TAG,
        "========================================"
    );

    ESP_LOGI(
        TAG,
        "Ghar Sajag C3 Node"
    );

    ESP_LOGI(
        TAG,
        "Firmware: %s",
        NODE_FW_VERSION
    );

    ESP_LOGI(
        TAG,
        "ESP-NOW channel: %d",
        ESPNOW_CHANNEL
    );

    ESP_LOGI(
        TAG,
        "TX power: 10 dBm (API=%d)",
        C3_TX_POWER_QDBM
    );

    ESP_LOGI(
        TAG,
        "========================================"
    );


    nvs_init_node();

    gpio_init_node();

    wifi_init_node();


    g_fota_queue =
        xQueueCreate(
            FOTA_QUEUE_LEN,
            sizeof(fota_rx_event_t)
        );


    if (g_fota_queue == NULL) {

        ESP_LOGE(
            TAG,
            "Failed to create FOTA queue"
        );

        return;
    }


    espnow_init_node();


    const esp_partition_t *running =
        esp_ota_get_running_partition();


    ESP_LOGI(
        TAG,
        "Running partition: %s @ 0x%08lX",
        running->label,
        (unsigned long)running->address
    );


    if (xTaskCreate(
            fota_task,
            "gs_fota",
            6144,
            NULL,
            8,
            NULL) != pdPASS) {

        ESP_LOGE(
            TAG,
            "Failed to create FOTA task"
        );

        return;
    }


    if (xTaskCreate(
            pir_task,
            "gs_pir",
            4096,
            NULL,
            5,
            NULL) != pdPASS) {

        ESP_LOGE(
            TAG,
            "Failed to create PIR task"
        );

        return;
    }


    if (xTaskCreate(
            ota_validation_task,
            "gs_ota_validate",
            3072,
            NULL,
            4,
            NULL) != pdPASS) {

        ESP_LOGE(
            TAG,
            "Failed to create OTA validation task"
        );

        return;
    }


    ESP_LOGI(
        TAG,
        "NODE READY"
    );
}
