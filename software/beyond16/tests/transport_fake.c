#include "pico_stub.h"
#include "b16_qspi.h"
#include "hardware/dma.h"
#include "b16_profile.h"
fake_pio_hw fake_bus;
#include <string.h>
#define API __declspec(dllexport)
static unsigned dma_active_count(void),dma_abort_count(void);
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
 switch(kind){case 0:return trace_n;case 1:return trace[i];case 2:return regs[i];case 3:return drive[i];case 4:return slew[i];case 5:return hyst[i];case 6:return pin_cs;case 7:return dirs;case 8:return pins;case 9:return cycle_n;case 10:return cycles[i];case 11:return cs_n;case 12:return cs_events[i];case 13:return (uint)(config.clkdiv*1000);case 14:return config.out_base;case 15:return config.out_count;case 16:return config.in_base;case 17:return config.side_pin;case 18:return config.autopush;case 19:return config.threshold;case 20:return config.out_right|config.in_right;case 21:return dma_active_count();case 22:return dma_abort_count();default:return 0;}
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

typedef struct {dma_channel_config c;volatile uint32_t *dst;const volatile uint32_t *src;unsigned n;bool active,claimed;} fake_dma;
static fake_dma channels[2];static unsigned aborts;static dma_channel_hw_t dma_registers[2];
dma_channel_hw_t *dma_channel_hw_addr(uint ch){return &dma_registers[ch];}
static unsigned dma_active_count(void){return channels[0].active+channels[1].active;}
static unsigned dma_abort_count(void){return aborts;}
int dma_claim_unused_channel(bool required){(void)required;if(mode==9)return -1;for(int i=0;i<2;i++)if(!channels[i].claimed){if(mode==10&&i==1)return -1;channels[i].claimed=true;return i;}return -1;}
void dma_channel_unclaim(uint ch){channels[ch].claimed=false;}
void dma_channel_abort(uint ch){channels[ch].active=false;aborts++;}
dma_channel_config dma_channel_get_default_config(uint ch){(void)ch;dma_channel_config c={0};return c;}
void channel_config_set_transfer_data_size(dma_channel_config *c,uint n){c->size=n;}
void channel_config_set_read_increment(dma_channel_config *c,bool b){c->read_inc=b;}
void channel_config_set_write_increment(dma_channel_config *c,bool b){c->write_inc=b;}
void channel_config_set_dreq(dma_channel_config *c,uint n){c->dreq=n;}
uint pio_get_dreq(PIO p,uint sm_,bool tx){(void)p;return sm_+(tx?0:4);}
void dma_channel_configure(uint ch,const dma_channel_config *c,volatile void *dst,const volatile void *src,uint n,bool start){channels[ch].c=*c;channels[ch].dst=dst;channels[ch].src=src;channels[ch].n=n;dma_registers[ch].transfer_count=n;dma_registers[ch].ctrl_trig=0;channels[ch].active=start;}
void dma_start_channel_mask(uint mask){for(uint i=0;i<2;i++)if(mask&(1u<<i))channels[i].active=true;}
bool dma_channel_is_busy(uint ch){
 if(mode==11){channels[0].active=channels[1].active=false;dma_registers[0].ctrl_trig=DMA_CH0_CTRL_TRIG_READ_ERROR_BITS;return false;}
 if(mode!=6){fake_dma *t=&channels[0],*r=&channels[1];
  if(t->active&&rx_in-rx_out<4){pio_sm_put(pio0,0,*t->src);if(t->c.read_inc)t->src++;dma_registers[0].transfer_count=--t->n;if(!t->n)t->active=false;}
  if(r->active&&mode!=7&&rx_in!=rx_out){*r->dst=pio_sm_get(pio0,0);if(r->c.write_inc)r->dst++;dma_registers[1].transfer_count=--r->n;if(!r->n)r->active=false;}
 }
 return channels[ch].active;
}
API uint64_t fake_dma_count(void){return mt_qspi_statistics()->dma_transfers;}
API void fake_profile_init(void){b16_profile_init(time_us_64);}
API uint64_t fake_profile_us(uint r){return b16_profile_get()->us[r];}
API uint32_t fake_work(uint32_t seed,unsigned n){return b16_work(seed,n);}
API void fake_push(uint r){b16_profile_push(r);}
API void fake_pop(void){b16_profile_pop();}
API uint64_t fake_time(void){return time_us_64();}
