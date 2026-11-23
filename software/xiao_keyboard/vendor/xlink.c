#include "xlink.h"

enum {
    DEC_WAIT_START,
    DEC_TYPE,
    DEC_LENGTH,
    DEC_PAYLOAD,
    DEC_CRC
};

uint8_t xlink_crc8_update(uint8_t crc, uint8_t byte)
{
    crc ^= byte;
    for (uint8_t bit = 0; bit < 8; ++bit) {
        crc = (crc & 0x80u) != 0u ? (uint8_t)((crc << 1) ^ 0x07u)
                                  : (uint8_t)(crc << 1);
    }
    return crc;
}

uint8_t xlink_crc8(const uint8_t *data, size_t length)
{
    uint8_t crc = 0;
    for (size_t i = 0; i < length; ++i) {
        crc = xlink_crc8_update(crc, data[i]);
    }
    return crc;
}

void xlink_decoder_init(xlink_decoder_t *decoder)
{
    decoder->state = DEC_WAIT_START;
    decoder->type = 0;
    decoder->length = 0;
    decoder->offset = 0;
    decoder->crc = 0;
}

xlink_decode_result_t xlink_decoder_push(
    xlink_decoder_t *decoder,
    uint8_t byte,
    xlink_frame_t *frame)
{
    switch (decoder->state) {
    case DEC_WAIT_START:
        if (byte == XLINK_FRAME_START) {
            decoder->state = DEC_TYPE;
        }
        return XLINK_DECODE_NONE;
    case DEC_TYPE:
        if (byte == XLINK_FRAME_START) {
            return XLINK_DECODE_NONE;
        }
        decoder->type = byte;
        decoder->crc = xlink_crc8_update(0, byte);
        decoder->state = DEC_LENGTH;
        return XLINK_DECODE_NONE;
    case DEC_LENGTH:
        if (byte > XLINK_MAX_PAYLOAD) {
            decoder->state = DEC_WAIT_START;
            return XLINK_DECODE_BAD_FRAME;
        }
        decoder->length = byte;
        decoder->offset = 0;
        decoder->crc = xlink_crc8_update(decoder->crc, byte);
        decoder->state = byte == 0 ? DEC_CRC : DEC_PAYLOAD;
        return XLINK_DECODE_NONE;
    case DEC_PAYLOAD:
        decoder->frame.payload[decoder->offset++] = byte;
        decoder->crc = xlink_crc8_update(decoder->crc, byte);
        if (decoder->offset == decoder->length) {
            decoder->state = DEC_CRC;
        }
        return XLINK_DECODE_NONE;
    case DEC_CRC:
        decoder->state = DEC_WAIT_START;
        if (byte != decoder->crc) {
            return XLINK_DECODE_BAD_FRAME;
        }
        decoder->frame.type = decoder->type;
        decoder->frame.length = decoder->length;
        *frame = decoder->frame;
        return XLINK_DECODE_FRAME;
    default:
        decoder->state = DEC_WAIT_START;
        return XLINK_DECODE_BAD_FRAME;
    }
}
