// SPDX-License-Identifier: Apache-2.0
// KAGURA-9 PIO/timing reused; HD raw register protocol has 6 address bits.
#include "b16_qspi.h"
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/pio.h"
#include "kagura_host.pio.h"
#include <string.h>
enum { IO0=2,SCK=6,CS=7 };
static PIO const bus=pio0;
static int sm=-1;
static uint offset,pull_pc;
static bool loaded;
static mt_qspi_stats stats;
#ifndef B16_HOST_FAST
#define B16_HOST_FAST 1
#endif
#if B16_HOST_FAST
/* All call sites pass constants. Macro ensures division folds at the call site. */
#define wait_ns(ns) busy_wait_at_least_cycles((uint32_t)(((uint64_t)MT_QSPI_SYS_HZ*(ns)+999999999u)/1000000000u))
#else
static void wait_ns(uint32_t ns){uint32_t cycles=(uint32_t)(((uint64_t)clock_get_hz(clk_sys)*ns+999999999u)/1000000000u);busy_wait_at_least_cycles(cycles);}
#endif
static bool expired(uint64_t deadline){return time_us_64()>=deadline;}
static void abort_transaction(void){
 /* Stop the SM, force SCK low and discard FIFO state. Raise CS before handing
  * IO ownership back. Latch the fault: don't replay uncertain commands. */
 pio_sm_set_enabled(bus,(uint)sm,false);
 pio_sm_clear_fifos(bus,(uint)sm);
 pio_sm_restart(bus,(uint)sm);
 pio_sm_exec(bus,(uint)sm,pio_encode_jmp(pull_pc)|pio_encode_sideset(1,0));
 pio_sm_set_pins_with_mask(bus,(uint)sm,0,1u<<SCK);
 wait_ns(MT_QSPI_CSH_NS);gpio_put(CS,1);wait_ns(MT_QSPI_CSW_NS);
 pio_sm_set_pindirs_with_mask(bus,(uint)sm,0,15u<<IO0);
 stats.faulted=true;stats.timeouts++;
}
static int transfer_inner(const uint8_t *tx,uint8_t *rx,size_t count,bool release_last,uint64_t deadline){
 size_t sent=0,got=0;
#if B16_HOST_FAST
 unsigned check_budget=0;
#endif
 while(got<count){
  if(sent<count&&!pio_sm_is_tx_fifo_full(bus,(uint)sm)){
   uint32_t word=(uint32_t)(tx?tx[sent]:0)<<22;
   if(release_last&&sent+1==count)word|=1u<<30;
   /* bit31 remains 0: KAGURA-9 queue-consuming registers/BUSY gating do
    * not describe HD's descriptor protocol. kfb SDK serializes commands. */
   pio_sm_put(bus,(uint)sm,word);sent++;
  }
  if(!pio_sm_is_rx_fifo_empty(bus,(uint)sm)){
   uint8_t value=(uint8_t)pio_sm_get(bus,(uint)sm);
   if(rx)rx[got]=value;
   got++;stats.wire_bytes++;
  }
#if B16_HOST_FAST
  /* Check immediately, then at most 32 FIFO service iterations apart.
   * End-of-transaction polling still checks its deadline every iteration. */
  if((check_budget++ & 31u)==0 && expired(deadline))return KFB_TIMEOUT;
#else
  if(expired(deadline))return KFB_TIMEOUT;
#endif
 }
 return 0;
}
static int transfer(const uint8_t *tx,uint8_t *rx,size_t count,bool release_last,uint64_t deadline){uint64_t t=time_us_64();int r=transfer_inner(tx,rx,count,release_last,deadline);stats.transfer_us+=time_us_64()-t;return r;}
static int begin_transaction(void){
 if(sm<0||stats.faulted)return KFB_IO;
 /* SM is stalled at pull with SCK low after the previous end. */
 pio_sm_set_enabled(bus,(uint)sm,false);
 pio_sm_set_pindirs_with_mask(bus,(uint)sm,15u<<IO0,15u<<IO0);
 pio_sm_set_enabled(bus,(uint)sm,true);
 gpio_put(CS,0);wait_ns(MT_QSPI_CSS_NS);stats.transactions++;
 return 0;
}
static int end_transaction(int result,uint64_t started,uint64_t deadline){
 uint64_t end_started=time_us_64();
 if(!result){
  while(!pio_sm_is_tx_fifo_empty(bus,(uint)sm)||pio_sm_get_pc(bus,(uint)sm)!=pull_pc){
   if(expired(deadline)){result=KFB_TIMEOUT;break;}
   tight_loop_contents();
  }
 }
 if(result)abort_transaction();
 else{wait_ns(MT_QSPI_CSH_NS);gpio_put(CS,1);wait_ns(MT_QSPI_CSW_NS);}
 stats.end_us+=time_us_64()-end_started;
 uint32_t elapsed=(uint32_t)(time_us_64()-started);stats.elapsed_us+=elapsed;
 if(elapsed>stats.max_transaction_us)stats.max_transaction_us=elapsed;
 return result;
}
static int write_regs(void *ctx,uint8_t reg,bool inc,const uint8_t *data,size_t n){
 (void)ctx;if(reg>63||(n&&!data))return KFB_ARGUMENT;
 uint64_t started=time_us_64(),deadline=started+MT_QSPI_TIMEOUT_US;
 int r=begin_transaction();stats.begin_us+=time_us_64()-started;if(r)return r;
 uint8_t header=(uint8_t)(reg|(inc?64:0));
 r=transfer(&header,0,1,false,deadline);
 if(!r)r=transfer(data,0,n,false,deadline);
 return end_transaction(r,started,deadline);
}
static int read_regs(void *ctx,uint8_t reg,bool inc,uint8_t *data,size_t n){
 (void)ctx;if(reg>63||!data||n<1||n>256)return KFB_ARGUMENT;
 uint64_t started=time_us_64(),deadline=started+MT_QSPI_TIMEOUT_US;
 int r=begin_transaction();stats.begin_us+=time_us_64()-started;if(r)return r;
 uint8_t header[2]={(uint8_t)(128|reg|(inc?64:0)),(uint8_t)n};
 r=transfer(header,0,2,true,deadline); // release IO after count, BEFORE dummy
 if(!r)r=transfer(0,0,1,false,deadline); // exactly one dummy byte
 if(!r)r=transfer(0,data,n,false,deadline);
 return end_transaction(r,started,deadline);
}
static uint32_t now_ms(void *ctx){(void)ctx;return to_ms_since_boot(get_absolute_time());}
kfb_io mt_qspi_io(void){kfb_io io={0,read_regs,write_regs,now_ms};return io;}
const mt_qspi_stats *mt_qspi_statistics(void){return &stats;}
int mt_qspi_init(void){
 if(sm>=0)return KFB_ARGUMENT;
 if(clock_get_hz(clk_sys)!=MT_QSPI_SYS_HZ)return KFB_ARGUMENT;
 if(!pio_can_add_program(bus,&kagura_qspi_program))return KFB_IO;
 int claimed=pio_claim_unused_sm(bus,false);if(claimed<0)return KFB_IO;sm=claimed;
 offset=pio_add_program(bus,&kagura_qspi_program);loaded=true;pull_pc=offset+kagura_qspi_wrap_target;
 memset(&stats,0,sizeof stats);
 gpio_init(CS);gpio_put(CS,1);gpio_set_dir(CS,GPIO_OUT);
 pio_sm_config c=kagura_qspi_program_get_default_config(offset);
 kagura_host_sm_config(bus,(uint)sm,offset,&c,IO0,4,IO0,SCK,MT_QSPI_PIO_DIV);
 for(uint pin=IO0;pin<=SCK;pin++)pio_gpio_init(bus,pin);
 for(uint pin=IO0;pin<=CS;pin++){
  gpio_set_drive_strength(pin,GPIO_DRIVE_STRENGTH_2MA);
  gpio_set_slew_rate(pin,GPIO_SLEW_RATE_SLOW);
  if(pin<SCK)gpio_set_input_hysteresis_enabled(pin,true);
 }
 pio_sm_set_pins_with_mask(bus,(uint)sm,0,15u<<IO0);
 pio_sm_set_pindirs_with_mask(bus,(uint)sm,0,15u<<IO0);
 pio_sm_init(bus,(uint)sm,offset,&c);pio_sm_set_enabled(bus,(uint)sm,true);
 wait_ns(MT_QSPI_CSW_NS);return 0;
}
void mt_qspi_deinit(void){
 if(sm<0)return;
 pio_sm_set_enabled(bus,(uint)sm,false);
 pio_sm_set_pins_with_mask(bus,(uint)sm,0,1u<<SCK);
 wait_ns(MT_QSPI_CSH_NS);gpio_put(CS,1);wait_ns(MT_QSPI_CSW_NS);
 if(loaded)pio_remove_program(bus,&kagura_qspi_program,offset);
 pio_sm_unclaim(bus,(uint)sm);sm=-1;loaded=false;
 for(uint pin=IO0;pin<=SCK;pin++)gpio_init(pin);
}
