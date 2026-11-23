#ifndef KAGURA_HD_BRIDGE_H
#define KAGURA_HD_BRIDGE_H
#include <stdint.h>
#include <stdbool.h>
enum { HD_KEY = 1, HD_CONFIG = 0x83, HD_HELLO = 0x85, HD_STATUS = 0xc5 };
uint8_t hd_keycode(uint8_t usage, uint8_t modifiers, bool caps);
bool hd_repeatable(uint8_t usage);
#endif
