// SPDX-License-Identifier: Apache-2.0
#ifndef KAGURA_FB_H
#define KAGURA_FB_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum { KFB_OK=0, KFB_ARGUMENT=-1, KFB_IO=-2, KFB_TIMEOUT=-3,
       KFB_VERSION=-4, KFB_DEVICE=-5, KFB_TRANSPORT=-6 };
typedef struct {
    void *context;
    int (*read)(void *,uint8_t,bool,uint8_t *,size_t);
    int (*write)(void *,uint8_t,bool,const uint8_t *,size_t);
    uint32_t (*now_ms)(void *);
} kfb_io;
typedef struct {
    kfb_io io;
    uint32_t timeout_ms;
    uint16_t next_tag;
    uint8_t last_device_error;
    bool connected;
} kfb_device;

// IO callbacks implement raw register transfers and return zero on success.
// The caller serializes access to one device, including across CPU cores.
int kfb_init(kfb_device *,kfb_io,uint32_t timeout_ms);
int kfb_probe(kfb_device *);
// Raw 16-byte command submission; tag bytes are assigned by the driver.
// Wait before submitting another drawing command; cursor calls may interleave.
int kfb_submit(kfb_device *,const uint8_t descriptor[16],const uint8_t *payload,size_t size,uint16_t *tag);
int kfb_wait(kfb_device *,uint16_t tag);
int kfb_fence(kfb_device *);
int kfb_fill_rect(kfb_device *,unsigned page,int32_t x,int32_t y,int32_t width,int32_t height,unsigned color);
// Strict page bounds; even X/width and sx%8==dx%8. Overlap-safe.
int kfb_copy_rect(kfb_device *,unsigned src_page,int32_t sx,int32_t sy,unsigned dst_page,int32_t dx,int32_t dy,int32_t width,int32_t height);
int kfb_palette(kfb_device *,unsigned index,unsigned rgb444);
int kfb_present(kfb_device *,unsigned page);
int kfb_write_bytes(kfb_device *,uint32_t address,const uint8_t *,size_t);
int kfb_read_bytes(kfb_device *,uint32_t address,uint8_t *,size_t);
// Cursor is independent of GPU BUSY. Shape is exactly 256 MSB-first 2bpp
// bytes; bank must be inactive and no cursor commit pending. Move submits
// asynchronously and coalesces; wait returns the applied update count.
int kfb_cursor_shape(kfb_device *,unsigned bank,const uint8_t shape[256],const uint16_t colors[3],unsigned hotspot_x,unsigned hotspot_y);
int kfb_cursor_move(kfb_device *,int32_t x,int32_t y,unsigned bank,bool visible);
int kfb_cursor_status(kfb_device *,uint8_t *status,uint16_t *generation);
int kfb_cursor_wait(kfb_device *,uint16_t *generation);
// ABI 1.4 PCM2-only indexed audio; voice indices 00..5F unsupported. PCM addresses are HD die-relative.
// Shadow writes may interleave with a pending commit; one owner only.
int kfb_audio_write(kfb_device *,uint8_t index,uint8_t value);
int kfb_audio_read(kfb_device *,uint8_t index,uint8_t *value);
// Returns the existing command tag; use kfb_wait for actual apply completion.
int kfb_audio_commit(kfb_device *,uint16_t *tag);
#endif
