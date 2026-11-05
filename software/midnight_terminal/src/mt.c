// SPDX-License-Identifier: Apache-2.0
#include "mt.h"
#include <string.h>
#include "../generated/counts.h"
#include "../generated/assets.inc"
#include "../generated/story.inc"
size_t mt_size(void){return sizeof(mt_engine);}
uint32_t mt_decode(const char **s){
 const unsigned char *p=(const unsigned char *)*s; uint32_t c=*p; unsigned n;
 if(!c)return 0;
 if(c<128){(*s)++;return c;}
 if(c>=0xc2&&c<=0xdf){n=1;c&=31;}else if(c>=0xe0&&c<=0xef){n=2;c&=15;}else if(c>=0xf0&&c<=0xf4){n=3;c&=7;}else{(*s)++;return 0xfffd;}
 for(unsigned i=1;i<=n;i++){if((p[i]&0xc0)!=0x80){(*s)++;return 0xfffd;}c=(c<<6)|(p[i]&63);}
 if((n==1&&c<128)||(n==2&&c<2048)||(n==3&&c<65536)||c>0x10ffff||(c>=0xd800&&c<=0xdfff)){(*s)++;return 0xfffd;}
 *s+=(n+1);return c;
}
const mt_glyph *mt_lookup(uint32_t cp,int small){
 const mt_glyph *f=small?mt_misaki:mt_mplus;unsigned lo=0,hi=MT_GLYPHS;
 while(lo<hi){unsigned m=(lo+hi)/2;if(f[m].cp<cp)lo=m+1;else hi=m;}
 if(lo<MT_GLYPHS&&f[lo].cp==cp)return &f[lo];
 return mt_lookup('?',small);
}
static int closing(uint32_t c){return c==0x3001||c==0x3002||c==0xff01||c==0xff1f||c==0x300d||c==0x300f||c==0xff09;}
static int opening(uint32_t c){return c==0x300c||c==0x300e||c==0xff08;}
int mt_layout(const char *s,int width,int small,int16_t *xx,int16_t *yy,uint32_t *cc,int cap){
 int x=0,y=0,n=0,h=small?8:17;uint32_t prev=0;
 while(*s&&n<cap){uint32_t c=mt_decode(&s);if(c=='\n'){x=0;y+=h;prev=0;continue;}int w=small?8:mt_lookup(c,0)->advance;
 const char *look=s;uint32_t next=mt_decode(&look);int nw=next?(small?8:mt_lookup(next,0)->advance):0;uint32_t third=mt_decode(&look);
 int reserve=opening(c)&&closing(third)?(small?8:mt_lookup(third,0)->advance):0;
 if(x&&(x+w>width || (closing(next)&&x+w+nw>width) || (opening(c)&&x+w+nw+reserve>width))){x=0;y+=h;}
 (void)prev;xx[n]=(int16_t)x;yy[n]=(int16_t)y;cc[n++]=c;x+=w;prev=c;
 }return n;
}
static int cmd(mt_engine *e,int op,int32_t *a,const uint8_t *d,uint32_t n){if(e->error)return e->error;e->commands++;if(op==MT_WRITE)e->bytes+=n;int r=e->emit(e->ctx,op,a,d,n);if(r)e->error=r;return r;}
static void fill(mt_engine *e,int p,int x,int y,int w,int h,int c){int32_t a[]={p,x,y,w,h,c};cmd(e,MT_FILL,a,0,0);}
static void write_mem(mt_engine *e,uint32_t addr,const uint8_t *p,uint32_t n){int32_t a[]={(int32_t)addr};cmd(e,MT_WRITE,a,p,n);}
static void copy(mt_engine *e,int s,int sx,int sy,int d,int dx,int dy,int w,int h){int32_t a[]={s,sx,sy,d,dx,dy,w,h};cmd(e,MT_BLIT,a,0,0);}
static void present(mt_engine *e,int p){int32_t a[]={p};cmd(e,MT_PRESENT,a,0,0);e->presents++;e->page=p;}
#include "../generated/palette.inc"
static void palette(mt_engine *e,int anomaly,int fade){for(int i=0;i<16;i++){uint16_t c=normal_pal[i];if(anomaly){c=i==0?0:i==13?0x833:i==11?0x9cc:i==7?0xcbb:0x211;}unsigned r=(c>>8)*fade/16,g=((c>>4)&15)*fade/16,b=(c&15)*fade/16;int32_t a[]={i,(int32_t)((r<<8)|(g<<4)|b)};cmd(e,MT_PALETTE,a,0,0);}}
static void glyph(mt_engine *e,int p,int x,int y,uint32_t cp,int small,int color){
 const mt_glyph *g=mt_lookup(cp,small);int w=small?8:g->advance,h=small?8:13;
 /* Local clipping; even aligned glyph rectangles, no transparent GPU assumption. */
 for(int j=0;j<h;j++){if(y+j<0||y+j>=360)continue;for(int i=0;i<w;i++){if(!(g->rows[j]&(1u<<(15-i))))continue;if(x+i>=0&&x+i<640)fill(e,p,x+i,y+j,1,1,color);}}
}
static void text_span(mt_engine *e,int p,int x,int y,const char *s,int first,int count,int small,int color,int width){
 int16_t xx[128],yy[128];uint32_t cc[128];int n=mt_layout(s,width,small,xx,yy,cc,128);if(count<n)n=count;
 int h=small?8:13;int bg=small?(e->scene==3?15:0):(e->scene==6?0:(e->scene==2&&y<262&&color==11?8:1));
 /* One small scanline buffer; no RP2040 framebuffer. Opaque known UI background. */
 for(int i=first;i<n;i++){
  const mt_glyph *g=mt_lookup(cc[i],small);int w=small?8:g->advance,dx=x+xx[i],dy=y+yy[i];
  if(dx<0||dx+w>640||dy<0||dy+h>329)continue;
  if(dx&1){glyph(e,p,dx,dy,cc[i],small,color);continue;}
  for(int j=0;j<h;j++){uint8_t row[6];for(int k=0;k<w;k+=2){unsigned a=g->rows[j]&(1u<<(15-k))?color:bg,b=g->rows[j]&(1u<<(14-k))?color:bg;row[k/2]=(uint8_t)((a<<4)|b);}write_mem(e,(uint32_t)p*115200+(dy+j)*320+dx/2,row,(uint32_t)w/2);}
 }
}
static void text(mt_engine *e,int p,int x,int y,const char *s,int count,int small,int color,int width){text_span(e,p,x,y,s,0,count,small,color,width);}
static void final_warning(mt_engine *e,int p){
 /* Exact 2x nearest-neighbour Misaki bitmap; still the same independent font. */
 uint32_t cp[40];const char *s=mt_last;int n=0;while(*s&&n<40)cp[n++]=mt_decode(&s);
 int width=n*16,x=((640-width)/2)&~1;
 for(int y=0;y<16;y++){uint8_t row[320]={0};for(int i=0;i<n;i++){uint16_t bits=mt_lookup(cp[i],1)->rows[y/2];for(int j=0;j<8;j++)if(bits&(1u<<(15-j)))row[i*8+j]=0xbb;}write_mem(e,(uint32_t)p*115200+(172+y)*320+x/2,row,(uint32_t)width/2);}
}
const uint8_t *mt_sound(int id,uint32_t *n){
 if(id==0){*n=384000;
#ifdef MT_COMPRESSED_BGM
 return 0; // startup decoder streams exact original samples to PSRAM
#else
 return mt_pcm_bgm;
#endif
 }
 switch(id){case 1:*n=sizeof mt_pcm_select;return mt_pcm_select;case 2:*n=sizeof mt_pcm_talk;return mt_pcm_talk;case 3:*n=sizeof mt_pcm_alarm;return mt_pcm_alarm;case 4:*n=sizeof mt_pcm_restore;return mt_pcm_restore;default:*n=0;return 0;}}
static void audio(mt_engine *e,int id,int gain){int32_t a[]={id,gain};cmd(e,MT_AUDIO,a,0,0);}
static void base(mt_engine *e,int p){write_mem(e,(uint32_t)p*115200,mt_bar,sizeof mt_bar);e->last_text[p]=-1;e->last_count[p]=-1;e->last_rain[p]=-1;e->last_expression[p]=-1;}
int mt_init(mt_engine *e,mt_emit emit,void *ctx,int reduced){if(!e||!emit)return -1;memset(e,0,sizeof *e);e->emit=emit;e->ctx=ctx;e->scene=-1;e->choice=2;e->selected=-1;e->reduced_flash=reduced;e->autoplay=1;return 0;}
static int scene_at(uint32_t t){return t<12000?0:t<30000?1:t<40000?2:t<47000?3:t<65000?4:t<80000?5:6;}
static void enter(mt_engine *e,int s){
 e->scene=s;e->last_audio=-1;e->blink=-1;e->reveal_id=-1;
 /* Blank at VBlank before touching either page during scene preparation. */
 palette(e,0,0);present(e,e->page);
 for(int p=0;p<2;p++){e->last_text[p]=-1;e->last_count[p]=-1;e->last_warning[p]=-1;e->last_scroll[p]=0;e->last_rain[p]=-1;e->last_expression[p]=-1;}
 if(s==0){e->choice=2;e->selected=-1;palette(e,0,0);write_mem(e,0x40000,mt_bar,sizeof mt_bar);write_mem(e,0x60000,mt_warning,sizeof mt_warning);base(e,0);base(e,1);audio(e,0,155);}
 if(s==1||s==2||s==3||s==5){palette(e,0,16);base(e,0);base(e,1);}
 if(s==3)audio(e,0,48);
 if(s==4){palette(e,1,16);audio(e,-1,0);base(e,0);base(e,1);}
 if(s==5){audio(e,0,155);audio(e,4,150);}
 if(s==6){palette(e,0,16);fill(e,0,0,0,640,360,0);fill(e,1,0,0,640,360,0);audio(e,-1,0);}
}
int mt_tick(mt_engine *e,uint32_t ms,int key){
 if(!e||!e->emit)return -1;
 if(key==9){e->next_frame=0;e->scene=-1;ms=0;}
 e->elapsed=ms%88000;uint32_t t=e->elapsed;int s=scene_at(t);if(s!=e->scene)enter(e,s);
 if(s==2){if(e->selected<0){if(key==1)e->choice=(e->choice+2)%3;if(key==2)e->choice=(e->choice+1)%3;}if((key==3||t>=38500)&&e->selected<0){e->selected=e->choice;e->selected_at=t;audio(e,1,170);}}
 if(ms<e->next_frame)return e->error;
 e->next_frame=ms+33;e->frames++;int p=e->page^1;int dirty=0;
 if(s==0){int level=(int)(t/125);if(level>16)level=16;if(level!=e->blink){palette(e,0,level);e->blink=level;dirty=1;}if(e->last_text[p]!=0){fill(e,p,8,262,624,90,1);text(e,p,130,282,"MIDNIGHT TERMINAL",128,0,11,500);text(e,p,177,307,"A KAGURA-HD SHOWCASE",128,0,5,430);e->last_text[p]=0;dirty=1;}}
 if(s==1||s==2||s==3||s==5){
  int id=s==1?(int)((t-12000)/6000):s==2?(e->selected<0?5+e->choice:8+e->selected):s==3?3:4;
  const char *line=id<5?mt_dialogue[id]:id<8?mt_choices[id-5]:mt_branches[id-8];
  uint32_t start=s==1?12000+(uint32_t)id*6000:s==2?(e->selected<0?30000:e->selected_at):s==3?40000:65000;
  if(key==3&&s!=2)e->reveal_id=id;
  int count=e->reveal_id==id?128:(int)((t-start)/65);
  const char *end=line;int len=0;while(*end){mt_decode(&end);len++;}if(count>len)count=len;
  if(e->last_text[p]==id&&e->last_count[p]>count)count=e->last_count[p];
  if(e->last_text[p]!=id||e->last_count[p]!=count){int first=0;if(e->last_text[p]!=id||count<e->last_count[p])fill(e,p,24,280,590,49,1);else first=e->last_count[p];text_span(e,p,28,286,line,first,count,0,7,572);
   if(s==2&&e->selected>=0&&e->last_text[p]!=id)for(int yy=151;yy<228;yy++)write_mem(e,(uint32_t)p*115200+yy*320+140,mt_bar+yy*320+140,164);
   if(s==2&&e->selected<0&&e->last_text[p]!=id){fill(e,p,280,151,328,76,1);for(int i=0;i<3;i++){fill(e,p,284,155+i*23,320,21,i==e->choice?8:1);text(e,p,294,158+i*23,mt_choices[i],128,0,i==e->choice?11:6,302);}}
   e->last_text[p]=id;e->last_count[p]=count;dirty=1;
  }
  if(s==1&&count>0&&t-e->last_talk>550&&count<len){audio(e,2,50);e->last_talk=t;}
  if(s!=3){int glow=e->reduced_flash?2:(int)(t/1200)%3;if(glow!=e->blink){int32_t a[]={14,glow==0?0xc79:glow==1?0xd89:0xe8a};cmd(e,MT_PALETTE,a,0,0);e->blink=glow;dirty=1;}}
  int rain=(int)(t/33)%32;
  if(e->last_rain[p]!=rain){for(int i=0;i<2;i++){int x=306+i*65;fill(e,p,x,49,2,45,8);fill(e,p,x,50+(rain+i*3)%32,1,5,10);}e->last_rain[p]=rain;dirty=1;}
  int expression=s==3?2:(t%5100<170?1:0);
  if(e->last_expression[p]!=expression){for(int yy=119;yy<128;yy++)write_mem(e,(uint32_t)p*115200+yy*320+60,mt_bar+yy*320+60,24);
   if(expression==1){fill(e,p,120,120,48,8,6);fill(e,p,123,124,10,1,3);fill(e,p,155,124,10,1,3);}
   if(expression==2){fill(e,p,125,122,6,5,11);fill(e,p,155,122,6,5,11);fill(e,p,489,185,62,29,15);text(e,p,494,189,"0x09",128,1,13,56);}
   e->last_expression[p]=expression;dirty=1;}
  if(s==3){int level=(t>=46000)?0:16;if(level!=e->blink){palette(e,0,level);e->blink=level;dirty=1;}if(e->last_audio<0){audio(e,3,120);e->last_audio=0;}}
 }
 if(s==4){
  uint32_t a=t-47000;
  if(a<14500){int step=(int)(a/130);if(step>43)step=43;int old=e->last_warning[p];if(step!=old){
   if(old<0){fill(e,p,0,0,640,8,0);text(e,p,8,0,"FICTION / 架空ログ",128,1,11,600);old=-1;}
   /* Opaque pre-rasterized eight-pixel rows. Only newly exposed rows cross Host. */
   for(int k=old+1;k<=step;k++)write_mem(e,(uint32_t)p*115200+(uint32_t)(8+k*8)*320,mt_warning+(8+k*8)*320,2560);
   e->last_warning[p]=step;dirty=1;
  }
  if(a>=5590){int offset=(int)((a-5590)*8/130),delta=offset-e->last_scroll[p];if(delta>0){if(delta>352)delta=352;if(delta<352)copy(e,p,0,8+delta,p,0,8,640,352-delta);
   int source=(offset-delta)%352,dest=360-delta,left=delta;while(left){int rows=352-source;if(rows>left)rows=left;write_mem(e,(uint32_t)p*115200+dest*320,mt_warning+(8+source)*320,(uint32_t)rows*320);dest+=rows;left-=rows;source=0;}e->last_scroll[p]=offset;dirty=1;}}
  int blink=e->reduced_flash?0:(int)(a/1200)%2;if(blink!=e->blink){int32_t v[]={13,blink?0xb55:0x733};cmd(e,MT_PALETTE,v,0,0);e->blink=blink;dirty=1;}
  if(a>=6500&&a/2100!=(uint32_t)e->last_audio){audio(e,3,85);e->last_audio=(int)(a/2100);}
  }else if(a<17000&&e->last_text[p]!=99){fill(e,p,0,0,640,360,0);final_warning(e,p);e->last_text[p]=99;dirty=1;}
  if(a>=17000&&e->last_text[p]!=100){fill(e,p,0,0,640,360,0);e->last_text[p]=100;dirty=1;}
 }
 if(s==6&&e->last_text[p]!=88){text(e,p,175,103,"POWERED BY KAGURA-HD",128,0,11,450);text(e,p,175,146,"640 x 360 / 16 COLORS",128,0,6,450);text(e,p,175,169,"PCM 2CH / 48kHz",128,0,6,450);text(e,p,175,192,"RP2040 + TANG NANO 9K",128,0,6,450);text(e,p,175,242,"MIDNIGHT TERMINAL",128,0,14,450);e->last_text[p]=88;dirty=1;}
 if(dirty){present(e,p);int32_t a[]={s==2?274:604,s==2?164+e->choice*23:334,s!=4&&s!=6};cmd(e,MT_CURSOR,a,0,0);}
 return e->error;
}

