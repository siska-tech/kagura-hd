#ifndef KAGURA_PROFILE_H
#define KAGURA_PROFILE_H
#include <stdint.h>
#ifndef KAGURA_PROFILE
#define KAGURA_PROFILE 0
#endif
/* Elapsed, exclusive wall time on core0; IRQ time is included. Never CPU idle. */
enum kg_profile_region { KAGURA_IDLE, KAGURA_DRAW, KAGURA_NO_DRAW, KAGURA_USB, KAGURA_LOG,
 KAGURA_SCHEDULE, KAGURA_SLEEP, KAGURA_GEOMETRY, KAGURA_MASK, KAGURA_RECT,
 KAGURA_DESCRIPTOR, KAGURA_SUBMIT, KAGURA_DONE, KAGURA_PRESENT, KAGURA_BEGIN,
 KAGURA_DIRECTION, KAGURA_CS_SETUP, KAGURA_TX, KAGURA_RX, KAGURA_FIFO_WAIT,
 KAGURA_DEADLINE, KAGURA_WIRE, KAGURA_CS_HOLD, KAGURA_END, KAGURA_DMA_SETUP,
 KAGURA_DMA_WAIT, KAGURA_WORK, KAGURA_COOP_WORK, KAGURA_REGIONS };
typedef struct {uint64_t us[KAGURA_REGIONS],calls[KAGURA_REGIONS];uint32_t overflow;} kg_profile_profile_stats;
void kg_profile_profile_init(uint64_t (*clock_us)(void));
void kg_profile_profile_push(unsigned region);
void kg_profile_profile_pop(void);
const kg_profile_profile_stats *kg_profile_profile_get(void);
extern uint64_t kg_profile_present_before,kg_profile_present_after;
void kg_profile_present_mark(int completed);
uint32_t kg_profile_work(uint32_t seed, unsigned rounds);
#if KAGURA_PROFILE
#define BPUSH(r) kg_profile_profile_push(r)
#define BPOP() kg_profile_profile_pop()
#else
#define BPUSH(r) ((void)0)
#define BPOP() ((void)0)
#endif
#if KAGURA_PROFILE == 2
#define BDETAIL(r) BPUSH(r)
#define BDETAIL_END() BPOP()
#else
#define BDETAIL(r) ((void)0)
#define BDETAIL_END() ((void)0)
#endif
#endif
