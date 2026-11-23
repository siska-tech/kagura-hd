// SPDX-License-Identifier: Apache-2.0
// Generic four-operator FM DSP. Patches and every timed command come from Python.
#include "fm.h"
#include <math.h>
#include <string.h>
#include <stdatomic.h>
#if KAGURA_RAMFUNC
#define HOT __attribute__((section(".time_critical.kagura_fm"), noinline))
#else
#define HOT
#endif
#define BLOCK 16u
#define FM_OPS 4
#define VOICES 7
#define MOD_SHIFT 18
#define DELAY_FRAMES 12000u
#define STUTTER_FRAMES 4096u
#define HZ(f) ((uint32_t)((f)*4294967296.0/FM_RATE))
enum { ALG_SERIAL, ALG_STACKS };
enum { ENV_OFF, ENV_ATTACK, ENV_DECAY, ENV_SUSTAIN, ENV_RELEASE };
static const uint8_t carriers[2]={1,5};
typedef struct { uint16_t ratio; int8_t detune; uint16_t tl,ar,dr,sl,rr; } op_patch;
typedef struct { uint8_t alg,fb,vib,vib_shift,send; uint16_t vib_hz10; op_patch op[4]; } patch;
static patch patches[16];
static unsigned patch_count;
static uint32_t effects[33];
typedef struct { uint32_t phase, inc; uint32_t level; uint8_t env; } op_state;
typedef struct {
    const patch *p; op_state op[FM_OPS]; int32_t fb0, fb1;
    uint32_t vib_phase; uint16_t vib_ramp, gl, gr, vel; uint8_t note; uint32_t off_at;
} voice;
static voice voices[VOICES];
static int16_t sine[1024];
static uint32_t note_inc[128];
static int16_t delay_line[DELAY_FRAMES];
static int8_t stutter_l[STUTTER_FRAMES], stutter_r[STUTTER_FRAMES];
static uint32_t position, delay_pos, rng = 0x2545f491u, peak, clipped;
static int32_t mix_l[BLOCK], mix_r[BLOCK], mix_s[BLOCK];
static uint32_t pitch_q16 = 65536;          /* global pitch multiplier */
static unsigned crush_bits;
static uint32_t stutter_start, stutter_len, stutter_until;

static inline uint32_t xorshift(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }
static inline int32_t S(uint32_t ph) { return sine[ph >> 22]; }

/* -------------------------------------------------------------- voices */
static void note_on(unsigned v, const patch *p, unsigned note, unsigned vel, uint32_t off_at) {
    voice *x = &voices[v];
    bool retune = x->p != p;
    x->p = p; x->note = (uint8_t)note; x->vel = (uint16_t)vel; x->off_at = off_at; x->vib_ramp = 0;
    for (unsigned o = 0; o < FM_OPS; o++) {
        const op_patch *q = &p->op[o];
        uint32_t inc = (uint32_t)(((uint64_t)note_inc[note & 127]*q->ratio) >> 8);
        inc += (uint32_t)((int32_t)(inc >> 14)*q->detune);
        x->op[o].inc = inc; x->op[o].env = ENV_ATTACK;
        if (retune) x->op[o].level = 0;
    }
}
static void note_off(unsigned v) {
    for (unsigned o = 0; o < FM_OPS; o++) if (voices[v].op[o].env != ENV_OFF) voices[v].op[o].env = ENV_RELEASE;
    voices[v].off_at = 0;
}
HOT static void envelope(op_state *s, const op_patch *q) {
    switch (s->env) {
    case ENV_ATTACK: s->level += q->ar; if (s->level >= 65535u) { s->level = 65535u; s->env = ENV_DECAY; } break;
    case ENV_DECAY:
        if (s->level > q->sl) s->level -= ((s->level - q->sl)*q->dr) >> 16;
        if (s->level <= q->sl + 64u) { s->level = q->sl; s->env = q->sl ? ENV_SUSTAIN : ENV_OFF; } break;
    case ENV_RELEASE: s->level -= (s->level*q->rr) >> 16; if (s->level < 48u) { s->level = 0; s->env = ENV_OFF; } break;
    default: break;
    }
}
HOT static void render_voice(voice *x) {
    const patch *p = x->p;
    if (!p) return;
    uint32_t amp[FM_OPS], inc[FM_OPS], active = 0;
    int32_t vib = 0;
    if (p->vib) {
        x->vib_phase += BLOCK*(HZ(1.0)/10u)*p->vib_hz10;
        if (x->vib_ramp < 65535u-120u) x->vib_ramp += 120u;
        vib = ((S(x->vib_phase) >> 7)*(int32_t)p->vib) >> 8;
        vib = (vib*(int32_t)(x->vib_ramp >> 8)) >> 8;
    }
    for (unsigned o = 0; o < FM_OPS; o++) {
        envelope(&x->op[o], &p->op[o]);
        uint32_t a = (x->op[o].level*p->op[o].tl) >> 16;
        if (carriers[p->alg] >> o & 1) a = (a*x->vel) >> 8;
        amp[o] = a; active |= a;
        uint32_t base = (uint32_t)(((uint64_t)x->op[o].inc*pitch_q16) >> 16);
        inc[o] = base + (uint32_t)(((int64_t)(base >> p->vib_shift)*vib) >> 8);
    }
    if (!active) return;
    uint32_t p0 = x->op[0].phase, p1 = x->op[1].phase, p2 = x->op[2].phase, p3 = x->op[3].phase;
    int32_t f0 = x->fb0, f1 = x->fb1;
    const unsigned fbs = p->fb ? 11u + p->fb : 0u;
    for (unsigned i = 0; i < BLOCK; i++) {
        p0 += inc[0]; p1 += inc[1]; p2 += inc[2]; p3 += inc[3];
        uint32_t fb = fbs ? (uint32_t)((f0 + f1) >> 1) << fbs : 0u;
        int32_t o3 = (S(p3 + fb)*(int32_t)amp[3]) >> 16; f1 = f0; f0 = o3;
        int32_t o2 = (S(p2 + ((uint32_t)o3 << MOD_SHIFT))*(int32_t)amp[2]) >> 16, out;
        if (p->alg == ALG_SERIAL) {
            int32_t o1 = (S(p1 + ((uint32_t)o2 << MOD_SHIFT))*(int32_t)amp[1]) >> 16;
            out = (S(p0 + ((uint32_t)o1 << MOD_SHIFT))*(int32_t)amp[0]) >> 16;
        } else {
            int32_t o1 = (S(p1)*(int32_t)amp[1]) >> 16;
            out = ((S(p0 + ((uint32_t)o1 << MOD_SHIFT))*(int32_t)amp[0]) >> 16) + o2;
        }
        mix_l[i] += (out*(int32_t)x->gl) >> 8; mix_r[i] += (out*(int32_t)x->gr) >> 8;
        mix_s[i] += (out*(int32_t)p->send) >> 8;
    }
    x->op[0].phase = p0; x->op[1].phase = p1; x->op[2].phase = p2; x->op[3].phase = p3;
    x->fb0 = f0; x->fb1 = f1;
}

/* ----------------------------------------------- configurable signal sources */
typedef struct { uint32_t phase, amp, amp2, decay, decay2; int32_t lp, prev; uint8_t hard; } drum;
static drum kick, brush, ride, rim;
static int32_t noise_lp, noise_hp, noise_level, noise_target, noise_drop;
static void hit_kick(unsigned vel, bool hard) { kick.phase = 0; kick.amp = vel << 8; kick.amp2 = 65535; kick.hard = hard;
    kick.decay = effects[hard ? 4 : 3]; kick.decay2 = effects[hard ? 6 : 5]; }
static void hit_brush(unsigned vel) { brush.amp = vel << 8; brush.amp2 = 0; brush.decay = effects[9]; }
static void hit_ride(unsigned vel) { ride.amp = vel << 8; ride.decay = effects[15]; }
static void hit_rim(unsigned vel) { rim.amp = vel << 8; rim.decay = effects[19]; rim.phase = 0; }
HOT static void render_drums(void) {
    if (kick.amp > 16) {
        uint32_t inc = effects[0] + (uint32_t)(((uint64_t)effects[kick.hard ? 2 : 1]*kick.amp2) >> 16);
        for (unsigned i = 0; i < BLOCK; i++) {
            kick.phase += inc; int32_t o = (S(kick.phase)*(int32_t)(kick.amp >> 1)) >> 15;
            o = (o*(int32_t)effects[kick.hard ? 8 : 7]) >> 4; mix_l[i] += o; mix_r[i] += o;
        }
        kick.amp -= (kick.amp*kick.decay) >> 16; kick.amp2 -= (kick.amp2*kick.decay2) >> 16;
    }
    if (brush.amp > 16) {   /* swish: lowpassed noise with a short swell */
        if (brush.amp2 < 65535u-effects[10]) brush.amp2 += effects[10]; else brush.amp2 = 65535u;
        int32_t a = (int32_t)((brush.amp >> 8)*(brush.amp2 >> 8)) >> 2;
        for (unsigned i = 0; i < BLOCK; i++) {
            int32_t n = (int16_t)(xorshift() >> 16); brush.lp += (n - brush.lp) >> effects[11];
            int32_t o = (brush.lp*a) >> 14; mix_l[i] += (o*(int32_t)effects[12]) >> 8; mix_r[i] += (o*(int32_t)effects[13]) >> 8; mix_s[i] += (o*(int32_t)effects[14]) >> 8;
        }
        brush.amp -= (brush.amp*brush.decay) >> 16;
    }
    if (ride.amp > 16) {
        for (unsigned i = 0; i < BLOCK; i++) {
            ride.phase += effects[16]; int32_t n = (int16_t)(xorshift() >> 16), m = n - ride.prev; ride.prev = n;
            int32_t o = ((m + (S(ride.phase) >> 1))*(int32_t)(ride.amp >> 4)) >> 16;
            mix_l[i] += (o*(int32_t)effects[17]) >> 8; mix_r[i] += (o*(int32_t)effects[18]) >> 8;
        }
        ride.amp -= (ride.amp*ride.decay) >> 16;
    }
    if (rim.amp > 16) {
        for (unsigned i = 0; i < BLOCK; i++) {
            rim.phase += effects[20]; int32_t o = (S(rim.phase)*(int32_t)(rim.amp >> 2)) >> 16;
            mix_l[i] += (o*(int32_t)effects[21]) >> 8; mix_r[i] += (o*(int32_t)effects[22]) >> 8;
        }
        rim.amp -= (rim.amp*rim.decay) >> 16;
    }
    /* Filtered stochastic noise; target level is supplied by Python. */
    noise_level += (noise_target - noise_level) >> effects[23];
    if (noise_level > 8) {
        for (unsigned i = 0; i < BLOCK; i++) {
            int32_t n = (int16_t)(xorshift() >> 16);
            noise_lp += (n - noise_lp) >> effects[24]; noise_hp += (noise_lp - noise_hp) >> effects[25];
            int32_t o = ((noise_lp - noise_hp)*noise_level) >> 14;
            if (noise_drop > 0) { o += (int32_t)(((xorshift() >> 20) & 1023) - 512)*noise_drop >> 6; noise_drop -= (int32_t)effects[31]; }
            mix_l[i] += (o*(int32_t)effects[26]) >> 8; mix_r[i] += (o*(int32_t)effects[27]) >> 8;
        }
        if ((xorshift() & effects[28]) == 0) noise_drop = effects[29] + (int32_t)(xorshift() & effects[30]);
    }
}


enum { NOTE,OFF,GAIN,DRUM,NOISE,PITCH,MASTER,CRUSH,STUTTER,PITCH_RAMP,MASTER_RAMP,ALL_OFF,DELAY };
static const uint8_t *schedule;
static size_t schedule_bytes,schedule_offset;
static const uint8_t *schedule_pages[128];
static bool schedule_segmented;
static int configuration_error;
int fm_configuration_error(void) { return configuration_error; }
static const uint8_t *event_at(size_t offset) {
    return schedule_segmented ? schedule_pages[offset/1024]+offset%1024 : schedule+offset;
}
const uint8_t *fm_configuration_event(void) {
    return configuration_error>=0 ? event_at((size_t)configuration_error*16) : NULL;
}
typedef struct { uint8_t op,channel,a,b; uint32_t v0,v1; } command;
static command live[32];
static _Atomic uint32_t written,read_at;
typedef struct { uint32_t start,from,to,duration; bool active; } ramp;
static ramp pitch_ramp,master_ramp;
static unsigned master_gain,delay_feedback,delay_wet;
static unsigned get16(const uint8_t *p) { return p[0]|((unsigned)p[1]<<8); }
static uint32_t get32(const uint8_t *p) { return get16(p)|((uint32_t)get16(p+2)<<16); }
bool fm_effects(const uint8_t *p,size_t n) {
    if(!p || n!=33*4) return false;
    uint32_t v[33]; for(unsigned i=0;i<33;i++) v[i]=get32(p+i*4);
    for(unsigned i=3;i<=6;i++) if(v[i]>65535) return false;
    if(v[7]>32 || v[8]>32 || v[9]>65535 || v[10]>65535 || v[11]>15 ||
       v[12]>256 || v[13]>256 || v[14]>256 || v[15]>65535 || v[17]>256 || v[18]>256 ||
       v[19]>65535 || v[21]>256 || v[22]>256 || v[23]>15 || v[24]>15 || v[25]>15 ||
       v[26]>256 || v[27]>256 || v[28]>65535 || v[29]>1024 || v[30]>1023 || v[31]>1024 ||
       v[32]<2 || v[32]>DELAY_FRAMES) return false;
    memcpy(effects,v,sizeof effects); return true;
}
static bool valid(command c) {
    switch(c.op) {
    case NOTE: return c.channel<7 && c.a<patch_count && c.b<128 && c.v0<256 && c.v1<=2880000;
    case OFF: case GAIN: return c.channel<7 && (c.op==OFF || (c.v0<256 && c.v1<256));
    case DRUM: return c.a<4 && c.v0<2;
    case NOISE: return c.v0<=16384;
    case PITCH: return c.v0<=262144;
    case MASTER: return c.v0<256;
    case CRUSH: return c.v0<=7;
    case STUTTER: return c.v0>=1 && c.v0<=4096 && c.v1<=2880000;
    case PITCH_RAMP: return c.v0<=262144 && c.v1>=16 && c.v1<=172800000;
    case MASTER_RAMP: return c.v0<256 && c.v1>=16 && c.v1<=172800000;
    case ALL_OFF: return true;
    case DELAY: return c.v0<=250 && c.v1<256;
    default: return false;
    }
}
static bool configure_patches(const uint8_t *p,size_t pn) {
    if(!p || pn==0 || pn%59 || pn/59>16) return false;
    patch_count=pn/59;
    for(unsigned i=0;i<patch_count;i++,p+=59) {
        patch *q=&patches[i];
        q->alg=p[0]; q->fb=p[1]; q->vib=p[2]; q->vib_shift=p[3]; q->send=p[4]; q->vib_hz10=get16(p+5);
        if(q->alg>1 || q->fb>16 || q->vib_shift<3 || q->vib_shift>24 || q->vib_hz10>2000) return false;
        for(unsigned o=0;o<4;o++) {
            const uint8_t *v=p+7+13*o; op_patch *op=&q->op[o];
            op->ratio=get16(v); op->detune=(int8_t)v[2]; op->tl=get16(v+3); op->ar=get16(v+5);
            op->dr=get16(v+7); op->sl=get16(v+9); op->rr=get16(v+11);
        }
    }
    return true;
}
static bool validate_schedule(void) {
    uint32_t previous=0;
    for(size_t i=0;i<schedule_bytes;i+=16) {
        const uint8_t *v=event_at(i);
        uint32_t at=get32(v); command c={v[4],v[5],v[6],v[7],get32(v+8),get32(v+12)};
        if(at<previous || !valid(c) || (c.v1 && at>UINT32_MAX-c.v1)) {
            configuration_error=(int)(i/16); return false;
        }
        previous=at;
    }
    configuration_error=-1; schedule_offset=0; return true;
}
bool fm_configure(const uint8_t *p,size_t pn,const uint8_t *s,size_t sn) {
    configuration_error=-2;
    if(sn%16 || sn>131072 || (sn && !s) || !configure_patches(p,pn)) return false;
    schedule_segmented=false; schedule=s; schedule_bytes=sn;
    return validate_schedule();
}
bool fm_configure_pages(const uint8_t *p,size_t pn,const uint8_t *const *pages,size_t count,size_t total) {
    configuration_error=-2;
    if(total%16 || total>131072 || count!=(total+1023)/1024 || (count && !pages) || !configure_patches(p,pn)) return false;
    for(size_t i=0;i<count;i++) { if(!pages[i]) return false; schedule_pages[i]=pages[i]; }
    schedule_segmented=true; schedule_bytes=total;
    return validate_schedule();
}
bool fm_command(unsigned op,unsigned channel,unsigned a,unsigned b,uint32_t v0,uint32_t v1) {
    if(op>DELAY || channel>255 || a>255 || b>255) return false;
    command c={op,channel,a,b,v0,v1}; if(!valid(c)) return false;
    uint32_t w=atomic_load_explicit(&written,memory_order_relaxed);
    if(w-atomic_load_explicit(&read_at,memory_order_acquire)==32) return false;
    live[w%32]=c; atomic_store_explicit(&written,w+1,memory_order_release); return true;
}
bool fm_note_on(unsigned v,unsigned p,unsigned n,unsigned vel,uint32_t gate_ms) {
    if(gate_ms>60000 || n>127) return false;
    return fm_command(NOTE,v,p,n,vel,gate_ms*48u);
}
bool fm_note_off(unsigned v) { return fm_command(OFF,v,0,0,0,0); }
bool fm_all_off(void) { return fm_command(ALL_OFF,0,0,0,0,0); }
static void execute(command c) {
    switch(c.op) {
    case NOTE: note_on(c.channel,&patches[c.a],c.b,c.v0,c.v1?position+c.v1:0); break;
    case OFF: note_off(c.channel); break;
    case GAIN: voices[c.channel].gl=c.v0; voices[c.channel].gr=c.v1; break;
    case DRUM:
        if(c.a==0) hit_kick(c.b,c.v0!=0); else if(c.a==1) hit_brush(c.b);
        else if(c.a==2) hit_ride(c.b); else hit_rim(c.b);
        break;
    case NOISE: noise_target=c.v0; break;
    case PITCH: pitch_q16=c.v0; pitch_ramp.active=false; break;
    case MASTER: master_gain=c.v0; master_ramp.active=false; break;
    case CRUSH: crush_bits=c.v0; break;
    case STUTTER: stutter_start=position; stutter_len=c.v0; stutter_until=position+c.v1; break;
    case PITCH_RAMP: pitch_ramp=(ramp){position,pitch_q16,c.v0,c.v1,true}; break;
    case MASTER_RAMP: master_ramp=(ramp){position,master_gain,c.v0,c.v1,true}; break;
    case ALL_OFF: for(unsigned v=0;v<7;v++) note_off(v); break;
    case DELAY: delay_feedback=c.v0; delay_wet=c.v1; break;
    }
}
static void commands(void) {
    uint32_t r=atomic_load_explicit(&read_at,memory_order_relaxed),w=atomic_load_explicit(&written,memory_order_acquire);
    while(r!=w) execute(live[r++%32]);
    atomic_store_explicit(&read_at,r,memory_order_release);
    while(schedule_offset<schedule_bytes && get32(event_at(schedule_offset))<=position) {
        const uint8_t *v=event_at(schedule_offset);
        execute((command){v[4],v[5],v[6],v[7],get32(v+8),get32(v+12)}); schedule_offset+=16;
    }
}
static uint32_t ramp_value(ramp *r,bool weighted) {
    uint32_t t=position-r->start;
    if(t>=r->duration) { r->active=false; return r->to; }
    if(weighted) return ((uint64_t)r->from*(r->duration-t)+(uint64_t)r->to*t)/r->duration;
    return r->from+(int64_t)((int32_t)r->to-(int32_t)r->from)*t/r->duration;
}
void fm_init(void) {
    for(unsigned i=0;i<1024;i++) sine[i]=(int16_t)lrintf(32767.0f*sinf((float)i*6.28318530718f/1024.0f));
    for(unsigned n=0;n<128;n++) note_inc[n]=(uint32_t)(440.0*pow(2.0,((double)n-69.0)/12.0)*4294967296.0/FM_RATE);
    memset(voices,0,sizeof voices); for(unsigned v=0;v<7;v++) voices[v].gl=voices[v].gr=200;
    memset(&kick,0,sizeof kick); memset(&brush,0,sizeof brush); memset(&ride,0,sizeof ride); memset(&rim,0,sizeof rim);
    memset(delay_line,0,sizeof delay_line); memset(stutter_l,0,sizeof stutter_l); memset(stutter_r,0,sizeof stutter_r);
    position=delay_pos=peak=clipped=0; rng=0x2545f491u; pitch_q16=65536; crush_bits=0;
    stutter_until=0; noise_level=noise_target=noise_lp=noise_hp=noise_drop=0;
    pitch_ramp.active=master_ramp.active=false; master_gain=255; delay_feedback=delay_wet=0;
    memset(effects,0,sizeof effects); effects[32]=DELAY_FRAMES;
    patch_count=0; schedule=NULL; schedule_bytes=schedule_offset=0; schedule_segmented=false;
    atomic_store(&written,0); atomic_store(&read_at,0);
}
HOT void fm_render(int8_t *left,int8_t *right,unsigned frames) {
    while(frames) {
        for(unsigned v=0;v<7;v++) if(voices[v].off_at && voices[v].off_at<=position) note_off(v);
        if(pitch_ramp.active) pitch_q16=ramp_value(&pitch_ramp,false);
        if(master_ramp.active) master_gain=ramp_value(&master_ramp,true);
        commands();
        memset(mix_l,0,sizeof mix_l); memset(mix_r,0,sizeof mix_r); memset(mix_s,0,sizeof mix_s);
        for(unsigned v=0;v<7;v++) render_voice(&voices[v]);
        render_drums();
        int32_t master=master_gain;
        for (unsigned i = 0; i < BLOCK; i++) {
            unsigned opposite=delay_pos+effects[32]/2;
            if(opposite>=effects[32]) opposite-=effects[32];
            int32_t d = delay_line[delay_pos], d2 = delay_line[opposite];
            int32_t w = mix_s[i] + ((d*(int32_t)delay_feedback) >> 8);
            delay_line[delay_pos] = (int16_t)(w > 32767 ? 32767 : w < -32768 ? -32768 : w);
            if (++delay_pos == effects[32]) delay_pos = 0;
            int32_t ch[2] = {mix_l[i] + ((d*(int32_t)delay_wet) >> 8), mix_r[i] + ((d2*(int32_t)delay_wet) >> 8)};
            uint32_t pos = position + i;
            for (unsigned c = 0; c < 2; c++) {
                int32_t x = (ch[c]*master) >> 8, a = x < 0 ? -x : x;
                if ((uint32_t)a > peak) peak = (uint32_t)a;
                if (a > 24000) { a = 24000 + ((a - 24000) >> 2); if (a > 32000) { a = 32000; clipped++; } x = x < 0 ? -a : a; }
                int32_t dither = (int32_t)(xorshift() & 255) - (int32_t)(xorshift() & 255);
                int32_t y = (x + dither + 128) >> 8;
                y = y > 127 ? 127 : y < -128 ? -128 : y;
                if (crush_bits) y = (y >> crush_bits) * (1 << crush_bits);
                int8_t *buf = c ? stutter_r : stutter_l;
                if (pos < stutter_until && pos >= stutter_start + stutter_len) y = buf[(stutter_start + (pos - stutter_start) % stutter_len) % STUTTER_FRAMES];
                else buf[pos % STUTTER_FRAMES] = (int8_t)y;
                (c ? right : left)[i] = (int8_t)y;
            }
        }
        left += BLOCK; right += BLOCK; frames = frames > BLOCK ? frames - BLOCK : 0; position += BLOCK;
    }
}
uint32_t fm_position(void) { return position; }
uint32_t fm_peak(void) { return peak; }
uint32_t fm_clipped(void) { return clipped; }
