/* PC-only Pico SDK seam: tests C orchestration, not physical PIO timing. */
#ifndef MT_PICO_STUB_H
#define MT_PICO_STUB_H
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
typedef unsigned uint;
typedef void *PIO;
#define pio0 ((PIO)(uintptr_t)1)
#define clk_sys 0
#define GPIO_OUT 1
#define GPIO_DRIVE_STRENGTH_2MA 2
#define GPIO_SLEW_RATE_SLOW 0
typedef struct {float clkdiv;uint out_base,out_count,in_base,side_pin,autopush,threshold,out_right,in_right;} pio_sm_config;
typedef struct pio_program {const uint16_t *instructions;uint8_t length;int8_t origin;uint8_t pio_version;} pio_program_t;
typedef uint64_t absolute_time_t;
uint32_t clock_get_hz(int clk);
uint64_t time_us_64(void);
absolute_time_t get_absolute_time(void);
uint32_t to_ms_since_boot(absolute_time_t t);
void busy_wait_at_least_cycles(uint32_t n);
void tight_loop_contents(void);
void gpio_init(uint pin);
void gpio_put(uint pin,bool value);
void gpio_set_dir(uint pin,bool dir);
void gpio_set_drive_strength(uint pin,uint strength);
void gpio_set_slew_rate(uint pin,uint rate);
void gpio_set_input_hysteresis_enabled(uint pin,bool on);
bool pio_can_add_program(PIO p,const pio_program_t *program);
int pio_claim_unused_sm(PIO p,bool required);
uint pio_add_program(PIO p,const pio_program_t *program);
void pio_remove_program(PIO p,const pio_program_t *program,uint offset);
void pio_sm_unclaim(PIO p,uint sm);
void pio_gpio_init(PIO p,uint pin);
void pio_sm_init(PIO p,uint sm,uint offset,const pio_sm_config *c);
void pio_sm_set_enabled(PIO p,uint sm,bool on);
void pio_sm_set_pins_with_mask(PIO p,uint sm,uint32_t values,uint32_t mask);
void pio_sm_set_pindirs_with_mask(PIO p,uint sm,uint32_t values,uint32_t mask);
void pio_sm_clear_fifos(PIO p,uint sm);
void pio_sm_restart(PIO p,uint sm);
void pio_sm_exec(PIO p,uint sm,uint instruction);
bool pio_sm_is_tx_fifo_full(PIO p,uint sm);
bool pio_sm_is_tx_fifo_empty(PIO p,uint sm);
bool pio_sm_is_rx_fifo_empty(PIO p,uint sm);
uint pio_sm_get_pc(PIO p,uint sm);
void pio_sm_put(PIO p,uint sm,uint32_t word);
uint32_t pio_sm_get(PIO p,uint sm);
static inline uint pio_encode_jmp(uint a){return a;}
static inline uint pio_encode_sideset(uint n,uint v){(void)n;return v<<12;}
static inline pio_sm_config pio_get_default_sm_config(void){pio_sm_config c={0};return c;}
static inline void sm_config_set_wrap(pio_sm_config *c,uint a,uint b){(void)c;(void)a;(void)b;}
static inline void sm_config_set_sideset(pio_sm_config *c,uint n,bool opt,bool dir){(void)c;(void)n;(void)opt;(void)dir;}
static inline void sm_config_set_out_pins(pio_sm_config *c,uint base,uint n){c->out_base=base;c->out_count=n;}
static inline void sm_config_set_set_pins(pio_sm_config *c,uint base,uint n){(void)c;(void)base;(void)n;}
static inline void sm_config_set_in_pins(pio_sm_config *c,uint base){c->in_base=base;}
static inline void sm_config_set_sideset_pins(pio_sm_config *c,uint base){c->side_pin=base;}
static inline void sm_config_set_out_shift(pio_sm_config *c,bool right,bool autopull,uint n){c->out_right=right;(void)autopull;(void)n;}
static inline void sm_config_set_in_shift(pio_sm_config *c,bool right,bool push,uint n){c->in_right=right;c->autopush=push;c->threshold=n;}
static inline void sm_config_set_clkdiv(pio_sm_config *c,float div){c->clkdiv=div;}
#endif
