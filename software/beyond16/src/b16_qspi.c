// SPDX-License-Identifier: Apache-2.0
// KAGURA-9 PIO/timing reused; HD raw register protocol has 6 address bits.
#include "b16_qspi.h"
#include "b16_profile.h"
#ifndef B16_TRANSPORT
#define B16_TRANSPORT 0
#endif
#ifndef B16_DMA_THRESHOLD
#define B16_DMA_THRESHOLD 0
#endif
#if B16_TRANSPORT
#include "hardware/dma.h"
static int dma_tx=-1,dma_rx=-1;
static uint32_t dma_words[512],dma_sink;
#endif
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/pio.h"
#include "kagura_host.pio.h"
#include <string.h>
enum { IO0=2,SCK=6,CS=7 };
/* B16_HOST_LANES=1 builds the SPI host for the SPI-only FPGA build (the two
 * are build-time exclusive): KAGURA-9 kagura_spi, MOSI=IO0, MISO=IO1. The
 * host drives only IO0; IO1 belongs to the FPGA, IO2/IO3 stay inputs. */
#ifndef B16_HOST_LANES
#define B16_HOST_LANES 4
#endif
#if B16_HOST_LANES==1
#define HOST_PROGRAM kagura_spi_program
#define HOST_WRAP kagura_spi_wrap_target
#define HOST_CONFIG kagura_spi_program_get_default_config
#define HOST_SHIFT 23
#define HOST_DRIVE (1u<<IO0)
#ifndef B16_SPI_PIO_DIV
#define B16_SPI_PIO_DIV MT_QSPI_PIO_DIV
#endif
#elif B16_HOST_LANES==4
#define HOST_PROGRAM kagura_qspi_program
#define HOST_WRAP kagura_qspi_wrap_target
#define HOST_CONFIG kagura_qspi_program_get_default_config
#define HOST_SHIFT 22
#define HOST_DRIVE (15u<<IO0)
#else
#error "B16_HOST_LANES must be 1 or 4"
#endif
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
static bool expired(uint64_t deadline){BDETAIL(B16_DEADLINE);bool r=time_us_64()>=deadline;BDETAIL_END();return r;}
static void abort_transaction(bool timeout){
 /* Stop the SM, force SCK low and discard FIFO state. Raise CS before handing
  * IO ownership back. Latch the fault: don't replay uncertain commands. */
#if B16_TRANSPORT
 if(dma_tx>=0)dma_channel_abort((uint)dma_tx);
 if(dma_rx>=0)dma_channel_abort((uint)dma_rx);
#endif
 pio_sm_set_enabled(bus,(uint)sm,false);
 pio_sm_clear_fifos(bus,(uint)sm);
 pio_sm_restart(bus,(uint)sm);
 pio_sm_exec(bus,(uint)sm,pio_encode_jmp(pull_pc)|pio_encode_sideset(1,0));
 pio_sm_set_pins_with_mask(bus,(uint)sm,0,1u<<SCK);
 wait_ns(MT_QSPI_CSH_NS);gpio_put(CS,1);wait_ns(MT_QSPI_CSW_NS);
 pio_sm_set_pindirs_with_mask(bus,(uint)sm,0,15u<<IO0);
 stats.faulted=true;if(timeout)stats.timeouts++;
}
static int transfer_inner(const uint8_t *tx,uint8_t *rx,size_t count,bool release_last,uint64_t deadline){
 size_t sent=0,got=0;
#if B16_HOST_FAST
 unsigned check_budget=0;
#endif
 while(got<count){
  bool progress=false;
  if(sent<count&&!pio_sm_is_tx_fifo_full(bus,(uint)sm)){
   uint32_t word=(uint32_t)(tx?tx[sent]:0)<<HOST_SHIFT;
   /* QSPI only: bit30 releases IO0..3 after the byte. SPI never turns IO0 around. */
   if(B16_HOST_LANES==4&&release_last&&sent+1==count)word|=1u<<30;
   /* bit31 remains 0: KAGURA-9 queue-consuming registers/BUSY gating do
    * not describe HD's descriptor protocol. kfb SDK serializes commands. */
   BDETAIL(B16_TX);pio_sm_put(bus,(uint)sm,word);sent++;progress=true;BDETAIL_END();
  }
  if(!pio_sm_is_rx_fifo_empty(bus,(uint)sm)){
   BDETAIL(B16_RX);uint8_t value=(uint8_t)pio_sm_get(bus,(uint)sm);
   if(rx)rx[got]=value;
   got++;stats.wire_bytes++;progress=true;BDETAIL_END();
  }
  if(!progress){BDETAIL(B16_FIFO_WAIT);stats.fifo_stalls++;tight_loop_contents();BDETAIL_END();}
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
#if B16_TRANSPORT
/* Synchronous private staging: no caller-owned byte buffer is DMA-visible.
 * RX is drained even on WRITE (PIO autopushes every byte). No chaining/IRQ. */
static int transfer_dma(const uint8_t *data,size_t n,uint64_t deadline){
 BPUSH(B16_DMA_SETUP);uint64_t start=time_us_64();
 for(size_t i=0;i<n;i++)dma_words[i]=(uint32_t)data[i]<<HOST_SHIFT;
 dma_channel_config tx=dma_channel_get_default_config((uint)dma_tx);
 channel_config_set_transfer_data_size(&tx,DMA_SIZE_32);
 channel_config_set_read_increment(&tx,true);channel_config_set_write_increment(&tx,false);
 channel_config_set_dreq(&tx,pio_get_dreq(bus,(uint)sm,true));
 dma_channel_config rx=dma_channel_get_default_config((uint)dma_rx);
 channel_config_set_transfer_data_size(&rx,DMA_SIZE_32);
 channel_config_set_read_increment(&rx,false);channel_config_set_write_increment(&rx,false);
 channel_config_set_dreq(&rx,pio_get_dreq(bus,(uint)sm,false));
 dma_channel_configure((uint)dma_rx,&rx,&dma_sink,&bus->rxf[sm],n,false);
 dma_channel_configure((uint)dma_tx,&tx,&bus->txf[sm],dma_words,n,false);
 /* Arm the RX sink first. It waits on RX DREQ before TX can produce bytes. */
 dma_start_channel_mask(1u<<(uint)dma_rx);dma_start_channel_mask(1u<<(uint)dma_tx);
 stats.dma_setup_us+=time_us_64()-start;BPOP();BPUSH(B16_DMA_WAIT);start=time_us_64();
 while(dma_channel_is_busy((uint)dma_tx)||dma_channel_is_busy((uint)dma_rx)){
  if(expired(deadline)){BPOP();return KFB_TIMEOUT;}tight_loop_contents();
 }
 stats.dma_wait_us+=time_us_64()-start;BPOP();
 const uint32_t errors=DMA_CH0_CTRL_TRIG_READ_ERROR_BITS|DMA_CH0_CTRL_TRIG_WRITE_ERROR_BITS;
 if((dma_channel_hw_addr((uint)dma_tx)->ctrl_trig&errors)||(dma_channel_hw_addr((uint)dma_rx)->ctrl_trig&errors)||dma_channel_hw_addr((uint)dma_tx)->transfer_count||dma_channel_hw_addr((uint)dma_rx)->transfer_count){stats.dma_errors++;return KFB_IO;}
 if(expired(deadline))return KFB_TIMEOUT;
 stats.dma_transfers++;stats.wire_bytes+=n;
 /* end_transaction still requires TX FIFO empty AND SM stalled at pull. */
 return 0;
}
#endif
static int begin_transaction(void){
 if(sm<0||stats.faulted)return KFB_IO;
 /* SM is stalled at pull with SCK low after the previous end. */
 pio_sm_set_enabled(bus,(uint)sm,false);
 BDETAIL(B16_DIRECTION);pio_sm_set_pindirs_with_mask(bus,(uint)sm,HOST_DRIVE,15u<<IO0);BDETAIL_END();
 pio_sm_set_enabled(bus,(uint)sm,true);
 BDETAIL(B16_CS_SETUP);gpio_put(CS,0);wait_ns(MT_QSPI_CSS_NS);BDETAIL_END();stats.transactions++;
 return 0;
}
static int end_transaction(int result,uint64_t started,uint64_t deadline){
 uint64_t end_started=time_us_64();
 if(!result){
  BPUSH(B16_WIRE);uint64_t wire_start=time_us_64();
  while(!pio_sm_is_tx_fifo_empty(bus,(uint)sm)||pio_sm_get_pc(bus,(uint)sm)!=pull_pc){
   if(expired(deadline)){result=KFB_TIMEOUT;break;}
   tight_loop_contents();
  }
  stats.wire_wait_us+=time_us_64()-wire_start;BPOP();
 }
 if(result)abort_transaction(result==KFB_TIMEOUT);
 else{BDETAIL(B16_CS_HOLD);wait_ns(MT_QSPI_CSH_NS);gpio_put(CS,1);wait_ns(MT_QSPI_CSW_NS);BDETAIL_END();}
 stats.end_us+=time_us_64()-end_started;
 uint32_t elapsed=(uint32_t)(time_us_64()-started);stats.elapsed_us+=elapsed;
 if(elapsed>stats.max_transaction_us)stats.max_transaction_us=elapsed;
 return result;
}
static int write_regs(void *ctx,uint8_t reg,bool inc,const uint8_t *data,size_t n){
 (void)ctx;if(reg>63||(n&&!data))return KFB_ARGUMENT;
 uint64_t started=time_us_64(),deadline=started+MT_QSPI_TIMEOUT_US;
 BPUSH(B16_BEGIN);int r=begin_transaction();BPOP();stats.begin_us+=time_us_64()-started;if(r)return r;
 uint8_t header=(uint8_t)(reg|(inc?64:0));
 r=transfer(&header,0,1,false,deadline);
 if(!r){
#if B16_TRANSPORT
  size_t threshold=B16_TRANSPORT==1?64u:B16_DMA_THRESHOLD;
  if(threshold&&n>=threshold&&n<=512&&!inc&&(reg==24||reg==25))r=transfer_dma(data,n,deadline);
  else
#endif
  r=transfer(data,0,n,false,deadline);
 }
 BPUSH(B16_END);r=end_transaction(r,started,deadline);BPOP();return r;
}
static int read_regs(void *ctx,uint8_t reg,bool inc,uint8_t *data,size_t n){
 (void)ctx;if(reg>63||!data||n<1||n>256)return KFB_ARGUMENT;
 uint64_t started=time_us_64(),deadline=started+MT_QSPI_TIMEOUT_US;
 BPUSH(B16_BEGIN);int r=begin_transaction();BPOP();stats.begin_us+=time_us_64()-started;if(r)return r;
 uint8_t header[2]={(uint8_t)(128|reg|(inc?64:0)),(uint8_t)n};
 r=transfer(header,0,2,true,deadline); // release IO after count, BEFORE dummy
 if(!r)r=transfer(0,0,1,false,deadline); // exactly one dummy byte
 if(!r)r=transfer(0,data,n,false,deadline);
 BPUSH(B16_END);r=end_transaction(r,started,deadline);BPOP();return r;
}
static uint32_t now_ms(void *ctx){(void)ctx;return to_ms_since_boot(get_absolute_time());}
kfb_io mt_qspi_io(void){kfb_io io={0,read_regs,write_regs,now_ms};return io;}
const mt_qspi_stats *mt_qspi_statistics(void){return &stats;}
int mt_qspi_init(void){
 if(sm>=0)return KFB_ARGUMENT;
 if(clock_get_hz(clk_sys)!=MT_QSPI_SYS_HZ)return KFB_ARGUMENT;
 if(!pio_can_add_program(bus,&HOST_PROGRAM))return KFB_IO;
 int claimed=pio_claim_unused_sm(bus,false);if(claimed<0)return KFB_IO;sm=claimed;
 offset=pio_add_program(bus,&HOST_PROGRAM);loaded=true;pull_pc=offset+HOST_WRAP;
#if B16_TRANSPORT
 dma_tx=dma_claim_unused_channel(false);dma_rx=dma_claim_unused_channel(false);
 if(dma_tx<0||dma_rx<0){if(dma_tx>=0)dma_channel_unclaim((uint)dma_tx);if(dma_rx>=0)dma_channel_unclaim((uint)dma_rx);dma_tx=dma_rx=-1;pio_remove_program(bus,&HOST_PROGRAM,offset);pio_sm_unclaim(bus,(uint)sm);sm=-1;loaded=false;return KFB_IO;}
#endif
 memset(&stats,0,sizeof stats);
 gpio_init(CS);gpio_put(CS,1);gpio_set_dir(CS,GPIO_OUT);
 pio_sm_config c=HOST_CONFIG(offset);
#if B16_HOST_LANES==1
 kagura_host_sm_config(bus,(uint)sm,offset,&c,IO0,1,IO0+1,SCK,B16_SPI_PIO_DIV);
#else
 kagura_host_sm_config(bus,(uint)sm,offset,&c,IO0,4,IO0,SCK,MT_QSPI_PIO_DIV);
#endif
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
#if B16_TRANSPORT
 if(dma_tx>=0){dma_channel_abort((uint)dma_tx);dma_channel_unclaim((uint)dma_tx);dma_tx=-1;}
 if(dma_rx>=0){dma_channel_abort((uint)dma_rx);dma_channel_unclaim((uint)dma_rx);dma_rx=-1;}
#endif
 pio_sm_set_enabled(bus,(uint)sm,false);
 pio_sm_set_pins_with_mask(bus,(uint)sm,0,1u<<SCK);
 wait_ns(MT_QSPI_CSH_NS);gpio_put(CS,1);wait_ns(MT_QSPI_CSW_NS);
 if(loaded)pio_remove_program(bus,&HOST_PROGRAM,offset);
 pio_sm_unclaim(bus,(uint)sm);sm=-1;loaded=false;
 for(uint pin=IO0;pin<=SCK;pin++)gpio_init(pin);
}
