// SPDX-License-Identifier: Apache-2.0
// MIDNIGHT TERMINAL sound engine. 4-operator FM voices (engine shared in
// design with FOUR OPERATORS), synthesized brushes, rain, and effects that
// follow the script in generated/script.h. Integer-only render path.
#include "mt_fm.h"
#include "script.h"
#include <math.h>
#include <stdbool.h>
#include <string.h>

#if MT_RAMFUNC
#define HOT __attribute__((section(".time_critical.mt_fm"), noinline))
#else
#define HOT
#endif
#define BLOCK 16u
#define FM_OPS 4
#define VOICES 7
#define MOD_SHIFT 18
#define DELAY_FRAMES 12000u
#define STUTTER_FRAMES 4096u
#define MS(t) ((uint32_t)(t)*48u)
#define ATK(ms) ((uint16_t)((ms) ? (65535u/(3u*(ms)) ? 65535u/(3u*(ms)) : 1u) : 65535u))
#define DEC(ms) ((uint16_t)((ms) ? (65536u/(3u*(ms)) ? 65536u/(3u*(ms)) : 1u) : 65535u))
#define SL(x) ((uint16_t)((x)*65535.0))
#define RATIO(x) ((uint16_t)((x)*256.0))
#define HZ(f) ((uint32_t)((f)*4294967296.0/FM_RATE))

enum { V_BASS, V_EP0, V_EP1, V_EP2, V_EP3, V_VIB, V_SFX };
enum { ALG_SERIAL, ALG_STACKS };
enum { ENV_OFF, ENV_ATTACK, ENV_DECAY, ENV_SUSTAIN, ENV_RELEASE };
static const uint8_t carriers[2] = {0x1, 0x5};

typedef struct { uint16_t ratio; int8_t detune; uint16_t tl, ar, dr, sl, rr; } op_patch;
typedef struct { uint8_t alg, fb, vib, vib_shift, send; uint16_t vib_hz10; op_patch op[FM_OPS]; } patch;

static const patch P_EP = {ALG_STACKS, 0, 22, 8, 45, 48, {
    {RATIO(1.0), 2, 15500, ATK(1), DEC(1700), SL(0.25), DEC(320)},
    {RATIO(1.0), 0, 8000, ATK(0), DEC(500), SL(0.12), DEC(320)},
    {RATIO(1.0), -2, 5200, ATK(0), DEC(420), SL(0.0), DEC(320)},
    {RATIO(14.0), 0, 5600, ATK(0), DEC(55), SL(0.0), DEC(320)}}};
static const patch P_BASS = {ALG_STACKS, 0, 0, 8, 0, 0, {
    {RATIO(1.0), 0, 22500, ATK(3), DEC(650), SL(0.35), DEC(90)},
    {RATIO(1.0), 0, 15000, ATK(0), DEC(130), SL(0.18), DEC(90)},
    {RATIO(1.0), 0, 6000, ATK(0), DEC(180), SL(0.0), DEC(90)},
    {RATIO(3.0), 0, 5000, ATK(0), DEC(35), SL(0.0), DEC(90)}}};
static const patch P_VIB = {ALG_STACKS, 0, 70, 8, 120, 55, {
    {RATIO(1.0), 0, 15500, ATK(0), DEC(2300), SL(0.0), DEC(700)},
    {RATIO(4.0), 0, 11500, ATK(0), DEC(320), SL(0.0), DEC(700)},
    {RATIO(3.0), 0, 3600, ATK(0), DEC(600), SL(0.0), DEC(700)},
    {RATIO(10.0), 0, 3800, ATK(0), DEC(80), SL(0.0), DEC(700)}}};
static const patch P_BLIP = {ALG_STACKS, 0, 0, 8, 30, 0, {
    {RATIO(1.0), 0, 7000, ATK(0), DEC(40), SL(0.0), DEC(30)},
    {RATIO(2.0), 0, 8000, ATK(0), DEC(25), SL(0.0), DEC(30)},
    {RATIO(1.0), 0, 0, ATK(0), DEC(10), SL(0.0), DEC(10)},
    {RATIO(1.0), 0, 0, ATK(0), DEC(10), SL(0.0), DEC(10)}}};
static const patch P_CHIME = {ALG_STACKS, 0, 0, 8, 110, 0, {
    {RATIO(1.0), 0, 12000, ATK(0), DEC(900), SL(0.0), DEC(500)},
    {RATIO(3.5), 0, 15000, ATK(0), DEC(400), SL(0.0), DEC(500)},
    {RATIO(2.0), 0, 5000, ATK(0), DEC(600), SL(0.0), DEC(500)},
    {RATIO(7.0), 0, 6000, ATK(0), DEC(150), SL(0.0), DEC(500)}}};
static const patch P_SIREN = {ALG_STACKS, 5, 255, 3, 40, 25, {
    {RATIO(1.0), 0, 10500, ATK(30), DEC(4000), SL(0.9), DEC(200)},
    {RATIO(1.0), 0, 14000, ATK(30), DEC(4000), SL(0.8), DEC(200)},
    {RATIO(1.5), 7, 6000, ATK(30), DEC(4000), SL(0.9), DEC(200)},
    {RATIO(2.0), 0, 9000, ATK(30), DEC(4000), SL(0.8), DEC(200)}}};
static const patch P_DRONE = {ALG_STACKS, 0, 30, 8, 30, 3, {
    {RATIO(1.0), 0, 15000, ATK(500), DEC(4000), SL(1.0), DEC(1500)},
    {RATIO(2.0), 0, 2500, ATK(800), DEC(4000), SL(0.8), DEC(1500)},
    {RATIO(1.5), 3, 3500, ATK(900), DEC(4000), SL(0.9), DEC(1500)},
    {RATIO(3.0), 0, 1500, ATK(900), DEC(4000), SL(0.7), DEC(1500)}}};
static const patch P_STING = {ALG_STACKS, 6, 0, 8, 60, 0, {
    {RATIO(1.0), 9, 14000, ATK(0), DEC(500), SL(0.0), DEC(200)},
    {RATIO(1.01), 0, 20000, ATK(0), DEC(400), SL(0.0), DEC(200)},
    {RATIO(0.5), -9, 12000, ATK(0), DEC(600), SL(0.0), DEC(200)},
    {RATIO(1.41), 0, 18000, ATK(0), DEC(300), SL(0.0), DEC(200)}}};

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
static uint32_t pitch_q16 = 65536;          /* global pitch (tape stop) */
static bool crush;
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
        inc[o] = base + (uint32_t)(((int32_t)(base >> p->vib_shift)*vib) >> 8);
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

/* ------------------------------------------------- drums, rain, effects */
typedef struct { uint32_t phase, amp, amp2, decay, decay2; int32_t lp, prev; uint8_t hard; } drum;
static drum kick, brush, ride, rim;
static int32_t rain_lp, rain_hp, rain_level, rain_target, rain_drop;
static uint32_t dcoef(unsigned ms) { return 65536u/(3u*ms); }
static void hit_kick(unsigned vel, bool hard) { kick.phase = 0; kick.amp = vel << 8; kick.amp2 = 65535; kick.hard = hard;
    kick.decay = dcoef(hard ? 260 : 190); kick.decay2 = dcoef(hard ? 30 : 45); }
static void hit_brush(unsigned vel) { brush.amp = vel << 8; brush.amp2 = 0; brush.decay = dcoef(170); }
static void hit_ride(unsigned vel) { ride.amp = vel << 8; ride.decay = dcoef(85); }
static void hit_rim(unsigned vel) { rim.amp = vel << 8; rim.decay = dcoef(14); rim.phase = 0; }
HOT static void render_drums(void) {
    if (kick.amp > 16) {
        uint32_t inc = HZ(44) + (uint32_t)(((uint64_t)HZ(kick.hard ? 120 : 70)*kick.amp2) >> 16);
        for (unsigned i = 0; i < BLOCK; i++) {
            kick.phase += inc; int32_t o = (S(kick.phase)*(int32_t)(kick.amp >> 1)) >> 15;
            o = (o*(kick.hard ? 15 : 11)) >> 4; mix_l[i] += o; mix_r[i] += o;
        }
        kick.amp -= (kick.amp*kick.decay) >> 16; kick.amp2 -= (kick.amp2*kick.decay2) >> 16;
    }
    if (brush.amp > 16) {   /* swish: lowpassed noise with a short swell */
        if (brush.amp2 < 65535u-9000u) brush.amp2 += 9000u; else brush.amp2 = 65535u;
        int32_t a = (int32_t)((brush.amp >> 8)*(brush.amp2 >> 8)) >> 2;
        for (unsigned i = 0; i < BLOCK; i++) {
            int32_t n = (int16_t)(xorshift() >> 16); brush.lp += (n - brush.lp) >> 2;
            int32_t o = (brush.lp*a) >> 14; mix_l[i] += (o*200) >> 8; mix_r[i] += (o*150) >> 8; mix_s[i] += o >> 3;
        }
        brush.amp -= (brush.amp*brush.decay) >> 16;
    }
    if (ride.amp > 16) {
        for (unsigned i = 0; i < BLOCK; i++) {
            ride.phase += HZ(5400); int32_t n = (int16_t)(xorshift() >> 16), m = n - ride.prev; ride.prev = n;
            int32_t o = ((m + (S(ride.phase) >> 1))*(int32_t)(ride.amp >> 4)) >> 16;
            mix_l[i] += (o*120) >> 8; mix_r[i] += (o*200) >> 8;
        }
        ride.amp -= (ride.amp*ride.decay) >> 16;
    }
    if (rim.amp > 16) {
        for (unsigned i = 0; i < BLOCK; i++) {
            rim.phase += HZ(1700); int32_t o = (S(rim.phase)*(int32_t)(rim.amp >> 2)) >> 16;
            mix_l[i] += (o*160) >> 8; mix_r[i] += (o*220) >> 8;
        }
        rim.amp -= (rim.amp*rim.decay) >> 16;
    }
    /* rain: soft lowpassed hiss plus sparse drops, level glides to target */
    rain_level += (rain_target - rain_level) >> 7;
    if (rain_level > 8) {
        for (unsigned i = 0; i < BLOCK; i++) {
            int32_t n = (int16_t)(xorshift() >> 16);
            rain_lp += (n - rain_lp) >> 3; rain_hp += (rain_lp - rain_hp) >> 6;
            int32_t o = ((rain_lp - rain_hp)*rain_level) >> 14;
            if (rain_drop > 0) { o += (int32_t)(((xorshift() >> 20) & 1023) - 512)*rain_drop >> 6; rain_drop -= 2; }
            mix_l[i] += o; mix_r[i] += (o*3) >> 2;
        }
        if ((xorshift() & 63) == 0) rain_drop = 40 + (int32_t)(xorshift() & 31);
    }
}

/* -------------------------------------------------------------- events */
enum { E_BLIP, E_KEY, E_CHIME, E_MOVE, E_THUMP, E_STING, E_BRUSH, E_RIDE };
typedef struct { uint32_t at; uint8_t kind, a; } event;
#define MAX_EVENTS 768
static event events[MAX_EVENTS];
static unsigned n_events, next_event;
static void add_event(uint32_t at, uint8_t kind, uint8_t a) {
    if (n_events < MAX_EVENTS) events[n_events++] = (event){at, kind, a};
}
/* swung brush/ride hits from the sequencer (never more than a few pending) */
static event pending[16];
static unsigned n_pending;
static void add_hit(uint32_t at, uint8_t kind, uint8_t a) {
    if (n_pending < 16) pending[n_pending++] = (event){at, kind, a};
}
static int cmp_event(const void *x, const void *y) {
    uint32_t a = ((const event *)x)->at, b = ((const event *)y)->at; return a < b ? -1 : a > b;
}
#include <stdlib.h>
static void build_script_events(void) {
    n_events = next_event = 0;
    for (unsigned d = 0; d < DIALOGUES; d++)
        for (unsigned i = 0; i < DIALOGUE_LEN[d]; i += 2) add_event(MS(DIALOGUE[d].at + i*CHAR_MS), E_BLIP, (uint8_t)(i & 7));
    for (unsigned t = 0; t < TERMINAL_LINES; t++)
        for (unsigned i = 0; i < TERMINAL_LEN[t]; i++) add_event(MS(TERMINAL[t].at + i*TERM_CHAR_MS), E_KEY, (uint8_t)i);
    add_event(MS(CHOICE_SHOW), E_CHIME, 0); add_event(MS(CHOICE_MOVE0), E_MOVE, 0); add_event(MS(CHOICE_MOVE1), E_MOVE, 1);
    add_event(MS(CHOICE_PICK), E_CHIME, 1);
    for (unsigned i = 0; i < MESSAGE_LEN; i++) add_event(MS(MESSAGE_START + i*MESSAGE_CHAR_MS), E_KEY, 200);
    for (uint32_t t = MESSAGE_START - 600; t < MESSAGE_END; t += 1150) { add_event(MS(t), E_THUMP, 0); add_event(MS(t + 230), E_THUMP, 1); }
    add_event(MS(GLITCH_START), E_STING, 0); add_event(MS(RED_EYES_ON), E_STING, 1);
    qsort(events, n_events, sizeof events[0], cmp_event);
}
static void run_event(const event *e) {
    switch (e->kind) {
    case E_BLIP: voices[V_SFX].gl = voices[V_SFX].gr = 170; note_on(V_SFX, &P_BLIP, 84 + (e->a & 3)*2, 150, 0); break;
    case E_KEY: hit_rim(e->a == 200 ? 120 : 70 + (e->a*37 & 31)); break;
    case E_CHIME: note_on(V_SFX, &P_CHIME, e->a ? 81 : 76, 200, 0); break;
    case E_MOVE: note_on(V_SFX, &P_BLIP, 79 + e->a*3, 190, 0); break;
    case E_THUMP: hit_kick(e->a ? 120 : 170, false); break;
    case E_STING:
        note_on(V_SFX, &P_STING, e->a ? 38 : 45, 230, position + MS(700));
        stutter_start = position; stutter_len = e->a ? 1600 : 2400; stutter_until = position + MS(e->a ? 300 : 500);
        break;
    default: break;
    }
}

/* ----------------------------------------------------------------- song */
enum { Gm9, C13, Fmaj9, Dm9, Bbm7, TRI1, TRI2 };
static const uint8_t VOICING[][4] = {{58, 62, 65, 69}, {58, 64, 69, 74}, {57, 60, 64, 67}, {60, 64, 65, 69},
                                     {58, 62, 64, 69}, {59, 65, 71, 77}, {58, 64, 70, 76}};
static const uint8_t ROOT[] = {43, 48, 41, 50, 46, 40, 39};
static const uint8_t WALK[4][4] = {{43, 46, 50, 53}, {48, 52, 43, 46}, {41, 45, 48, 52}, {50, 48, 45, 42}};
static const uint8_t GROOVE[4] = {Gm9, C13, Fmaj9, Dm9};
typedef struct { uint8_t bar, step, note, len; } mel;
static const mel VIB_MELODY[] = {
    {8, 0, 74, 6}, {8, 6, 77, 2}, {8, 8, 81, 8}, {9, 0, 79, 4}, {9, 4, 76, 4}, {9, 8, 74, 8},
    {10, 0, 72, 4}, {10, 4, 76, 4}, {10, 8, 79, 4}, {10, 12, 81, 4}, {11, 0, 77, 8}, {11, 8, 76, 4}, {11, 12, 74, 4},
    {12, 0, 70, 4}, {12, 4, 74, 4}, {12, 8, 77, 8}, {13, 0, 76, 6}, {13, 6, 79, 2}, {13, 8, 82, 8},
    {14, 0, 81, 12}, {14, 12, 79, 4}, {15, 0, 77, 16},
    {35, 0, 81, 8}, {35, 8, 79, 8}, {36, 0, 77, 8}, {36, 8, 76, 8}, {37, 0, 74, 16}, {38, 0, 77, 24}, {255, 0, 0, 0}};
#define SWING 2400u

static void chord(unsigned c, unsigned vel, uint32_t off_at) {
    for (unsigned i = 0; i < 4; i++) note_on(V_EP0 + i, &P_EP, VOICING[c][i], vel, off_at);
}
static void sequence(uint32_t k) {   /* k = absolute 16th step */
    uint32_t at = k*FM_STEP_FRAMES;
    unsigned bar = k/16, st = k%16;
    for (unsigned v = 0; v < VOICES; v++) if (voices[v].off_at && voices[v].off_at <= at) note_off(v);
    if (bar <= 3) {                                          /* TITLE: rain + slow chords */
        static const uint8_t INTRO[4] = {Fmaj9, Dm9, Gm9, C13};
        rain_target = 9000;
        if (st == 0) chord(INTRO[bar], bar ? 150 : 120, at + 15*FM_STEP_FRAMES);
        if (bar >= 2 && st == 0) note_on(V_BASS, &P_BASS, ROOT[INTRO[bar]], 160, at + 14*FM_STEP_FRAMES);
    } else if (bar <= 16) {                                  /* BAR: lo-fi groove */
        unsigned c = GROOVE[(bar - 4) % 4];
        rain_target = 3500;
        if (st == 0) chord(c, 175, at + 5*FM_STEP_FRAMES);
        if (st == 10) chord(c, 140, at + 3*FM_STEP_FRAMES);
        if (st % 4 == 0) note_on(V_BASS, &P_BASS, WALK[(bar - 4) % 4][st/4], st ? 200 : 225, at + 3*FM_STEP_FRAMES);
        if (st == 0 || st == 7 || (st == 10 && bar % 2)) hit_kick(st ? 150 : 185, false);
        if (st == 4 || st == 12) add_hit(at + 600, E_BRUSH, 210);
        if (st % 2 == 0) add_hit(at + (st % 4 == 2 ? SWING : 0), E_RIDE, st % 4 == 2 ? 110 : 150);
    } else if (bar <= 21) {                                  /* TERMINAL: pedal, eerie arpeggio */
        unsigned c = bar % 2 ? Bbm7 : Dm9;
        rain_target = 0;
        if (st == 0) note_on(V_BASS, &P_BASS, 38, bar >= 20 ? 190 : 150, at + 15*FM_STEP_FRAMES);
        if (st % 2 == 0) {
            unsigned v = V_EP0 + (st/2) % 4;
            note_on(v, &P_EP, VOICING[c][(st/2*3) % 4] + 12*((st/8) & 1), 120 + st*3, at + 3*FM_STEP_FRAMES);
        }
        if (bar >= 20 && st % 8 == 4) note_on(V_VIB, &P_VIB, 71 + (st == 12), 120, at + 6*FM_STEP_FRAMES);
    } else if (bar <= 27) {                                  /* ANOMALY */
        crush = true;
        if (st % 4 == 0) hit_kick(255, true);
        if (st % 8 == 4) add_hit(at, E_BRUSH, 255);
        if (st == 0 && bar == 22) { voices[V_SFX].gl = 230; voices[V_SFX].gr = 230; note_on(V_SFX, &P_SIREN, 66, 210, MS(ANOMALY_END - 600)); }
        if (st % 3 == 0) {
            unsigned c = (k/3) % 2 ? TRI1 : TRI2;
            for (unsigned i = 0; i < 4; i++) note_on(V_EP0 + i, &P_EP, VOICING[c][i] + ((xorshift() >> 30) ? 0 : 12), 200, at + FM_STEP_FRAMES);
        }
        if (st % 8 == 0) note_on(V_BASS, &P_BASS, 40 - (st == 8), 240, at + 7*FM_STEP_FRAMES);
        if ((st == 6 || st == 14) && (xorshift() & 3)) { stutter_start = at; stutter_len = (xorshift() & 1) ? 1000 : 2000; stutter_until = at + 2*FM_STEP_FRAMES; }
    } else if (bar <= 30) {                                  /* MESSAGE: near silence, drone */
        crush = false;
        if (bar == 28 && st == 0) { for (unsigned v = 0; v < VOICES; v++) note_off(v); note_on(V_BASS, &P_DRONE, 26, 200, MS(MESSAGE_END)); }
    } else if (bar <= 38) {                                  /* RESTORE */
        static const uint8_t R[4] = {Fmaj9, Dm9, Gm9, C13};
        unsigned c = bar == 38 ? Fmaj9 : R[(bar - 31) % 4];
        rain_target = bar >= 37 ? 1500 : 4000;
        if (st == 0) chord(c, bar == 38 ? 170 : 150, bar == 38 ? at + 30*FM_STEP_FRAMES : at + 15*FM_STEP_FRAMES);
        if (bar >= 35 && st == 0) note_on(V_BASS, &P_BASS, ROOT[c], 190, at + (bar == 38 ? 28 : 14)*FM_STEP_FRAMES);
        if (bar >= 35 && bar < 38) {
            if (st == 4 || st == 12) add_hit(at + 600, E_BRUSH, 150);
            if (st % 4 == 2) add_hit(at + SWING, E_RIDE, 90);
        }
    } else rain_target = 0;
    for (const mel *m = VIB_MELODY; m->bar != 255; m++)
        if (m->bar == bar && m->step == st) {
            voices[V_VIB].gl = 200; voices[V_VIB].gr = 240;
            note_on(V_VIB, &P_VIB, m->note, 210, at + m->len*FM_STEP_FRAMES);
        }
}

/* --------------------------------------------------------------- render */
void fm_init(void) {
    for (unsigned i = 0; i < 1024; i++) sine[i] = (int16_t)lrintf(32767.0f*sinf((float)i*6.28318530718f/1024.0f));
    for (unsigned n = 0; n < 128; n++) note_inc[n] = (uint32_t)(440.0*pow(2.0, ((double)n - 69.0)/12.0)*4294967296.0/FM_RATE);
    memset(voices, 0, sizeof voices);
    static const uint16_t gl[VOICES] = {225, 240, 205, 170, 140, 200, 200}, gr[VOICES] = {225, 140, 205, 240, 240, 240, 200};
    for (unsigned v = 0; v < VOICES; v++) { voices[v].gl = gl[v]; voices[v].gr = gr[v]; }
    memset(&kick, 0, sizeof kick); memset(&brush, 0, sizeof brush); memset(&ride, 0, sizeof ride); memset(&rim, 0, sizeof rim);
    memset(delay_line, 0, sizeof delay_line);
    position = delay_pos = peak = clipped = 0; rng = 0x2545f491u; pitch_q16 = 65536; crush = false;
    stutter_until = 0; n_pending = 0; rain_level = rain_target = rain_lp = rain_hp = rain_drop = 0;
    build_script_events();
}
HOT void fm_render(int8_t *left, int8_t *right, unsigned frames) {
    while (frames) {
        if (position % FM_STEP_FRAMES == 0) sequence(position/FM_STEP_FRAMES);
        while (next_event < n_events && events[next_event].at <= position) run_event(&events[next_event++]);
        for (unsigned i = 0; i < n_pending;) {
            if (pending[i].at <= position) {
                if (pending[i].kind == E_BRUSH) hit_brush(pending[i].a); else hit_ride(pending[i].a);
                pending[i] = pending[--n_pending];
            } else i++;
        }
        /* tape stop: pitch falls over 1.2 s before the anomaly, snaps back */
        uint32_t ts0 = MS(ANOMALY_START - 1300), ts1 = MS(ANOMALY_START - 100);
        if (position >= ts0 && position < ts1) pitch_q16 = 65536u - (uint32_t)(((uint64_t)(position - ts0)*52000u)/(ts1 - ts0));
        else pitch_q16 = 65536u;
        memset(mix_l, 0, sizeof mix_l); memset(mix_r, 0, sizeof mix_r); memset(mix_s, 0, sizeof mix_s);
        for (unsigned v = 0; v < VOICES; v++) render_voice(&voices[v]);
        render_drums();
        bool fade_end = position > MS(END_MS - 3000);
        int32_t base = crush ? 150 : 200;
        int32_t master = fade_end ? (int32_t)(((uint64_t)(position < MS(END_MS) ? MS(END_MS) - position : 0)*(uint32_t)base)/MS(3000)) : base;
        for (unsigned i = 0; i < BLOCK; i++) {
            int32_t d = delay_line[delay_pos], d2 = delay_line[(delay_pos + DELAY_FRAMES/2) % DELAY_FRAMES];
            int32_t w = mix_s[i] + ((d*100) >> 8);
            delay_line[delay_pos] = (int16_t)(w > 32767 ? 32767 : w < -32768 ? -32768 : w);
            if (++delay_pos == DELAY_FRAMES) delay_pos = 0;
            int32_t ch[2] = {mix_l[i] + ((d*120) >> 8), mix_r[i] + ((d2*120) >> 8)};
            uint32_t pos = position + i;
            for (unsigned c = 0; c < 2; c++) {
                int32_t x = (ch[c]*master) >> 8, a = x < 0 ? -x : x;
                if ((uint32_t)a > peak) peak = (uint32_t)a;
                if (a > 24000) { a = 24000 + ((a - 24000) >> 2); if (a > 32000) { a = 32000; clipped++; } x = x < 0 ? -a : a; }
                int32_t dither = (int32_t)(xorshift() & 255) - (int32_t)(xorshift() & 255);
                int32_t y = (x + dither + 128) >> 8;
                y = y > 127 ? 127 : y < -128 ? -128 : y;
                if (crush) y = (y >> 4) << 4;
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
