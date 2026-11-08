// SPDX-License-Identifier: Apache-2.0
// FOUR OPERATORS: integer 4-operator FM synthesizer and song sequencer.
// Platform independent; on RP2040 it runs alone on core 1.
#ifndef FM_H
#define FM_H
#include <stdint.h>

#define FM_RATE 48000u
#define FM_VOICES 6
#define FM_OPS 4
#define FM_DRUMS 3
#define FM_STEP_FRAMES 6000u                    /* one 16th note at 120 BPM */
#define FM_BAR_FRAMES (16u*FM_STEP_FRAMES)      /* 2 s */
#define FM_SONG_BARS 65u                        /* 64 bars + final chord */
#define FM_SONG_FRAMES (FM_SONG_BARS*FM_BAR_FRAMES+2u*FM_RATE)
#define FM_SNAP_FRAMES 256u
#define FM_SNAP_RING 256u                       /* 65536 frames of history */

enum { V_BASS, V_LEAD, V_ARP, V_PAD0, V_PAD1, V_PAD2 };
enum { D_KICK, D_SNARE, D_HAT };

// Envelope/level view for the visuals, one per FM_SNAP_FRAMES block.
typedef struct {
    uint8_t op[FM_VOICES][FM_OPS];   /* operator envelope levels 0..255 */
    uint8_t voice[FM_VOICES];        /* carrier output level 0..255 */
    uint8_t note[FM_VOICES];         /* MIDI note, 0 = silent */
    uint8_t drum[FM_DRUMS];          /* drum envelope 0..255 */
    uint8_t bar, step;
} fm_snapshot;

void fm_init(void);
// Render the next `frames` stereo frames as signed 8-bit PCM.
void fm_render(int8_t *left, int8_t *right, unsigned frames);
uint32_t fm_position(void);
// Snapshot of the block containing `frame`; valid for the last 65536 frames.
const fm_snapshot *fm_snapshot_at(uint32_t frame);
// Peak absolute 16-bit mix level before 8-bit conversion (diagnostics).
uint32_t fm_peak(void);
uint32_t fm_clipped(void);
#endif
