// SPDX-License-Identifier: Apache-2.0
// Minimal raw-DEFLATE decoder (RFC 1951) for the packed 4bpp artwork.
// 4 KiB window (images are compressed with wbits=-12), output in 64-byte
// pieces to a sink. Canonical Huffman decoding as described in the RFC.
#include "mt_inflate.h"
#include <string.h>

#define WSIZE 4096u
typedef struct { uint16_t count[16]; uint16_t symbol[288]; } huff;
typedef struct {
    const uint8_t *src; uint32_t n, pos; uint32_t bitbuf; unsigned bitcnt;
    uint8_t window[WSIZE]; uint32_t out, expected; uint8_t chunk[64]; unsigned fill;
    mt_sink sink; void *ctx;
} state;
static state S;

static int bits(state *s, unsigned need, unsigned *v) {
    while (s->bitcnt < need) {
        if (s->pos >= s->n) return -1;
        s->bitbuf |= (uint32_t)s->src[s->pos++] << s->bitcnt; s->bitcnt += 8;
    }
    *v = s->bitbuf & ((1u << need) - 1u); s->bitbuf >>= need; s->bitcnt -= need;
    return 0;
}
static int emit(state *s, uint8_t b) {
    if (s->out >= s->expected) return -2;
    s->window[s->out & (WSIZE-1)] = b; s->out++;
    s->chunk[s->fill++] = b;
    if (s->fill == 64) { s->fill = 0; return s->sink(s->ctx, s->chunk, 64); }
    return 0;
}
static int build(huff *h, const uint8_t *len, unsigned n) {
    uint16_t offs[16];
    memset(h->count, 0, sizeof h->count);
    for (unsigned i = 0; i < n; i++) h->count[len[i]]++;
    h->count[0] = 0;
    offs[1] = 0;
    for (unsigned i = 1; i < 15; i++) offs[i+1] = (uint16_t)(offs[i] + h->count[i]);
    for (unsigned i = 0; i < n; i++) if (len[i]) h->symbol[offs[len[i]]++] = (uint16_t)i;
    return 0;
}
static int decode(state *s, const huff *h) {
    int code = 0, first = 0, index = 0;
    for (unsigned len = 1; len < 16; len++) {
        unsigned b; if (bits(s, 1, &b)) return -1;
        code |= (int)b;
        int count = h->count[len];
        if (code - count < first) return h->symbol[index + (code - first)];
        index += count; first += count; first <<= 1; code <<= 1;
    }
    return -3;
}
static const uint16_t LBASE[29] = {3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,67,83,99,115,131,163,195,227,258};
static const uint8_t LEXT[29] = {0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,0};
static const uint16_t DBASE[30] = {1,2,3,4,5,7,9,13,17,25,33,49,65,97,129,193,257,385,513,769,1025,1537,2049,3073,4097,6145,8193,12289,16385,24577};
static const uint8_t DEXT[30] = {0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11,12,12,13,13};

static int codes(state *s, const huff *lit, const huff *dist) {
    for (;;) {
        int sym = decode(s, lit); if (sym < 0) return sym;
        if (sym < 256) { int r = emit(s, (uint8_t)sym); if (r) return r; continue; }
        if (sym == 256) return 0;
        sym -= 257; if (sym >= 29) return -4;
        unsigned e, len, d; if (bits(s, LEXT[sym], &e)) return -1; len = LBASE[sym] + e;
        int ds = decode(s, dist); if (ds < 0 || ds >= 30) return -5;
        if (bits(s, DEXT[ds], &e)) return -1;
        d = DBASE[ds] + e;
        if (d > s->out || d > WSIZE) return -6;
        while (len--) { int r = emit(s, s->window[(s->out - d) & (WSIZE-1)]); if (r) return r; }
    }
}
static int fixed(state *s) {
    static huff lit, dist; static int ready;
    if (!ready) {
        uint8_t l[288];
        for (unsigned i = 0; i < 144; i++) l[i] = 8;
        for (unsigned i = 144; i < 256; i++) l[i] = 9;
        for (unsigned i = 256; i < 280; i++) l[i] = 7;
        for (unsigned i = 280; i < 288; i++) l[i] = 8;
        build(&lit, l, 288);
        for (unsigned i = 0; i < 30; i++) l[i] = 5;
        build(&dist, l, 30); ready = 1;
    }
    return codes(s, &lit, &dist);
}
static int dynamic(state *s) {
    static const uint8_t ORDER[19] = {16,17,18,0,8,7,9,6,10,5,11,4,12,3,13,2,14,1,15};
    static huff lit, dist, lc; uint8_t lengths[320];
    unsigned nlen, ndist, ncode, v;
    if (bits(s, 5, &nlen) || bits(s, 5, &ndist) || bits(s, 4, &ncode)) return -1;
    nlen += 257; ndist += 1; ncode += 4;
    if (nlen > 286 || ndist > 30) return -7;
    memset(lengths, 0, 19);
    for (unsigned i = 0; i < ncode; i++) { if (bits(s, 3, &v)) return -1; lengths[ORDER[i]] = (uint8_t)v; }
    build(&lc, lengths, 19);
    for (unsigned i = 0; i < nlen + ndist;) {
        int sym = decode(s, &lc); if (sym < 0) return sym;
        if (sym < 16) { lengths[i++] = (uint8_t)sym; continue; }
        unsigned rep, val = 0;
        if (sym == 16) { if (!i) return -8; val = lengths[i-1]; if (bits(s, 2, &rep)) return -1; rep += 3; }
        else if (sym == 17) { if (bits(s, 3, &rep)) return -1; rep += 3; }
        else { if (bits(s, 7, &rep)) return -1; rep += 11; }
        if (i + rep > nlen + ndist) return -9;
        while (rep--) lengths[i++] = (uint8_t)val;
    }
    build(&lit, lengths, nlen); build(&dist, lengths + nlen, ndist);
    return codes(s, &lit, &dist);
}
int mt_inflate(const uint8_t *src, uint32_t n, uint32_t expected, mt_sink sink, void *ctx) {
    state *s = &S;
    s->src = src; s->n = n; s->pos = 0; s->bitbuf = 0; s->bitcnt = 0;
    s->out = 0; s->expected = expected; s->fill = 0; s->sink = sink; s->ctx = ctx;
    unsigned last, type;
    do {
        if (bits(s, 1, &last) || bits(s, 2, &type)) return -1;
        int r;
        if (type == 0) {
            s->bitbuf = 0; s->bitcnt = 0;
            if (s->pos + 4 > n) return -1;
            unsigned len = s->src[s->pos] | (unsigned)s->src[s->pos+1] << 8; s->pos += 4;
            if (s->pos + len > n) return -1;
            r = 0; while (len-- && !r) r = emit(s, s->src[s->pos++]);
        } else if (type == 1) r = fixed(s);
        else if (type == 2) r = dynamic(s);
        else return -10;
        if (r) return r;
    } while (!last);
    if (s->out != expected) return -11;
    return s->fill ? sink(ctx, s->chunk, s->fill) : 0;
}
