// SPDX-License-Identifier: Apache-2.0
// PCM streaming client for kagura-hd-qspi-pcm-stream.fs (audio index E3..E5).
// Core 1 renders into the ring; core 0 owns the KFB device and copies one
// 4096-frame half per channel into PSRAM whenever the FPGA returns one.
#ifndef FM_STREAM_H
#define FM_STREAM_H
#include "../../kagura_fb/kagura_fb.h"
#include <stdint.h>

#define STREAM_RING 16384u              /* frames per channel, power of two */
#define STREAM_HALF 4096u
#define STREAM_LEAD 8192u               /* core 1 may run this far ahead of the FPGA copy */

extern int8_t stream_ring_l[STREAM_RING], stream_ring_r[STREAM_RING];
extern volatile uint32_t stream_produced, stream_consumed;

typedef struct {
    uint32_t halves, wraps, chunks, synth_waits;
    uint32_t worst_latency_us;          /* HALF_FREE seen -> token published */
    uint32_t worst_poll_gap_us;         /* longest gap between status polls while armed */
    uint64_t start_us;                  /* AUDIO_COMMIT completed: audible frame 0 */
} stream_stats;

enum { STREAM_BAD_PROTOCOL=-20, STREAM_DEADLINE=-22, STREAM_SYNTH_LATE=-24 };

int stream_start(kfb_device *gpu);      /* needs 2 halves rendered */
int stream_service(void);               /* non-blocking; safe before start */
int stream_stop(void);
int stream_check(uint8_t *left, uint8_t *right, uint8_t *hdmi);
const stream_stats *stream_statistics(void);
#endif
