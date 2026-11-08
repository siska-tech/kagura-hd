// SPDX-License-Identifier: Apache-2.0
#include "kagura_fb.h"
#include "b16_queue.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned count,head,submitted,acked,barriers,full_done,fail_mode,ack_before;
static unsigned now;
static unsigned delayed_polls,snapshot_reads,separate_completion_reads;
#if B16_QUEUE_METRICS
uint64_t b16_queue_clock_us(void){static uint64_t t;return ++t;}
#endif
static uint8_t staging[16],commands[8][16],sticky;
static uint16_t tagof(const uint8_t *p){return (uint16_t)(p[2]|(p[3]<<8));}
static uint16_t lasttag;
static int rd(void *ctx,uint8_t reg,bool inc,uint8_t *p,size_t n){
 (void)ctx;memset(p,0,n);
 if(reg==27){
  bool done=count!=0 && delayed_polls==0;
  if(delayed_polls)delayed_polls--;
  p[0]=2|(count==8?1:0)|(done?16:0)|(fail_mode==3?128:0);if(count==8)full_done++;
  if(inc && n==4){
   snapshot_reads++;uint16_t t=count?tagof(commands[head]):0;if(fail_mode==2)t++;
   p[1]=done?(uint8_t)t:0xef;p[2]=done?(uint8_t)(t>>8):0xbe;p[3]=done?(fail_mode==1?3:0):0xff;
  }
  if(fail_mode==4)return -1; // Simulate partial transfer with no usable snapshot.
 }
 else if(reg==28){assert(count);uint16_t tag=tagof(commands[head]);if(fail_mode==2)tag++;
 separate_completion_reads++;
 p[0]=(uint8_t)tag;if(n>1)p[1]=tag>>8;if(n>2)p[2]=fail_mode==1?3:0;}
 else if(reg==7)p[0]=fail_mode==5?3:sticky;
 else if(reg==6)p[0]=255;
 (void)inc;return 0;
}
static int wr(void *ctx,uint8_t reg,bool inc,const uint8_t *p,size_t n){
 (void)ctx;
 if(reg==7){sticky=0;if(inc){assert(n==17);memcpy(staging,p+1,16);}}
 else if(reg==8){assert(n==16);memcpy(staging,p,16);}
 else if(reg==26){assert(count<8);if(staging[0]!=1 && staging[0]!=2){assert(!count);barriers++;}
  uint16_t t=tagof(staging);if(submitted)assert(t==(uint16_t)(lasttag+1));lasttag=t;
  memcpy(commands[(head+count)&7],staging,16);count++;submitted++;}
 else if(reg==31){assert(count);head=(head+1)&7;count--;acked++;}
 return 0;
}
static uint32_t ms(void *c){(void)c;return now++;}
int main(int argc,char **argv){
 kfb_device d;kfb_io io={0,rd,wr,ms};assert(!kfb_init(&d,io,20));d.connected=true;d.next_tag=65530;
 if(argc>1 && (!strcmp(argv[1],"delay") || !strcmp(argv[1],"race"))){
  for(unsigned i=0;i<8;i++)assert(!kfb_fill_rect(&d,0,0,0,8,1,2));
  delayed_polls=!strcmp(argv[1],"delay")?3:1;
  assert(!kfb_fence(&d));assert(!count && submitted==9 && acked==9);
#if B16_COMPLETION_BURST
  assert(snapshot_reads==8 && separate_completion_reads==2);
#if B16_QUEUE_METRICS
  const b16_queue_metrics *m=b16_queue_measurements();
  assert(m->completion_bursts==8 && m->completion_hits==7 && m->completion_misses==1 && m->fallback_completions==1);
#endif
#endif
  puts("PASS incomplete/racing snapshot ignored, status-only fallback, ordered completion");return 0;
 }
 if(argc>1){
  assert(!kfb_fill_rect(&d,0,0,0,8,1,2));ack_before=acked;int expected=KFB_DEVICE;
  if(!strcmp(argv[1],"tag"))fail_mode=2;
  else if(!strcmp(argv[1],"transport")){fail_mode=3;expected=KFB_TRANSPORT;}
  else if(!strcmp(argv[1],"io")){fail_mode=4;expected=KFB_IO;}
  else if(!strcmp(argv[1],"sticky"))fail_mode=5;
  else if(!strcmp(argv[1],"timeout")){delayed_polls=1000;expected=KFB_TIMEOUT;}
  else fail_mode=1;
  assert(kfb_fence(&d)==expected);assert(kfb_fill_rect(&d,0,0,0,8,1,3)==expected);
  assert(submitted==1);if(fail_mode!=1 && fail_mode!=5)assert(acked==ack_before);
  puts("PASS queue first-fault latch; no replay; unexpected tag not ACKed");return 0;}
 for(unsigned i=0;i<100;i++)assert(!kfb_fill_rect(&d,i&1,-2,0,10,1,i&15));
 for(unsigned i=0;i<16;i++)assert(!kfb_palette(&d,i,i*17));
 assert(!kfb_present(&d,1));assert(!count);assert(submitted==117 && acked==117 && barriers==1);
 const b16_queue_stats *s=b16_queue_statistics();assert(s->peak==8 && !s->pending && s->submitted==116 && s->retired==116 && full_done);
 assert(!kfb_copy_rect(&d,0,0,0,1,0,0,8,1));assert(!count);
 uint8_t desc[16]={0};uint16_t tag;assert(!kfb_submit(&d,desc,0,0,&tag));assert(!kfb_wait(&d,tag));assert(!count);
#if B16_COMPLETION_BURST
 assert(snapshot_reads==116 && separate_completion_reads==3);
#else
 assert(snapshot_reads==0 && separate_completion_reads==119);
#endif
 puts("PASS queue wrap/full+DONE/barriers/clipping/tags/ordered ACK; 116 queued commands");
#if B16_QUEUE_METRICS
 const b16_queue_metrics *m=b16_queue_measurements();
 assert(m->retire_calls[0]+m->retire_calls[2]==116);
 assert(m->sync_calls[3]==1 && m->sync_calls[6]==1 && m->retire_samples[0]>0);
 assert(m->ack_us[0]>0 && m->poll_us[0]>0 && m->metadata_us[0]>0);
 b16_queue_metrics_reset();assert(!m->retire_calls[0] && !m->sync_calls[3]);
 puts("PASS sampled queue metric partition and reset");
#endif
}
