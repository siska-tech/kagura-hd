// SPDX-License-Identifier: Apache-2.0
// Protocol follows diagnostics/pcm-stream-rc1/hardware-host/main.c (the
// validated stream host); the refill is split into 64-byte chunks that run
// between drawing commands, finishing in one go only near the deadline.
#include "stream.h"
#include "pico/stdlib.h"
#include <string.h>

enum {
    STREAM_CTL=0xe3, STREAM_TOKEN=0xe4, STREAM_STATUS=0xe5, MASTER=0xe0, HDMI_STATUS=0xe1, HDMI_CLEAR=0xe2,
    HALF_FREE=1, ARMED=2, READ_PENDING=4,
    PCM_READY=1, PCM_FAULTS=0x38,
    CHUNK=64, CHUNKS=2*STREAM_HALF/CHUNK, STREAM_BASE=0x40000,
    POLL_US=2000, URGENT_US=45000, HALF_US=85333, WAIT_US=300000
};
#define TRY(x) do { int rc_=(x); if (rc_) return rc_; } while (0)

int8_t stream_ring_l[STREAM_RING], stream_ring_r[STREAM_RING];
volatile uint32_t stream_produced, stream_consumed;
static kfb_device *dev;
static stream_stats st;
static bool armed, filling;
static unsigned chunk;
static uint8_t token, expected;
static uint64_t free_at, last_poll;

static uint8_t status_index(unsigned c) { return (uint8_t)(0x6f+0x20*c); }
static int write_address(uint8_t reg, uint32_t address) {
    for (unsigned i=0;i<3;i++) TRY(kfb_audio_write(dev,(uint8_t)(reg+i),(uint8_t)(address>>(8*i))));
    return 0;
}
static int write_chunk(unsigned half, unsigned index) {
    unsigned c=index/(STREAM_HALF/CHUNK), off=(index%(STREAM_HALF/CHUNK))*CHUNK;
    uint32_t frame=stream_consumed+off;
    while ((int32_t)(stream_produced-(frame+CHUNK))<0) { st.synth_waits++; tight_loop_contents(); }
    const int8_t *src=(c ? stream_ring_r : stream_ring_l)+(frame%STREAM_RING);
    st.chunks++;
    return kfb_write_bytes(dev,STREAM_BASE+(c*2+half)*STREAM_HALF+off,(const uint8_t *)src,CHUNK);
}
static int write_half(unsigned half) {
    for (unsigned i=0;i<CHUNKS;i++) TRY(write_chunk(half,i));
    return 0;
}

int stream_stop(void) {
    if (!dev) return 0;
    armed=false; filling=false;
    TRY(kfb_audio_write(dev,STREAM_CTL,0));
    uint64_t deadline=time_us_64()+WAIT_US;
    do {
        uint8_t s; TRY(kfb_audio_read(dev,STREAM_STATUS,&s));
        if (!(s&(ARMED|READ_PENDING))) return 0;
    } while (time_us_64()<deadline);
    return STREAM_DEADLINE;
}

int stream_start(kfb_device *gpu) {
    dev=gpu; memset(&st,0,sizeof st);
    uint8_t id; TRY(kfb_audio_read(dev,STREAM_CTL,&id));
    if (id!=0x51) return KFB_VERSION;
    TRY(stream_stop());
    TRY(kfb_audio_write(dev,HDMI_CLEAR,6));
    for (unsigned c=0;c<2;c++) {
        uint8_t base=(uint8_t)(0x60+0x20*c);
        uint32_t start=STREAM_BASE+2*c*STREAM_HALF;
        TRY(kfb_audio_write(dev,status_index(c),2));
        TRY(kfb_audio_write(dev,status_index(c),4));
        TRY(write_address(base,start));
        TRY(write_address((uint8_t)(base+4),start+2*STREAM_HALF));
        TRY(write_address((uint8_t)(base+8),start));
        TRY(kfb_audio_write(dev,(uint8_t)(base+12),c==0 ? 255 : 0));
        TRY(kfb_audio_write(dev,(uint8_t)(base+13),c==1 ? 255 : 0));
        TRY(kfb_audio_write(dev,(uint8_t)(base+14),3));
    }
    stream_consumed=0;
    TRY(write_half(0)); stream_consumed=STREAM_HALF;
    TRY(write_half(1)); stream_consumed=2*STREAM_HALF;
    TRY(kfb_fence(dev));
    TRY(kfb_audio_write(dev,MASTER,180));
    TRY(kfb_audio_write(dev,STREAM_CTL,1));
    uint8_t s; TRY(kfb_audio_read(dev,STREAM_STATUS,&s));
    if ((s&(ARMED|HALF_FREE))!=ARMED) return STREAM_BAD_PROTOCOL;
    TRY(kfb_audio_read(dev,STREAM_TOKEN,&expected));
    if (expected&1) return STREAM_BAD_PROTOCOL;
    for (unsigned c=0;c<2;c++) TRY(kfb_audio_write(dev,status_index(c),1));
    uint64_t deadline=time_us_64()+WAIT_US;
    for (;;) {
        uint8_t l,r;
        TRY(kfb_audio_read(dev,status_index(0),&l)); TRY(kfb_audio_read(dev,status_index(1),&r));
        if ((l|r)&PCM_FAULTS) return STREAM_BAD_PROTOCOL;
        if (l&r&PCM_READY) break;
        if (time_us_64()>=deadline) return STREAM_DEADLINE;
    }
    uint16_t tag; TRY(kfb_audio_commit(dev,&tag)); TRY(kfb_wait(dev,tag));
    st.start_us=last_poll=time_us_64();
    armed=true;
    return 0;
}

int stream_service(void) {
    if (!armed) return 0;
    uint64_t now=time_us_64();
    if (!filling) {
        if (now-last_poll<POLL_US) return 0;
        uint32_t gap=(uint32_t)(now-last_poll); if (gap>st.worst_poll_gap_us) st.worst_poll_gap_us=gap;
        last_poll=now;
        uint8_t s; TRY(kfb_audio_read(dev,STREAM_STATUS,&s));
        if (!(s&ARMED)) return STREAM_BAD_PROTOCOL;
        if (!(s&HALF_FREE)) return 0;
        TRY(kfb_audio_read(dev,STREAM_TOKEN,&token));
        if (token!=expected) return STREAM_BAD_PROTOCOL;
        filling=true; chunk=0; free_at=now;
    }
    unsigned budget=now-free_at>URGENT_US ? CHUNKS : 12;
    while (budget-- && chunk<CHUNKS) TRY(write_chunk(token&1,chunk++));
    if (chunk<CHUNKS) return 0;
    uint8_t next,s;
    TRY(kfb_audio_write(dev,STREAM_TOKEN,token));
    TRY(kfb_audio_read(dev,STREAM_TOKEN,&next));
    TRY(kfb_audio_read(dev,STREAM_STATUS,&s));
    if (!(s&ARMED) || next!=(uint8_t)(token+1)) return STREAM_BAD_PROTOCOL;
    uint32_t latency=(uint32_t)(time_us_64()-free_at);
    if (latency>st.worst_latency_us) st.worst_latency_us=latency;
    stream_consumed+=STREAM_HALF; expected=next; filling=false;
    st.halves++; if (next==0) st.wraps++;
    last_poll=time_us_64();
    return latency>HALF_US ? STREAM_DEADLINE : 0;
}

int stream_check(uint8_t *left, uint8_t *right, uint8_t *hdmi) {
    TRY(kfb_audio_read(dev,status_index(0),left));
    TRY(kfb_audio_read(dev,status_index(1),right));
    return kfb_audio_read(dev,HDMI_STATUS,hdmi);
}
const stream_stats *stream_statistics(void) { return &st; }
