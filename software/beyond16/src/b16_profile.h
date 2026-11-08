#ifndef B16_PROFILE_H
#define B16_PROFILE_H
#include <stdint.h>
#ifndef B16_PROFILE
#define B16_PROFILE 0
#endif
/* Elapsed, exclusive wall time on core0; IRQ time is included. Never CPU idle. */
enum b16_region { B16_IDLE, B16_DRAW, B16_NO_DRAW, B16_USB, B16_LOG,
 B16_SCHEDULE, B16_SLEEP, B16_GEOMETRY, B16_MASK, B16_RECT,
 B16_DESCRIPTOR, B16_SUBMIT, B16_DONE, B16_PRESENT, B16_BEGIN,
 B16_DIRECTION, B16_CS_SETUP, B16_TX, B16_RX, B16_FIFO_WAIT,
 B16_DEADLINE, B16_WIRE, B16_CS_HOLD, B16_END, B16_DMA_SETUP,
 B16_DMA_WAIT, B16_WORK, B16_COOP_WORK, B16_REGIONS };
typedef struct {uint64_t us[B16_REGIONS],calls[B16_REGIONS];uint32_t overflow;} b16_profile_stats;
void b16_profile_init(uint64_t (*clock_us)(void));
void b16_profile_push(unsigned region);
void b16_profile_pop(void);
const b16_profile_stats *b16_profile_get(void);
extern uint64_t b16_present_before,b16_present_after;
void b16_present_mark(int completed);
uint32_t b16_work(uint32_t seed, unsigned rounds);
#if B16_PROFILE
#define BPUSH(r) b16_profile_push(r)
#define BPOP() b16_profile_pop()
#else
#define BPUSH(r) ((void)0)
#define BPOP() ((void)0)
#endif
#if B16_PROFILE == 2
#define BDETAIL(r) BPUSH(r)
#define BDETAIL_END() BPOP()
#else
#define BDETAIL(r) ((void)0)
#define BDETAIL_END() ((void)0)
#endif
#endif
