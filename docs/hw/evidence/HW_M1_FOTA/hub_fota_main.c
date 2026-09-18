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
#include "esp_system.h"
#include "esp_random.h"
#include "esp_wifi.h"

#include "nvs_flash.h"

#include "fota_protocol.h"


#define HUB_FW_VERSION             "HW-M1-FOTA-SENDER-1"

#define ESPNOW_CHANNEL             1

#define RX_QUEUE_LEN               32
#define RX_DATA_MAX_LEN            128

#define FOTA_ACK_QUEUE_LEN         8
#define FOTA_START_QUEUE_LEN       1

#define FOTA_ACK_TIMEOUT_MS        1500
#define FOTA_MAX_RETRIES           8

/*
 * ESP32 DevKit BOOT button = GPIO0.
 *
 * Hold BOOT while application is already running for about
 * 2 seconds to start the NODE FOTA test.
 *
 * Do NOT hold BOOT while resetting/powering up, because that
 * enters ROM download mode.
 */
#define FOTA_TRIGGER_GPIO          GPIO_NUM_0
#define FOTA_TRIGGER_HOLD_MS       2000
#define FOTA_TRIGGER_POLL_MS       50


static const char *TAG = "HW_M1_HUB";


/*
 * Qualified C3 node.
 */
static const uint8_t NODE_MAC[6] = {
    0x14, 0x63, 0x93, 0xC5, 0xD1, 0x58
};


/*
 * Embedded C3 application image.
 *
 * This is temporary for HW-M1 FOTA qualification.
 *
 * Production architecture will obtain firmware from the
 * backend rather than permanently embedding node firmware
 * inside the Hub application.
 */
extern const uint8_t node_firmware_start[]
    asm("_binary_node_firmware_bin_start");

extern const uint8_t node_firmware_end[]
    asm("_binary_node_firmware_bin_end");


_Static_assert(
    sizeof(gs_fota_packet_t) <= 250,
    "FOTA packet exceeds ESP-NOW v1 packet limit"
);

_Static_assert(
    sizeof(gs_fota_ack_t) <= 250,
    "FOTA ACK exceeds ESP-NOW packet limit"
);


/* ============================================================
 * Normal node-event RX queue
 * ============================================================
 */

typedef struct {
    uint8_t src_mac[6];

    int len;

    int8_t rssi;
    uint8_t channel;

    uint8_t data[RX_DATA_MAX_LEN + 1];
} rx_event_t;


static QueueHandle_t g_rx_queue = NULL;


/* ============================================================
 * FOTA ACK queue
 * ============================================================
 */

typedef struct {
    uint8_t src_mac[6];

    int8_t rssi;

    gs_fota_ack_t ack;
} fota_ack_event_t;


static QueueHandle_t g_fota_ack_queue = NULL;


/* ============================================================
 * FOTA start queue
 * ============================================================
 */

static QueueHandle_t g_fota_start_queue = NULL;


static volatile bool g_fota_running = false;


static uint32_t g_rx_count = 0;
static uint32_t g_rx_queue_drop_count = 0;
static uint32_t g_ack_queue_drop_count = 0;


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

                crc =
                    (crc >> 1U) ^
                    0xEDB88320U;

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
    uint32_t crc =
        0xFFFFFFFFU;

    crc =
        crc32_update(
            crc,
            data,
            len
        );

    return crc ^
           0xFFFFFFFFU;
}


/* ============================================================
 * Printable payload check
 * ============================================================
 */

static bool payload_is_printable(const uint8_t *data,
                                 int len)
{
    if (data == NULL ||
        len <= 0) {

        return false;
    }


    for (int i = 0;
         i < len;
         i++) {

        if (data[i] < 32 ||
            data[i] > 126) {

            return false;
        }
    }


    return true;
}


/* ============================================================
 * ESP-NOW receive callback
 * ============================================================
 */

static void espnow_recv_cb(
    const esp_now_recv_info_t *recv_info,
    const uint8_t *data,
    int data_len)
{
    if (recv_info == NULL ||
        recv_info->src_addr == NULL ||
        data == NULL ||
        data_len <= 0) {

        return;
    }


    /*
     * --------------------------------------------------------
     * First determine whether this is a FOTA ACK.
     * --------------------------------------------------------
     */

    if (data_len ==
        (int)sizeof(gs_fota_ack_t)) {

        gs_fota_ack_t ack;

        memcpy(
            &ack,
            data,
            sizeof(ack)
        );


        if (ack.magic ==
                GS_FOTA_MAGIC &&
            ack.protocol_version ==
                GS_FOTA_PROTOCOL_VERSION &&
            ack.type == 0x80) {

            /*
             * Accept FOTA ACKs only from our qualified C3.
             */
            if (memcmp(
                    recv_info->src_addr,
                    NODE_MAC,
                    sizeof(NODE_MAC)) != 0) {

                return;
            }


            fota_ack_event_t event = {0};


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
                &event.ack,
                &ack,
                sizeof(event.ack)
            );


            if (xQueueSend(
                    g_fota_ack_queue,
                    &event,
                    0) != pdTRUE) {

                g_ack_queue_drop_count++;
            }


            return;
        }
    }


    /*
     * --------------------------------------------------------
     * Normal node event.
     * --------------------------------------------------------
     */

    rx_event_t event = {0};


    memcpy(
        event.src_mac,
        recv_info->src_addr,
        sizeof(event.src_mac)
    );


    if (recv_info->rx_ctrl != NULL) {

        event.rssi =
            recv_info->rx_ctrl->rssi;

        event.channel =
            recv_info->rx_ctrl->channel;

    } else {

        event.rssi =
            -127;

        event.channel =
            0;
    }


    event.len =
        data_len;


    if (event.len >
        RX_DATA_MAX_LEN) {

        event.len =
            RX_DATA_MAX_LEN;
    }


    memcpy(
        event.data,
        data,
        event.len
    );


    event.data[event.len] =
        '\0';


    if (xQueueSend(
            g_rx_queue,
            &event,
            0) != pdTRUE) {

        g_rx_queue_drop_count++;
    }
}


/* ============================================================
 * ESP-NOW TX callback
 * ============================================================
 */

#if ESP_IDF_VERSION_MAJOR >= 6

static void espnow_send_cb(
    const esp_now_send_info_t *tx_info,
    esp_now_send_status_t status)
{
    (void)tx_info;


    if (status !=
        ESP_NOW_SEND_SUCCESS) {

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


    if (status !=
        ESP_NOW_SEND_SUCCESS) {

        ESP_LOGW(
            TAG,
            "ESP-NOW MAC delivery failed"
        );
    }
}

#endif


/* ============================================================
 * Normal RX processing task
 * ============================================================
 */

static void rx_task(void *arg)
{
    (void)arg;


    rx_event_t event;


    while (true) {

        if (xQueueReceive(
                g_rx_queue,
                &event,
                portMAX_DELAY) != pdTRUE) {

            continue;
        }


        g_rx_count++;


        if (payload_is_printable(
                event.data,
                event.len)) {

            ESP_LOGI(
                TAG,
                "RX#%lu | "
                "SRC=%02X:%02X:%02X:%02X:%02X:%02X | "
                "RSSI=%d dBm | CH=%u | "
                "len=%d | DATA=%.*s",

                (unsigned long)g_rx_count,

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
                "len=%d | NON-TEXT",

                (unsigned long)g_rx_count,

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


        if (g_rx_queue_drop_count > 0) {

            ESP_LOGW(
                TAG,
                "RX queue drops=%lu",
                (unsigned long)
                    g_rx_queue_drop_count
            );
        }
    }
}


/* ============================================================
 * Clear stale ACKs
 * ============================================================
 */

static void clear_fota_ack_queue(void)
{
    fota_ack_event_t stale;


    while (xQueueReceive(
               g_fota_ack_queue,
               &stale,
               0) == pdTRUE) {

        /* discard */
    }
}


/* ============================================================
 * Wait for application-layer FOTA ACK
 * ============================================================
 */

static bool wait_for_fota_ack(
    uint32_t session_id,
    uint32_t expected_ack_seq,
    int32_t expected_status,
    bool allow_duplicate)
{
    TickType_t start =
        xTaskGetTickCount();


    TickType_t timeout =
        pdMS_TO_TICKS(
            FOTA_ACK_TIMEOUT_MS
        );


    while ((xTaskGetTickCount() -
            start) < timeout) {

        TickType_t elapsed =
            xTaskGetTickCount() -
            start;


        TickType_t remaining =
            timeout -
            elapsed;


        fota_ack_event_t event;


        if (xQueueReceive(
                g_fota_ack_queue,
                &event,
                remaining) != pdTRUE) {

            return false;
        }


        const gs_fota_ack_t *ack =
            &event.ack;


        if (ack->session_id !=
            session_id) {

            ESP_LOGW(
                TAG,
                "Ignoring ACK from stale session=%lu",
                (unsigned long)
                    ack->session_id
            );

            continue;
        }


        if (ack->ack_seq !=
            expected_ack_seq) {

            ESP_LOGW(
                TAG,
                "Ignoring unexpected ACK seq=%lu expected=%lu",
                (unsigned long)
                    ack->ack_seq,
                (unsigned long)
                    expected_ack_seq
            );

            continue;
        }


        if (ack->status <
            0) {

            ESP_LOGE(
                TAG,
                "NODE FOTA error status=%ld "
                "seq=%lu next=%lu bytes=%lu RSSI=%d",

                (long)ack->status,

                (unsigned long)
                    ack->ack_seq,

                (unsigned long)
                    ack->next_seq,

                (unsigned long)
                    ack->bytes_written,

                event.rssi
            );


            return false;
        }


        if (ack->status ==
            expected_status) {

            return true;
        }


        if (allow_duplicate &&
            ack->status ==
                GS_FOTA_ACK_DUPLICATE) {

            return true;
        }


        ESP_LOGW(
            TAG,
            "Unexpected ACK status=%ld seq=%lu",
            (long)ack->status,
            (unsigned long)
                ack->ack_seq
        );
    }


    return false;
}


/* ============================================================
 * Send one FOTA packet with retry
 * ============================================================
 */

static bool send_fota_packet_with_retry(
    const gs_fota_packet_t *packet,
    int32_t expected_status,
    bool allow_duplicate)
{
    for (int attempt = 1;
         attempt <= FOTA_MAX_RETRIES;
         attempt++) {

        clear_fota_ack_queue();


        esp_err_t err =
            esp_now_send(
                NODE_MAC,
                (const uint8_t *)packet,
                sizeof(*packet)
            );


        if (err != ESP_OK) {

            ESP_LOGW(
                TAG,
                "FOTA send failed seq=%lu "
                "attempt=%d/%d: %s",

                (unsigned long)
                    packet->seq,

                attempt,
                FOTA_MAX_RETRIES,

                esp_err_to_name(err)
            );


            vTaskDelay(
                pdMS_TO_TICKS(100)
            );


            continue;
        }


        if (wait_for_fota_ack(
                packet->session_id,
                packet->seq,
                expected_status,
                allow_duplicate)) {

            return true;
        }


        ESP_LOGW(
            TAG,
            "FOTA ACK timeout/reject "
            "seq=%lu attempt=%d/%d",

            (unsigned long)
                packet->seq,

            attempt,
            FOTA_MAX_RETRIES
        );


        vTaskDelay(
            pdMS_TO_TICKS(100)
        );
    }


    return false;
}


/* ============================================================
 * Send FOTA ABORT
 * ============================================================
 */

static void send_fota_abort(
    uint32_t session_id,
    uint32_t seq)
{
    gs_fota_packet_t packet = {0};


    packet.magic =
        GS_FOTA_MAGIC;

    packet.protocol_version =
        GS_FOTA_PROTOCOL_VERSION;

    packet.type =
        GS_FOTA_MSG_ABORT;

    packet.session_id =
        session_id;

    packet.seq =
        seq;


    esp_err_t err =
        esp_now_send(
            NODE_MAC,
            (const uint8_t *)&packet,
            sizeof(packet)
        );


    if (err != ESP_OK) {

        ESP_LOGW(
            TAG,
            "Could not send FOTA ABORT: %s",
            esp_err_to_name(err)
        );
    }
}


/* ============================================================
 * Perform complete C3 FOTA transfer
 * ============================================================
 */

static bool perform_node_fota(void)
{
    const uint8_t *image =
        node_firmware_start;


    size_t image_size =
        (size_t)(
            node_firmware_end -
            node_firmware_start
        );


    if (image_size == 0) {

        ESP_LOGE(
            TAG,
            "Embedded C3 firmware image is empty"
        );

        return false;
    }


    if (image_size >
        UINT32_MAX) {

        ESP_LOGE(
            TAG,
            "Embedded C3 image too large"
        );

        return false;
    }


    uint32_t image_crc =
        crc32_buffer(
            image,
            image_size
        );


    uint32_t session_id =
        esp_random();


    if (session_id == 0) {

        session_id =
            1;
    }


    uint32_t total_chunks =
        (uint32_t)(
            (image_size +
             GS_FOTA_CHUNK_SIZE -
             1U) /
            GS_FOTA_CHUNK_SIZE
        );


    ESP_LOGI(
        TAG,
        "========================================"
    );

    ESP_LOGI(
        TAG,
        "NODE FOTA START"
    );

    ESP_LOGI(
        TAG,
        "Target MAC: "
        "%02X:%02X:%02X:%02X:%02X:%02X",

        NODE_MAC[0],
        NODE_MAC[1],
        NODE_MAC[2],
        NODE_MAC[3],
        NODE_MAC[4],
        NODE_MAC[5]
    );

    ESP_LOGI(
        TAG,
        "Image size : %lu bytes",
        (unsigned long)
            image_size
    );

    ESP_LOGI(
        TAG,
        "Image CRC32: 0x%08lX",
        (unsigned long)
            image_crc
    );

    ESP_LOGI(
        TAG,
        "Chunks     : %lu x <=%u bytes",
        (unsigned long)
            total_chunks,
        GS_FOTA_CHUNK_SIZE
    );

    ESP_LOGI(
        TAG,
        "Session    : %lu",
        (unsigned long)
            session_id
    );

    ESP_LOGI(
        TAG,
        "========================================"
    );


    /*
     * BEGIN
     */
    gs_fota_packet_t begin = {0};


    begin.magic =
        GS_FOTA_MAGIC;

    begin.protocol_version =
        GS_FOTA_PROTOCOL_VERSION;

    begin.type =
        GS_FOTA_MSG_BEGIN;

    begin.session_id =
        session_id;

    begin.seq =
        0;

    begin.image_size =
        (uint32_t)
            image_size;

    begin.image_crc32 =
        image_crc;


    if (!send_fota_packet_with_retry(
            &begin,
            GS_FOTA_ACK_READY,
            false)) {

        ESP_LOGE(
            TAG,
            "NODE FOTA BEGIN failed"
        );

        send_fota_abort(
            session_id,
            0
        );

        return false;
    }


    ESP_LOGI(
        TAG,
        "Node READY for FOTA"
    );


    /*
     * DATA
     */
    size_t offset = 0;


    for (uint32_t seq = 0;
         seq < total_chunks;
         seq++) {

        size_t remaining =
            image_size -
            offset;


        size_t chunk_size =
            remaining >
                    GS_FOTA_CHUNK_SIZE
                ? GS_FOTA_CHUNK_SIZE
                : remaining;


        gs_fota_packet_t packet = {0};


        packet.magic =
            GS_FOTA_MAGIC;

        packet.protocol_version =
            GS_FOTA_PROTOCOL_VERSION;

        packet.type =
            GS_FOTA_MSG_DATA;

        packet.session_id =
            session_id;

        packet.seq =
            seq;

        packet.image_size =
            (uint32_t)
                image_size;

        packet.image_crc32 =
            image_crc;

        packet.payload_len =
            (uint16_t)
                chunk_size;


        memcpy(
            packet.payload,
            image + offset,
            chunk_size
        );


        packet.payload_crc32 =
            crc32_buffer(
                packet.payload,
                chunk_size
            );


        if (!send_fota_packet_with_retry(
                &packet,
                GS_FOTA_ACK_DATA_OK,
                true)) {

            ESP_LOGE(
                TAG,
                "NODE FOTA DATA failed "
                "seq=%lu offset=%lu",

                (unsigned long)seq,
                (unsigned long)offset
            );


            send_fota_abort(
                session_id,
                seq
            );


            return false;
        }


        offset +=
            chunk_size;


        if ((seq % 100U) == 0U ||
            offset ==
                image_size) {

            uint32_t percentage =
                (uint32_t)(
                    (offset * 100U) /
                    image_size
                );


            ESP_LOGI(
                TAG,
                "FOTA TX progress "
                "%lu/%lu bytes (%lu%%) "
                "chunk=%lu/%lu",

                (unsigned long)
                    offset,

                (unsigned long)
                    image_size,

                (unsigned long)
                    percentage,

                (unsigned long)
                    (seq + 1U),

                (unsigned long)
                    total_chunks
            );
        }
    }


    /*
     * END
     */
    gs_fota_packet_t end = {0};


    end.magic =
        GS_FOTA_MAGIC;

    end.protocol_version =
        GS_FOTA_PROTOCOL_VERSION;

    end.type =
        GS_FOTA_MSG_END;

    end.session_id =
        session_id;

    end.seq =
        total_chunks;

    end.image_size =
        (uint32_t)
            image_size;

    end.image_crc32 =
        image_crc;


    if (!send_fota_packet_with_retry(
            &end,
            GS_FOTA_ACK_COMPLETE,
            false)) {

        ESP_LOGE(
            TAG,
            "NODE FOTA END failed"
        );


        return false;
    }


    ESP_LOGI(
        TAG,
        "========================================"
    );

    ESP_LOGI(
        TAG,
        "NODE FOTA TRANSFER COMPLETE"
    );

    ESP_LOGI(
        TAG,
        "C3 should now reboot into new OTA slot"
    );

    ESP_LOGI(
        TAG,
        "========================================"
    );


    return true;
}


/* ============================================================
 * FOTA sender task
 * ============================================================
 */

static void fota_sender_task(void *arg)
{
    (void)arg;


    uint8_t start_command;


    while (true) {

        if (xQueueReceive(
                g_fota_start_queue,
                &start_command,
                portMAX_DELAY) != pdTRUE) {

            continue;
        }


        if (g_fota_running) {

            ESP_LOGW(
                TAG,
                "FOTA already running"
            );

            continue;
        }


        g_fota_running =
            true;


        bool success =
            perform_node_fota();


        if (success) {

            ESP_LOGI(
                TAG,
                "FOTA RESULT: PASS"
            );

        } else {

            ESP_LOGE(
                TAG,
                "FOTA RESULT: FAIL"
            );
        }


        g_fota_running =
            false;
    }
}


/* ============================================================
 * BOOT button FOTA trigger task
 * ============================================================
 */

static void fota_trigger_task(void *arg)
{
    (void)arg;


    uint32_t held_ms = 0;

    bool already_triggered = false;


    ESP_LOGI(
        TAG,
        "Hold BOOT button for %d ms "
        "to start C3 FOTA test",
        FOTA_TRIGGER_HOLD_MS
    );


    while (true) {

        int level =
            gpio_get_level(
                FOTA_TRIGGER_GPIO
            );


        if (level == 0) {

            if (!already_triggered) {

                held_ms +=
                    FOTA_TRIGGER_POLL_MS;


                if (held_ms >=
                    FOTA_TRIGGER_HOLD_MS) {

                    uint8_t command =
                        1;


                    if (xQueueSend(
                            g_fota_start_queue,
                            &command,
                            0) == pdTRUE) {

                        ESP_LOGW(
                            TAG,
                            "BOOT long-press: "
                            "C3 FOTA requested"
                        );

                    } else {

                        ESP_LOGW(
                            TAG,
                            "Could not queue FOTA request"
                        );
                    }


                    already_triggered =
                        true;
                }
            }

        } else {

            held_ms =
                0;

            already_triggered =
                false;
        }


        vTaskDelay(
            pdMS_TO_TICKS(
                FOTA_TRIGGER_POLL_MS
            )
        );
    }
}


/* ============================================================
 * FOTA trigger GPIO
 * ============================================================
 */

static void fota_trigger_gpio_init(void)
{
    gpio_config_t cfg = {
        .pin_bit_mask =
            (1ULL <<
             FOTA_TRIGGER_GPIO),

        .mode =
            GPIO_MODE_INPUT,

        .pull_up_en =
            GPIO_PULLUP_ENABLE,

        .pull_down_en =
            GPIO_PULLDOWN_DISABLE,

        .intr_type =
            GPIO_INTR_DISABLE
    };


    ESP_ERROR_CHECK(
        gpio_config(
            &cfg
        )
    );
}


/* ============================================================
 * NVS
 * ============================================================
 */

static void nvs_init_hub(void)
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

static void wifi_init_hub(void)
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
}


/* ============================================================
 * ESP-NOW initialization
 * ============================================================
 */

static void espnow_init_hub(void)
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
        NODE_MAC,
        sizeof(NODE_MAC)
    );


    /*
     * 0 = current Wi-Fi channel.
     */
    peer.channel =
        0;

    peer.ifidx =
        WIFI_IF_STA;

    peer.encrypt =
        false;


    if (!esp_now_is_peer_exist(
            NODE_MAC)) {

        ESP_ERROR_CHECK(
            esp_now_add_peer(
                &peer
            )
        );
    }
}


/* ============================================================
 * Application entry
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
        "Ghar Sajag HW-M1 Hub"
    );

    ESP_LOGI(
        TAG,
        "Firmware: %s",
        HUB_FW_VERSION
    );

    ESP_LOGI(
        TAG,
        "ESP-NOW channel: %d",
        ESPNOW_CHANNEL
    );

    ESP_LOGI(
        TAG,
        "========================================"
    );


    nvs_init_hub();

    fota_trigger_gpio_init();

    wifi_init_hub();


    g_rx_queue =
        xQueueCreate(
            RX_QUEUE_LEN,
            sizeof(rx_event_t)
        );


    g_fota_ack_queue =
        xQueueCreate(
            FOTA_ACK_QUEUE_LEN,
            sizeof(fota_ack_event_t)
        );


    g_fota_start_queue =
        xQueueCreate(
            FOTA_START_QUEUE_LEN,
            sizeof(uint8_t)
        );


    if (g_rx_queue == NULL ||
        g_fota_ack_queue == NULL ||
        g_fota_start_queue == NULL) {

        ESP_LOGE(
            TAG,
            "Failed to create queues"
        );

        return;
    }


    espnow_init_hub();


    uint8_t hub_mac[6] = {0};


    ESP_ERROR_CHECK(
        esp_wifi_get_mac(
            WIFI_IF_STA,
            hub_mac
        )
    );


    uint8_t actual_channel = 0;

    wifi_second_chan_t secondary =
        WIFI_SECOND_CHAN_NONE;


    ESP_ERROR_CHECK(
        esp_wifi_get_channel(
            &actual_channel,
            &secondary
        )
    );


    ESP_LOGI(
        TAG,
        "HUB MAC: "
        "%02X:%02X:%02X:%02X:%02X:%02X",

        hub_mac[0],
        hub_mac[1],
        hub_mac[2],
        hub_mac[3],
        hub_mac[4],
        hub_mac[5]
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
        "Embedded C3 image: %lu bytes",
        (unsigned long)(
            node_firmware_end -
            node_firmware_start
        )
    );


    if (xTaskCreate(
            rx_task,
            "hub_rx",
            4096,
            NULL,
            5,
            NULL) != pdPASS) {

        ESP_LOGE(
            TAG,
            "Failed to create RX task"
        );

        return;
    }


    if (xTaskCreate(
            fota_sender_task,
            "node_fota",
            6144,
            NULL,
            8,
            NULL) != pdPASS) {

        ESP_LOGE(
            TAG,
            "Failed to create FOTA sender task"
        );

        return;
    }


    if (xTaskCreate(
            fota_trigger_task,
            "fota_trigger",
            3072,
            NULL,
            4,
            NULL) != pdPASS) {

        ESP_LOGE(
            TAG,
            "Failed to create FOTA trigger task"
        );

        return;
    }


    ESP_LOGI(
        TAG,
        "Waiting for node events"
    );


    ESP_LOGI(
        TAG,
        "To start NODE FOTA:"
    );


    ESP_LOGI(
        TAG,
        "Hold Hub BOOT button for ~2 seconds "
        "while Hub is already running"
    );
}
