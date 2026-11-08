// SPDX-License-Identifier: Apache-2.0
// FOUR OPERATORS: 6-voice 4-operator FM synthesizer, 3 synthesized drums,
// a stereo echo and an original 130 s song in A minor at 120 BPM.
// Integer only in the render path (RP2040 core 1 has no FPU).
#include "fm.h"
#include <math.h>
#include <stdbool.h>
#include <string.h>

#define BLOCK 16u                    /* envelope/control rate: 3 kHz */
#define MOD_SHIFT 18                 /* full-scale modulator = 2 cycles */
#define ATK(ms) ((uint16_t)((ms) ? (65535u/(3u*(ms)) ? 65535u/(3u*(ms)) : 1u) : 65535u))
#define DEC(ms) ((uint16_t)((ms) ? (65536u/(3u*(ms)) ? 65536u/(3u*(ms)) : 1u) : 65535u))
#define SL(x) ((uint16_t)((x)*65535.0))
#define RATIO(x) ((uint16_t)((x)*256.0))
#define DELAY_FRAMES 18000u          /* dotted eighth: 375 ms */

static int16_t sine[1024];
static uint32_t note_inc[128];

typedef struct { uint16_t ratio; int8_t detune; uint16_t tl, ar, dr, sl, rr; } op_patch;
typedef struct { uint8_t alg, fb, vib, send; op_patch op[FM_OPS]; } patch;
enum { ALG_SERIAL, ALG_STACKS, ALG_BRANCH, ALG_TRIPLE };
enum { ENV_OFF, ENV_ATTACK, ENV_DECAY, ENV_SUSTAIN, ENV_RELEASE };

// Carrier/modulator assignment per algorithm (bit set = carrier).
static const uint8_t carriers[4]={0x1,0x5,0x1,0x7};

static const patch P_BASS={ALG_STACKS,3,0,0,{
    {RATIO(1.0),0,23000,ATK(0),DEC(450),SL(0.55),DEC(60)},
    {RATIO(1.0),0,30000,ATK(0),DEC(70),SL(0.12),DEC(60)},
    {RATIO(0.5),0,15000,ATK(0),DEC(600),SL(0.8),DEC(60)},
    {RATIO(2.0),0,9000,ATK(0),DEC(45),SL(0.0),DEC(60)}}};
static const patch P_LEAD={ALG_STACKS,4,150,80,{
    {RATIO(1.0),5,15000,ATK(8),DEC(900),SL(0.7),DEC(160)},
    {RATIO(1.0),0,24000,ATK(15),DEC(350),SL(0.45),DEC(160)},
    {RATIO(2.0),-5,8000,ATK(10),DEC(900),SL(0.7),DEC(160)},
    {RATIO(1.0),0,16000,ATK(20),DEC(400),SL(0.4),DEC(160)}}};
static const patch P_LEAD2={ALG_STACKS,5,170,95,{
    {RATIO(1.0),4,14000,ATK(5),DEC(700),SL(0.65),DEC(140)},
    {RATIO(3.0),0,17000,ATK(5),DEC(250),SL(0.35),DEC(140)},
    {RATIO(2.0),-4,9000,ATK(5),DEC(700),SL(0.6),DEC(140)},
    {RATIO(1.0),0,19000,ATK(10),DEC(300),SL(0.45),DEC(140)}}};
static const patch P_BELL={ALG_STACKS,0,60,130,{
    {RATIO(1.0),0,17000,ATK(0),DEC(1600),SL(0.0),DEC(900)},
    {RATIO(3.5),0,21000,ATK(0),DEC(700),SL(0.0),DEC(900)},
    {RATIO(2.0),3,6500,ATK(0),DEC(900),SL(0.0),DEC(900)},
    {RATIO(7.0),0,9000,ATK(0),DEC(250),SL(0.0),DEC(900)}}};
static const patch P_ARP={ALG_STACKS,0,0,70,{
    {RATIO(1.0),0,12500,ATK(0),DEC(260),SL(0.0),DEC(90)},
    {RATIO(4.0),0,17000,ATK(0),DEC(110),SL(0.0),DEC(90)},
    {RATIO(2.0),2,5500,ATK(0),DEC(200),SL(0.0),DEC(90)},
    {RATIO(7.0),0,8000,ATK(0),DEC(60),SL(0.0),DEC(90)}}};
static const patch P_PAD={ALG_TRIPLE,2,40,25,{
    {RATIO(1.0),4,6200,ATK(450),DEC(2000),SL(0.85),DEC(700)},
    {RATIO(1.0),-4,6200,ATK(500),DEC(2000),SL(0.85),DEC(700)},
    {RATIO(2.0),1,2600,ATK(650),DEC(2000),SL(0.8),DEC(700)},
    {RATIO(1.0),0,8500,ATK(700),DEC(1500),SL(0.7),DEC(700)}}};

typedef struct { uint32_t phase, inc; uint32_t level; uint8_t env; } op_state;
typedef struct {
    const patch *p;
    op_state op[FM_OPS];
    int32_t fb0, fb1;
    uint32_t base_inc, vib_phase;
    uint16_t vib_ramp, gl, gr, vel;
    uint8_t note;
    uint32_t off_step;                 /* absolute step for note-off, 0 = none */
} voice;
static voice voices[FM_VOICES];

typedef struct { uint32_t phase, amp, amp2, decay, decay2; int32_t prev; uint8_t open; } drum;
static drum drums[FM_DRUMS];

static int16_t delay_line[DELAY_FRAMES];
static uint32_t delay_pos, position, rng=0x2545f491u, peak, clipped;
static fm_snapshot snaps[FM_SNAP_RING];
static int32_t mix_l[BLOCK], mix_r[BLOCK], mix_s[BLOCK];

static inline uint32_t xorshift(void) { rng^=rng<<13; rng^=rng>>17; rng^=rng<<5; return rng; }
static inline int32_t S(uint32_t phase) { return sine[phase>>22]; }

void fm_init(void) {
    for (unsigned i=0;i<1024;i++) sine[i]=(int16_t)lrintf(32767.0f*sinf((float)i*6.28318530718f/1024.0f));
    for (unsigned n=0;n<128;n++)
        note_inc[n]=(uint32_t)(440.0*pow(2.0,((double)n-69.0)/12.0)*4294967296.0/FM_RATE);
    memset(voices,0,sizeof voices); memset(drums,0,sizeof drums);
    memset(delay_line,0,sizeof delay_line); memset(snaps,0,sizeof snaps);
    delay_pos=position=peak=clipped=0; rng=0x2545f491u;
    static const uint16_t gl[FM_VOICES]={225,190,200,240,205,140}, gr[FM_VOICES]={225,235,200,140,205,240};
    for (unsigned v=0;v<FM_VOICES;v++) { voices[v].gl=gl[v]; voices[v].gr=gr[v]; voices[v].p=&P_PAD; }
}

/* ---------------------------------------------------------------- voices */
static void note_on(unsigned v, const patch *p, unsigned note, unsigned vel, uint32_t off_step) {
    voice *x=&voices[v];
    bool retune=x->p!=p;
    x->p=p; x->note=(uint8_t)note; x->vel=(uint16_t)vel; x->off_step=off_step;
    x->base_inc=note_inc[note&127]; x->vib_ramp=0;
    for (unsigned o=0;o<FM_OPS;o++) {
        const op_patch *q=&p->op[o];
        uint32_t inc=(uint32_t)(((uint64_t)x->base_inc*q->ratio)>>8);
        inc+=(uint32_t)((int32_t)(inc>>14)*q->detune);
        x->op[o].inc=inc; x->op[o].env=ENV_ATTACK;   /* attack from current level: no click */
        if (retune) x->op[o].level=0;
    }
}
static void note_off(unsigned v) {
    for (unsigned o=0;o<FM_OPS;o++) if (voices[v].op[o].env!=ENV_OFF) voices[v].op[o].env=ENV_RELEASE;
    voices[v].off_step=0;
}
static void envelope(op_state *s, const op_patch *q) {
    switch (s->env) {
    case ENV_ATTACK:
        s->level+=q->ar; if (s->level>=65535u) { s->level=65535u; s->env=ENV_DECAY; } break;
    case ENV_DECAY:
        if (s->level>q->sl) s->level-=((s->level-q->sl)*q->dr)>>16;
        if (s->level<=q->sl+64u) { s->level=q->sl; s->env=q->sl ? ENV_SUSTAIN : ENV_OFF; } break;
    case ENV_RELEASE:
        s->level-=(s->level*q->rr)>>16; if (s->level<48u) { s->level=0; s->env=ENV_OFF; } break;
    default: break;
    }
}
static void render_voice(voice *x) {
    const patch *p=x->p;
    uint32_t amp[FM_OPS], inc[FM_OPS], active=0;
    // Delayed vibrato on the base pitch.
    int32_t vib=0;
    if (p->vib) {
        x->vib_phase+=BLOCK*(uint32_t)(5.4*4294967296.0/FM_RATE);
        if (x->vib_ramp<65535u-80u) x->vib_ramp+=80u;
        vib=((S(x->vib_phase)>>7)*(int32_t)p->vib)>>8;
        vib=(vib*(int32_t)(x->vib_ramp>>8))>>8;
    }
    for (unsigned o=0;o<FM_OPS;o++) {
        envelope(&x->op[o],&p->op[o]);
        uint32_t a=(x->op[o].level*p->op[o].tl)>>16;
        if (carriers[p->alg]>>o&1) a=(a*x->vel)>>8;
        amp[o]=a; active|=a;
        inc[o]=x->op[o].inc+(uint32_t)(((int32_t)(x->op[o].inc>>8)*vib)>>8);
    }
    if (!active) return;
    uint32_t p0=x->op[0].phase,p1=x->op[1].phase,p2=x->op[2].phase,p3=x->op[3].phase;
    int32_t f0=x->fb0,f1=x->fb1;
    const unsigned fbs=p->fb ? 11u+p->fb : 0u;
    for (unsigned i=0;i<BLOCK;i++) {
        p0+=inc[0]; p1+=inc[1]; p2+=inc[2]; p3+=inc[3];
        uint32_t fb=fbs ? (uint32_t)((f0+f1)>>1)<<fbs : 0u;
        int32_t o3=(S(p3+fb)*(int32_t)amp[3])>>16; f1=f0; f0=o3;
        int32_t out;
        switch (p->alg) {
        case ALG_SERIAL: {
            int32_t o2=(S(p2+((uint32_t)o3<<MOD_SHIFT))*(int32_t)amp[2])>>16;
            int32_t o1=(S(p1+((uint32_t)o2<<MOD_SHIFT))*(int32_t)amp[1])>>16;
            out=(S(p0+((uint32_t)o1<<MOD_SHIFT))*(int32_t)amp[0])>>16; break; }
        case ALG_STACKS: {
            int32_t o2=(S(p2+((uint32_t)o3<<MOD_SHIFT))*(int32_t)amp[2])>>16;
            int32_t o1=(S(p1)*(int32_t)amp[1])>>16;
            out=((S(p0+((uint32_t)o1<<MOD_SHIFT))*(int32_t)amp[0])>>16)+o2; break; }
        case ALG_BRANCH: {
            int32_t o2=(S(p2+((uint32_t)o3<<MOD_SHIFT))*(int32_t)amp[2])>>16;
            int32_t o1=(S(p1)*(int32_t)amp[1])>>16;
            out=(S(p0+((uint32_t)(o1+o2)<<MOD_SHIFT))*(int32_t)amp[0])>>16; break; }
        default: { /* TRIPLE: op3 modulates three carriers */
            uint32_t m=(uint32_t)o3<<MOD_SHIFT;
            out=((S(p0+m)*(int32_t)amp[0])>>16)+((S(p1+m)*(int32_t)amp[1])>>16)+((S(p2+m)*(int32_t)amp[2])>>16); break; }
        }
        mix_l[i]+=(out*(int32_t)x->gl)>>8; mix_r[i]+=(out*(int32_t)x->gr)>>8;
        mix_s[i]+=(out*(int32_t)p->send)>>8;
    }
    x->op[0].phase=p0; x->op[1].phase=p1; x->op[2].phase=p2; x->op[3].phase=p3;
    x->fb0=f0; x->fb1=f1;
}

/* ----------------------------------------------------------------- drums */
#define HZ(f) ((uint32_t)((f)*4294967296.0/FM_RATE))
static uint32_t decay_coef(unsigned ms) { return 65536u/(3u*ms); }
static void hit(unsigned d, unsigned vel, bool open) {
    drum *x=&drums[d];
    x->amp=vel<<8; x->amp2=vel<<8; x->open=open;
    if (d==D_KICK) { x->phase=0; x->decay=decay_coef(230); x->decay2=decay_coef(38); }
    if (d==D_SNARE) { x->decay=decay_coef(115); x->decay2=decay_coef(45); }
    if (d==D_HAT) { x->decay=decay_coef(open ? 170 : 26); }
}
static void render_drums(void) {
    drum *k=&drums[D_KICK], *s=&drums[D_SNARE], *h=&drums[D_HAT];
    if (k->amp>16) {
        uint32_t inc=HZ(44)+(uint32_t)(((uint64_t)HZ(118)*k->amp2)>>16);
        for (unsigned i=0;i<BLOCK;i++) {
            k->phase+=inc; int32_t o=(S(k->phase)*(int32_t)(k->amp>>1))>>15;
            o=(o*14)>>4; mix_l[i]+=o; mix_r[i]+=o;
        }
        k->amp-=(k->amp*k->decay)>>16; k->amp2-=(k->amp2*k->decay2)>>16;
    }
    if (s->amp>16) {
        for (unsigned i=0;i<BLOCK;i++) {
            s->phase+=HZ(186);
            int32_t n=(int16_t)(xorshift()>>16);
            int32_t o=((n*(int32_t)(s->amp>>2))>>14)+((S(s->phase)*(int32_t)(s->amp2>>2))>>14);
            o=(o*6)>>4; mix_l[i]+=(o*235)>>8; mix_r[i]+=(o*185)>>8; mix_s[i]+=o>>4;
        }
        s->amp-=(s->amp*s->decay)>>16; s->amp2-=(s->amp2*(s->decay*5/2))>>16;
    }
    if (h->amp>16) {
        for (unsigned i=0;i<BLOCK;i++) {
            int32_t n=(int16_t)(xorshift()>>16), o=n-h->prev; h->prev=n;
            o=(o*(int32_t)(h->amp>>3))>>15; mix_l[i]+=(o*140)>>8; mix_r[i]+=(o*230)>>8;
        }
        h->amp-=(h->amp*h->decay)>>16;
    }
}

/* ------------------------------------------------------------------ song */
enum { Am, F, C, G, Dm, E, Em };
static const uint8_t chord_tones[][3]={{57,60,64},{53,57,60},{55,60,64},{55,59,62},{57,62,65},{56,59,64},{55,59,64}};
static const uint8_t chord_root[]={45,41,36,43,38,40,40};
typedef struct { uint8_t bar, step, note, len; } ev;
static const ev MEL_A[]={
 {0,0,76,4},{0,4,81,4},{0,8,79,2},{0,10,76,2},{0,12,72,4},{1,0,74,4},{1,4,72,2},{1,6,69,2},{1,8,72,8},
 {2,0,76,4},{2,4,79,4},{2,8,84,4},{2,12,83,2},{2,14,79,2},{3,0,81,6},{3,6,79,2},{3,8,74,8},
 {4,0,76,2},{4,2,81,2},{4,4,84,4},{4,8,83,2},{4,10,81,2},{4,12,79,4},{5,0,81,4},{5,4,77,4},{5,8,72,4},{5,12,74,4},
 {6,0,76,4},{6,4,74,2},{6,6,72,2},{6,8,79,4},{6,12,76,4},{7,0,74,8},{7,8,71,4},{7,12,74,4},{255,0,0,0}};
static const ev MEL_B[]={
 {0,0,77,4},{0,4,81,4},{0,8,86,6},{0,14,84,2},{1,0,81,4},{1,4,76,4},{1,8,72,8},
 {2,0,84,4},{2,4,81,2},{2,6,77,2},{2,8,81,4},{2,12,84,4},{3,0,83,6},{3,6,80,2},{3,8,76,8},
 {4,0,86,4},{4,4,89,4},{4,8,88,2},{4,10,86,2},{4,12,84,4},{5,0,88,4},{5,4,84,4},{5,8,81,8},
 {6,0,77,2},{6,2,81,2},{6,4,84,2},{6,6,89,2},{6,8,88,4},{6,12,84,4},{7,0,83,8},{7,8,80,4},{7,12,83,4},{255,0,0,0}};
static const ev MEL_C[]={
 {0,0,81,3},{0,3,84,3},{0,6,89,2},{0,8,88,4},{0,12,84,4},{1,0,86,3},{1,3,83,3},{1,6,79,2},{1,8,83,4},{1,12,86,4},
 {2,0,88,4},{2,4,83,4},{2,8,79,4},{2,12,83,4},{3,0,84,6},{3,6,83,2},{3,8,81,8},
 {4,0,81,3},{4,3,84,3},{4,6,89,2},{4,8,88,4},{4,12,84,4},{5,0,86,3},{5,3,83,3},{5,6,79,2},{5,8,83,4},{5,12,86,4},
 {6,0,91,4},{6,4,88,4},{6,8,83,4},{6,12,88,4},{7,0,93,12},{7,12,88,4},{255,0,0,0}};
static const ev MEL_D[]={
 {0,0,81,8},{0,8,88,8},{1,0,84,8},{1,8,83,8},{2,0,81,16},{3,0,77,8},{3,8,84,8},{4,0,88,8},{4,8,91,8},
 {5,0,88,16},{6,0,86,8},{6,8,83,8},{7,0,80,8},{7,8,83,4},{7,12,88,4},{255,0,0,0}};
static const ev MEL_E[]={
 {0,0,81,8},{0,8,84,8},{1,0,83,8},{1,8,86,8},{2,0,84,16},{3,0,81,16},{4,0,81,8},{4,8,84,8},
 {5,0,83,8},{5,8,86,8},{6,0,80,16},{7,0,83,16},{255,0,0,0}};

enum { T_PAD=1, T_BASS=2, T_ARP8=4, T_ARP16=8, T_LEAD=16, T_DRUMS=32, T_HAT16=64, T_DRIVE=128 };
typedef struct { uint8_t chords[8]; const ev *melody; const patch *lead; int8_t transpose; uint8_t tracks; } section;
static const section song[8]={
    {{Am,F,C,G,Am,F,C,G},NULL,NULL,0,T_PAD},                                     /* intro: builds up */
    {{Am,F,C,G,Am,F,C,G},MEL_A,&P_LEAD,0,T_PAD|T_BASS|T_ARP8|T_LEAD|T_DRUMS},
    {{Dm,Am,F,E,Dm,Am,F,E},MEL_B,&P_LEAD,0,T_PAD|T_BASS|T_ARP16|T_LEAD|T_DRUMS},
    {{Am,F,C,G,Am,F,C,G},MEL_A,&P_LEAD2,0,T_PAD|T_BASS|T_ARP16|T_LEAD|T_DRUMS},
    {{F,G,Em,Am,F,G,Em,Am},MEL_C,&P_LEAD2,0,T_PAD|T_BASS|T_ARP8|T_LEAD|T_DRUMS|T_DRIVE},
    {{Am,Am,F,F,C,C,G,E},MEL_D,&P_BELL,0,T_PAD},                                   /* breakdown */
    {{Am,F,C,G,Am,F,C,G},MEL_A,&P_LEAD2,12,T_PAD|T_BASS|T_ARP16|T_LEAD|T_DRUMS|T_HAT16},
    {{F,G,Am,Am,F,G,E,E},MEL_E,&P_LEAD,0,T_PAD|T_BASS|T_LEAD}};
static const int8_t BASS_8[16]={0,-1,0,-1,12,-1,0,-1,0,-1,12,-1,0,-1,7,-1};
static const int8_t BASS_16[16]={0,0,12,0,0,0,12,0,0,0,12,0,0,12,7,12};
static const uint8_t ARP_SEQ[8]={0,1,2,3,4,3,2,1};

static unsigned arp_note(unsigned chord, unsigned i) {
    const uint8_t *t=chord_tones[chord];
    unsigned k=ARP_SEQ[i&7];
    return (unsigned)(k<3 ? t[k] : t[k-3]+12)+12;
}
static void drums_for(unsigned sec, unsigned sbar, unsigned st) {
    const section *s=&song[sec];
    if (sec==0) {                              /* intro: kick from bar 4, hats from bar 6 */
        if (sbar>=4 && st%4==0) hit(D_KICK,230,false);
        if (sbar>=6 && st%4==2) hit(D_HAT,150,false);
        if (sbar==7 && st>=12) hit(D_SNARE,120+st*8,false);
        return;
    }
    if (sec==5) {                              /* breakdown */
        if (sbar<6 && st%4==2) hit(D_HAT,110+(st==14)*40,st==14);
        if (sbar==6 && st%4==0) hit(D_KICK,210,false);
        if (sbar==6 && st%2==1) hit(D_HAT,120,false);
        if (sbar==7) { hit(D_SNARE,(unsigned)(90+st*10),false); if (st%4==0) hit(D_KICK,230,false); }
        return;
    }
    if (sec==7) {                              /* finale: half time, stops before the last bar */
        if (sbar<7 && st==0) hit(D_KICK,230,false);
        if (sbar<6 && st==8) hit(D_SNARE,200,false);
        if (sbar<6 && st%4==2) hit(D_HAT,130,false);
        return;
    }
    if (!(s->tracks&T_DRUMS)) return;
    bool kick=st%4==0 || ((s->tracks&T_DRIVE) && (st==10 || st==7));
    if (kick) hit(D_KICK,240,false);
    if (st==4 || st==12) hit(D_SNARE,215,false);
    if (sbar==7 && st>=13) hit(D_SNARE,140+(st-13)*30,false);
    if (s->tracks&T_HAT16) hit(D_HAT,st%2 ? 105 : 150,st==14);
    else if (st%4==2) hit(D_HAT,150,st==14);
}
static void sequence(uint32_t k) {
    unsigned bar=k/16, st=k%16;
    for (unsigned v=0;v<FM_VOICES;v++) if (voices[v].off_step && voices[v].off_step<=k) note_off(v);
    if (bar>=FM_SONG_BARS) return;
    if (bar==FM_SONG_BARS-1) {                  /* final chord */
        if (st==0) {
            for (unsigned i=0;i<3;i++) note_on(V_PAD0+i,&P_PAD,chord_tones[Am][i],255,k+12);
            note_on(V_BASS,&P_BASS,chord_root[Am],255,k+10);
            note_on(V_LEAD,&P_BELL,81,240,k+12);
            note_on(V_ARP,&P_BELL,69,200,k+12);
            hit(D_KICK,255,false); hit(D_HAT,170,true);
        }
        return;
    }
    unsigned sec=bar/8, sbar=bar%8;
    const section *s=&song[sec];
    unsigned chord=s->chords[sbar];
    if (st==0 && (s->tracks&T_PAD)) {
        bool change=sbar==0 || s->chords[sbar-1]!=chord || voices[V_PAD0].op[0].env==ENV_OFF;
        if (change) for (unsigned i=0;i<3;i++) note_on(V_PAD0+i,&P_PAD,chord_tones[chord][i],sec==0 && sbar<2 ? 190 : 230,0);
    }
    if (s->tracks&T_BASS || (sec==0 && sbar>=4)) {
        unsigned root=chord_root[chord];
        if (sec==0 || sec==7) { if (st==0) note_on(V_BASS,&P_BASS,root,235,k+15); }
        else {
            const int8_t *pat=(s->tracks&T_DRIVE) ? BASS_16 : BASS_8;
            if (pat[st]>=0) note_on(V_BASS,&P_BASS,root+(unsigned)pat[st],pat==BASS_16 ? 215 : 240,k+((s->tracks&T_DRIVE) ? 1 : 2));
        }
    }
    if ((s->tracks&T_ARP16) || ((s->tracks&T_ARP8) && st%2==0)) {
        unsigned i=(s->tracks&T_ARP16) ? st : st/2;
        voices[V_ARP].gl=(st&2) ? 235 : 150; voices[V_ARP].gr=(st&2) ? 150 : 235;
        note_on(V_ARP,&P_ARP,arp_note(chord,i),(st%4==0) ? 230 : 185,k+1);
    }
    if (s->melody) for (const ev *e=s->melody;e->bar!=255;e++)
        if (e->bar==sbar && e->step==st) note_on(V_LEAD,s->lead,(unsigned)(e->note+s->transpose),240,k+e->len);
    drums_for(sec,sbar,st);
}

/* ---------------------------------------------------------------- render */
static void snapshot(uint32_t frame) {
    fm_snapshot *s=&snaps[(frame/FM_SNAP_FRAMES)%FM_SNAP_RING];
    for (unsigned v=0;v<FM_VOICES;v++) {
        unsigned top=0;
        for (unsigned o=0;o<FM_OPS;o++) {
            unsigned l=voices[v].op[o].level>>8; s->op[v][o]=(uint8_t)l;
            if ((carriers[voices[v].p->alg]>>o&1) && l>top) top=l;
        }
        s->voice[v]=(uint8_t)((top*voices[v].vel)>>8);
        s->note[v]=top ? voices[v].note : 0;
    }
    for (unsigned d=0;d<FM_DRUMS;d++) s->drum[d]=(uint8_t)(drums[d].amp>>8 > 255 ? 255 : drums[d].amp>>8);
    s->bar=(uint8_t)(frame/FM_BAR_FRAMES); s->step=(uint8_t)(frame/FM_STEP_FRAMES%16);
}
void fm_render(int8_t *left, int8_t *right, unsigned frames) {
    while (frames) {
        if (position%FM_STEP_FRAMES==0) sequence(position/FM_STEP_FRAMES);
        if (position%FM_SNAP_FRAMES==0) snapshot(position);
        memset(mix_l,0,sizeof mix_l); memset(mix_r,0,sizeof mix_r); memset(mix_s,0,sizeof mix_s);
        for (unsigned v=0;v<FM_VOICES;v++) render_voice(&voices[v]);
        render_drums();
        unsigned n=frames<BLOCK ? frames : BLOCK;     /* frames is always a multiple of 16 in practice */
        for (unsigned i=0;i<n;i++) {
            int32_t d=delay_line[delay_pos], d2=delay_line[(delay_pos+DELAY_FRAMES/2)%DELAY_FRAMES];
            int32_t w=mix_s[i]+((d*112)>>8);
            delay_line[delay_pos]=(int16_t)(w>32767 ? 32767 : w<-32768 ? -32768 : w);
            if (++delay_pos==DELAY_FRAMES) delay_pos=0;
            int32_t ch[2]={mix_l[i]+((d*150)>>8),mix_r[i]+((d2*150)>>8)};
            for (unsigned c=0;c<2;c++) {
                int32_t x=(ch[c]*158)>>8, a=x<0 ? -x : x;
                if ((uint32_t)a>peak) peak=(uint32_t)a;
                if (a>24000) { a=24000+((a-24000)>>2); if (a>32000) { a=32000; clipped++; } x=x<0 ? -a : a; }
                int32_t dither=(int32_t)(xorshift()&255)-(int32_t)(xorshift()&255);
                int32_t y=(x+dither+128)>>8;
                y=y>127 ? 127 : y<-128 ? -128 : y;
                (c ? right : left)[i]=(int8_t)y;
            }
        }
        left+=n; right+=n; frames-=n; position+=n;
    }
}
uint32_t fm_position(void) { return position; }
const fm_snapshot *fm_snapshot_at(uint32_t frame) { return &snaps[(frame/FM_SNAP_FRAMES)%FM_SNAP_RING]; }
uint32_t fm_peak(void) { return peak; }
uint32_t fm_clipped(void) { return clipped; }
