// SPDX-License-Identifier: Apache-2.0
// MIDNIGHT TERMINAL visual timeline on the KFB drawing ABI.
#ifndef MT_SHOW_H
#define MT_SHOW_H
#include "../../kagura_fb/kagura_fb.h"
typedef struct {
    uint32_t frames, commands, fills, copies, palettes, presents, writes, uploads;
    uint32_t scene_frames[8];
    uint8_t scene;
} show_stats;
int show_init(kfb_device *gpu, int (*service)(void));   /* uploads title + bar while black */
int show_frame(uint32_t ms);
const show_stats *show_statistics(void);
#endif
