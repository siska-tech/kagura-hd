// SPDX-License-Identifier: Apache-2.0
#include "b16.h"
#include "../../midnight_terminal/src/mt_qspi.h"
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "hardware/clocks.h"
#include <stdio.h>
#include <string.h>
static kfb_device gpu;static b16_engine engine;static b16_bus bus;
static int benchmark(void){
 const unsigned lengths[]={1,2,4,8,16,64,512};uint8_t buffer[512]={0},readback[512];int r=0;
 // Raw repeated pointer writes are legal only while the GPU is idle.
 r=kfb_fence(&gpu);if(r)return r;
 for(unsigned i=0;i<7&&!r;i++){
  unsigned n=lengths[i];uint64_t t=time_us_64();r=gpu.io.write(gpu.io.context,25,false,buffer,n);printf("BENCH raw_pointer_write n=%u us=%llu rc=%d\n",n,(unsigned long long)(time_us_64()-t),r);
  if(r){break;}
  t=time_us_64();unsigned chunk=n>256?256:n;r=gpu.io.read(gpu.io.context,0,false,readback,chunk);if(!r&&n>256)r=gpu.io.read(gpu.io.context,0,false,readback+256,n-256);printf("BENCH raw_csr_read n=%u transactions=%u us=%llu rc=%d\n",n,n>256?2:1,(unsigned long long)(time_us_64()-t),r);
  if(r){break;}
  t=time_us_64();r=kfb_write_bytes(&gpu,0x100000,buffer,n);printf("BENCH psram_write n=%u us=%llu rc=%d\n",n,(unsigned long long)(time_us_64()-t),r);
  if(r){break;}
  t=time_us_64();r=kfb_read_bytes(&gpu,0x100000,readback,n);printf("BENCH psram_read n=%u us=%llu rc=%d\n",n,(unsigned long long)(time_us_64()-t),r);if(!r&&memcmp(buffer,readback,n))r=KFB_DEVICE;
 }
 for(unsigned i=0;i<64&&!r;i++){
  uint8_t command[16]={0};uint16_t tag=0;uint64_t t=time_us_64();r=kfb_submit(&gpu,command,0,0,&tag);uint64_t issued=time_us_64();if(!r)r=kfb_wait(&gpu,tag);printf("BENCH fence issue_us=%llu completion_us=%llu rc=%d\n",(unsigned long long)(issued-t),(unsigned long long)(time_us_64()-issued),r);
 }
 // Bounded FILL/BLIT/PRESENT trials; destructive only after explicit firmware b.
 for(unsigned i=0;i<8&&!r;i++){
  uint64_t t=time_us_64();r=kfb_fill_rect(&gpu,0,32,96,32,32,i);printf("BENCH fill us=%llu rc=%d\n",(unsigned long long)(time_us_64()-t),r);
  if(r){break;}
  t=time_us_64();r=kfb_copy_rect(&gpu,0,32,96,1,32,96,32,32);printf("BENCH blit pixels=1024 us=%llu rc=%d\n",(unsigned long long)(time_us_64()-t),r);
  if(r){break;}
  t=time_us_64();r=kfb_present(&gpu,1);printf("BENCH present us=%llu rc=%d\n",(unsigned long long)(time_us_64()-t),r);
 }
 return r;
}
int main(void){set_sys_clock_khz(120000,true);stdio_init_all();while(!stdio_usb_connected())sleep_ms(10);
 printf("BEYOND 16 COLORS / release_ready=false / g=150s autoplay b=benchmark q=idle; no automatic start\n");int key=0;while(key!='g'&&key!='b')key=getchar_timeout_us(100000);
 int rc=mt_qspi_init();kfb_io raw=mt_qspi_io();
 if(!rc)rc=kfb_init(&gpu,b16_cached_io(&bus,raw),2000);
 if(!rc)rc=kfb_probe(&gpu);
 if(key=='b'&&!rc){rc=b16_audio_stop(&gpu);printf("BENCH_PHASE PCM_STOPPED\n");
 if(!rc)rc=benchmark();
 if(!rc)rc=b16_init(&engine,&gpu,0xb1616);
 if(!rc){rc=b16_audio(&gpu,-1);}
 printf("BENCH_PHASE PCM_PLAYING\n");
 if(!rc)rc=benchmark();
 if(!rc){rc=b16_audio_stop(&gpu);}
 goto stopped;}
 if(!rc)rc=b16_init(&engine,&gpu,0xb1616);
 if(!rc)rc=b16_tick(&engine,0);
 // Timeline epoch follows actual completed BGM COMMIT; startup/preload excluded.
 uint32_t epoch_ms=engine.audio_epoch_ms;uint32_t logged=0;uint64_t sum_us=0,worst_us=0;uint32_t drawn=0;
 while(!rc){uint32_t ms=(uint32_t)(to_ms_since_boot(get_absolute_time())-epoch_ms);if(ms>=B16_DURATION||getchar_timeout_us(0)=='q')break;
  uint32_t before=engine.stats.frames;uint64_t t=time_us_64();rc=b16_tick(&engine,ms);uint64_t dt=time_us_64()-t;if(engine.stats.frames!=before){sum_us+=dt;if(dt>worst_us)worst_us=dt;drawn++;printf("FRAME ms=%lu scene=%lu us=%llu commands=%llu blit_pixels=%llu\n",(unsigned long)ms,(unsigned long)engine.stats.scene,(unsigned long long)dt,(unsigned long long)engine.stats.commands,(unsigned long long)engine.stats.blit_pixels);}
  if(ms-logged>=1000){const mt_qspi_stats *s=mt_qspi_statistics();printf("PERF ms=%lu scene=%d frames=%lu skipped=%lu transactions=%llu wire_bytes=%llu transaction_us=%llu max_transaction_us=%lu timeouts=%lu frame_sum_us=%llu worst_us=%llu audio_fault=%d\n",(unsigned long)ms,engine.scene,(unsigned long)drawn,(unsigned long)engine.stats.skipped,(unsigned long long)s->transactions,(unsigned long long)s->wire_bytes,(unsigned long long)s->elapsed_us,(unsigned long)s->max_transaction_us,(unsigned long)s->timeouts,(unsigned long long)sum_us,(unsigned long long)worst_us,engine.error);logged=ms;}sleep_ms(1);
 }
 if(!rc)rc=b16_finish(&engine);
 stopped:printf("STOP rc=%d; no retry; release_ready=false\n",rc);mt_qspi_deinit();while(true)tight_loop_contents();}
