// SPDX-License-Identifier: Apache-2.0
#include "b16.h"
#include "b16_profile.h"
#include "../../midnight_terminal/src/mt_lz.h"
#include <string.h>
#include "../generated/assets.inc"
static int read_cached(void *p,uint8_t reg,bool inc,uint8_t *v,size_t n){b16_bus *b=p;if(b->cached&&reg==6&&n==1){*v=b->caps;return 0;}int r=b->raw.read(b->raw.context,reg,inc,v,n);if(!r&&reg==0&&inc&&n>=7){b->caps=v[6];b->cached=1;}return r;}
static int write_cached(void *p,uint8_t r,bool i,const uint8_t *v,size_t n){b16_bus *b=p;return b->raw.write(b->raw.context,r,i,v,n);}
static uint32_t clock_cached(void *p){b16_bus *b=p;return b->raw.now_ms(b->raw.context);}
kfb_io b16_cached_io(b16_bus *b,kfb_io raw){memset(b,0,sizeof *b);b->raw=raw;kfb_io io={b,read_cached,write_cached,clock_cached};return io;}
typedef struct {kfb_device *g;uint32_t address;} sink_context;
static int sink(void *p,const uint8_t *data,uint32_t n){sink_context *c=p;int r=kfb_write_bytes(c->g,c->address,data,n);if(!r)c->address+=n;return r;}
int b16_assets(kfb_device *g){int r=0;sink_context c={g,0};for(unsigned page=0;page<2&&!r;page++){c.address=page*PAGE_BYTES;r=mt_lz_decode(frame_lz,sizeof frame_lz,PAGE_BYTES,sink,&c);}c.address=BGM_ADDR;if(!r)r=mt_lz_decode(song_lz,sizeof song_lz,BGM_SIZE,sink,&c);const uint8_t *fx[]={fx0,fx1,fx2,fx3};const unsigned ns[]={sizeof fx0,sizeof fx1,sizeof fx2,sizeof fx3};for(unsigned i=0;i<4&&!r;i++)r=kfb_write_bytes(g,FX_ADDR+i*16384,fx[i],ns[i]);if(!r)r=kfb_fence(g);return r;}
static int aw(kfb_device *g,unsigned i,unsigned v){uint8_t a[2]={(uint8_t)i,(uint8_t)v};return g->io.write(g->io.context,54,true,a,2)?KFB_IO:0;}
static int ar(kfb_device *g,unsigned i,uint8_t *v){uint8_t a=(uint8_t)i;if(g->io.write(g->io.context,54,false,&a,1))return KFB_IO;return g->io.read(g->io.context,55,false,v,1)?KFB_IO:0;}
static int wait_pcm(kfb_device *g,unsigned ch,int ready){uint32_t t=g->io.now_ms(g->io.context);for(;;){uint8_t s;int r=ar(g,0x6f+ch*32,&s);if(r)return r;if(s&0x38)return KFB_DEVICE;if(ready?(s&1):!(s&0x42))return 0;if((uint32_t)(g->io.now_ms(g->io.context)-t)>=g->timeout_ms)return KFB_TIMEOUT;}}
static unsigned bgm_gain=150;
static int pcm_commit(kfb_device *g,int fx){int r=0;for(unsigned ch=0;ch<2&&!r;ch++){unsigned b=0x60+ch*32;r=aw(g,b+12,ch?90:bgm_gain);if(!r)r=aw(g,b+13,ch?90:bgm_gain);if(!r)r=aw(g,b+14,ch?(fx?1:0):3);}if(!r)r=aw(g,0xe0,180);uint8_t cmd[16]={7};uint16_t tag=0;if(!r)r=kfb_submit(g,cmd,0,0,&tag);return r?r:kfb_wait(g,tag);}
int b16_audio_stop(kfb_device *g){int r=0;for(unsigned ch=0;ch<2&&!r;ch++){r=aw(g,0x6f+ch*32,2);if(!r)r=wait_pcm(g,ch,0);}return r;}
int b16_audio(kfb_device *g,int scene){static const unsigned gains[8]={150,165,175,160,180,195,170,185};bgm_gain=scene<0?150:gains[scene&7];unsigned ch=scene<0?0:1,b=0x60+ch*32;unsigned id=scene<0?0:(unsigned)scene%4;const unsigned ns[]={4096,2048,8192,8192};uint32_t start=ch?FX_ADDR+id*16384:BGM_ADDR,end=start+(ch?ns[id]:BGM_SIZE);int r=aw(g,b+15,2);if(!r)r=wait_pcm(g,ch,0);if(!r)r=aw(g,b+15,4);uint32_t val[]={start,end,start};for(unsigned k=0;k<3&&!r;k++)for(unsigned j=0;j<3&&!r;j++)r=aw(g,b+k*4+j,(val[k]>>(8*j))&255);if(!r)r=aw(g,b+14,ch?0:2);if(!r)r=aw(g,b+15,1);if(!r)r=wait_pcm(g,ch,1);if(!r)r=pcm_commit(g,ch!=0);return r;}
int b16_audio_poll(kfb_device *g){for(unsigned ch=0;ch<2;ch++){uint8_t s;int r=ar(g,0x6f+ch*32,&s);if(r)return r;if(s&0x38)return KFB_DEVICE;}return 0;}
static int fs(b16_engine *e,int p,int x,int y,int w,int h,int c){if(e->error)return e->error;e->stats.commands++;int r=kfb_fill_rect(e->gpu,(unsigned)p,x,y,w,h,(unsigned)c);if(r)e->error=r;return r;}
static void mark(b16_engine *e,int p,int x,int y,int w,int h){int x0=x/8,x1=(x+w-1)/8,y0=(y-88)/8,y1=(y+h-1-88)/8;for(int j=y0;j<=y1;j++)for(int i=x0;i<=x1;i++)if(j>=0&&j<26&&i>=0&&i<80)e->dirty[p][j][i]=1;}
static void dot(b16_engine *e,int x,int y,int w,int h,int c){if(x<16||y<88||x+w>624||y+h>280)return;fs(e,e->page,x,y,w,h,c);mark(e,e->page,x,y,w,h);}
static void clear_dirty(b16_engine *e){
 uint8_t (*d)[80]=e->dirty[e->page];
 for(int y=0;y<26;y++)for(int x=0;x<80;){
  if(!d[y][x]){x++;continue;}
  int first=x;while(x<80&&d[y][x])x++;int bottom=y+1;
  while(bottom<26){int ok=1;for(int i=first;i<x;i++)if(!d[bottom][i]){ok=0;break;}if(!ok)break;bottom++;}
  for(int j=y;j<bottom;j++)memset(&d[j][first],0,(size_t)(x-first));
  fs(e,e->page,first*8,88+y*8,(x-first)*8,(bottom-y)*8,0);
 }
}
static int sn(unsigned a){return sine[a&255];}
static uint32_t hash(uint32_t a){a^=a>>16;a*=0x7feb352du;a^=a>>15;a*=0x846ca68bu;return a^(a>>16);}
#ifndef B16_COOP
#define B16_COOP 0
#endif
#if B16_COOP
/* CPU-only immutable seed table. GPU never accesses this workspace. A wait
 * slice prepares exactly one entry; no descriptor/page/audio access. */
static uint32_t star_seed_cache[256],star_seed;
static unsigned star_seed_ready;
void b16_gpu_wait_work(void){if(star_seed_ready<256){BPUSH(B16_COOP_WORK);unsigned i=star_seed_ready;star_seed_cache[i]=hash(star_seed+i);star_seed_ready=i+1;BPOP();}}
static uint32_t star_hash(b16_engine *e,unsigned i){return star_seed==e->seed&&i<star_seed_ready?star_seed_cache[i]:hash(i+e->seed);}
#else
static uint32_t star_hash(b16_engine *e,unsigned i){return hash(i+e->seed);}
#endif
static void sprite(b16_engine *e,int id,int x,int y){if(e->error)return;x&=~7;if(x<16||x+32>624||y<88||y+32>280)return;int sx=(id&15)*40;e->stats.commands++;e->stats.blit_pixels+=1024;int r=kfb_copy_rect(e->gpu,e->page,sx,320,e->page,x,y,32,32);if(r)e->error=r;mark(e,e->page,x,y,32,32);}
/* 152x48 final indexed cells, expanded 4x4 by existing FILL. */
static uint8_t vector_mask[48][152];
static void vector_flush_inner(b16_engine *e){uint8_t (*prev)[152]=e->vector_previous[e->page];
 for(int y=0;y<48;y++)for(int x=0;x<152;){unsigned c=vector_mask[y][x];if(prev[y][x]==c){x++;continue;}int first=x;while(x<152&&vector_mask[y][x]==c)x++;int bottom=y+1;
  while(bottom<48){int ok=1;for(int i=first;i<x;i++)if(vector_mask[bottom][i]!=c){ok=0;break;}if(!ok)break;bottom++;}
  dot(e,16+first*4,88+y*4,(x-first)*4,(bottom-y)*4,(int)c);
  if(e->error)return;
  for(int j=y;j<bottom;j++)for(int i=first;i<x;i++)prev[j][i]=(uint8_t)c;
 }
}
static void vector_flush(b16_engine *e){BPUSH(B16_RECT);vector_flush_inner(e);BPOP();}
static void line_inner(b16_engine *e,int x0,int y0,int x1,int y1,int c){(void)e;
 x0=(x0-16)/4;y0=(y0-88)/4;x1=(x1-16)/4;y1=(y1-88)/4;
 int dx=x1>x0?x1-x0:x0-x1,dy=y1>y0?y0-y1:y1-y0,sx=x0<x1?1:-1,sy=y0<y1?1:-1,err=dx+dy;
 for(;;){if(x0>=0&&x0<152&&y0>=0&&y0<48)vector_mask[y0][x0]=(uint8_t)c;if(x0==x1&&y0==y1)break;int twice=2*err;if(twice>=dy){err+=dy;x0+=sx;}if(twice<=dx){err+=dx;y0+=sy;}}
}
static void line(b16_engine *e,int x0,int y0,int x1,int y1,int c){BPUSH(B16_MASK);line_inner(e,x0,y0,x1,y1,c);BPOP();}
static void stars(b16_engine *e,uint32_t t,unsigned count){unsigned turn=t/31;for(unsigned i=0;i<count;i++){uint32_t h=star_hash(e,i);unsigned beat=(t/500)&3;uint32_t travel=((t/2000)*5000+250*beat*(beat+1)+(t%500)*(beat+1))/3;int z=32+(int)(999-(h+travel)%1000);int x=(int)(h&511)-256,y=(int)((h>>9)&255)-128;int a=(x*sn(turn+64)-y*sn(turn))/1024,b=(x*sn(turn)+y*sn(turn+64))/1024;x=320+a*180/z;y=192+b*110/z;int size=z<180?3:1;dot(e,x,y,size+1,size,z<240?10:4+(int)(i%9));if(z<180)dot(e,x-(x-320)/30,y-(y-192)/30,2,2,12);}}
/* Immutable header slices, copied by the real aligned page BLIT instruction. */
#ifndef B16_MERGE_LOGO
#define B16_MERGE_LOGO 1
#endif
static void waving_logo(b16_engine *e,uint32_t t){
 for(int x=40;x<480&&!e->error;){int dx=x+80,dy=142+sn(t/17+x/3)*22/1024,width=8;
#if B16_MERGE_LOGO
  while(x+width<480&&142+sn(t/17+(x+width)/3)*22/1024==dy)width+=8;
#endif
  e->stats.commands++;e->stats.blit_pixels+=(unsigned)width*48;
  int r=kfb_copy_rect(e->gpu,e->page,x,22,e->page,dx,dy,width,48);
  if(r)e->error=r;else {mark(e,e->page,dx,dy,width,48);if(e->scene==6){for(int j=(dy-88)/4;j<=(dy+47-88)/4;j++)for(int i=(dx-16)/4;i<=(dx+width-1-16)/4;i++)if(j>=0&&j<48&&i>=0&&i<152)e->vector_previous[e->page][j][i]=255;}}
  x+=width;
 }
}
static void waves(b16_engine *e,uint32_t t){
 /* Temporary opaque 32x9 strip; the source is restored before PRESENT. */
 for(int layer=0;layer<3;layer++){
  for(int band=0;band<3;band++)fs(e,e->page,0,300+band*3,32,3,3+(layer+band+(int)(t/500))%10);
  for(int x=24;x<616;x+=32){int y=178+layer*8+sn(x/4+t/14+layer*27)*(22+layer*5)/1024;if(x+32>624)continue;
   e->stats.commands++;e->stats.blit_pixels+=32*9;int r=kfb_copy_rect(e->gpu,e->page,0,300,e->page,x,y,32,9);if(r)e->error=r;else mark(e,e->page,x,y,32,9);
  }
 }
 e->stats.commands++;e->stats.blit_pixels+=32*9;int r=kfb_copy_rect(e->gpu,e->page^1,0,300,e->page,0,300,32,9);if(r)e->error=r;
}
static void plasma_effect(b16_engine *e,uint32_t t){for(int y=0;y<6;y++)for(int x=0;x<18;x++){int phase=(sn(x*9+t/25)+sn(y*21+t/37)+2048)/256;int tile=8+((phase+(int)(t/180))&7);if(e->plasma_cache[e->page][y][x]!=tile){sprite(e,tile,32+x*32,88+y*32);e->plasma_cache[e->page][y][x]=(uint8_t)tile;}}}
static void roto(b16_engine *e,uint32_t t){int a=(int)(t/22),scale=180+(sn(t/40)+1024)/6;for(int y=0;y<12;y++){int colors[24];for(int x=0;x<24;x++){int xx=x-12,yy=y-6,u=((xx*sn(a+64)-yy*sn(a))*scale)/4096,v=((xx*sn(a)+yy*sn(a+64))*scale)/4096;colors[x]=(((u/256)^(v/256))&1)?11:3+(y/3);}for(int x=0;x<24;){int first=x,c=colors[x++];while(x<24&&colors[x]==c)x++;dot(e,32+first*24,88+y*16,(x-first)*24,16,c);}}for(int i=0;i<7;i++){int radius=18+(int)((t/40+i*17)%98);int x=320+sn(a+i*32)*radius/1024,y=180+sn(a+i*32+64)*radius/1400;sprite(e,i,x,y);}}
static void storm(b16_engine *e,uint32_t t,unsigned count){for(unsigned i=0;i<count;i++){unsigned a=(unsigned)(t/(15+i%7)+i*29);int x=304+sn(a)*(270-(int)(i%7)*8)/1024,y=174+sn(a*2+i*11)*82/1024;sprite(e,(int)i&7,x,y);}}
static void vector_geometry(b16_engine *e,uint32_t t){
 static const uint8_t cube_edges[12][2]={{0,1},{1,3},{3,2},{2,0},{4,5},{5,7},{7,6},{6,4},{0,4},{1,5},{2,6},{3,7}};
 static const uint8_t octa_edges[12][2]={{0,1},{0,3},{0,2},{0,4},{5,1},{5,3},{5,2},{5,4},{1,2},{1,4},{3,2},{3,4}};
 static const int8_t octa[6][3]={{-65,0,0},{0,-65,0},{0,0,-65},{0,65,0},{0,0,65},{65,0,0}};
 if(t>=14000){
  for(int ring=0;ring<6;ring++){
   int radius=18+(int)((t/32+ring*37)%232),px[4],py[4];
   unsigned angle=t/40+(unsigned)ring*8;
   for(int i=0;i<4;i++){px[i]=320+sn(angle+i*64)*radius/1024;py[i]=186+sn(angle+i*64+64)*radius/3072;}
   for(int i=0;i<4;i++)line(e,px[i],py[i],px[(i+1)&3],py[(i+1)&3],3+ring);
  }

  return;
 }
 int px[8],py[8],count=t>=7000?6:8;
 const uint8_t (*edges)[2]=t>=7000?octa_edges:cube_edges;
 for(int o=0;o<3;o++){
  unsigned a=t/21+o*17,b=t/33+o*11;
  for(int i=0;i<count;i++){
   int x=t>=7000?octa[i][0]:((i&1)?50:-50);
   int y=t>=7000?octa[i][1]:((i&2)?50:-50);
   int z=t>=7000?octa[i][2]:((i&4)?50:-50);
   int xx=(x*sn(a+64)-z*sn(a))/1024,zz=(x*sn(a)+z*sn(a+64))/1024;
   int yy=(y*sn(b+64)-zz*sn(b))/1024;z=(y*sn(b)+zz*sn(b+64))/1024+240;
   px[i]=120+o*200+xx*180/z;py[i]=188+yy*180/z;
  }
  for(int i=0;i<12;i++)line(e,px[edges[i][0]],py[edges[i][0]],px[edges[i][1]],py[edges[i][1]],o==1?10:12-o*3);
 }
}
static void vectors(b16_engine *e,uint32_t t){BPUSH(B16_MASK);memset(vector_mask,0,sizeof vector_mask);BPUSH(B16_GEOMETRY);vector_geometry(e,t);BPOP();BPOP();vector_flush(e);if(t>=17500)waving_logo(e,t);}
static void lettering(b16_engine *e,int x,int y,const char *s,int scale,int c){
 for(;*s;s++,x+=8*scale){
  if((unsigned char)*s<32||(unsigned char)*s>127)continue;
  const uint8_t *rows=&ascii_rows[(*s-32)*8];
#if B16_MERGE_LETTERING
  // dot rejects whole rectangles at the stage boundary. Preserve that exact
  // behavior with the original row path for a partially clipped glyph.
  if(scale>0 && x>=16 && y>=88 && (int64_t)x+8*(int64_t)scale<=624 && (int64_t)y+8*(int64_t)scale<=280){
   uint8_t done[8]={0};
   for(int j=0;j<8;j++)for(int i=0;i<8;){
    if(!(rows[j]&(128>>i))||(done[j]&(128>>i))){i++;continue;}
    int first=i;while(i<8&&(rows[j]&(128>>i))&&!(done[j]&(128>>i)))i++;
    unsigned mask=((255u>>(unsigned)first)&(255u<<(8-i)))&255u;int bottom=j+1;
    while(bottom<8&&(rows[bottom]&mask)==mask&&!(done[bottom]&mask))bottom++;
    for(int k=j;k<bottom;k++)done[k]|=(uint8_t)mask;
    dot(e,x+first*scale,y+j*scale,(i-first)*scale,(bottom-j)*scale,c);
   }
   continue;
  }
#endif
  for(int j=0;j<8;j++)for(int i=0;i<8;){
   if(!(rows[j]&(128>>i))){i++;continue;}
   int first=i;while(i<8&&(rows[j]&(128>>i)))i++;
   dot(e,x+first*scale,y+j*scale,(i-first)*scale,scale,c);
  }
 }
}
static void caption(b16_engine *e,const char *s){
 fs(e,e->page,24,282,560,13,0);int x=32;
 for(;*s;s++,x+=8){uint8_t done[8]={0};const uint8_t *rows=&ascii_rows[(*s-32)*8];
  for(int j=0;j<8;j++)for(int i=0;i<8;){
   if(!(rows[j]&(128>>i))||(done[j]&(128>>i))){i++;continue;}
   int first=i;while(i<8&&(rows[j]&(128>>i))&&!(done[j]&(128>>i)))i++;
   unsigned mask=((255u>>(unsigned)first)&(255u<<(8-i)))&255u;int bottom=j+1;
   while(bottom<8&&(rows[bottom]&mask)==mask&&!(done[bottom]&mask))bottom++;
   for(int k=j;k<bottom;k++)done[k]|=(uint8_t)mask;
   fs(e,e->page,x+first,284+j,i-first,bottom-j,11);
  }
 }
}
static const uint32_t boundaries[]={0,10000,30000,50000,70000,95000,120000,140000,150000};
static const char *names[]={"00 / BOOT SEQUENCE","01 / HYPERSPACE","02 / RASTER WAVES","03 / PLASMA ENGINE","04 / ROTOZOOM","05 / BLIT STORM","06 / VECTOR WORLD","07 / BEYOND 16 COLORS"};
size_t b16_size(void){return sizeof(b16_engine);}
const b16_stats *b16_statistics(b16_engine *e){return &e->stats;}
void b16_load_test(b16_engine *e,unsigned stars_count,unsigned objects){e->stars=stars_count>256?256:stars_count;e->objects=objects>128?128:objects;}
int b16_init(b16_engine *e,kfb_device *g,uint32_t seed){if(!e||!g)return KFB_ARGUMENT;memset(e,0,sizeof *e);memset(e->vector_previous,255,sizeof e->vector_previous);e->gpu=g;e->seed=seed;
#if B16_COOP
star_seed=seed;star_seed_ready=0;
#endif
e->scene=-1;e->page_scene[0]=e->page_scene[1]=-1;e->page=1;e->stars=64;e->objects=32;int r=kfb_probe(g);uint8_t id[7];if(!r&&g->io.read(g->io.context,0,true,id,7))r=KFB_IO;if(!r&&(id[4]!=1||id[5]!=4||id[6]!=255))r=KFB_VERSION;if(!r)r=b16_audio_stop(g);if(!r)r=b16_assets(g);for(unsigned i=0;i<16&&!r;i++)r=kfb_palette(g,i,b16_pal[i]);if(!r)r=kfb_present(g,1);memcpy(e->palette_cache,b16_pal,sizeof e->palette_cache);e->stats.upload_bytes=636928;e->error=r;return r;}
static bool frame_due(b16_engine *e,uint32_t ms){if(ms<e->next_frame)return false;if(e->next_frame&&ms>e->next_frame+34)e->stats.skipped+=(ms-e->next_frame)/34;
#if B16_SCHEDULER == 1
/* ceil(next slot * 1000/30), skip stale slots without accumulating drift. */
e->next_frame=(((ms*30u)/1000u+1u)*1000u+29u)/30u;
#else
e->next_frame=ms+33;
#endif
return true;}
int b16_tick(b16_engine *e,uint32_t ms){if(!e||e->error)return e?e->error:KFB_ARGUMENT;if(ms>=B16_DURATION)return 0;BPUSH(B16_SCHEDULE);bool due=frame_due(e,ms);BPOP();if(!due)return 0;e->stats.now_ms=ms;if(!e->started){int r=b16_audio(e->gpu,-1);if(r)return e->error=r;e->started=1;e->audio_epoch_ms=e->gpu->io.now_ms(e->gpu->io.context);}
 int scene=0;while(scene<7&&ms>=boundaries[scene+1])scene++;if(scene!=e->scene){e->scene=scene;int r=b16_audio(e->gpu,scene);if(r)return e->error=r;}
 e->stats.scene=(uint32_t)scene;uint32_t t=ms-boundaries[scene];e->page^=1;if(!(scene==7&&t>=3000&&e->final_ready[e->page])&&!(scene==3&&e->page_scene[e->page]==3)&&!(scene==6&&e->page_scene[e->page]==6))clear_dirty(e);if(scene==6&&e->page_scene[e->page]!=6)memset(e->vector_previous[e->page],255,sizeof e->vector_previous[e->page]);if(scene==3&&e->page_scene[e->page]!=3)memset(e->plasma_cache[e->page],255,sizeof e->plasma_cache[e->page]);if(e->page_scene[e->page]!=scene){caption(e,names[scene]);e->page_scene[e->page]=scene;}
 switch(scene){case 0:stars(e,ms,48);storm(e,ms,8);break;case 1:stars(e,ms,e->stars);break;case 2:waves(e,t);waving_logo(e,t);break;case 3:plasma_effect(e,t);break;case 4:roto(e,t);break;case 5:{unsigned n=e->objects?e->objects:(8u<<((t/5000)%5));storm(e,t,n);break;}case 6:vectors(e,t);break;case 7:if(t<3000){stars(e,ms,32);storm(e,t,8);waving_logo(e,t);}else if(!e->final_ready[e->page]){fs(e,e->page,24,282,560,13,0);e->final_ready[e->page]=1;lettering(e,192,98,"KAGURA-HD",3,10);lettering(e,128,128,"BEYOND 16 COLORS",3,12);const char *s[]={"ONE TINY FPGA.","A WHOLE WORLD OF PIXELS.","640X360 / 16 COLORS","720p60 HDMI / PCM 2CH / 48kHz","RP2040 + TANG NANO 9K"};for(int i=0;i<5;i++)lettering(e,88,170+i*21,s[i],2,i<2?11:9);}break;}

 // Palette shadow applies with the following PRESENT, never per scanline.
 if(e->error){e->stats.error=e->error;return e->error;}
 unsigned idx=6+(ms/500)%4;unsigned value=b16_pal[6+((ms/500+scene)%4)];int r=0;if(e->palette_cache[idx]!=value){r=kfb_palette(e->gpu,idx,value);if(!r)e->palette_cache[idx]=(uint16_t)value;e->stats.commands++;}if(!r&&!e->error)r=kfb_present(e->gpu,e->page);e->stats.commands++;if(r)e->error=r;
 if(ms-e->last_audio_poll>=1000&&!e->error){e->error=b16_audio_poll(e->gpu);e->last_audio_poll=ms;}e->stats.frames++;e->stats.error=e->error;return e->error;}
int b16_finish(b16_engine *e){if(!e)return KFB_ARGUMENT;return b16_audio_stop(e->gpu);}


