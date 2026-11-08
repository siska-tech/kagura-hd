// SPDX-License-Identifier: Apache-2.0
#ifndef FM_FONT_H_
#define FM_FONT_H_
#include <stdint.h>
#define FONT_W 5
#define FONT_H 7
void font_init(void);
// 7 rows; bit 4 is the leftmost of the 5 columns.
const uint8_t *font_glyph(char c);
unsigned font_width(const char *s, unsigned scale);
#endif
