// SPDX-License-Identifier: Apache-2.0
// PC preview of FOUR OPERATORS: behavioural KFB register model (drawing only,
// no PSRAM/QSPI/HDMI timing), the real C SDK, the real demo and synthesizer.
//   fm_pc --wav out.wav                 song only
//   fm_pc --video out.rgb [--fps 30]    640x360 RGB24 frames on stdout or file
//   fm_pc --stats                       per-scene command/transaction counts
#include "demo.h"
#include "fm.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint8_t memory[4194304], stage[16], window_data[64];
static uint16_t palette[16], display_palette[16], tag;
static unsigned pointer_reg, page, polls, done, pending, device_error, sticky;
static uint32_t clock_ms;
static uint64_t transactions, wire_bytes;

static unsigned u16(const uint8_t *p) { return p[0]|((unsigned)p[1]<<8); }
static uint32_t u32(const uint8_t *p) { return u16(p)|((uint32_t)u16(p+2)<<16); }
static void fill(unsigned p, unsigned x, unsigned y, unsigned w, unsigned h, unsigned c) {
    for (unsigned j=y;j<y+h;j++) for (unsigned i=x;i<x+w;i++) {
        uint8_t *b=memory+p*115200u+j*320u+i/2u;
        *b=(uint8_t)(i&1 ? (*b&0xf0)|c : (*b&0x0f)|(c<<4));
    }
}
static void finish(void) {
    unsigned op=stage[0], arg=stage[1];
    device_error=0; tag=(uint16_t)u16(stage+2);
    switch (op) {
    case 0: break;
    case 1: { unsigned x=u16(stage+4),y=u16(stage+6),w=u16(stage+8),h=u16(stage+10);
        if (arg>1 || x+w>640 || y+h>360 || stage[12]>15) device_error=3; else fill(arg,x,y,w,h,stage[12]); break; }
    case 2: if (arg>15) device_error=3; else palette[arg]=(uint16_t)u16(stage+4); break;
    case 3: if (arg>1) device_error=3; else { page=arg; memcpy(display_palette,palette,sizeof palette); } break;
    case 4: case 5: { uint32_t a=u32(stage+4); unsigned n=arg*4u;
        if (!arg || arg>16 || a%4 || a+n>sizeof memory) { device_error=3; break; }
        if (op==4) { for (unsigned i=0;i<n;i++) if (!(stage[8+i/8]>>(i%8)&1)) memory[a+i]=window_data[i]; }
        else { memcpy(window_data,memory+a,n); pointer_reg=0; } break; }
    case 6: { unsigned sx=u16(stage+4),sy=u16(stage+6),dx=u16(stage+8),dy=u16(stage+10),w=u16(stage+12),h=u16(stage+14);
        if (arg>3 || sx+w>640 || dx+w>640 || sy+h>360 || dy+h>360 || ((sx|dx|w)&1) || ((sx^dx)&7)) { device_error=3; break; }
        unsigned sp=arg&1, dp=arg>>1&1; int first=0,end=(int)h,step=1;
        if (sp==dp && dy>sy) { first=(int)h-1; end=-1; step=-1; }
        for (int j=first;j!=end;j+=step)
            memmove(memory+dp*115200u+(dy+(unsigned)j)*320u+dx/2u,memory+sp*115200u+(sy+(unsigned)j)*320u+sx/2u,w/2u);
        break; }
    default: device_error=2;
    }
    if (device_error) { fprintf(stderr,"device error %u op %u\n",device_error,op); sticky=device_error; }
    pending=0; done=1;
}
static int read_reg(void *ctx, uint8_t reg, bool inc, uint8_t *v, size_t n) {
    (void)ctx; transactions++; wire_bytes+=n+3;
    for (size_t i=0;i<n;i++) {
        unsigned val=0;
        if (reg==27) { if (pending && !--polls) finish(); val=2|(pending?1:0)|(done?16:0); }
        else if (reg<7) { static const uint8_t id[7]={'K','F','B','1',1,4,255}; val=id[reg]; }
        else if (reg==7) val=sticky;
        else if (reg==28) val=tag&255;
        else if (reg==29) val=tag>>8;
        else if (reg==30) val=device_error;
        else if (reg==24) { if (pointer_reg>=64) return -1; val=window_data[pointer_reg++]; }
        else if (reg==26) val=pending ? 0 : 1;
        else if (reg==31) val=done;
        else return -1;
        v[i]=(uint8_t)val; if (inc) reg++;
    }
    return 0;
}
static int write_reg(void *ctx, uint8_t reg, bool inc, const uint8_t *v, size_t n) {
    (void)ctx; transactions++; wire_bytes+=n+1;
    for (size_t i=0;i<n;i++) {
        if (reg==7) sticky=0;
        else if (reg==31) { if (v[i]&1) done=0; }
        else if (pending) return -1;
        else if (reg>=8 && reg<24) stage[reg-8]=v[i];
        else if (reg==25) pointer_reg=v[i];
        else if (reg==24) { if (pointer_reg>=64) return -1; window_data[pointer_reg++]=v[i]; }
        else if (reg==26) { pending=1; polls=2; done=0; }
        else return -1;
        if (inc) reg++;
    }
    return 0;
}
static uint32_t now_ms(void *ctx) { (void)ctx; return clock_ms++; }

static int8_t *song_l, *song_r;
static uint32_t rendered;
static void render_until(uint32_t frame) {
    while (rendered<frame && rendered<FM_SONG_FRAMES) {
        unsigned n=FM_SONG_FRAMES-rendered<4096 ? FM_SONG_FRAMES-rendered : 4096;
        fm_render(song_l+rendered,song_r+rendered,n); rendered+=n;
    }
}
static int8_t sample_at(uint32_t frame) {
    render_until(frame+4096);
    return frame<FM_SONG_FRAMES ? (int8_t)((song_l[frame]+song_r[frame])/2) : 0;
}
static const fm_snapshot *snapshot_at(uint32_t frame) { render_until(frame+FM_SNAP_FRAMES); return fm_snapshot_at(frame); }

static void put16(FILE *f, unsigned v) { fputc((int)(v&255),f); fputc((int)(v>>8),f); }
static void put32(FILE *f, uint32_t v) { put16(f,v&0xffff); put16(f,v>>16); }
static int write_wav(const char *path) {
    render_until(FM_SONG_FRAMES);
    FILE *f=fopen(path,"wb"); if (!f) return 1;
    fwrite("RIFF",1,4,f); put32(f,36+FM_SONG_FRAMES*4u); fwrite("WAVEfmt ",1,8,f); put32(f,16);
    put16(f,1); put16(f,2); put32(f,FM_RATE); put32(f,FM_RATE*4u); put16(f,4); put16(f,16);
    fwrite("data",1,4,f); put32(f,FM_SONG_FRAMES*4u);
    for (uint32_t i=0;i<FM_SONG_FRAMES;i++) { put16(f,(uint16_t)(song_l[i]*256)); put16(f,(uint16_t)(song_r[i]*256)); }
    fclose(f);
    fprintf(stderr,"wav: %u frames peak=%u clipped=%u\n",FM_SONG_FRAMES,fm_peak(),fm_clipped());
    return 0;
}

int main(int argc, char **argv) {
    const char *wav=NULL, *video=NULL; unsigned fps=30; int want_stats=0;
    for (int i=1;i<argc;i++) {
        if (!strcmp(argv[i],"--wav") && i+1<argc) wav=argv[++i];
        else if (!strcmp(argv[i],"--video") && i+1<argc) video=argv[++i];
        else if (!strcmp(argv[i],"--fps") && i+1<argc) fps=(unsigned)atoi(argv[++i]);
        else if (!strcmp(argv[i],"--stats")) want_stats=1;
        else { fprintf(stderr,"usage: fm_pc [--wav f] [--video f|-] [--fps n] [--stats]\n"); return 2; }
    }
    song_l=malloc(FM_SONG_FRAMES); song_r=malloc(FM_SONG_FRAMES);
    if (!song_l || !song_r) return 1;
    fm_init();
    if (wav) return write_wav(wav);
    kfb_device gpu; kfb_io io={NULL,read_reg,write_reg,now_ms};
    static const demo_platform platform={NULL,sample_at,snapshot_at};
    int rc=kfb_init(&gpu,io,100); if (!rc) rc=kfb_probe(&gpu); if (!rc) rc=demo_init(&gpu,&platform);
    if (rc) { fprintf(stderr,"init rc=%d\n",rc); return 1; }
    FILE *out=video ? (strcmp(video,"-") ? fopen(video,"wb") : stdout) : NULL;
    static uint8_t rgb[640*360*3];
    uint64_t scene_tx[DEMO_SCENES]={0}, scene_cmd[DEMO_SCENES]={0}, max_tx[DEMO_SCENES]={0};
    uint32_t frames=DEMO_END_MS*fps/1000u;
    for (uint32_t f=0;f<frames;f++) {
        uint32_t ms=f*1000u/fps; uint64_t t0=transactions; uint32_t c0=demo_statistics()->commands;
        rc=demo_frame(ms); if (rc) { fprintf(stderr,"frame %u rc=%d\n",f,rc); return 1; }
        unsigned sc=demo_statistics()->scene; uint64_t dt=transactions-t0;
        scene_tx[sc]+=dt; scene_cmd[sc]+=demo_statistics()->commands-c0; if (dt>max_tx[sc]) max_tx[sc]=dt;
        if (out) {
            const uint8_t *m=memory+page*115200u;
            for (unsigned i=0;i<640*360;i++) {
                unsigned c=display_palette[(m[i/2]>>(i&1 ? 0 : 4))&15];
                rgb[i*3]=(uint8_t)((c>>8&15)*17); rgb[i*3+1]=(uint8_t)((c>>4&15)*17); rgb[i*3+2]=(uint8_t)((c&15)*17);
            }
            fwrite(rgb,1,sizeof rgb,out);
        }
    }
    if (out && out!=stdout) fclose(out);
    if (want_stats || !out) {
        const demo_stats *s=demo_statistics();
        fprintf(stderr,"scene frames  cmd/frame  tx/frame  max_tx  est_ms/frame(15us/tx)\n");
        for (unsigned i=0;i<DEMO_SCENES;i++) {
            uint32_t n=s->scene_frames[i]?s->scene_frames[i]:1;
            fprintf(stderr,"%5u %6u %9.1f %9.1f %7llu %8.1f\n",i,s->scene_frames[i],(double)scene_cmd[i]/n,(double)scene_tx[i]/n,
                    (unsigned long long)max_tx[i],(double)scene_tx[i]/n*0.015);
        }
        fprintf(stderr,"total commands=%u fills=%u copies=%u palettes=%u presents=%u writes=%u transactions=%llu wire=%llu\n",
                s->commands,s->fills,s->copies,s->palettes,s->presents,s->writes,(unsigned long long)transactions,(unsigned long long)wire_bytes);
    }
    return 0;
}
