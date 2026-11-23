#include "tusb.h"

#include <string.h>

#define DEVICE_VID 0xcafeu
#define DEVICE_PID 0x4011u

enum {
    ITF_CDC = 0,
    ITF_CDC_DATA,
    ITF_TOTAL
};

#define EP_CDC_NOTIF 0x81
#define EP_CDC_OUT 0x02
#define EP_CDC_IN 0x82
#define CONFIG_TOTAL_LEN (TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN)

static const tusb_desc_device_t device_descriptor = {
    .bLength = sizeof(tusb_desc_device_t),
    .bDescriptorType = TUSB_DESC_DEVICE,
    .bcdUSB = 0x0200,
    .bDeviceClass = TUSB_CLASS_MISC,
    .bDeviceSubClass = MISC_SUBCLASS_COMMON,
    .bDeviceProtocol = MISC_PROTOCOL_IAD,
    .bMaxPacketSize0 = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor = DEVICE_VID,
    .idProduct = DEVICE_PID,
    .bcdDevice = 0x0100,
    .iManufacturer = 0x01,
    .iProduct = 0x02,
    .iSerialNumber = 0,
    .bNumConfigurations = 1
};

static const uint8_t configuration_descriptor[] = {
    TUD_CONFIG_DESCRIPTOR(
        1, ITF_TOTAL, 0, CONFIG_TOTAL_LEN, 0x00, 100),
    TUD_CDC_DESCRIPTOR(
        ITF_CDC,
        3,
        EP_CDC_NOTIF,
        8,
        EP_CDC_OUT,
        EP_CDC_IN,
        64)
};

static const char *const string_descriptors[] = {
    "KAGURA",
    "KAGURA-HD XIAO keyboard",
    "HD keyboard bridge"
};

uint8_t const *tud_descriptor_device_cb(void)
{
    return (uint8_t const *)&device_descriptor;
}

uint8_t const *tud_descriptor_configuration_cb(uint8_t index)
{
    return index == 0 ? configuration_descriptor : NULL;
}

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid)
{
    static uint16_t descriptor[32];
    (void)langid;

    uint8_t count;
    if (index == 0) {
        descriptor[1] = 0x0409;
        count = 1;
    } else {
        const size_t total =
            sizeof(string_descriptors) / sizeof(string_descriptors[0]);
        if (index > total) {
            return NULL;
        }
        const char *text = string_descriptors[index - 1u];
        count = (uint8_t)strlen(text);
        if (count > 31u) {
            count = 31u;
        }
        for (uint8_t i = 0; i < count; ++i) {
            descriptor[1u + i] = (uint8_t)text[i];
        }
    }
    descriptor[0] =
        (uint16_t)((TUSB_DESC_STRING << 8) | (2u * count + 2u));
    return descriptor;
}
