#pragma once

#include <stdint.h>

#define GS_FOTA_MAGIC              0x4753464FU
#define GS_FOTA_PROTOCOL_VERSION   1U

/*
 * Keep enough margin below ESP-NOW packet size.
 */
#define GS_FOTA_CHUNK_SIZE         200U

typedef enum {
    GS_FOTA_MSG_BEGIN = 1,
    GS_FOTA_MSG_DATA  = 2,
    GS_FOTA_MSG_END   = 3,
    GS_FOTA_MSG_ABORT = 4
} gs_fota_msg_type_t;

typedef enum {
    GS_FOTA_ACK_READY       = 0,
    GS_FOTA_ACK_DATA_OK     = 1,
    GS_FOTA_ACK_COMPLETE    = 2,
    GS_FOTA_ACK_DUPLICATE   = 3,

    GS_FOTA_ERR_BAD_PACKET  = -1,
    GS_FOTA_ERR_BAD_SESSION = -2,
    GS_FOTA_ERR_BAD_SEQ     = -3,
    GS_FOTA_ERR_BAD_CRC     = -4,
    GS_FOTA_ERR_BAD_SIZE    = -5,
    GS_FOTA_ERR_OTA_BEGIN   = -6,
    GS_FOTA_ERR_OTA_WRITE   = -7,
    GS_FOTA_ERR_OTA_END     = -8,
    GS_FOTA_ERR_SET_BOOT    = -9
} gs_fota_status_t;

typedef struct __attribute__((packed)) {
    uint32_t magic;

    uint8_t protocol_version;
    uint8_t type;
    uint16_t reserved0;

    uint32_t session_id;
    uint32_t seq;

    uint32_t image_size;
    uint32_t image_crc32;

    uint16_t payload_len;
    uint16_t reserved1;

    uint32_t payload_crc32;

    uint8_t payload[GS_FOTA_CHUNK_SIZE];
} gs_fota_packet_t;

typedef struct __attribute__((packed)) {
    uint32_t magic;

    uint8_t protocol_version;
    uint8_t type;
    uint16_t reserved;

    uint32_t session_id;

    uint32_t ack_seq;
    uint32_t next_seq;

    int32_t status;

    uint32_t bytes_written;
} gs_fota_ack_t;
