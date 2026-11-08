// SPDX-License-Identifier: Apache-2.0
#ifndef B16_QUEUE_H
#define B16_QUEUE_H
#include <stdint.h>
typedef struct {
 uint32_t submitted,retired,barriers,peak,pending,errors;
} b16_queue_stats;
#if B16_GPU_QUEUE > 1
const b16_queue_stats *b16_queue_statistics(void);
extern int b16_queue_retiring;
#if B16_QUEUE_METRICS
typedef struct {
 uint32_t retire_calls[4],retire_samples[4],sync_calls[8],sync_samples[8],sync_nonempty[8];
 uint32_t completion_bursts,completion_hits,completion_misses,fallback_completions;
 uint64_t poll_us[4],metadata_us[4],ack_us[4],sync_drain_us[8],sync_command_us[8];
} b16_queue_metrics;
uint64_t b16_queue_clock_us(void);
const b16_queue_metrics *b16_queue_measurements(void);
void b16_queue_metrics_reset(void);
extern int b16_queue_sample_reason;
void b16_queue_observe(uint64_t poll,uint64_t metadata,uint64_t ack);
void b16_queue_burst_observe(int done);
void b16_queue_fallback_observe(void);
#endif
#endif
#endif
