#ifndef KAGURA_XLINK_H
#define KAGURA_XLINK_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define XLINK_MAX_PAYLOAD 240u
#define XLINK_MAX_RX_PAYLOAD 240u
#define XLINK_FRAME_START 0x7eu

enum {
    XLINK_KEY = 0x01,
    XLINK_KBD_STATE = 0x02,
    XLINK_HELLO = 0x81,
    XLINK_HELLO_REPLY = 0xc1,
    XLINK_BOOT = 0xa0,
    XLINK_DATA = 0xe0,
    XLINK_END = 0xe1,
    XLINK_ACK = 0x06,
    XLINK_NAK = 0x15,
    /* boot menu (bootmenu/): CPU -> XIAO list request [slot] and boot
     * request [slot] (answered with DATA ... END like BOOT), XIAO -> CPU
     * entry [slot, present, size lo, size hi, name...] */
    /* BIOS 0.2.1 reset with a valid PSRAM image: CPU -> XIAO boot query (no
     * payload), XIAO -> CPU reply [flags b0 = boot from the XIAO] */
    XLINK_BOOT_QUERY = 0x82,
    XLINK_BOOT_QUERY_REPLY = 0xc2,
    XLINK_MENU_LIST = 0xa1,
    XLINK_MENU_BOOT = 0xa2,
    XLINK_MENU_ENTRY = 0xe2
};

typedef struct {
    uint8_t type;
    uint8_t length;
    uint8_t payload[XLINK_MAX_RX_PAYLOAD];
} xlink_frame_t;

typedef struct {
    uint8_t state;
    uint8_t type;
    uint8_t length;
    uint8_t offset;
    uint8_t crc;
    xlink_frame_t frame;
} xlink_decoder_t;

typedef enum {
    XLINK_DECODE_NONE,
    XLINK_DECODE_FRAME,
    XLINK_DECODE_BAD_FRAME
} xlink_decode_result_t;

uint8_t xlink_crc8_update(uint8_t crc, uint8_t byte);
uint8_t xlink_crc8(const uint8_t *data, size_t length);
void xlink_decoder_init(xlink_decoder_t *decoder);
xlink_decode_result_t xlink_decoder_push(
    xlink_decoder_t *decoder,
    uint8_t byte,
    xlink_frame_t *frame);
bool xlink_send_frame(uint8_t type, const uint8_t *payload, uint8_t length);

#endif
