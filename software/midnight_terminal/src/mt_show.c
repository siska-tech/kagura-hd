// SPDX-License-Identifier: Apache-2.0
// MIDNIGHT TERMINAL: rainy exterior -> bar and Mio -> the old terminal ->
// the anomaly -> the warning -> the bar again. Timings come from
// generated/script.h (tools/story.py); artwork from generated/assets.c.
// Pages: title 0 / bar 1 are uploaded before the music starts; the terminal
// is decoded into page 0 during a quiet moment in the bar, the bar is
// re-decoded into page 1 while the warning holds the screen.
#include "mt_show.h"
#include "assets.h"
#include "script.h"
#include "mt_inflate.h"
#include "../../fm_megademo/src/font.h"
#include <stdbool.h>
#include <string.h>

#define W 640
#define TERM_X ((SCREEN_X0 + 18) & ~1)
#define H 360
#define PAGE_BYTES 115200u
#define TRY(x) do { int rc_ = (x); if (rc_) return rc_; } while (0)

static kfb_device *gpu;
static int (*service)(void);
static show_stats st;
static uint16_t pal_want[16], pal_sent[16];
static bool pal_valid[16];
static unsigned displayed;
static uint32_t seed = 0x9e3779b9u;
static uint32_t rnd(void) { seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5; return seed; }

/* ------------------------------------------------------------ GPU calls */
static int svc(void) { st.commands++; return service ? service() : 0; }
static int g_fill(unsigned p, int x, int y, int w, int h, unsigned c) {
    if (w <= 0 || h <= 0) return 0;
    TRY(svc()); st.fills++; return kfb_fill_rect(gpu, p, x, y, w, h, c);
}
static int g_copy(unsigned sp, int sx, int sy, unsigned dp, int dx, int dy, int w, int h) {
    TRY(svc()); st.copies++; return kfb_copy_rect(gpu, sp, sx, sy, dp, dx, dy, w, h);
}
static int g_write(uint32_t a, const uint8_t *d, size_t n) { TRY(svc()); st.writes++; return kfb_write_bytes(gpu, a, d, n); }
static int pal_commit(void) {
    for (unsigned i = 0; i < 16; i++) if (!pal_valid[i] || pal_sent[i] != pal_want[i]) {
        TRY(svc()); st.palettes++;
        TRY(kfb_palette(gpu, i, pal_want[i])); pal_sent[i] = pal_want[i]; pal_valid[i] = true;
    }
    return 0;
}
static int present(unsigned p) { TRY(pal_commit()); TRY(svc()); st.presents++; TRY(kfb_present(gpu, p)); displayed = p; return 0; }

/* ---------------------------------------------------------------- colour */
static uint16_t lerp(unsigned a, unsigned b, unsigned t) {
    unsigned r = 0;
    for (unsigned s = 0; s < 12; s += 4) {
        int ca = (int)(a >> s & 15), cb = (int)(b >> s & 15);
        r |= (unsigned)(ca + ((cb - ca)*(int)t + 128)/256) << s;
    }
    return (uint16_t)r;
}
static void set_pal(const uint16_t *base, unsigned fade) { for (unsigned i = 0; i < 16; i++) pal_want[i] = lerp(0, base[i], fade); }
static unsigned ramp_in(uint32_t t, uint32_t t0, uint32_t len) { return t <= t0 ? 0 : t >= t0 + len ? 256 : (t - t0)*256/len; }
static unsigned ramp_out(uint32_t t, uint32_t t1, uint32_t len) { return t >= t1 ? 0 : t + len <= t1 ? 256 : (t1 - t)*256/len; }
static const uint16_t PAL_MESSAGE[16] = {0x000, 0x200, 0x300, 0x500, 0, 0, 0, 0xfdd, 0, 0, 0, 0, 0, 0, 0xc23, 0xfff};
static const uint16_t PAL_END[16] = {0x000, 0x102, 0x213, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x8ac, 0xe38, 0xeef};

/* ------------------------------------------------------- artwork decode */
typedef struct { uint32_t base, off; int bx0, bx1, y0, y1; uint8_t row[320]; } upload_ctx;
static upload_ctx up;
static int sink_page(void *c, const uint8_t *d, uint32_t n) {
    upload_ctx *u = c; TRY(g_write(u->base + u->off, d, n)); u->off += n; return 0;
}
static int sink_rect(void *c, const uint8_t *d, uint32_t n) {
    upload_ctx *u = c;
    if (service) TRY(service());          /* decoding outside the rectangle writes nothing: keep the stream fed */
    if (u->off >= (uint32_t)u->y1*320u) return 1;   /* rectangle done: stop decoding */
    for (uint32_t k = 0; k < n; k++, u->off++) {
        int y = (int)(u->off/320), bx = (int)(u->off%320);
        if (y < u->y0 || y >= u->y1 || bx < u->bx0 || bx >= u->bx1) continue;
        u->row[bx - u->bx0] = d[k];
        if (bx == u->bx1 - 1) TRY(g_write(u->base + (uint32_t)y*320u + (uint32_t)u->bx0, u->row, (size_t)(u->bx1 - u->bx0)));
    }
    return 0;
}
static int upload(const uint8_t *img, uint32_t n, unsigned page) {
    up.base = page*PAGE_BYTES; up.off = 0; st.uploads++;
    return mt_inflate(img, n, PAGE_BYTES, sink_page, &up);
}
static int restore_rect(const uint8_t *img, uint32_t n, unsigned page, int x0, int y0, int x1, int y1) {
    up.base = page*PAGE_BYTES; up.off = 0; up.bx0 = x0/2; up.bx1 = x1/2; up.y0 = y0; up.y1 = y1;
    int rc = mt_inflate(img, n, PAGE_BYTES, sink_rect, &up);
    return rc == 1 ? 0 : rc;
}
static int eye_patch(unsigned page, const uint8_t *patch) {
    for (int r = 0; r < EYE_H; r++)
        TRY(g_write(page*PAGE_BYTES + (uint32_t)(EYE_Y + r)*320u + EYE_X/2, patch + r*(EYE_W/2), EYE_W/2));
    return 0;
}

/* ------------------------------------------------------------------ text */
enum { F_MPLUS, F_MISAKI };
static unsigned g_adv(int font, uint16_t g) { return font == F_MPLUS ? mplus_adv[g] : misaki_adv[g]; }
static unsigned g_h(int font) { return font == F_MPLUS ? MPLUS_H : MISAKI_H; }
static uint16_t g_row(int font, uint16_t g, unsigned r) { return font == F_MPLUS ? mplus_rows[g*MPLUS_H + r] : misaki_rows[g*MISAKI_H + r]; }
static unsigned text_len(uint16_t id) { return text_offset[id + 1] - text_offset[id]; }
static unsigned text_width(int font, uint16_t id, unsigned scale) {
    unsigned w = 0;
    for (unsigned i = 0; i < text_len(id); i++) w += g_adv(font, text_glyphs[text_offset[id] + i]);
    return w*scale;
}
/* Draw glyphs [from, to) of a string at pixel x (even) with fg on bg. Each
 * scanline of the run is one WRITE (the SDK splits it into 64-byte pieces). */
static int draw_text(unsigned page, int x, int y, int font, uint16_t id, unsigned from, unsigned to,
                     unsigned fg, unsigned bg, unsigned scale) {
    static uint8_t line[320];
    const uint16_t *gl = text_glyphs + text_offset[id];
    int x0 = x;
    for (unsigned i = 0; i < from; i++) x0 += (int)(g_adv(font, gl[i])*scale);
    unsigned width = 0;
    for (unsigned i = from; i < to; i++) width += g_adv(font, gl[i])*scale;
    if (!width) return 0;
    if (x0 + (int)width > W) width = (unsigned)(W - x0);
    for (unsigned r = 0; r < g_h(font)*scale; r++) {
        unsigned px = 0;
        memset(line, (int)(bg*17u), width/2);
        for (unsigned i = from; i < to && px < width; i++) {
            unsigned adv = g_adv(font, gl[i]); uint16_t bits = g_row(font, gl[i], r/scale);
            for (unsigned c = 0; c < adv*scale && px < width; c++, px++)
                if (bits >> (adv - 1 - c/scale) & 1) {
                    uint8_t *b = &line[px/2];
                    *b = (uint8_t)(px & 1 ? (*b & 0xf0) | fg : (*b & 0x0f) | (fg << 4));
                }
        }
        TRY(g_write(page*PAGE_BYTES + (uint32_t)(y + (int)r)*320u + (uint32_t)x0/2, line, width/2));
    }
    return 0;
}
static int big_text(unsigned page, int x, int y, const char *s, unsigned scale, unsigned color) {
    for (; *s; s++, x += (int)(6*scale)) {
        const uint8_t *g = font_glyph(*s);
        for (unsigned r = 0; r < FONT_H; r++)
            for (int c = 0; c < FONT_W;) {
                if (!(g[r] >> (4 - c) & 1)) { c++; continue; }
                int e = c; while (e < FONT_W && (g[r] >> (4 - e) & 1)) e++;
                TRY(g_fill(page, x + c*(int)scale, y + (int)(r*scale), (e - c)*(int)scale, (int)scale, color));
                c = e;
            }
    }
    return 0;
}
static int big_text_c(unsigned page, int y, const char *s, unsigned scale, unsigned color) {
    return big_text(page, ((W - (int)font_width(s, scale))/2) & ~1, y, s, scale, color);
}

/* ------------------------------------------------------- dialogue window */
#define BOX_X0 16
#define BOX_Y0 280
#define BOX_X1 624
#define BOX_Y1 352
#define TEXT_X 36
#define TEXT_Y 304
static int dialogue_box(unsigned page) {
    TRY(g_fill(page, BOX_X0, BOX_Y0, BOX_X1 - BOX_X0, BOX_Y1 - BOX_Y0, 1));
    TRY(g_fill(page, BOX_X0, BOX_Y0, BOX_X1 - BOX_X0, 2, 6));
    TRY(g_fill(page, BOX_X0, BOX_Y1 - 2, BOX_X1 - BOX_X0, 2, 6));
    TRY(g_fill(page, BOX_X0, BOX_Y0, 2, BOX_Y1 - BOX_Y0, 6));
    TRY(g_fill(page, BOX_X1 - 2, BOX_Y0, 2, BOX_Y1 - BOX_Y0, 6));
    TRY(g_fill(page, 28, 270, 72, 22, 14));
    return draw_text(page, 40 + (48 - (int)text_width(F_MPLUS, TXT_SPEAKER, 1))/2, 275, F_MPLUS, TXT_SPEAKER, 0, text_len(TXT_SPEAKER), 7, 14, 1);
}
typedef struct { int line; unsigned drawn; bool marker; } typer;
static typer dlg;
static int dialogue(unsigned page, uint32_t ms, int first, int last) {
    int cur = -1;
    for (int i = first; i <= last; i++) if (ms >= DIALOGUE[i].at) cur = i;
    if (cur < 0) return 0;
    uint16_t id = DIALOGUE[cur].text;
    if (cur != dlg.line) {
        TRY(g_fill(page, TEXT_X - 4, TEXT_Y - 4, BOX_X1 - 8 - (TEXT_X - 4), 22, 1));
        dlg.line = cur; dlg.drawn = 0; dlg.marker = false;
    }
    unsigned due = (ms - DIALOGUE[cur].at)/CHAR_MS + 1, n = text_len(id);
    if (due > n) due = n;
    if (due > dlg.drawn) { TRY(draw_text(page, TEXT_X, TEXT_Y, F_MPLUS, id, dlg.drawn, due, 7, 1, 1)); dlg.drawn = due; }
    bool marker = dlg.drawn == n && (ms/400) % 2;
    if (marker != dlg.marker) {
        for (int r = 0; r < 6; r++) TRY(g_fill(page, 598 + r, 334 + r, 12 - 2*r, 1, marker ? 6 : 1));
        dlg.marker = marker;
    }
    return 0;
}

/* --------------------------------------------------------------- blinking */
static int eyes_state;            /* 0 open, 1 closed, 2 red */
static int eyes(unsigned page, uint32_t ms, bool allow_red) {
    int want = (ms % 3700) < 140 ? 1 : 0;
    if (allow_red && ms >= RED_EYES_ON && ms < RED_EYES_OFF) want = 2;
    if (want == eyes_state) return 0;
    eyes_state = want;
    return eye_patch(page, want == 1 ? eye_closed : want == 2 ? eye_red : eye_open);
}

/* ------------------------------------------------------------------ scenes */
static bool terminal_ready, bar_ready, title_text, choice_open, choice_closed;
static unsigned subtitle_drawn, choice_sel, term_drawn[8], log_written;
static int term_cursor_x, term_cursor_y;
static bool term_cursor_on;

static int title_frame(uint32_t t) {
    unsigned fade = t < 10000 ? ramp_in(t, 0, 1500) : ramp_out(t, 11000, 1000);
    uint16_t base[16]; memcpy(base, pal_title, sizeof base);
    unsigned k = t/85;
    base[12 + k % 3] = 0x9bd; base[12 + (k + 2) % 3] = 0x46a; base[12 + (k + 1) % 3] = 0x213;
    base[15] = lerp(0x000, 0xfff, ramp_in(t, 3000, 1200));
    set_pal(base, fade);
    if (t >= 3000 && !title_text) {
        TRY(big_text_c(0, 14 + 4, TITLE_TEXT, 4, 0));
        TRY(big_text_c(0, 14, TITLE_TEXT, 4, 15));
        title_text = true;
    }
    if (t >= 5500) {
        unsigned n = text_len(TXT_SUBTITLE), due = (t - 5500)/90 + 1;
        if (due > n) due = n;
        int x = ((W - (int)text_width(F_MPLUS, TXT_SUBTITLE, 1))/2) & ~1;
        if (due > subtitle_drawn) { TRY(draw_text(0, x, 318, F_MPLUS, TXT_SUBTITLE, subtitle_drawn, due, 15, 1, 1)); subtitle_drawn = due; }
    }
    return present(0);
}

#define CH_X0 396
#define CH_Y0 120
#define CH_X1 616
#define CH_Y1 230
static int choice_item(unsigned i, bool sel) {
    int y = CH_Y0 + 16 + (int)i*32;
    TRY(g_fill(1, CH_X0 + 6, y - 6, CH_X1 - CH_X0 - 12, 24, sel ? 5 : 1));
    if (sel) for (int r = 0; r < 5; r++) TRY(g_fill(1, CH_X0 + 12 + r, y + 1 + r, 1, 10 - 2*r, 14));
    return draw_text(1, CH_X0 + 30, y, F_MPLUS, CHOICE_TEXT[i], 0, text_len(CHOICE_TEXT[i]), 7, sel ? 5 : 1, 1);
}
static int bar_frame(uint32_t ms) {
    unsigned fade = ms < 44000 ? ramp_in(ms, AT_BAR, 1000) : ramp_out(ms, AT_TERMINAL, 600);
    set_pal(pal_bar, fade);
    if (ms >= CHOICE_PICK && ms < CHOICE_PICK + 120) pal_want[5] = 0xfff;
    TRY(eyes(1, ms, false));
    TRY(dialogue(1, ms, 0, 3));
    if (ms >= CHOICE_SHOW && !choice_open) {
        TRY(g_fill(1, CH_X0, CH_Y0, CH_X1 - CH_X0, CH_Y1 - CH_Y0, 1));
        TRY(g_fill(1, CH_X0, CH_Y0, CH_X1 - CH_X0, 2, 6)); TRY(g_fill(1, CH_X0, CH_Y1 - 2, CH_X1 - CH_X0, 2, 6));
        TRY(g_fill(1, CH_X0, CH_Y0, 2, CH_Y1 - CH_Y0, 6)); TRY(g_fill(1, CH_X1 - 2, CH_Y0, 2, CH_Y1 - CH_Y0, 6));
        for (unsigned i = 0; i < 3; i++) TRY(choice_item(i, i == 0));
        choice_open = true; choice_sel = 0;
    }
    if (choice_open && !choice_closed) {
        unsigned sel = ms >= CHOICE_MOVE1 ? 2 : ms >= CHOICE_MOVE0 ? 1 : 0;
        if (sel != choice_sel) { TRY(choice_item(choice_sel, false)); TRY(choice_item(sel, true)); choice_sel = sel; }
        if (ms >= CHOICE_PICK + 600) {
            TRY(restore_rect(img_bar, sizeof img_bar, 1, CH_X0, CH_Y0, CH_X1, CH_Y1));
            choice_closed = true;
        }
    }
    TRY(present(1));
    if (ms >= 29000 && !terminal_ready) { TRY(upload(img_terminal, sizeof img_terminal, 0)); terminal_ready = true; }
    return 0;
}
static int terminal_frame(uint32_t ms) {
    set_pal(pal_terminal, ms < AT_TERMINAL + 600 ? ramp_in(ms, AT_TERMINAL, 600) : 256);
    for (unsigned l = 0; l < TERMINAL_LINES; l++) {
        if (ms < TERMINAL[l].at) break;
        unsigned n = text_len(TERMINAL[l].text), due = (ms - TERMINAL[l].at)/TERM_CHAR_MS + 1;
        if (due > n) due = n;
        if (due > term_drawn[l]) {
            int y = 70 + (int)l*22;
            if (term_cursor_on) { TRY(g_fill(0, term_cursor_x, term_cursor_y, 8, 13, 13)); term_cursor_on = false; }
            TRY(draw_text(0, TERM_X, y, F_MPLUS, TERMINAL[l].text, term_drawn[l], due, 14, 13, 1));
            term_drawn[l] = due;
            term_cursor_x = TERM_X + (int)text_width(F_MPLUS, TERMINAL[l].text, 1)*(int)due/(int)n;
            term_cursor_x &= ~1; term_cursor_y = y;
        }
    }
    bool on = (ms/350) % 2;
    if (on != term_cursor_on && term_cursor_y) { TRY(g_fill(0, term_cursor_x, term_cursor_y, 8, 13, on ? 14 : 13)); term_cursor_on = on; }
    if (ms >= GLITCH_START) {              /* tearing, colour faults, darkening into the tape stop */
        unsigned level = (ms - GLITCH_START)*256/(AT_ANOMALY - GLITCH_START);
        for (unsigned i = 0; i < 1 + level/64; i++) {
            int y = SCREEN_Y0 + (int)(rnd() % (SCREEN_Y1 - SCREEN_Y0 - 12)), h = 2 + (int)(rnd() % 10), d = ((int)(rnd() % 5) - 2)*8;
            if (d) TRY(g_copy(0, SCREEN_X0 + (d < 0 ? -d : 0), y, 0, SCREEN_X0 + (d > 0 ? d : 0), y, SCREEN_X1 - SCREEN_X0 - (d < 0 ? -d : d), h));
        }
        if (rnd() % 4 == 0) TRY(g_fill(0, (SCREEN_X0 + (int)(rnd() % (SCREEN_X1 - SCREEN_X0 - 24))) & ~1, SCREEN_Y0 + (int)(rnd() % (SCREEN_Y1 - SCREEN_Y0 - 8)), (4 + (int)(rnd() % 20)) & ~1, 2 + (int)(rnd() % 6), 11));
        if (rnd() % 3 == 0) { pal_want[14] = 0xe38; pal_want[13] = 0x201; }
        for (unsigned i = 0; i < 16; i++) pal_want[i] = lerp(pal_want[i], 0, level*3/4);
    }
    return present(0);
}
static int anomaly_frame(uint32_t ms) {
    uint32_t t = ms - AT_ANOMALY;
    set_pal(pal_bar_red, ms >= ANOMALY_END - 500 ? ramp_out(ms, ANOMALY_END, 500) : 256);
    if ((rnd() & 7) == 0) for (unsigned i = 0; i < 16; i++) pal_want[i] = (uint16_t)(0xfff - pal_want[i]);
    /* lines written so far: 6/s rising by 2.4/s per second, capped at 32/s */
    uint32_t ts = t/100;                                   /* tenths of a second */
    uint32_t due = ts < 110 ? (6*ts + ts*ts*12/100)/10 : 211 + (ts - 110)*32/10;
    unsigned budget = 6;
    while (log_written < due && budget--) {
        unsigned i = log_written++, row = i % 45;
        uint16_t a = LOG_TEXT[(i*7) % LOG_LINES], b = LOG_TEXT[(i*11 + 3) % LOG_LINES];
        int x = (int)((i*37) % 13)*16, y = (int)row*8;
        unsigned wa = text_width(F_MISAKI, a, 1), wb = text_width(F_MISAKI, b, 1);
        int xb = (x + (int)wa + 24 + (int)((i*53) % 7)*16) & ~1;
        TRY(g_fill(1, 0, y, x, 8, 0));
        TRY(draw_text(1, x, y, F_MISAKI, a, 0, text_len(a), (i % 5 == 0) ? 14 : 7, 0, 1));
        TRY(g_fill(1, x + (int)wa, y, xb - x - (int)wa, 8, 0));
        if (xb + (int)wb <= W) {
            TRY(draw_text(1, xb, y, F_MISAKI, b, 0, text_len(b), (i % 3 == 0) ? 14 : 7, 0, 1));
            TRY(g_fill(1, xb + (int)wb, y, W - xb - (int)wb, 8, 0));
        } else TRY(g_fill(1, xb, y, W - xb, 8, 0));
    }
    unsigned slices = ms >= ANOMALY_FULL ? 3 : 1;
    for (unsigned i = 0; i < slices; i++) {
        int h = 2 + (int)(rnd() % 12), y = (int)(rnd() % (unsigned)(H - h)), d = ((int)(rnd() % 9) - 4)*8;   /* y + h <= H */
        if (d) TRY(g_copy(1, d < 0 ? -d : 0, y, 1, d > 0 ? d : 0, y, W - (d < 0 ? -d : d), h));
    }
    return present(1);
}
static int message_frame(uint32_t ms) {
    unsigned heart = (ms - MESSAGE_START + 600) % 1150;
    uint16_t base[16]; memcpy(base, PAL_MESSAGE, sizeof base);
    base[7] = lerp(0xc66, 0xfdd, heart < 300 ? 256 - heart*256/300 : 0);
    set_pal(base, ramp_out(ms, MESSAGE_END, 600));
    if (ms >= MESSAGE_START) {
        static unsigned drawn;
        unsigned n = text_len(TXT_MESSAGE), due = (ms - MESSAGE_START)/MESSAGE_CHAR_MS + 1;
        if (due > n) due = n;
        int x = ((W - (int)text_width(F_MPLUS, TXT_MESSAGE, 2))/2) & ~1;
        if (due > drawn) { TRY(draw_text(0, x, 166, F_MPLUS, TXT_MESSAGE, drawn, due, 7, 0, 2)); drawn = due; }
    }
    TRY(present(0));
    if (ms >= 79000 && !bar_ready) { TRY(upload(img_bar, sizeof img_bar, 1)); TRY(dialogue_box(1)); bar_ready = true; }
    return 0;
}
static int restore_frame(uint32_t ms) {
    unsigned fade = ms < 95000 ? ramp_in(ms, AT_RESTORE, 1000) : ramp_out(ms, AT_END, 700);
    set_pal(ms >= RED_EYES_ON && ms < RED_EYES_OFF ? pal_bar_red : pal_bar, fade);
    TRY(eyes(1, ms, true));
    TRY(dialogue(1, ms, 4, 5));
    return present(1);
}
static int end_frame(uint32_t ms) {
    set_pal(PAL_END, ms < END_MS - 2500 ? ramp_in(ms, AT_END, 1000) : ramp_out(ms, END_MS, 2500));
    return present(0);
}

/* ---------------------------------------------------------------- enter */
static int enter(int scene) {
    switch (scene) {
    case 1: return dialogue_box(1);                                  /* bar: page 1 hidden until now */
    case 2: if (!terminal_ready) { TRY(upload(img_terminal, sizeof img_terminal, 0)); terminal_ready = true; } return 0;
    case 3: return 0;
    case 4: TRY(g_fill(0, 0, 0, W, H, 0)); return 0;                 /* page 0 hidden (bar red on 1) */
    case 5: if (!bar_ready) { TRY(upload(img_bar, sizeof img_bar, 1)); TRY(dialogue_box(1)); bar_ready = true; }
            dlg.line = -1; eyes_state = 0; return 0;
    case 6:
        TRY(g_fill(0, 0, 0, W, H, 0));
        TRY(big_text_c(0, 120, END_LINES[0], 5, 15));
        TRY(big_text_c(0, 196, END_LINES[1], 2, 13));
        return big_text_c(0, 222, END_LINES[2], 2, 14);
    default: return 0;
    }
}
static const uint32_t AT[7] = {AT_TITLE, AT_BAR, AT_TERMINAL, AT_ANOMALY, AT_MESSAGE, AT_RESTORE, AT_END};
static int entered;

int show_init(kfb_device *device, int (*service_fn)(void)) {
    gpu = device; service = service_fn;
    memset(&st, 0, sizeof st); memset(pal_valid, 0, sizeof pal_valid); memset(pal_want, 0, sizeof pal_want);
    font_init();
    entered = 0; dlg.line = -1; eyes_state = 0; displayed = 0;
    terminal_ready = bar_ready = title_text = choice_open = choice_closed = false;
    subtitle_drawn = choice_sel = log_written = 0; memset(term_drawn, 0, sizeof term_drawn);
    term_cursor_x = term_cursor_y = 0; term_cursor_on = false;
    TRY(present(0));                                                  /* black palette */
    TRY(upload(img_title, sizeof img_title, 0));
    TRY(upload(img_bar, sizeof img_bar, 1));
    return 0;
}
int show_frame(uint32_t ms) {
    if (ms >= END_MS) ms = END_MS - 1;
    int scene = 0;
    while (scene < 6 && ms >= AT[scene + 1]) scene++;
    while (entered < scene) { entered++; TRY(enter(entered)); }
    st.scene = (uint8_t)scene; st.frames++; st.scene_frames[scene]++;
    switch (scene) {
    case 0: return title_frame(ms);
    case 1: return bar_frame(ms);
    case 2: return terminal_frame(ms);
    case 3: return anomaly_frame(ms);
    case 4: return message_frame(ms);
    case 5: return restore_frame(ms);
    default: return end_frame(ms);
    }
}
const show_stats *show_statistics(void) { return &st; }
