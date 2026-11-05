#include "pico_stub.h"
#include "../src/mt_qspi.h"
#include <string.h>
#define API __declspec(dllexport)
typedef int (*reg_callback)(int,uint,uint);
static reg_callback callback;
static uint32_t hz=120000000,mode,trace[8192],trace_n;
static uint32_t regs[64],drive[8],slew[8],hyst[8];
static uint64_t us;
static uint pin_cs=1,dirs,pins,phase,reg,inc,is_read,left,rx[16],rx_in,rx_out;
static uint cycles[256],cycle_n,cs_events[256],cs_n;
static pio_sm_config config;
API void fake_reset(void){mt_qspi_deinit();mode=0;trace_n=0;callback=0;us=0;hz=120000000;pin_cs=1;dirs=0;rx_in=rx_out=0;cycle_n=cs_n=0;memset(regs,0,sizeof regs);memset(drive,0,sizeof drive);memset(slew,255,sizeof slew);memset(hyst,0,sizeof hyst);}
API void fake_mode(uint m){mode=m;}
API void fake_clock(uint n){hz=n;}
API void fake_callback(reg_callback cb){callback=cb;}
API uint fake_get(uint kind,uint i){
 switch(kind){case 0:return trace_n;case 1:return trace[i];case 2:return regs[i];case 3:return drive[i];case 4:return slew[i];case 5:return hyst[i];case 6:return pin_cs;case 7:return dirs;case 8:return pins;case 9:return cycle_n;case 10:return cycles[i];case 11:return cs_n;case 12:return cs_events[i];case 13:return (uint)(config.clkdiv*1000);case 14:return config.out_base;case 15:return config.out_count;case 16:return config.in_base;case 17:return config.side_pin;case 18:return config.autopush;case 19:return config.threshold;case 20:return config.out_right|config.in_right;default:return 0;}
}
API int fake_write(uint reg_,bool inc_,const uint8_t *p,size_t n){kfb_io io=mt_qspi_io();return io.write(io.context,(uint8_t)reg_,inc_,p,n);}
API int fake_read(uint reg_,bool inc_,uint8_t *p,size_t n){kfb_io io=mt_qspi_io();return io.read(io.context,(uint8_t)reg_,inc_,p,n);}
uint32_t clock_get_hz(int clk){(void)clk;return hz;}
uint64_t time_us_64(void){return us++;}
absolute_time_t get_absolute_time(void){return time_us_64();}
uint32_t to_ms_since_boot(absolute_time_t t){return (uint32_t)(t/1000);}
void busy_wait_at_least_cycles(uint32_t n){if(cycle_n<256)cycles[cycle_n++]=n;}
void tight_loop_contents(void){}
void gpio_init(uint pin){if(pin>=2&&pin<=6)dirs&=~(1u<<pin);}
void gpio_put(uint pin,bool value){if(pin==7){if(pin_cs&&!value){phase=0;rx_in=rx_out=0;}pin_cs=value;if(cs_n<256)cs_events[cs_n++]=value;}}
void gpio_set_dir(uint pin,bool dir){(void)pin;(void)dir;}
void gpio_set_drive_strength(uint pin,uint strength){drive[pin]=strength;}
void gpio_set_slew_rate(uint pin,uint rate){slew[pin]=rate;}
void gpio_set_input_hysteresis_enabled(uint pin,bool on){hyst[pin]=on;}
bool pio_can_add_program(PIO p,const pio_program_t *program){(void)p;(void)program;return mode!=4;}
int pio_claim_unused_sm(PIO p,bool required){(void)p;(void)required;return mode==5?-1:0;}
uint pio_add_program(PIO p,const pio_program_t *program){(void)p;(void)program;return 5;}
void pio_remove_program(PIO p,const pio_program_t *program,uint offset){(void)p;(void)program;(void)offset;}
void pio_sm_unclaim(PIO p,uint sm_){(void)p;(void)sm_;}
void pio_gpio_init(PIO p,uint pin){(void)p;(void)pin;}
void pio_sm_init(PIO p,uint sm_,uint offset,const pio_sm_config *c){(void)p;(void)sm_;(void)offset;config=*c;}
void pio_sm_set_enabled(PIO p,uint sm_,bool on){(void)p;(void)sm_;(void)on;}
void pio_sm_set_pins_with_mask(PIO p,uint sm_,uint32_t values,uint32_t mask){(void)p;(void)sm_;pins=(pins&~mask)|(values&mask);}
void pio_sm_set_pindirs_with_mask(PIO p,uint sm_,uint32_t values,uint32_t mask){(void)p;(void)sm_;dirs=(dirs&~mask)|(values&mask);}
void pio_sm_clear_fifos(PIO p,uint sm_){(void)p;(void)sm_;rx_in=rx_out=0;}
void pio_sm_restart(PIO p,uint sm_){(void)p;(void)sm_;}
void pio_sm_exec(PIO p,uint sm_,uint instruction){(void)p;(void)sm_;(void)instruction;}
bool pio_sm_is_tx_fifo_full(PIO p,uint sm_){(void)p;(void)sm_;return mode==3;}
bool pio_sm_is_tx_fifo_empty(PIO p,uint sm_){(void)p;(void)sm_;return true;}
bool pio_sm_is_rx_fifo_empty(PIO p,uint sm_){(void)p;(void)sm_;return mode==1||rx_in==rx_out;}
uint pio_sm_get_pc(PIO p,uint sm_){(void)p;(void)sm_;return mode==2?6:5;}
void pio_sm_put(PIO p,uint sm_,uint32_t word){
 (void)p;(void)sm_;if(trace_n<8192)trace[trace_n++]=word;
 uint byte=(word>>22)&255,value=0;
 if(phase==0){reg=byte&63;inc=(byte>>6)&1;is_read=byte>>7;phase=1;}
 else if(is_read&&phase==1){left=byte?byte:256;phase=2;}
 else if(is_read&&phase==2)phase=3;
 else if(!is_read){regs[reg]=byte;if(callback&&callback(1,reg,byte)<0)mode=1;if(inc)reg=(reg+1)&63;}
 else if(left){int r=callback?callback(0,reg,0):(int)regs[reg];if(r<0)mode=1;value=(uint)r;left--;if(inc)reg=(reg+1)&63;}
 if(word&(1u<<30))dirs&=~(15u<<2);
 if(rx_in-rx_out<16)rx[(rx_in++)%16]=value;
}
uint32_t pio_sm_get(PIO p,uint sm_){(void)p;(void)sm_;return rx[(rx_out++)%16];}
