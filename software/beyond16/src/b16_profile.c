#include "b16_profile.h"
#include <string.h>
static b16_profile_stats stats;
static uint64_t (*clock_fn)(void),last;
static unsigned stack[24],depth,suppressed;
void b16_profile_init(uint64_t (*fn)(void)){memset(&stats,0,sizeof stats);clock_fn=fn;depth=1;suppressed=0;stack[0]=B16_IDLE;last=fn?fn():0;}
static void account(void){if(clock_fn&&depth){uint64_t t=clock_fn();stats.us[stack[depth-1]]+=t-last;last=t;}}
void b16_profile_push(unsigned r){if(!clock_fn)return;account();if(suppressed||r>=B16_REGIONS||depth>=24){stats.overflow++;suppressed++;return;}stack[depth++]=r;stats.calls[r]++;}
void b16_profile_pop(void){if(!clock_fn)return;account();if(suppressed){suppressed--;return;}if(depth>1)depth--;else stats.overflow++;}
const b16_profile_stats *b16_profile_get(void){account();return &stats;}
/* Input and observable returned checksum prevent dead-code elimination. */
uint32_t b16_work(uint32_t x,unsigned rounds){for(unsigned i=0;i<rounds;i++){x^=x<<13;x^=x>>17;x^=x<<5;x+=0x9e3779b9u+i;}return x;}

uint64_t b16_present_before,b16_present_after;
void b16_present_mark(int completed){if(clock_fn){if(completed)b16_present_after=clock_fn();else b16_present_before=clock_fn();}}
