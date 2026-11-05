// SPDX-License-Identifier: Apache-2.0
// Behavioral PC register model: no PSRAM arbitration, PIO time or HDMI timing.
#include "b16.h"
#include <stdio.h>
#include <string.h>
static uint8_t memory[4194304],stage[16],data_window[64],shadow[256],active[256],pcm[2],index_reg;
static uint16_t palette[16],display_palette[16],tag;
static unsigned pointer_reg,page,polls,done,pending;
static uint32_t clock_ms;
static int injected_error,device_error,sticky,late,hold,fail_write;
static uint64_t counts[16];
static FILE *trace;
static kfb_device gpu;static b16_engine engine;static b16_bus bus;
static unsigned u16(const uint8_t *p){return p[0]|((unsigned)p[1]<<8);}
static uint32_t u32(const uint8_t *p){return u16(p)|((uint32_t)u16(p+2)<<16);}
static void fill(unsigned p,unsigned x,unsigned y,unsigned w,unsigned h,unsigned c){for(unsigned j=y;j<y+h;j++){uint8_t *row=memory+p*PAGE_BYTES+j*320;unsigned a=x,b=x+w;if(a&1){row[a/2]=(uint8_t)((row[a/2]&240)|c);a++;}if(b&1){b--;row[b/2]=(uint8_t)((row[b/2]&15)|(c<<4));}if(b>a)memset(row+a/2,(int)(c*17),(b-a)/2);}}
static void finish(void){unsigned op=stage[0],arg=stage[1];device_error=injected_error;injected_error=0;tag=(uint16_t)u16(stage+2);counts[2]++;if(trace){fprintf(trace,"{\"descriptor\":\"");for(int i=0;i<16;i++)fprintf(trace,"%02x",stage[i]);fprintf(trace,"\"}\n");}
 if(!device_error)switch(op){case 0:break;case 1:{unsigned x=u16(stage+4),y=u16(stage+6),w=u16(stage+8),h=u16(stage+10);if(arg>1||x+w>640||y+h>360||stage[12]>15){device_error=3;break;}fill(arg,x,y,w,h,stage[12]);break;}
 case 2:if(arg>15)device_error=3;else palette[arg]=(uint16_t)u16(stage+4);break;
 case 3:if(arg>1)device_error=3;else{page=arg;memcpy(display_palette,palette,sizeof palette);counts[3]++;}break;
 case 4:case 5:{uint32_t a=u32(stage+4);unsigned n=arg*4;if(!arg||arg>16||a%4||a+n>sizeof memory){device_error=3;break;}if(op==4){for(unsigned i=0;i<n;i++)if(!(stage[8+i/8]&(1u<<(i%8))))memory[a+i]=data_window[i];counts[5]+=n;}else {memcpy(data_window,memory+a,n);pointer_reg=0;}break;}
 case 6:{unsigned sx=u16(stage+4),sy=u16(stage+6),dx=u16(stage+8),dy=u16(stage+10),w=u16(stage+12),h=u16(stage+14);if(arg>3||sx+w>640||dx+w>640||sy+h>360||dy+h>360||((sx|dx|w)&1)||((sx^dx)&7)){device_error=3;break;}unsigned sp=arg&1,dp=(arg>>1)&1;int first=0,end=(int)h,step=1;if(sp==dp&&dy>sy){first=(int)h-1;end=-1;step=-1;}for(int j=first;j!=end;j+=step)memmove(memory+dp*PAGE_BYTES+(dy+j)*320+dx/2,memory+sp*PAGE_BYTES+(sy+j)*320+sx/2,w/2);counts[4]+=(uint64_t)w*h;break;}
 case 7:memcpy(active,shadow,256);for(unsigned ch=0;ch<2;ch++)if(active[0x6e + ch*32]&1)pcm[ch]|=2;break;
 default:device_error=2;}
 sticky=device_error;pending=0;done=1;if(device_error)counts[6]++;
}
static int read_reg(void *ctx,uint8_t reg,bool inc,uint8_t *v,size_t n){(void)ctx;counts[0]++;counts[1]+=n+3;for(size_t i=0;i<n;i++){unsigned val=0;if(reg==27){if(pending&&!hold&&!--polls)finish();val=2|(pending?1:0)|(done?16:0)|(late?128:0);}else if(reg<7){static const uint8_t id[7]={'K','F','B','1',1,4,255};val=id[reg];}else if(reg==7)val=sticky;else if(reg==28)val=tag&255;else if(reg==29)val=tag>>8;else if(reg==30)val=device_error;else if(reg==24){if(pointer_reg>=64)return -1;val=data_window[pointer_reg++];}else if(reg==55)val=index_reg==0x6f?pcm[0]:index_reg==0x8f?pcm[1]:shadow[index_reg];else return -1;v[i]=(uint8_t)val;if(inc)reg++;}return 0;}
static int write_reg(void *ctx,uint8_t reg,bool inc,const uint8_t *v,size_t n){(void)ctx;counts[0]++;counts[1]+=n+1;for(size_t i=0;i<n;i++){if(fail_write&&reg==26){fail_write=0;return -1;}if(reg==7)sticky=0;else if(reg==31)done=0;else if(reg==54)index_reg=v[i];else if(reg==55){if(index_reg==0x6f||index_reg==0x8f){unsigned ch=(index_reg-0x6f)/32,b=0x60+ch*32;if(v[i]==2)pcm[ch]=0;else if(v[i]==4)pcm[ch]&=7;else if(v[i]==1){uint32_t s=u32(shadow+b)&0x3fffff,e=u32(shadow+b+4)&0x3fffff,l=u32(shadow+b+8)&0x3fffff;pcm[ch]=(s<e&&e<=0x3fffff&&l>=s&&l<e)?1:16;}}else shadow[index_reg]=v[i];}
 else {if(pending){counts[7]++;return -1;}if(reg>=8&&reg<24)stage[reg-8]=v[i];else if(reg==25)pointer_reg=v[i];else if(reg==24){if(pointer_reg>=64)return -1;data_window[pointer_reg++]=v[i];}else if(reg==26){pending=1;polls=3;done=0;}else return -1;}if(inc)reg++;}return 0;}
static uint32_t now(void *ctx){(void)ctx;return clock_ms++;}
API int pc_init(uint32_t seed,int cached){if(trace){fclose(trace);trace=NULL;}memset(memory,0,sizeof memory);memset(counts,0,sizeof counts);memset(shadow,0,sizeof shadow);memset(active,0,sizeof active);memset(pcm,0,sizeof pcm);memset(palette,0,sizeof palette);pending=done=polls=pointer_reg=clock_ms=0;tag=65535;injected_error=device_error=sticky=late=hold=fail_write=0;kfb_io raw={NULL,read_reg,write_reg,now};int r=kfb_init(&gpu,cached?b16_cached_io(&bus,raw):raw,100);if(!r)r=b16_init(&engine,&gpu,seed);return r;}
API int pc_tick(uint32_t ms){return b16_tick(&engine,ms);}
API void pc_load(unsigned stars,unsigned objects){b16_load_test(&engine,stars,objects);}
API const uint8_t *pc_memory(void){return memory;}
API const uint16_t *pc_palette(void){return display_palette;}
API unsigned pc_page(void){return page;}
API const uint64_t *pc_counts(void){return counts;}
API const b16_stats *pc_stats(void){return &engine.stats;}
API int pc_finish(void){return b16_finish(&engine);}
API void pc_trace(const char *path){if(trace)fclose(trace);trace=path?fopen(path,"w"):NULL;}
API void pc_fault(int mode){if(mode==1)injected_error=3;if(mode==2)late=1;if(mode==3)hold=1;if(mode==4)fail_write=1;}
API int pc_bench(int op,unsigned n){uint8_t buf[512]={0};int r=0;switch(op){case 0:return kfb_fence(&gpu);case 1:return kfb_fill_rect(&gpu,0,32,96,(int)n,16,9);case 2:return kfb_copy_rect(&gpu,0,0,320,0,32,128,32,32);case 3:return kfb_present(&gpu,0);case 4:return kfb_write_bytes(&gpu,0x100000,buf,n);case 5:return kfb_read_bytes(&gpu,0x100000,buf,n);case 6:return b16_audio(&gpu,1);case 7:return kfb_palette(&gpu,6,0xf0f);default:r=KFB_ARGUMENT;}return r;}

