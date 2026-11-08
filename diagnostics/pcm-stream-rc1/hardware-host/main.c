// SPDX-License-Identifier: Apache-2.0
#include "b16_qspi.h"
#include "hardware/clocks.h"
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include <stdio.h>
#include <string.h>
#ifdef STREAM_DRAWING_TESTS
#include "b16.h"
#endif

enum {
    STREAM_CTL=0xe3, STREAM_TOKEN=0xe4, STREAM_STATUS=0xe5,
    HALF_FREE=1, ARMED=2, READ_PENDING=4,
    PCM_READY=1, PCM_ACTIVE=2, PCM_UNDERRUN=8, PCM_FAULTS=0x38,
    HALF_BYTES=4096, CHUNK_BYTES=64, STREAM_BASE=0x40000,
    HALF_LIMIT_US=85333, WAIT_US=300000
};
enum { BAD_PROTOCOL=-20, BAD_DATA=-21, DEADLINE=-22, CANCELLED=-23 };
#define TRY(call) do { int rc_=(call); if (rc_) return rc_; } while (0)

static kfb_device device;
static uint8_t chunk[CHUNK_BYTES], readback[CHUNK_BYTES];
static const char *phase="idle";
static bool admitted;
static bool legacy_pcm;
static bool repeat_markers;
static bool publish_only;
// T8: CSR 31 bit1 selects all-word DI switching on the diagnostic image.
static bool diag_broadcast;

typedef struct {
    uint32_t halves, wraps, blits, worst_refill_us;
    uint8_t expected_token;
} measurements;

static uint8_t pcm_status_index(unsigned channel) {
    return (uint8_t)(0x6f+0x20*channel);
}

// Independent tones with a per-half amplitude marker in the first 64 samples.
// Negative values are stored as signed PCM8 in two's complement.
static uint8_t sample(unsigned channel, uint32_t half_number, unsigned offset) {
    int amplitude=offset<64 ? 24+(int)((half_number+37*channel)%64) : 72;
    unsigned period=channel ? 32 : 64;
    return (uint8_t)((offset%period)<period/2 ? amplitude : -amplitude);
}

static int transfer_half_to(uint32_t plane_base,unsigned half,uint32_t sequence,bool verify) {
    for (unsigned channel=0; channel<2; ++channel) {
        uint32_t base=plane_base+(channel*2+half)*HALF_BYTES;
        for (unsigned offset=0; offset<HALF_BYTES; offset+=CHUNK_BYTES) {
            for (unsigned i=0; i<CHUNK_BYTES; ++i)
                chunk[i]=sample(channel,sequence,offset+i);
            if (verify) {
                TRY(kfb_read_bytes(&device,base+offset,readback,sizeof readback));
                if (memcmp(chunk,readback,sizeof chunk)) return BAD_DATA;
            } else {
                TRY(kfb_write_bytes(&device,base+offset,chunk,sizeof chunk));
            }
        }
    }
    return KFB_OK;
}

static int transfer_half(unsigned half,uint32_t sequence,bool verify) {
    return transfer_half_to(STREAM_BASE,half,repeat_markers ? sequence&1u : sequence,verify);
}

static int channel_status(uint8_t *left, uint8_t *right) {
    TRY(kfb_audio_read(&device,pcm_status_index(0),left));
    return kfb_audio_read(&device,pcm_status_index(1),right);
}

static int stream_stop(void) {
    if (legacy_pcm) {
        for (unsigned c=0; c<2; ++c)
            TRY(kfb_audio_write(&device,pcm_status_index(c),2));
        uint64_t deadline=time_us_64()+WAIT_US;
        do {
            uint8_t left,right;
            TRY(channel_status(&left,&right));
            if (!((left|right)&0x42)) return KFB_OK;
        } while (time_us_64()<deadline);
        return DEADLINE;
    }
    TRY(kfb_audio_write(&device,STREAM_CTL,0));
    uint64_t deadline=time_us_64()+WAIT_US;
    do {
        uint8_t status;
        TRY(kfb_audio_read(&device,STREAM_STATUS,&status));
        if (!(status&(ARMED|READ_PENDING))) return KFB_OK;
    } while (time_us_64()<deadline);
    return DEADLINE;
}

static int write_address(uint8_t reg, uint32_t address) {
    for (unsigned i=0; i<3; ++i)
        TRY(kfb_audio_write(&device,(uint8_t)(reg+i),(uint8_t)(address>>(8*i))));
    return KFB_OK;
}

static int rejected_token(uint8_t value, uint8_t expected) {
    uint8_t actual;
    TRY(kfb_audio_write(&device,STREAM_TOKEN,value));
    TRY(kfb_audio_read(&device,STREAM_TOKEN,&actual));
    return actual==expected ? KFB_OK : BAD_PROTOCOL;
}

static int stream_start(measurements *m, bool verify) {
    phase="configure";
    TRY(stream_stop());
    for (unsigned c=0; c<2; ++c) {
        uint8_t base=(uint8_t)(0x60+0x20*c);
        uint32_t start=STREAM_BASE+2*c*HALF_BYTES;
        TRY(kfb_audio_write(&device,pcm_status_index(c),2));
        TRY(kfb_audio_write(&device,pcm_status_index(c),4));
        TRY(write_address(base,start));
        TRY(write_address((uint8_t)(base+4),start+2*HALF_BYTES));
        TRY(write_address((uint8_t)(base+8),start));
        TRY(kfb_audio_write(&device,(uint8_t)(base+12),c==0 ? 255 : 0));
        TRY(kfb_audio_write(&device,(uint8_t)(base+13),c==1 ? 255 : 0));
        TRY(kfb_audio_write(&device,(uint8_t)(base+14),3));
    }
    phase="initial_halves";
    TRY(transfer_half(0,0,false));
    TRY(transfer_half(1,1,false));
    TRY(kfb_fence(&device));
    if (verify) {
        TRY(transfer_half(0,0,true));
        TRY(transfer_half(1,1,true));
    }
    TRY(kfb_audio_write(&device,0xe0,180));
    phase="arm_and_ownership";
    if (!legacy_pcm) {
        TRY(kfb_audio_write(&device,STREAM_CTL,1));
        uint8_t status;
        TRY(kfb_audio_read(&device,STREAM_STATUS,&status));
        if ((status&(ARMED|HALF_FREE))!=ARMED) return BAD_PROTOCOL;
        TRY(kfb_audio_read(&device,STREAM_TOKEN,&m->expected_token));
        if (m->expected_token&1) return BAD_PROTOCOL;
        // A matching token must be rejected while both halves belong to FPGA.
        TRY(rejected_token(m->expected_token,m->expected_token));
    }
    phase="prepare";
    for (unsigned c=0; c<2; ++c)
        TRY(kfb_audio_write(&device,pcm_status_index(c),1));
    uint64_t deadline=time_us_64()+WAIT_US;
    for (;;) {
        uint8_t left,right;
        TRY(channel_status(&left,&right));
        if ((left|right)&PCM_FAULTS) return BAD_PROTOCOL;
        if (left&right&PCM_READY) break;
        if (time_us_64()>=deadline) return DEADLINE;
    }
    uint16_t tag;
    TRY(kfb_audio_commit(&device,&tag));
    return kfb_wait(&device,tag);
}

static int refill(measurements *m) {
    phase="refill";
    uint64_t begin=time_us_64();
    uint8_t token,next,status;
    TRY(kfb_audio_read(&device,STREAM_TOKEN,&token));
    if (token!=m->expected_token) return BAD_PROTOCOL;
    if (m->halves==0) TRY(rejected_token((uint8_t)(token-1),token));
    if (!publish_only)
        TRY(transfer_half(token&1,m->halves+2,false));
    TRY(kfb_audio_write(&device,STREAM_TOKEN,token));
    TRY(kfb_audio_read(&device,STREAM_TOKEN,&next));
    TRY(kfb_audio_read(&device,STREAM_STATUS,&status));
    if (!(status&ARMED) || next!=(uint8_t)(token+1)) return BAD_PROTOCOL;
    if (m->halves==0) TRY(rejected_token(token,next));
    uint32_t elapsed=(uint32_t)(time_us_64()-begin);
    if (elapsed>m->worst_refill_us) m->worst_refill_us=elapsed;
    m->expected_token=next;
    m->halves++;
    if (next==0) m->wraps++;
    return elapsed>HALF_LIMIT_US ? DEADLINE : KFB_OK;
}

static int play(measurements *m, uint32_t target_halves, uint32_t seconds, bool blit) {
    uint64_t now=time_us_64(), progress_deadline=now+WAIT_US;
    uint64_t end=now+UINT64_C(1000000)*seconds;
    while (seconds ? time_us_64()<end : m->halves<target_halves) {
        if (getchar_timeout_us(0)=='q') return CANCELLED;
        phase="wait_for_half";
        uint8_t status;
        TRY(kfb_audio_read(&device,STREAM_STATUS,&status));
        if (!(status&ARMED)) return BAD_PROTOCOL;
        if (status&HALF_FREE) {
            TRY(refill(m));
            progress_deadline=time_us_64()+WAIT_US;
            if ((m->halves&255)==0)
                printf("STREAM halves=%lu wraps=%lu blits=%lu max_refill_us=%lu\n",
                       (unsigned long)m->halves,(unsigned long)m->wraps,
                       (unsigned long)m->blits,(unsigned long)m->worst_refill_us);
        } else if (blit) {
            // One bounded COPY between ownership polls. This is a synthetic
            // contention workload using a scratch region of framebuffer page 0.
            phase="blit";
            TRY(kfb_copy_rect(&device,0,0,0,0,64,0,32,32));
            m->blits++;
        }
        if (time_us_64()>=progress_deadline) return DEADLINE;
    }
    return KFB_OK;
}

static int expect_underrun(void) {
    phase="intentional_underrun";
    uint64_t deadline=time_us_64()+WAIT_US;
    do {
        uint8_t status,left,right;
        TRY(kfb_audio_read(&device,STREAM_STATUS,&status));
        if (!(status&ARMED)) {
            TRY(channel_status(&left,&right));
            if (((left|right)&(PCM_ACTIVE|0x30)) || !(left&right&PCM_UNDERRUN))
                return BAD_PROTOCOL;
            TRY(stream_stop());
            printf("UNDERRUN expected=1 left=0x%02x right=0x%02x drained=1\n",left,right);
            return KFB_OK;
        }
    } while (time_us_64()<deadline);
    return DEADLINE;
}

#ifdef STREAM_DRAWING_TESTS
static measurements *drawing_stream;
static b16_engine engine;
static b16_bus drawing_bus;
static bool hidden_drawing;

enum { TRACE_BUCKET_US=5000, TRACE_BUCKETS=5100, TRACE_REFILLS=320 };
enum { OP_FILL, OP_COPY, OP_PALETTE, OP_PRESENT, OP_COUNT };
typedef struct {
    uint8_t count[OP_COUNT];
    uint16_t max_us[OP_COUNT];
} opcode_bucket;
typedef struct {
    uint32_t t_us, done_us;
    uint8_t token, status;
} refill_trace;
typedef struct {
    uint32_t t_us;
    uint8_t stream, hdmi, left, right;
} status_trace;
static opcode_bucket op_trace[TRACE_BUCKETS];
static refill_trace refills[TRACE_REFILLS];
static status_trace statuses[1020];
static unsigned refill_count, status_count, bucket_count;
static uint64_t trace_start, trace_next_status;

static uint32_t trace_elapsed(uint64_t now) {
    return trace_start ? (uint32_t)(now-trace_start) : 0;
}

static void trace_opcode(unsigned opcode,uint64_t begin) {
    if (!trace_start) return;
    uint32_t bucket=trace_elapsed(begin)/TRACE_BUCKET_US;
    if (bucket>=TRACE_BUCKETS) return;
    opcode_bucket *item=&op_trace[bucket];
    if (item->count[opcode]<255) item->count[opcode]++;
    uint64_t duration=time_us_64()-begin;
    if (duration>65535) duration=65535;
    if (duration>item->max_us[opcode]) item->max_us[opcode]=(uint16_t)duration;
    if (bucket>=bucket_count) bucket_count=bucket+1;
}

static int trace_audio(uint8_t stream,uint64_t now) {
    if (!trace_start || now<trace_next_status || status_count>=sizeof statuses/sizeof statuses[0])
        return KFB_OK;
    status_trace *item=&statuses[status_count++];
    item->t_us=trace_elapsed(now);
    item->stream=stream;
    trace_next_status=now+25000;
    TRY(kfb_audio_read(&device,0xe1,&item->hdmi));
    return channel_status(&item->left,&item->right);
}

static void dump_trace(void) {
    for (unsigned i=0;i<bucket_count;i++) {
        const opcode_bucket *p=&op_trace[i];
        if (!(p->count[0]|p->count[1]|p->count[2]|p->count[3])) continue;
        printf("OP t_us=%lu fill=%u copy=%u palette=%u present=%u fill_max=%u copy_max=%u palette_max=%u present_max=%u\n",
               (unsigned long)i*TRACE_BUCKET_US,p->count[0],p->count[1],p->count[2],p->count[3],
               p->max_us[0],p->max_us[1],p->max_us[2],p->max_us[3]);
    }
    for (unsigned i=0;i<refill_count;i++) {
        const refill_trace *p=&refills[i];
        printf("REFILL t_us=%lu done_us=%lu token=%u status=%u\n",
               (unsigned long)p->t_us,(unsigned long)p->done_us,p->token,p->status);
    }
    for (unsigned i=0;i<status_count;i++) {
        const status_trace *p=&statuses[i];
        printf("AUDIO t_us=%lu stream=%u hdmi=%u left=%u right=%u\n",
               (unsigned long)p->t_us,p->stream,p->hdmi,p->left,p->right);
    }
    printf("TRACE_END op_buckets=%u refills=%u audio=%u\n",bucket_count,refill_count,status_count);
}

static int service_drawing_stream(void) {
    if (!drawing_stream) return KFB_OK;
    phase="drawing_stream_status";
    uint8_t status;
    TRY(kfb_audio_read(&device,STREAM_STATUS,&status));
    if (!(status&ARMED)) return BAD_PROTOCOL;
    uint64_t now=time_us_64();
    TRY(trace_audio(status,now));
    if (status&HALF_FREE) {
        uint8_t token=drawing_stream->expected_token;
        TRY(refill(drawing_stream));
        if (trace_start && refill_count<TRACE_REFILLS)
            refills[refill_count++]=(refill_trace){trace_elapsed(now),trace_elapsed(time_us_64()),token,status};
    }
    return KFB_OK;
}

// Called at command boundaries by the isolated BEYOND translation unit.
// The synchronous SDK has finished the previous command before refill can run.
int stream_fill_rect(kfb_device *d,unsigned page,int32_t x,int32_t y,int32_t w,int32_t h,unsigned color) {
    TRY(service_drawing_stream());
    phase="drawing_fill";
    uint64_t begin=trace_start ? time_us_64() : 0;
    int rc=kfb_fill_rect(d,hidden_drawing ? 1 : page,x,y,w,h,color);
    trace_opcode(OP_FILL,begin);
    return rc;
}
int stream_copy_rect(kfb_device *d,unsigned src,int32_t sx,int32_t sy,
                     unsigned dst,int32_t dx,int32_t dy,int32_t w,int32_t h) {
    TRY(service_drawing_stream());
    phase="drawing_copy";
    uint64_t begin=trace_start ? time_us_64() : 0;
    int rc=kfb_copy_rect(d,hidden_drawing ? 1 : src,sx,sy,
                         hidden_drawing ? 1 : dst,dx,dy,w,h);
    trace_opcode(OP_COPY,begin);
    if (!rc && drawing_stream) drawing_stream->blits++;
    return rc;
}
int stream_palette(kfb_device *d,unsigned index,unsigned color) {
    TRY(service_drawing_stream());
    phase="drawing_palette";
    uint64_t begin=trace_start ? time_us_64() : 0;
    int rc=kfb_palette(d,index,color);
    trace_opcode(OP_PALETTE,begin);
    return rc;
}
int stream_present(kfb_device *d,unsigned page) {
    TRY(service_drawing_stream());
    phase="drawing_present";
    uint64_t begin=trace_start ? time_us_64() : 0;
    int rc=kfb_present(d,hidden_drawing ? 0 : page);
    trace_opcode(OP_PRESENT,begin);
    return rc;
}
int b16_audio(kfb_device *d,int scene) {
    (void)d;
    (void)scene;
    return KFB_OK;
}
int b16_audio_poll(kfb_device *d) {
    (void)d;
    return service_drawing_stream();
}
int b16_audio_stop(kfb_device *d) {
    (void)d;
    return stream_stop();
}

static int run_drawing(int mode, measurements *m) {
    phase="drawing_init";
    TRY(b16_init(&engine,&device,0xb1616));
    if (mode=='k') {
        for (unsigned color=0;color<16;color++)
            TRY(kfb_palette(&device,color,0));
        TRY(kfb_present(&device,1));
    }
    if (mode=='h') {
        TRY(kfb_present(&device,0));
        hidden_drawing=true;
    }
    uint8_t hdmi_status;
    TRY(kfb_audio_read(&device,0xe1,&hdmi_status));
    printf("HDMI_STATUS before=0x%02x\n",hdmi_status);
    TRY(kfb_audio_write(&device,0xe2,6));
    TRY(stream_start(m,true));
    drawing_stream=m;
    bool present_only=mode=='p';
    bool idle_control=mode=='n' || mode=='k' || mode=='u' || mode=='v';
    bool storm=mode!='m';
    unsigned offset=storm ? 95000 : 0;
    unsigned duration=storm ? 25000 : B16_DURATION;
    uint64_t start=time_us_64();
    if (mode=='t' || mode=='p' || mode=='h' || idle_control) trace_start=start;
    unsigned logged=0, scenes=0, present_count=0, next_present=0;
    int rc=0;
    for (;;) {
        unsigned elapsed=(unsigned)((time_us_64()-start)/1000);
        if (elapsed>=duration) break;
        if (getchar_timeout_us(0)=='q') { rc=CANCELLED; break; }
        rc=service_drawing_stream();
        if (!rc && present_only && elapsed>=next_present) {
            rc=stream_present(&device,present_count++&1);
            next_present=elapsed+42;
        } else if (!rc && !present_only && !idle_control) {
            rc=b16_tick(&engine,offset+elapsed);
        }
        if (rc) break;
        if (engine.stats.frames) scenes|=1u<<engine.stats.scene;
        if (elapsed-logged>=1000) {
            logged=elapsed;
            printf("DRAW ms=%u scene=%lu frames=%lu halves=%lu blits=%lu max_refill_us=%lu\n",
                   elapsed,(unsigned long)engine.stats.scene,(unsigned long)engine.stats.frames,
                   (unsigned long)m->halves,(unsigned long)m->blits,(unsigned long)m->worst_refill_us);
        }
    }
    drawing_stream=NULL;
    printf("DRAW_END frames=%lu scene_mask=0x%02x skipped=%lu\n",
           (unsigned long)engine.stats.frames,scenes,(unsigned long)engine.stats.skipped);
    if (present_only) printf("PRESENT_CONTROL count=%u\n",present_count);
    if (idle_control) puts("IDLE_CONTROL complete");
    if (!rc) {
        phase="drawing_hdmi_status";
        rc=kfb_audio_read(&device,0xe1,&hdmi_status);
        if (!rc) {
            printf("HDMI_STATUS after=0x%02x\n",hdmi_status);
            if (hdmi_status&6) rc=BAD_PROTOCOL;
        }
    }
    if (!rc && (!m->wraps || (present_only && !present_count) ||
        (!present_only && !idle_control && (!m->blits || scenes!=(storm ? 0x20u : 0xffu)))))
        rc=BAD_PROTOCOL;
    if (!rc) {
        phase="stop";
        rc=stream_stop();
    }
    if (trace_start) dump_trace();
    return rc;
}

// Audit A/B payloads (design-audit-report.md section 11). Each lane nibble is
// sent MSB first, so 0x55/0xAA keep every QSPI data lane constant within a
// chunk while 0x0F/0xF0 toggle all four lanes on every nibble. Alternating
// per chunk flips every window bit in both cases.
// T6: PAYLOAD_LOW2 flips only window bytes 0-1 (the bits that reach
// tx[15:0] and the PSRAM DQ ODDR inputs), PAYLOAD_HIGH62 flips bytes 2-63
// only, PAYLOAD_CONST55 leaves the window contents static after one write.
enum { PAYLOAD_PCM, PAYLOAD_ZERO, PAYLOAD_55AA, PAYLOAD_0FF0,
       PAYLOAD_LOW2, PAYLOAD_HIGH62, PAYLOAD_CONST55 };
enum { WINDOW_REG=24, STAGING_REG=8 };

static uint8_t audit_byte(int payload,unsigned chunks,unsigned i) {
    uint8_t flip=(chunks&1u) ? 0xaa : 0x55;
    switch (payload) {
    case PAYLOAD_ZERO: return 0;
    case PAYLOAD_55AA: return flip;
    case PAYLOAD_0FF0: return (chunks&1u) ? 0xf0 : 0x0f;
    case PAYLOAD_LOW2: return i<2 ? flip : 0;
    case PAYLOAD_HIGH62: return i<2 ? 0 : flip;
    case PAYLOAD_CONST55: return 0x55;
    default: return 0;
    }
}

static int write_window_only(unsigned sequence,int payload,uint8_t target) {
    uint64_t begin=time_us_64();
    unsigned chunks=0;
    for (unsigned channel=0;channel<2;channel++) {
        for (unsigned offset=0;offset<HALF_BYTES;offset+=CHUNK_BYTES) {
            for (unsigned i=0;i<CHUNK_BYTES;i++)
                chunk[i]=payload==PAYLOAD_PCM ? sample(channel,sequence,offset+i) :
                         audit_byte(payload,chunks,i);
            const uint8_t zero=0;
            // Non-incrementing writes: STAGING_REG rewrites staging byte 0 only.
            if (device.io.write(device.io.context,25,false,&zero,1) ||
                device.io.write(device.io.context,target,false,chunk,sizeof chunk))
                return KFB_IO;
            // Match the approximate duration of the full PSRAM WRITE burst.
            sleep_until(from_us_since_boot(begin+(uint64_t)++chunks*237));
        }
    }
    uint8_t error;
    if (device.io.read(device.io.context,7,false,&error,1)) return KFB_IO;
    return error ? KFB_DEVICE : KFB_OK;
}

static int run_legacy(int mode, measurements *m) {
    phase="legacy_init";
    TRY(b16_init(&engine,&device,0xb1616));
    if (mode=='d' || mode=='e' || mode=='y') {
        for (unsigned color=0;color<16;color++)
            TRY(kfb_palette(&device,color,mode=='y' ? 0xfff : 0));
        TRY(kfb_present(&device,1));
    }
    // T7: uniform gray 0x555 (TMDS edges about 2x the original screen) and
    // black/white stripes at framebuffer pixel pitch (fewer edges than black).
    // Uniform sweep after T7: R=0xf00, 1=0x111, E=0xeee (G=0x555).
    if (mode=='G' || mode=='R' || mode=='1' || mode=='E') {
        unsigned rgb=mode=='R' ? 0xf00 : mode=='1' ? 0x111 : mode=='E' ? 0xeee : 0x555;
        for (unsigned color=0;color<16;color++)
            TRY(kfb_palette(&device,color,rgb));
        TRY(kfb_present(&device,1));
    }
    if (mode=='S') {
        for (unsigned color=0;color<16;color++)
            TRY(kfb_palette(&device,color,color ? 0xfff : 0));
        TRY(kfb_fill_rect(&device,1,0,0,640,360,0));
        for (int32_t x=1;x<640;x+=2)
            TRY(kfb_fill_rect(&device,1,x,0,1,360,1));
        TRY(kfb_present(&device,1));
    }
    bool window_traffic=strchr("xz5fryeaioGSR1E",mode)!=NULL;
    if (diag_broadcast) {
        // Ignored by images without the T8 register (bit0 only there).
        const uint8_t value=0x02;
        if (device.io.write(device.io.context,31,false,&value,1)) return KFB_IO;
        puts("DIAG_BROADCAST set");
    }
    TRY(kfb_audio_write(&device,0xe2,6));
    TRY(stream_start(m,true));
    trace_start=time_us_64();
    uint64_t end=trace_start+UINT64_C(25000000);
    uint64_t next_write=trace_start+HALF_LIMIT_US;
    unsigned writes=0;
    phase="legacy_loop";
    while (time_us_64()<end) {
        if (getchar_timeout_us(0)=='q') return CANCELLED;
        uint64_t now=time_us_64();
        TRY(trace_audio(0,now));
        if ((mode=='w' || window_traffic) && now>=next_write) {
            uint64_t begin=time_us_64();
            // Match one stereo refill's write volume on a separate PSRAM area.
            if (mode=='w') {
                TRY(transfer_half_to(0x44000,writes&1u,writes&1u,false));
            } else {
                int payload=mode=='z' ? PAYLOAD_ZERO : mode=='5' ? PAYLOAD_55AA :
                            mode=='f' ? PAYLOAD_0FF0 : mode=='a' ? PAYLOAD_LOW2 :
                            mode=='i' ? PAYLOAD_HIGH62 : mode=='o' ? PAYLOAD_CONST55 : PAYLOAD_PCM;
                TRY(write_window_only(writes&1u,payload,mode=='r' ? STAGING_REG : WINDOW_REG));
            }
            uint32_t duration=(uint32_t)(time_us_64()-begin);
            if (duration>m->worst_refill_us) m->worst_refill_us=duration;
            if (duration>HALF_LIMIT_US) return DEADLINE;
            writes++;
            next_write+=HALF_LIMIT_US;
        }
        sleep_ms(1);
    }
    TRY(stream_stop());
    dump_trace();
    for (unsigned i=0;i<status_count;i++)
        if ((statuses[i].hdmi&6) || ((statuses[i].left|statuses[i].right)&PCM_FAULTS) ||
            !(statuses[i].left&statuses[i].right&PCM_ACTIVE)) return BAD_PROTOCOL;
    printf("LEGACY_CONTROL complete dummy_halves=%u\n",writes);
    return KFB_OK;
}
#endif

static int run(int mode, measurements *m) {
    phase="identify";
    kfb_io io=mt_qspi_io();
    {
        static const char upper[]="IOTX", lower[]="ioSx";
        const char *found=mode>0 ? strchr(upper,mode) : NULL;
        if (found) { diag_broadcast=true; mode=lower[found-upper]; }
    }
#ifdef STREAM_DRAWING_TESTS
    if (strchr("smthpnkcduwvxz5fryeaioGSR1E",mode)) io=b16_cached_io(&drawing_bus,io);
    legacy_pcm=strchr("cdwxz5fryeaioGSR1E",mode)!=NULL;
    repeat_markers=mode=='u' || mode=='v';
    publish_only=mode=='v';
#endif
    TRY(kfb_init(&device,io,500));
    TRY(kfb_probe(&device));
#ifdef STREAM_DRAWING_TESTS
    if (legacy_pcm) {
        admitted=true;
        return run_legacy(mode,m);
    }
#endif
    uint8_t id;
    TRY(kfb_audio_read(&device,STREAM_CTL,&id));
    if (id!=0x51) return KFB_VERSION;
    admitted=true;
#ifdef STREAM_DRAWING_TESTS
    if (strchr("smthpnkuv",mode)) return run_drawing(mode,m);
#endif
    if (mode=='b') {
        phase="blit_source";
        TRY(kfb_fill_rect(&device,0,0,0,32,32,5));
    }
    TRY(stream_start(m,true));
    TRY(play(m,300,mode=='b' ? 150 : mode=='l' ? 3600 : 0,mode=='b'));
    if (m->wraps==0 || (mode=='b' && m->blits==0)) return BAD_PROTOCOL;
    if (mode=='g') {
        TRY(expect_underrun());
        measurements restart={0};
        TRY(stream_start(&restart,false));
        TRY(play(&restart,4,0,false));
        printf("RESTART halves=%lu\n",(unsigned long)restart.halves);
    }
    phase="stop";
    return stream_stop();
}

int main(void) {
    set_sys_clock_khz(120000,true);
    stdio_init_all();
    while (!stdio_usb_connected()) sleep_ms(10);
    puts("PCM STREAM RC1 RAM HOST / g=protocol b=150s COPY+stream l=1h stream q=stop"
#ifdef STREAM_DRAWING_TESTS
         " s=BLIT STORM m=megademo t=trace p=PRESENT-only h=hidden-drawing n=idle-control k=black-palette c=legacy-color d=legacy-black u=repeat-stream w=legacy-with-writes v=publish-only x=window-only z=window-zero 5=window-55AA f=window-0FF0 r=staging-pcm y=window-white e=window-black a=window-low2 i=window-high62 o=window-const55 G=window-gray555 S=window-stripes R=window-red 1=window-111 E=window-eee I/O/T/X=i/o/S/x with T8 all-word DI"
#endif
    );
    int mode;
    do { mode=getchar_timeout_us(100000); } while (mode!='g' && mode!='b' && mode!='l'
#ifdef STREAM_DRAWING_TESTS
                                                  && (mode<=0 || !strchr("smthpnkcduwvxz5fryeaioGSR1EIOTX",mode))
#endif
    );
    measurements m={0};
    phase="qspi_init";
    int rc=mt_qspi_init();
    if (!rc) rc=run(mode,&m);
    const char *result_phase=phase;
    // Do not replay uncertain IO. A semantic failure may still be stopped.
    if (admitted && (rc==BAD_PROTOCOL || rc==BAD_DATA || rc==CANCELLED || rc==DEADLINE))
        (void)stream_stop();
    const mt_qspi_stats *stats=mt_qspi_statistics();
    printf("STOP rc=%d phase=%s halves=%lu wraps=%lu blits=%lu max_refill_us=%lu timeouts=%lu device_error=%u\n",
           rc,result_phase,(unsigned long)m.halves,(unsigned long)m.wraps,
           (unsigned long)m.blits,(unsigned long)m.worst_refill_us,
           (unsigned long)stats->timeouts,device.last_device_error);
    mt_qspi_deinit();
    for (;;) sleep_ms(1000);
}
