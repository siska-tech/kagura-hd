// SPDX-License-Identifier: Apache-2.0
// FOUR OPERATORS: eight 16 s scenes on the KAGURA-HD 640x360x16 framebuffer.
//   0 INTRO     copper stripes, title letters on the beat      (page 0)
//   1 PLASMA    palette-cycled plasma                          (page 1)
//   2 TUNNEL    palette-cycled tunnel                          (page 0)
//   3 SCROLLER  in-place 8 px BLIT scroller, copper, voice VU  (page 1)
//   4 VECTOR    flat-shaded icosahedron + starfield            (pages 0/1)
//   5 SCOPE     live oscilloscope and operator envelopes       (scope page)
//   6 MOIRE     palette-cycled interference rings              (other page)
//   7 FINALE    credits and fade, 20 s                         (scope page)
// Static palette-cycled images are uploaded in 64-byte WRITEs to the hidden
// page while the previous scene plays.
#include "demo.h"
#include "font.h"
#include <stdbool.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>

#define W 640
#define H 360
#define PAGE_BYTES 115200u
#define TRY(x) do { int rc_=(x); if (rc_) return rc_; } while (0)

static kfb_device *gpu;
static const demo_platform *plat;
static demo_stats stats;
static int16_t vs[1024];                 /* Q14 sine */
static uint16_t pal_want[16], pal_sent[16];
static bool pal_valid[16];
static int entered=-1;
static unsigned displayed;

/* ------------------------------------------------------------- GPU calls */
static int svc(void) { stats.commands++; return plat->service ? plat->service() : 0; }
static int g_fill(unsigned page, int x, int y, int w, int h, unsigned c) {
    if (w<=0 || h<=0) return 0;
    TRY(svc()); stats.fills++;
    return kfb_fill_rect(gpu,page,x,y,w,h,c);
}
static int g_copy(unsigned sp, int sx, int sy, unsigned dp, int dx, int dy, int w, int h) {
    TRY(svc()); stats.copies++;
    return kfb_copy_rect(gpu,sp,sx,sy,dp,dx,dy,w,h);
}
static int g_write(uint32_t address, const uint8_t *data, size_t size) {
    TRY(svc()); stats.writes++;
    return kfb_write_bytes(gpu,address,data,size);
}
static int pal_commit(void) {
    for (unsigned i=0;i<16;i++) if (!pal_valid[i] || pal_sent[i]!=pal_want[i]) {
        TRY(svc()); stats.palettes++;
        TRY(kfb_palette(gpu,i,pal_want[i]));
        pal_sent[i]=pal_want[i]; pal_valid[i]=true;
    }
    return 0;
}
static int show(unsigned page) {
    TRY(pal_commit());
    TRY(svc()); stats.presents++;
    TRY(kfb_present(gpu,page));
    displayed=page;
    return 0;
}

/* ---------------------------------------------------------------- colour */
static unsigned lerp(unsigned a, unsigned b, unsigned t) {      /* t 0..256 */
    unsigned r=0;
    for (unsigned s=0;s<12;s+=4) {
        int ca=(int)(a>>s&15), cb=(int)(b>>s&15);
        r|=(unsigned)(ca+((cb-ca)*(int)t+128)/256)<<s;
    }
    return r;
}
// Cyclic gradient over n keys; pos is 0..65535 around the cycle.
static unsigned ramp(const uint16_t *k, unsigned n, uint32_t pos) {
    uint32_t p=(pos&0xffffu)*n;
    unsigned i=p>>16, t=(p>>8)&255;
    return lerp(k[i],k[(i+1)%n],t);
}
static unsigned flash_of(const fm_snapshot *s) {
    unsigned k=s->drum[D_KICK];
    return k>190 ? (k-190)*2 : 0;
}
static const uint16_t K_PLASMA[]={0x102,0x52a,0xb3d,0xf6a,0xfc5,0x8e8,0x2ac};
static const uint16_t K_TUNNEL[]={0x014,0x13a,0x37f,0x8df,0xfff,0x8df,0x37f,0x13a};
static const uint16_t K_RAINBOW[]={0xf22,0xf92,0xee2,0x3e4,0x2bf,0x55f,0xc4f};
static const uint16_t K_COPPER[]={0x003,0x03b,0x3af,0xeff,0xfb4,0xc40,0x401};
static const uint16_t K_SHADE[]={0x103,0x326,0x63a,0x96c,0x4af,0x8df,0xeff};

/* ------------------------------------------------------------------ text */
static int text(unsigned page, int x, int y, const char *s, unsigned scale, unsigned color) {
    for (;*s;s++,x+=(int)(6*scale)) {
        const uint8_t *g=font_glyph(*s);
        for (unsigned r=0;r<FONT_H;r++)
            for (int c=0;c<FONT_W;) {
                if (!(g[r]>>(4-c)&1)) { c++; continue; }
                int e=c; while (e<FONT_W && (g[r]>>(4-e)&1)) e++;
                TRY(g_fill(page,x+c*(int)scale,y+(int)(r*scale),(e-c)*(int)scale,(int)scale,color));
                c=e;
            }
    }
    return 0;
}
static int text_c(unsigned page, int y, const char *s, unsigned scale, unsigned color) {
    return text(page,(W-(int)font_width(s,scale))/2,y,s,scale,color);
}
static int caption(unsigned page, const char *s) {
    int w=(int)font_width(s,2);
    TRY(g_fill(page,14,326,w+20,26,0));
    return text(page,24,332,s,2,15);
}

/* ---------------------------------------------------------- integer math */
static uint32_t isqrt(uint32_t v) {
    uint32_t r=0,b=1u<<30;
    while (b>v) b>>=2;
    while (b) { if (v>=r+b) { v-=r+b; r=(r>>1)+b; } else r>>=1; b>>=2; }
    return r;
}
static unsigned iatan2(int y, int x) {                /* 0..255 */
    if (!x && !y) return 0;
    int ax=abs(x), ay=abs(y);
    int a=ax>=ay ? 32*ay/ax : 64-32*ax/ay;
    if (x<0) a=128-a;
    if (y<0) a=256-a;
    return (unsigned)a&255;
}
static int vsin(unsigned a) { return vs[a&1023]; }
static int vcos(unsigned a) { return vs[(a+256)&1023]; }

/* ------------------------------------------------ palette-cycled images */
static unsigned px_plasma(int x, int y) {
    int dx=x-320, dy=y-180;
    int v=vsin((unsigned)(x*5))+vsin((unsigned)(y*7))+vsin((unsigned)((x+y)*3))+
          vsin((unsigned)(isqrt((uint32_t)(dx*dx+dy*dy))*6))+vsin((unsigned)(x*2-y*5));
    return 1u+(unsigned)((v+5*16384)/2300)%14u;
}
static unsigned px_tunnel(int x, int y) {
    int dx=x-320, dy=(y-180)*5/4;
    uint32_t r=isqrt((uint32_t)(dx*dx+dy*dy));
    if (r<22) return 0;
    unsigned depth=12000u/r, a=iatan2(dy,dx);
    unsigned band=depth%7u, chk=((a>>4)+(depth/7u))&1u;
    return 1u+band*2u+chk;
}
static unsigned px_moire(int x, int y) {
    int ax=x-210, ay=y-150, bx=x-430, by=y-215;
    uint32_t r1=isqrt((uint32_t)(ax*ax+ay*ay)), r2=isqrt((uint32_t)(bx*bx+by*by));
    int v=vsin(r1*22u)+vsin(r2*22u);                 /* two-source interference */
    return 1u+(unsigned)((v+32768)/2341)%14u;
}
typedef unsigned (*pixel_fn)(int, int);
static struct { pixel_fn fn; unsigned page, chunk; } bg;
static void bg_start(pixel_fn fn, unsigned page) { bg.fn=fn; bg.page=page; bg.chunk=0; }
static int bg_step(unsigned chunks) {
    uint8_t buf[64];
    while (bg.fn && chunks--) {
        unsigned y=bg.chunk/5, x0=(bg.chunk%5)*128;
        for (unsigned i=0;i<64;i++)
            buf[i]=(uint8_t)(bg.fn((int)(x0+2*i),(int)y)<<4 | bg.fn((int)(x0+2*i+1),(int)y));
        TRY(g_write(bg.page*PAGE_BYTES+y*320u+x0/2u,buf,sizeof buf));
        if (++bg.chunk==H*5) bg.fn=NULL;
    }
    return 0;
}
static int bg_finish(void) { return bg_step(H*5); }

/* ----------------------------------------------------------------- scenes */
static unsigned frame_of(uint32_t ms) { return ms*(FM_RATE/1000u); }

// 0 INTRO
static const char TITLE[]="KAGURA-HD", SUB[]="FOUR OPERATORS";
static unsigned intro_title, intro_sub, intro_lines;
static int intro_enter(void) {
    for (int y=0;y<H;y+=4) if (y<100 || y>=264) TRY(g_fill(0,0,y,W,4,1u+(unsigned)(y/4)%12u));
    intro_title=intro_sub=intro_lines=0;
    bg_start(px_plasma,1);
    return 0;
}
static int intro_frame(uint32_t t, const fm_snapshot *s) {
    unsigned fade=t<3000 ? t*256/3000 : 256, fl=flash_of(s);
    for (unsigned i=0;i<12;i++)
        pal_want[1+i]=(uint16_t)lerp(0,ramp(K_COPPER,7,i*65536u/12u+t*20u),fade);
    pal_want[13]=0x8ac; pal_want[14]=0x4df; pal_want[15]=(uint16_t)lerp(0xccc,0xfff,fl);
    // Title letters on the beat from 4 s, subtitle on eighths from 8 s.
    while (intro_title<sizeof TITLE-1 && t>=4000+intro_title*250u) {
        char c[2]={TITLE[intro_title],0};
        int x=(W-(int)font_width(TITLE,6))/2+(int)(intro_title*36);
        TRY(text(0,x,112,c,6,15)); intro_title++;
    }
    if (t>=7000 && !intro_lines) { TRY(text_c(0,164,"PRESENTS",2,13)); intro_lines=1; }
    while (intro_sub<sizeof SUB-1 && t>=8000+intro_sub*250u) {
        char c[2]={SUB[intro_sub],0};
        int x=(W-(int)font_width(SUB,4))/2+(int)(intro_sub*24);
        TRY(text(0,x,190,c,4,14)); intro_sub++;
    }
    if (t>=12000 && intro_lines==1) { TRY(text_c(0,232,"A SOFTWARE FM SYNTH MEGADEMO",2,13)); intro_lines=2; }
    if (t>=15500) for (unsigned i=1;i<16;i++) pal_want[i]=(uint16_t)lerp(pal_want[i],0xfff,(t-15500)*256/500);
    TRY(show(0));
    return bg_step(10);
}

// 1 PLASMA / 2 TUNNEL / 6 MOIRE: static image + palette cycling
static unsigned scope_page;
static bool scroll_ready, finale_ready;
static int plasma_enter(void) {
    TRY(bg_finish());
    TRY(caption(1,"PLASMA - 14 COLOURS CYCLING"));
    bg_start(px_tunnel,0);
    return 0;
}
static int plasma_frame(uint32_t t, const fm_snapshot *s) {
    unsigned fl=flash_of(s), in=t<600 ? 256-t*256/600 : 0;
    for (unsigned i=0;i<14;i++)
        pal_want[1+i]=(uint16_t)lerp(lerp(ramp(K_PLASMA,7,i*65536u/14u+t*14u),0xfff,fl),0xfff,in);
    pal_want[0]=0; pal_want[15]=0xfff;
    TRY(show(1));
    return bg_step(10);
}
static int tunnel_enter(void) {
    TRY(bg_finish());
    TRY(caption(0,"TUNNEL - DEPTH BY PALETTE"));
    scroll_ready=false;
    return 0;
}
static int scroller_prepare(void) {   /* page 1 is hidden once the tunnel is shown */
    TRY(g_fill(1,0,0,W,H,0));
    for (int y=0;y<204;y+=4) { int k=(y/4)%10; TRY(g_fill(1,0,y,W,4,1u+(unsigned)(k<6 ? k : 10-k))); }
    TRY(text_c(1,84+4,"FOUR OPERATORS",4,0));
    TRY(text_c(1,84,"FOUR OPERATORS",4,15));
    return 0;
}
static int tunnel_frame(uint32_t t, const fm_snapshot *s) {
    unsigned fl=flash_of(s);
    for (unsigned b=0;b<7;b++) {
        unsigned c=ramp(K_TUNNEL,8,b*65536u/7u+t*22u);
        c=lerp(c,0xfff,fl/2);
        pal_want[1+b*2]=(uint16_t)c; pal_want[2+b*2]=(uint16_t)lerp(c,0,110);
    }
    pal_want[0]=0; pal_want[15]=0xfff;
    TRY(show(0));
    if (!scroll_ready) { TRY(scroller_prepare()); scroll_ready=true; }
    return 0;
}
static int moire_enter(void) {
    TRY(bg_finish());
    unsigned page=!scope_page;
    TRY(caption(page,"MOIRE - TWO RING SETS, ONE PALETTE"));
    finale_ready=false;
    return 0;
}
static int moire_frame(uint32_t t, const fm_snapshot *s) {
    unsigned fl=flash_of(s);
    for (unsigned i=0;i<14;i++)
        pal_want[1+i]=(uint16_t)lerp(ramp(K_RAINBOW,7,i*65536u/14u+t*16u),0xfff,fl);
    pal_want[0]=0; pal_want[15]=0xfff;
    TRY(show(!scope_page));
    if (!finale_ready) { TRY(g_fill(scope_page,0,0,W,H,0)); finale_ready=true; }   /* hidden now */
    return 0;
}

// 3 SCROLLER
static const char SCROLL[]=
    "          FOUR OPERATORS ... SIX FM VOICES OF FOUR OPERATORS EACH, PLUS A KICK, A SNARE AND A HAT, "
    "SYNTHESIZED IN REAL TIME ON THE SECOND RP2040 CORE ... 48000 STEREO SAMPLES PER SECOND STREAMED "
    "OVER QSPI INTO A GW1NR-9C AND OUT THROUGH HDMI ... 640 X 360 IN 16 COLOURS ...          ";
#define SCROLL_Y 236
#define SCROLL_PX_PER_S 480u
static unsigned scroll_cols, vu_h[FM_VOICES];
static int scroll_column(unsigned col, int x) {
    unsigned ch=col/6, gc=col%6;
    TRY(g_fill(1,x,SCROLL_Y,8,FONT_H*8,0));
    if (ch>=sizeof SCROLL-1 || gc==5) return 0;
    const uint8_t *g=font_glyph(SCROLL[ch]);
    for (unsigned r=0;r<FONT_H;r++) if (g[r]>>(4-gc)&1) TRY(g_fill(1,x,SCROLL_Y+(int)r*8,8,8,7+r));
    return 0;
}
static int scroller_enter(void) { scroll_cols=0; memset(vu_h,0,sizeof vu_h); return 0; }
static int scroller_frame(uint32_t t, const fm_snapshot *s) {
    unsigned target=t*SCROLL_PX_PER_S/1000u/8u, n=target-scroll_cols;
    if (n>8) n=8;
    if (n) {
        TRY(g_copy(1,(int)(n*8),SCROLL_Y,1,0,SCROLL_Y,W-(int)(n*8),FONT_H*8));
        for (unsigned i=0;i<n;i++) TRY(scroll_column(scroll_cols+i,W-(int)((n-i)*8)));
        scroll_cols+=n;
    }
    for (unsigned v=0;v<FM_VOICES;v++) {           /* voice VU, incremental */
        unsigned h=s->voice[v]*48u/255u, x=88+v*80;
        if (h>vu_h[v]) TRY(g_fill(1,(int)x,350-(int)h,56,(int)(h-vu_h[v]),14));
        if (h<vu_h[v]) TRY(g_fill(1,(int)x,350-(int)vu_h[v],56,(int)(vu_h[v]-h),0));
        vu_h[v]=h;
    }
    unsigned fl=flash_of(s);
    for (unsigned i=0;i<6;i++) pal_want[1+i]=(uint16_t)ramp(K_COPPER,7,i*65536u/10u+t*30u);
    for (unsigned r=0;r<7;r++) pal_want[7+r]=(uint16_t)lerp(ramp(K_RAINBOW,7,r*6000u+t*40u),0xfff,fl/2);
    pal_want[0]=0; pal_want[14]=0x4f8; pal_want[15]=0xfff;
    return show(1);
}

// 4 VECTOR
static const int16_t ICO_V[12][3]={
 {-135,218,0},{135,218,0},{-135,-218,0},{135,-218,0},{0,-135,218},{0,135,218},
 {0,-135,-218},{0,135,-218},{218,0,-135},{218,0,135},{-218,0,-135},{-218,0,135}};
static const uint8_t ICO_F[20][3]={
 {0,11,5},{0,5,1},{0,1,7},{0,7,10},{0,10,11},{1,5,9},{5,11,4},{11,10,2},{10,7,6},{7,1,8},
 {3,9,4},{3,4,2},{3,2,6},{3,6,8},{3,8,9},{4,9,5},{2,4,11},{6,2,10},{8,6,7},{9,8,1}};
typedef struct { int32_t x, y, z; } star;
#define STARS 28
static star stars[STARS];
static uint32_t star_seed=0x1234567u, vec_last;
static bool vec_cleared[2];
static int32_t rnd(void) { star_seed=star_seed*1664525u+1013904223u; return (int32_t)(star_seed>>8); }
static void star_spawn(star *s, bool far) {
    s->x=rnd()%2048-1024; s->y=rnd()%1400-700; s->z=far ? 1024 : 64+rnd()%960;
}
static int vector_enter(void) {
    for (unsigned i=0;i<STARS;i++) star_spawn(&stars[i],false);
    vec_cleared[0]=vec_cleared[1]=false; vec_last=0;
    return 0;
}
static int span_triangle(unsigned page, const int p[3][2], unsigned color) {
    int a=0,b=1,c=2,tmp;
    if (p[b][1]<p[a][1]) { tmp=a; a=b; b=tmp; }
    if (p[c][1]<p[a][1]) { tmp=a; a=c; c=tmp; }
    if (p[c][1]<p[b][1]) { tmp=b; b=c; c=tmp; }
    int y0=p[a][1], y1=p[b][1], y2=p[c][1];
    if (y2==y0) return 0;
    for (int y=y0-((y0%4+4)%4);y<y2;y+=4) {         /* 4-pixel spans */
        int yc=y+2; if (yc<y0) continue;
        int xl=p[a][0]+(p[c][0]-p[a][0])*(yc-y0)/(y2-y0), xr;
        if (yc<y1) xr=y1==y0 ? p[b][0] : p[a][0]+(p[b][0]-p[a][0])*(yc-y0)/(y1-y0);
        else xr=y2==y1 ? p[b][0] : p[b][0]+(p[c][0]-p[b][0])*(yc-y1)/(y2-y1);
        if (xl>xr) { tmp=xl; xl=xr; xr=tmp; }
        int x0=xl<0 ? 0 : xl, x1=xr>=W ? W-1 : xr;
        if (y>=0 && y+4<=326 && x1>=x0) TRY(g_fill(page,x0,y,x1-x0+1,4,color));
    }
    return 0;
}
static int vector_frame(uint32_t t, const fm_snapshot *s) {
    unsigned back=!displayed;
    if (!vec_cleared[back]) {
        TRY(g_fill(back,0,0,W,H,0));
        TRY(caption(back,"VECTOR - 20 FLAT SHADED FACES"));
        vec_cleared[back]=true;
    }
    TRY(g_fill(back,0,0,W,326,0));
    // Stars.
    uint32_t dt=t-vec_last; vec_last=t; if (dt>100) dt=100;
    for (unsigned i=0;i<STARS;i++) {
        star *p=&stars[i];
        p->z-=(int32_t)(dt*9/10);
        if (p->z<24) star_spawn(p,true);
        int sx=320+p->x*256/p->z, sy=165+p->y*256/p->z;
        if (sx<0 || sx>=W-3 || sy<0 || sy>=324) { star_spawn(p,true); continue; }
        unsigned col=p->z<300 ? 3 : p->z<650 ? 2 : 1;
        TRY(g_fill(back,sx,sy,p->z<300 ? 3 : 2,p->z<300 ? 3 : 2,col));
    }
    // Icosahedron.
    unsigned ay=t*256u/2900u, ax=t*256u/4100u;
    int radius=118+(int)(s->drum[D_KICK]>150 ? (s->drum[D_KICK]-150)/7 : 0);
    int32_t rv[12][3]; int pv[12][2];
    for (unsigned i=0;i<12;i++) {
        int32_t x=ICO_V[i][0], y=ICO_V[i][1], z=ICO_V[i][2];
        int32_t x1=(x*vcos(ay)+z*vsin(ay))>>14, z1=(-x*vsin(ay)+z*vcos(ay))>>14;
        int32_t y2=(y*vcos(ax)-z1*vsin(ax))>>14, z2=(y*vsin(ax)+z1*vcos(ax))>>14;
        rv[i][0]=x1*radius/256; rv[i][1]=y2*radius/256; rv[i][2]=z2*radius/256;
        int32_t d=520+rv[i][2];
        pv[i][0]=320+rv[i][0]*520/d; pv[i][1]=165+rv[i][1]*520/d;
    }
    for (unsigned f=0;f<20;f++) {
        const uint8_t *q=ICO_F[f];
        int p[3][2]={{pv[q[0]][0],pv[q[0]][1]},{pv[q[1]][0],pv[q[1]][1]},{pv[q[2]][0],pv[q[2]][1]}};
        int32_t cross=(p[1][0]-p[0][0])*(p[2][1]-p[0][1])-(p[1][1]-p[0][1])*(p[2][0]-p[0][0]);
        if (cross>=0) continue;
        int32_t ux=rv[q[1]][0]-rv[q[0]][0], uy=rv[q[1]][1]-rv[q[0]][1], uz=rv[q[1]][2]-rv[q[0]][2];
        int32_t wx=rv[q[2]][0]-rv[q[0]][0], wy=rv[q[2]][1]-rv[q[0]][1], wz=rv[q[2]][2]-rv[q[0]][2];
        int32_t nx=uy*wz-uz*wy, ny=uz*wx-ux*wz, nz=ux*wy-uy*wx;
        int32_t len=(int32_t)isqrt((uint32_t)(nx*nx+ny*ny+nz*nz)); if (!len) continue;
        int32_t dot=(-nx*40-ny*55-nz*73)/len;          /* light (-0.4,-0.55,-0.73)*100 */
        if (dot<0) dot=-dot;
        unsigned shade=(unsigned)(dot*10/101); if (shade>9) shade=9;
        TRY(span_triangle(back,(const int (*)[2])p,4+shade));
    }
    unsigned fl=flash_of(s);
    for (unsigned i=0;i<10;i++) pal_want[4+i]=(uint16_t)lerp(ramp(K_SHADE,7,i*6553u),0xfff,fl/3);
    pal_want[0]=0; pal_want[1]=0x445; pal_want[2]=0x889; pal_want[3]=0xddf; pal_want[14]=0x9bf; pal_want[15]=0xfff;
    return show(back);
}

// 5 SCOPE
#define SCOPE_TOP 52
#define SCOPE_MID 132
#define SCOPE_COLS 128
static uint8_t scope_lo[SCOPE_COLS], scope_hi[SCOPE_COLS], bar_h[FM_VOICES][FM_OPS];
static int scope_enter(void) {
    scope_page=!displayed;
    unsigned p=scope_page;
    TRY(g_fill(p,0,0,W,H,0));
    TRY(text_c(p,14,"OPERATOR VIEW",3,14));
    TRY(g_fill(p,0,SCOPE_TOP-6,W,2,1)); TRY(g_fill(p,0,SCOPE_MID+86,W,2,1));
    static const char *names[FM_VOICES]={"BASS","LEAD","ARP","PAD","PAD","PAD"};
    for (unsigned v=0;v<FM_VOICES;v++) TRY(text(p,(int)(16+v*104+(84-font_width(names[v],2))/2),338,names[v],2,14));
    for (unsigned i=0;i<SCOPE_COLS;i++) scope_lo[i]=scope_hi[i]=SCOPE_MID;
    memset(bar_h,0,sizeof bar_h);
    TRY(show(scope_page));
    bg_start(px_moire,!scope_page);
    return 0;
}
static int scope_y(int8_t v) { int d=(int)v*3*78/128; return SCOPE_MID-(d>78 ? 78 : d<-78 ? -78 : d); }
static int scope_frame(uint32_t t, const fm_snapshot *s) {
    unsigned p=scope_page;
    uint32_t a=frame_of(t+5u*DEMO_SCENE_MS), base=a-1600u, trig=0;   /* song time, not scene time */
    for (uint32_t i=1;i<512;i++) if (plat->sample_at(base+i-1)<0 && plat->sample_at(base+i)>=0) { trig=i; break; }
    int prev=scope_y(plat->sample_at(base+trig));
    for (unsigned c=0;c<SCOPE_COLS;c++) {
        int y=scope_y(plat->sample_at(base+trig+c*4u+4u));
        int lo=y<prev ? y : prev, hi=(y<prev ? prev : y)+2;
        prev=y;
        if (lo!=scope_lo[c] || hi!=scope_hi[c]) {
            TRY(g_fill(p,(int)c*5,scope_lo[c],5,scope_hi[c]-scope_lo[c],0));
            TRY(g_fill(p,(int)c*5,lo,5,hi-lo,15));
            scope_lo[c]=(uint8_t)lo; scope_hi[c]=(uint8_t)hi;
        }
    }
    for (unsigned v=0;v<FM_VOICES;v++) for (unsigned o=0;o<FM_OPS;o++) {
        unsigned h=s->op[v][o]*76u/255u, x=16+v*104+o*21;
        unsigned old=bar_h[v][o];
        if (h>old) TRY(g_fill(p,(int)x,330-(int)h,17,(int)(h-old),4+o));
        if (h<old) TRY(g_fill(p,(int)x,330-(int)old,17,(int)(old-h),0));
        bar_h[v][o]=(uint8_t)h;
    }
    unsigned fl=flash_of(s);
    pal_want[0]=0; pal_want[1]=0x224; pal_want[4]=0xf64; pal_want[5]=0xfc4; pal_want[6]=0x4cf; pal_want[7]=0xa6f;
    pal_want[14]=0x9bf; pal_want[15]=(uint16_t)lerp(0x6f8,0xfff,fl);
    TRY(show(p));
    return bg_step(10);
}

// 7 FINALE
static unsigned finale_lines;
static const struct { uint32_t at; int y; unsigned scale, color; const char *s; } CREDITS[]={
    {500,48,5,15,"FOUR OPERATORS"},
    {2500,124,2,13,"FM SYNTHESIS, MUSIC AND CODE"},
    {3500,144,2,13,"KAGURA-HD PROJECT, 2026"},
    {5500,184,2,14,"GW1NR-9C FPGA  /  RP2040 HOST"},
    {6500,204,2,14,"4 OPERATORS X 6 VOICES AT 48 KHZ"},
    {9500,262,3,15,"THANK YOU FOR WATCHING"}};
static int finale_enter(void) { finale_lines=0; return 0; }
static int finale_frame(uint32_t t, const fm_snapshot *s) {
    (void)s;
    unsigned p=scope_page;
    while (finale_lines<sizeof CREDITS/sizeof CREDITS[0] && t>=CREDITS[finale_lines].at) {
        TRY(text_c(p,CREDITS[finale_lines].y,CREDITS[finale_lines].s,CREDITS[finale_lines].scale,CREDITS[finale_lines].color));
        finale_lines++;
    }
    unsigned total=DEMO_END_MS-7*DEMO_SCENE_MS, f=t<total-5000 ? 256 : t>=total ? 0 : (total-t)*256/5000;
    pal_want[0]=0;
    pal_want[13]=(uint16_t)lerp(0,0x8af,f); pal_want[14]=(uint16_t)lerp(0,0xfc6,f);
    pal_want[15]=(uint16_t)lerp(0,ramp(K_RAINBOW,7,t*12u),f);
    return show(p);
}

/* ------------------------------------------------------------- timeline */
typedef struct { int (*enter)(void); int (*frame)(uint32_t, const fm_snapshot *); } scene_def;
static const scene_def SCENES[DEMO_SCENES]={
    {intro_enter,intro_frame},{plasma_enter,plasma_frame},{tunnel_enter,tunnel_frame},
    {scroller_enter,scroller_frame},{vector_enter,vector_frame},{scope_enter,scope_frame},
    {moire_enter,moire_frame},{finale_enter,finale_frame}};

int demo_init(kfb_device *device, const demo_platform *platform) {
    gpu=device; plat=platform;
    memset(&stats,0,sizeof stats); memset(pal_valid,0,sizeof pal_valid); memset(pal_want,0,sizeof pal_want);
    for (unsigned i=0;i<1024;i++) vs[i]=(int16_t)lrintf(16384.0f*sinf((float)i*6.28318530718f/1024.0f));
    font_init();
    entered=-1; bg.fn=NULL; displayed=0; scope_page=0;
    TRY(g_fill(0,0,0,W,H,0)); TRY(g_fill(1,0,0,W,H,0));
    return show(0);
}
int demo_frame(uint32_t ms) {
    if (ms>=DEMO_END_MS) ms=DEMO_END_MS-1;
    unsigned scene=ms/DEMO_SCENE_MS; if (scene>=DEMO_SCENES) scene=DEMO_SCENES-1;
    uint32_t t=ms-scene*DEMO_SCENE_MS;
    if ((int)scene!=entered) {
        while (entered<(int)scene) { entered++; TRY(SCENES[entered].enter()); }  /* never skip a setup */
    }
    stats.scene=(uint8_t)scene; stats.frames++; stats.scene_frames[scene]++;
    return SCENES[scene].frame(t,plat->snapshot_at(frame_of(ms)));
}
const demo_stats *demo_statistics(void) { return &stats; }
