// SPDX-License-Identifier: Apache-2.0
// Experimental extension included inside the existing SDK translation unit.
// Only FILL/PALETTE return after admission. All other operations drain first.
// One device/owner, fixed software capacity equal to the approved hardware.
#if B16_GPU_QUEUE != 8
#error "This experiment requires the explicitly approved depth-eight bitstream"
#endif
static kfb_device *b16_queue_owner;
static uint16_t b16_queue_tags[8];
static unsigned b16_queue_head;
static int b16_queue_fault;
int b16_queue_retiring;
static b16_queue_stats b16_queue_counters;
static unsigned b16_queue_drain_reason=3;
#if B16_QUEUE_METRICS
static b16_queue_metrics b16_queue_measure;
int b16_queue_sample_reason=-1;
const b16_queue_metrics *b16_queue_measurements(void){return &b16_queue_measure;}
void b16_queue_metrics_reset(void){memset(&b16_queue_measure,0,sizeof b16_queue_measure);}
void b16_queue_burst_observe(int done){b16_queue_measure.completion_bursts++;if(done)b16_queue_measure.completion_hits++;else b16_queue_measure.completion_misses++;}
void b16_queue_fallback_observe(void){b16_queue_measure.fallback_completions++;}
void b16_queue_observe(uint64_t poll,uint64_t metadata,uint64_t ack){
 unsigned r=(unsigned)b16_queue_sample_reason;
 b16_queue_measure.retire_samples[r]++;b16_queue_measure.poll_us[r]+=poll;
 b16_queue_measure.metadata_us[r]+=metadata;b16_queue_measure.ack_us[r]+=ack;
}
#endif
const b16_queue_stats *b16_queue_statistics(void){return &b16_queue_counters;}
static int b16_queue_retire(kfb_device *dev){
#if B16_QUEUE_METRICS
 unsigned reason=b16_queue_drain_reason;
 b16_queue_sample_reason=(b16_queue_measure.retire_calls[reason]++&63u)==0 ? (int)reason : -1;
#endif
#if B16_COMPLETION_BURST
 b16_queue_retiring=1;
#endif
 int rc=kfb_wait(dev,b16_queue_tags[b16_queue_head]);
#if B16_COMPLETION_BURST
 b16_queue_retiring=0;
#endif
#if B16_QUEUE_METRICS
 b16_queue_sample_reason=-1;
#endif
 if(rc){b16_queue_fault=rc;b16_queue_counters.errors++;return rc;}
 b16_queue_head=(b16_queue_head+1u)&7u;
 b16_queue_counters.pending--;b16_queue_counters.retired++;return 0;
}
static int b16_queue_drain(kfb_device *dev){
 if(b16_queue_fault)return b16_queue_fault;
 if(b16_queue_counters.pending && b16_queue_owner!=dev)return KFB_ARGUMENT;
 if(b16_queue_counters.pending)b16_queue_counters.barriers++;
 while(b16_queue_counters.pending){int rc=b16_queue_retire(dev);if(rc)return rc;}
 return 0;
}
static int b16_queue_enqueue(kfb_device *dev,uint8_t command[16]){
 if(dev==NULL || !dev->connected)return KFB_ARGUMENT;
 if(b16_queue_fault)return b16_queue_fault;
 if(b16_queue_counters.pending && b16_queue_owner!=dev)return KFB_ARGUMENT;
 b16_queue_owner=dev;
 if(b16_queue_counters.pending==8){b16_queue_drain_reason=0;int rc=b16_queue_retire(dev);b16_queue_drain_reason=3;if(rc)return rc;}
 uint16_t tag;
 int rc=submit_inner(dev,command,NULL,0,&tag);
 if(rc){b16_queue_fault=rc;b16_queue_counters.errors++;return rc;}
 b16_queue_tags[(b16_queue_head+b16_queue_counters.pending)&7u]=tag;
 b16_queue_counters.pending++;b16_queue_counters.submitted++;
 if(b16_queue_counters.pending>b16_queue_counters.peak)b16_queue_counters.peak=b16_queue_counters.pending;
 return 0;
}
static int b16_queue_execute_sync(kfb_device *dev,uint8_t command[16],const uint8_t *payload,size_t size){
 unsigned op=command[0];
#if B16_QUEUE_METRICS
 bool sampled=op<8 && (b16_queue_measure.sync_calls[op]++&63u)==0;
 uint64_t begin=sampled ? b16_queue_clock_us() : 0;
 if(op<8 && b16_queue_counters.pending)b16_queue_measure.sync_nonempty[op]++;
#endif
 b16_queue_drain_reason=op==6 ? 1 : op==3 ? 2 : 3;
 int rc=b16_queue_drain(dev);b16_queue_drain_reason=3;if(rc)return rc;
#if B16_QUEUE_METRICS
 uint64_t drained=sampled ? b16_queue_clock_us() : 0;
#endif
 uint16_t tag;rc=submit_inner(dev,command,payload,size,&tag);
 if(!rc)rc=kfb_wait(dev,tag);
#if B16_QUEUE_METRICS
 if(sampled && !rc){b16_queue_measure.sync_samples[op]++;b16_queue_measure.sync_drain_us[op]+=drained-begin;
  b16_queue_measure.sync_command_us[op]+=b16_queue_clock_us()-drained;}
#endif
 return rc;
}
