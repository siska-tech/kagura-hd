// SPDX-License-Identifier: Apache-2.0
#ifndef MT_INFLATE_H
#define MT_INFLATE_H
#include <stdint.h>
typedef int (*mt_sink)(void *ctx, const uint8_t *data, uint32_t size);
// Decode raw DEFLATE (window <= 4 KiB) into exactly `expected` bytes, 64 at a time.
int mt_inflate(const uint8_t *src, uint32_t n, uint32_t expected, mt_sink sink, void *ctx);
#endif
