#ifndef KAGURA_USB_HOST_H
#define KAGURA_USB_HOST_H

#include <stdbool.h>
#include <stdint.h>

void usb_pointer_init(void);
bool usb_pointer_pop(uint8_t *packet);
#include <stdint.h>

void usb_host_task(void);
bool usb_host_keyboard_connected(void);
int usb_host_flash_safe_state(void);

#endif
