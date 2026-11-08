// SPDX-License-Identifier: Apache-2.0
// MIDNIGHT TERMINAL sound: 7-voice 4-operator FM, brushes, rain and the
// scripted effects (typing, cursor, alarm, tape stop, stutter, heartbeat).
#ifndef MT_FM_H
#define MT_FM_H
#include <stdint.h>
#define FM_RATE 48000u
#define FM_STEP_FRAMES 8000u                     /* 16th note at 90 BPM */
#define FM_BAR_FRAMES (16u*FM_STEP_FRAMES)
#define FM_SONG_FRAMES (104u*FM_RATE)
void fm_init(void);
void fm_render(int8_t *left, int8_t *right, unsigned frames);   /* frames: multiple of 16 */
uint32_t fm_position(void);
uint32_t fm_peak(void);
uint32_t fm_clipped(void);
#endif
