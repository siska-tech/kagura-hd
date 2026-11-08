// SPDX-License-Identifier: Apache-2.0
#include "b16.h"
#include "b16_profile.h"
#include "b16_queue.h"
#ifndef B16_WORK_ROUNDS
#define B16_WORK_ROUNDS 0
#endif
#include "b16_qspi.h"
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "hardware/clocks.h"
#include <stdio.h>
#include <string.h>
typedef struct {uint32_t ms,us,present_before,present_after,draw_start,deadline;} frame_record;
static unsigned scene_at(uint32_t ms){const uint32_t b[]={10000,30000,50000,70000,95000,120000,140000};unsigned i=0;while(i<7&&ms>=b[i])i++;return i;}
static uint64_t work_batches,work_us;static uint32_t work_checksum=0xb1616,work_reference=0xb1616,deadline_misses,call_over_budget;
static b16_profile_stats profile_snapshot;
static frame_record frame_log[4600];static unsigned frame_count;
static kfb_device gpu;static b16_engine engine;static b16_bus bus;
#if B16_GPU_QUEUE > 1 && B16_QUEUE_METRICS
uint64_t b16_queue_clock_us(void){return time_us_64();}
#endif
static int queue_selftest(void){
 uint8_t actual[32];int r=0;
 for(unsigned i=0;i<8&&!r;i++)r=kfb_fill_rect(&gpu,0,(int32_t)i*8,0,8,1,i+1);
 if(!r)r=kfb_fence(&gpu);
 if(!r)r=kfb_read_bytes(&gpu,0,actual,sizeof actual);
 for(unsigned i=0;i<32&&!r;i++)if(actual[i]!=(uint8_t)((i/4+1)*17))r=KFB_DEVICE;
 printf("QUEUE_SELFTEST commands=8 readback_bytes=32 rc=%d\n",r);
 return r;
}
static int benchmark(void){
 const unsigned lengths[]={1,2,4,8,16,32,64,128,256,512};uint8_t buffer[512]={0},readback[512];int r=0;
 // Raw repeated pointer writes are legal only while the GPU is idle.
 r=kfb_fence(&gpu);if(r)return r;
 for(unsigned i=0;i<10&&!r;i++)for(unsigned repeat=0;repeat<16&&!r;repeat++){
  unsigned n=lengths[i];mt_qspi_stats base=*mt_qspi_statistics();uint64_t t=time_us_64();r=gpu.io.write(gpu.io.context,25,false,buffer,n);printf("BENCH raw_pointer_write n=%u us=%llu rc=%d\n",n,(unsigned long long)(time_us_64()-t),r);
  if(r){break;}
  t=time_us_64();unsigned chunk=n>256?256:n;r=gpu.io.read(gpu.io.context,0,false,readback,chunk);if(!r&&n>256)r=gpu.io.read(gpu.io.context,0,false,readback+256,n-256);printf("BENCH raw_csr_read n=%u transactions=%u us=%llu rc=%d\n",n,n>256?2:1,(unsigned long long)(time_us_64()-t),r);
  if(r){break;}
  t=time_us_64();r=kfb_write_bytes(&gpu,0x100000,buffer,n);printf("BENCH psram_write n=%u us=%llu rc=%d\n",n,(unsigned long long)(time_us_64()-t),r);
  if(r){break;}
  t=time_us_64();r=kfb_read_bytes(&gpu,0x100000,readback,n);printf("BENCH psram_read n=%u us=%llu rc=%d\n",n,(unsigned long long)(time_us_64()-t),r);if(!r&&memcmp(buffer,readback,n))r=KFB_DEVICE;
  const mt_qspi_stats *s=mt_qspi_statistics();printf("BENCH stages n=%u begin_us=%llu transfer_us=%llu end_us=%llu dma_setup_us=%llu dma_wait_us=%llu wire_wait_us=%llu fifo_stalls=%llu timeouts=%lu gpu_error=%u\n",n,(unsigned long long)(s->begin_us-base.begin_us),(unsigned long long)(s->transfer_us-base.transfer_us),(unsigned long long)(s->end_us-base.end_us),(unsigned long long)(s->dma_setup_us-base.dma_setup_us),(unsigned long long)(s->dma_wait_us-base.dma_wait_us),(unsigned long long)(s->wire_wait_us-base.wire_wait_us),(unsigned long long)(s->fifo_stalls-base.fifo_stalls),(unsigned long)(s->timeouts-base.timeouts),gpu.last_device_error);
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
int main(void){b16_profile_init(time_us_64);set_sys_clock_khz(120000,true);stdio_init_all();while(!stdio_usb_connected())sleep_ms(10);
 printf("BEYOND 16 COLORS / release_ready=false / g=150s autoplay b=benchmark q=idle; no automatic start\n");int key=0;while(key!='g'&&key!='b')key=getchar_timeout_us(100000);
 printf("CONFIG gpu_queue=%d queue_metrics=%d merged_lettering=%d completion_burst=%d\n",B16_GPU_QUEUE,B16_QUEUE_METRICS,B16_MERGE_LETTERING,B16_COMPLETION_BURST);
 int rc=mt_qspi_init();kfb_io raw=mt_qspi_io();
 if(!rc)rc=kfb_init(&gpu,b16_cached_io(&bus,raw),2000);
 if(!rc)rc=kfb_probe(&gpu);
 /* Admission gate precedes ALL benchmark PSRAM/audio accesses as well. */
 if(!rc){uint8_t id[7];rc=raw.read(raw.context,0,true,id,7);if(!rc&&(memcmp(id,"KFB1",4)||id[4]!=1||id[5]!=4||id[6]!=255))rc=KFB_VERSION;}
 if(!rc)rc=queue_selftest();
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
 b16_profile_init(time_us_64);
#if B16_GPU_QUEUE > 1 && B16_QUEUE_METRICS
 b16_queue_metrics_reset();
#endif
 while(!rc){uint32_t ms=(uint32_t)(to_ms_since_boot(get_absolute_time())-epoch_ms);if(ms>=B16_DURATION)break;BPUSH(B16_USB);int input=getchar_timeout_us(0);BPOP();if(input=='q')break;
  uint32_t before=engine.stats.frames;uint64_t t=time_us_64();
#if B16_SCHEDULER == 1
  uint64_t frame_deadline=(uint64_t)epoch_ms*1000u+((uint64_t)(ms*30u/1000u+1u)*1000000u)/30u;
#else
  uint64_t frame_deadline=t+33333u;
#endif
  BPUSH(ms<engine.next_frame?B16_NO_DRAW:B16_DRAW);rc=b16_tick(&engine,ms);BPOP();uint64_t dt=time_us_64()-t;if(engine.stats.frames!=before){if(dt>33333u)call_over_budget++;if(b16_present_after>frame_deadline)deadline_misses++;sum_us+=dt;if(dt>worst_us)worst_us=dt;drawn++;if(frame_count<4600)frame_log[frame_count++]=(frame_record){ms,(uint32_t)dt,(uint32_t)b16_present_before,(uint32_t)b16_present_after,(uint32_t)t,(uint32_t)frame_deadline};
#ifdef B16_VERBOSE_FRAMES
 printf("FRAME ms=%lu scene=%lu us=%llu commands=%llu blit_pixels=%llu\n",(unsigned long)ms,(unsigned long)engine.stats.scene,(unsigned long long)dt,(unsigned long long)engine.stats.commands,(unsigned long long)engine.stats.blit_pixels);
#endif
 }
  BPUSH(B16_LOG);if(ms-logged>=1000){const mt_qspi_stats *s=mt_qspi_statistics();printf("PERF ms=%lu scene=%d frames=%lu skipped=%lu transactions=%llu wire_bytes=%llu transaction_us=%llu max_transaction_us=%lu timeouts=%lu frame_sum_us=%llu worst_us=%llu audio_fault=%d\n",(unsigned long)ms,engine.scene,(unsigned long)drawn,(unsigned long)engine.stats.skipped,(unsigned long long)s->transactions,(unsigned long long)s->wire_bytes,(unsigned long long)s->elapsed_us,(unsigned long)s->max_transaction_us,(unsigned long)s->timeouts,(unsigned long long)sum_us,(unsigned long long)worst_us,engine.error);printf("BUS ms=%lu begin_us=%llu transfer_us=%llu end_us=%llu\n",(unsigned long)ms,(unsigned long long)s->begin_us,(unsigned long long)s->transfer_us,(unsigned long long)s->end_us);logged=ms;}BPOP();
#if B16_WORK_ROUNDS > 0
 /* At most one finite batch per idle tick; actual deadline overruns measured.
  * No transport/GPU calls and no shared rendering workspace access. */
 BPUSH(B16_SCHEDULE);uint32_t current=(uint32_t)(to_ms_since_boot(get_absolute_time())-epoch_ms);bool spare=!rc&&engine.next_frame>current+2;BPOP();
 if(spare){BPUSH(B16_WORK);uint64_t w=time_us_64();work_checksum=b16_work(work_checksum,B16_WORK_ROUNDS);work_us+=time_us_64()-w;work_batches++;BPOP();}
#endif
 BPUSH(B16_SLEEP);sleep_ms(1);BPOP();
 }
 profile_snapshot=*b16_profile_get();
 if(!rc)rc=b16_finish(&engine);
 stopped:for(unsigned i=0;i<frame_count;i++){const frame_record *f=&frame_log[i];printf("FRAME ms=%lu scene=%lu us=%lu present_before_us=%lu present_after_us=%lu draw_start_us=%lu deadline_us=%lu\n",(unsigned long)f->ms,(unsigned long)scene_at(f->ms),(unsigned long)f->us,(unsigned long)f->present_before,(unsigned long)f->present_after,(unsigned long)f->draw_start,(unsigned long)f->deadline);}
#if B16_WORK_ROUNDS > 0
 for(uint64_t i=0;i<work_batches;i++)work_reference=b16_work(work_reference,B16_WORK_ROUNDS);
 if(work_reference!=work_checksum)rc=KFB_DEVICE;
#endif
 const b16_profile_stats *profile=&profile_snapshot;
 for(unsigned i=0;i<B16_REGIONS;i++)printf("PROFILE region=%u us=%llu calls=%llu overflow=%lu\n",i,(unsigned long long)profile->us[i],(unsigned long long)profile->calls[i],(unsigned long)profile->overflow);
 printf("WORK batches=%llu rounds=%u us=%llu checksum=%lu valid=%d call_over_budget=%lu deadline_misses=%lu\n",(unsigned long long)work_batches,B16_WORK_ROUNDS,(unsigned long long)work_us,(unsigned long)work_checksum,work_reference==work_checksum,(unsigned long)call_over_budget,(unsigned long)deadline_misses);
#if B16_GPU_QUEUE > 1
 const b16_queue_stats *qs=b16_queue_statistics();
 printf("QUEUE depth=8 submitted=%lu retired=%lu peak=%lu pending=%lu barriers=%lu errors=%lu\n",(unsigned long)qs->submitted,(unsigned long)qs->retired,(unsigned long)qs->peak,(unsigned long)qs->pending,(unsigned long)qs->barriers,(unsigned long)qs->errors);
#if B16_QUEUE_METRICS
 const b16_queue_metrics *qm=b16_queue_measurements();
 printf("QBURST bursts=%lu hits=%lu misses=%lu fallback=%lu\n",(unsigned long)qm->completion_bursts,(unsigned long)qm->completion_hits,(unsigned long)qm->completion_misses,(unsigned long)qm->fallback_completions);
 for(unsigned i=0;i<4;i++)printf("QRET reason=%u calls=%lu samples=%lu poll_us=%llu metadata_us=%llu ack_us=%llu\n",i,(unsigned long)qm->retire_calls[i],(unsigned long)qm->retire_samples[i],(unsigned long long)qm->poll_us[i],(unsigned long long)qm->metadata_us[i],(unsigned long long)qm->ack_us[i]);
 for(unsigned i=0;i<8;i++)printf("QSYNC op=%u calls=%lu nonempty=%lu samples=%lu drain_us=%llu command_us=%llu\n",i,(unsigned long)qm->sync_calls[i],(unsigned long)qm->sync_nonempty[i],(unsigned long)qm->sync_samples[i],(unsigned long long)qm->sync_drain_us[i],(unsigned long long)qm->sync_command_us[i]);
#endif
#endif
 printf("STOP rc=%d; no retry; release_ready=false\n",rc);mt_qspi_deinit();while(true)tight_loop_contents();}
