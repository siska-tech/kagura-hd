// SPDX-License-Identifier: Apache-2.0
// FOUR OPERATORS visual timeline. Uses only the KFB drawing ABI (FILL, COPY,
// PALETTE, PRESENT, WRITE); the platform supplies audio service and the
// audible synthesizer state.
#ifndef DEMO_H
#define DEMO_H
#include "../../kagura_fb/kagura_fb.h"
#include "fm.h"

#define DEMO_SCENE_MS 16000u
#define DEMO_END_MS 132000u           /* = FM_SONG_FRAMES: final chord tail */
#define DEMO_SCENES 8

typedef struct {
    int (*service)(void);                          /* called before every GPU command */
    int8_t (*sample_at)(uint32_t frame);           /* audible mono history */
    const fm_snapshot *(*snapshot_at)(uint32_t frame);
} demo_platform;

typedef struct {
    uint32_t frames, commands, fills, copies, palettes, presents, writes;
    uint32_t scene_frames[DEMO_SCENES];
    uint8_t scene;
} demo_stats;

int demo_init(kfb_device *gpu, const demo_platform *platform);
int demo_frame(uint32_t ms);                       /* draw and present one frame */
const demo_stats *demo_statistics(void);
#endif
