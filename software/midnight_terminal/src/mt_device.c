// SPDX-License-Identifier: Apache-2.0
#include "mt_device.h"
#include <string.h>
/* All PCM addresses are die-relative bytes, exclusive END <= 0x3fffff. */
static const uint32_t addr[]={0x80000,0xde000,0xe0000,0xe1000,0xe5000};
#ifdef MT_COMPRESSED_BGM
int mt_upload_bgm(kfb_device *gpu);
#endif
static int aw(mt_device *d,uint8_t i,uint8_t v){uint8_t p[]={i,v};return d->gpu->io.write(d->gpu->io.context,54,true,p,2)?KFB_IO:0;}
static int ar(mt_device *d,uint8_t i,uint8_t *v){if(d->gpu->io.write(d->gpu->io.context,54,false,&i,1))return KFB_IO;return d->gpu->io.read(d->gpu->io.context,55,false,v,1)?KFB_IO:0;}
static int wait_status(mt_device *d,int ch,int ready){uint32_t begin=d->gpu->io.now_ms(d->gpu->io.context);for(;;){uint8_t s=0;int r=ar(d,(uint8_t)(0x6f+ch*32),&s);if(r)return r;if(ready&&(s&0x38))return KFB_DEVICE;if(ready?(s&1):!(s&0x42))return 0;if((uint32_t)(d->gpu->io.now_ms(d->gpu->io.context)-begin)>=d->gpu->timeout_ms)return KFB_TIMEOUT;}}
static int commit(mt_device *d){
 /* COMMIT snapshots BOTH channels. Reapply owned channel shadows every time. */
 int r=0;for(int ch=0;ch<2&&!r;ch++){unsigned b=0x60+ch*32;r=aw(d,(uint8_t)(b+12),d->gain[ch]);if(!r)r=aw(d,(uint8_t)(b+13),d->gain[ch]);if(!r)r=aw(d,(uint8_t)(b+14),(uint8_t)(d->enabled[ch]|(ch==0?2:0)));}
 if(!r)r=aw(d,0xe0,180);
 uint8_t c[16]={7};uint16_t tag=0;if(!r)r=kfb_submit(d->gpu,c,0,0,&tag);if(!r)r=kfb_wait(d->gpu,tag);return r;
}
int mt_device_poll(mt_device *d){if(!d->audio_available)return d->audio_error;for(int ch=0;ch<2;ch++){uint8_t s=0;int r=ar(d,(uint8_t)(0x6f+ch*32),&s);if(r||(s&0x38)){d->audio_error=r?r:KFB_DEVICE;d->audio_available=0;aw(d,0x6f,2);aw(d,0x8f,2);return d->audio_error;}}return 0;}
static int play(mt_device *d,int id,int gain){
 if(!d->audio_available)return 0;
 int ch=id==0?0:1;int r=0;
 if(id<0){for(int c=0;c<2&&!r;c++){d->enabled[c]=0;r=aw(d,(uint8_t)(0x6f+c*32),2);if(!r)r=wait_status(d,c,0);}if(!r)r=commit(d);
 return r;}
 if(id>4)return KFB_ARGUMENT;
 if(id==0&&d->enabled[0]){d->gain[0]=(uint8_t)gain;return commit(d);}
 unsigned b=0x60+ch*32;uint32_t n;mt_sound(id,&n);
 r=aw(d,(uint8_t)(b+15),2);if(!r)r=wait_status(d,ch,0);if(!r)r=aw(d,(uint8_t)(b+15),4);
 uint32_t value[]={addr[id],addr[id]+n,addr[id]};
 for(int k=0;k<3&&!r;k++)for(int i=0;i<3&&!r;i++)r=aw(d,(uint8_t)(b+k*4+i),(uint8_t)(value[k]>>(8*i)));
 d->gain[ch]=(uint8_t)gain;d->enabled[ch]=1;
 if(!r)r=aw(d,(uint8_t)(b+14),(uint8_t)(ch==0?2:0));
 if(!r)r=aw(d,(uint8_t)(b+15),1);
 if(!r)r=wait_status(d,ch,1);
 if(!r)r=commit(d);
 return r;
}
int mt_device_start(mt_device *d,kfb_device *gpu){
 memset(d,0,sizeof *d);d->gpu=gpu;int r=kfb_probe(gpu);if(r)return r;uint8_t id[7];if(gpu->io.read(gpu->io.context,0,true,id,7))return KFB_IO;
 if(id[4]!=1||id[5]!=4||(id[6]&0x7f)!=0x7f)return KFB_VERSION;
 d->audio_available=(id[6]&0x80)!=0;
 if(d->audio_available){for(int ch=0;ch<2&&!r;ch++){r=aw(d,(uint8_t)(0x6f+ch*32),2);if(!r)r=wait_status(d,ch,0);if(!r)r=aw(d,(uint8_t)(0x6f+ch*32),4);}
#ifdef MT_COMPRESSED_BGM
 if(!r)r=mt_upload_bgm(gpu);
 int first=1;
#else
 int first=0;
#endif
 for(int i=first;i<5&&!r;i++){uint32_t n;const uint8_t *p=mt_sound(i,&n);r=kfb_write_bytes(gpu,addr[i],p,n);}if(!r)r=kfb_fence(gpu);if(r){d->audio_error=r;d->audio_available=0;r=0;}}
 /* Cursor shape: original small chevron, index 0 transparent, MSB-first 2bpp. */
 uint8_t shape[256]={0};uint16_t colors[]={0x9dc,0xa58,0xeed};for(int y=0;y<9;y++)for(int x=0;x<=4-(y>4?y-4:4-y);x++)shape[y*8+x/4]|=(uint8_t)(1u<<(6-2*(x%4)));
 if(!r)r=kfb_cursor_shape(gpu,1,shape,colors,0,0);
 return r;
}
int mt_device_emit(void *ctx,int op,const int32_t *a,const uint8_t *p,uint32_t n){
 mt_device *d=ctx;kfb_device *g=d->gpu;int r=0;uint32_t before=g->io.now_ms(g->io.context);
 switch(op){
 case MT_FILL:r=kfb_fill_rect(g,(unsigned)a[0],a[1],a[2],a[3],a[4],(unsigned)a[5]);break;
 case MT_BLIT:r=kfb_copy_rect(g,(unsigned)a[0],a[1],a[2],(unsigned)a[3],a[4],a[5],a[6],a[7]);break;
 case MT_WRITE:r=kfb_write_bytes(g,(uint32_t)a[0],p,n);break;
 case MT_PALETTE:r=kfb_palette(g,(unsigned)a[0],(unsigned)a[1]);break;
 case MT_PRESENT:r=kfb_present(g,(unsigned)a[0]);break;
 case MT_AUDIO:r=play(d,a[0],a[1]);if(r){d->audio_error=r;d->audio_available=0;/* Bounded silence fallback; never retry uncertain transactions. */}r=0;break;
 case MT_CURSOR:r=kfb_cursor_move(g,a[0],a[1],1,a[2]!=0);break;
 default:r=KFB_ARGUMENT;
 }d->waits_ms+=g->io.now_ms(g->io.context)-before;return r;
}
