// SPDX-License-Identifier: Apache-2.0
#include "mt_lz.h"
#include "../../kagura_fb/kagura_fb.h"
#include <string.h>
static uint8_t history[32768]; // startup only, never a full PCM or framebuffer
int mt_lz_decode(const uint8_t *src,uint32_t size,uint32_t expected,mt_lz_sink sink,void *ctx){
 if(!src||!sink)return KFB_ARGUMENT;
 uint32_t pos=0,written=0;uint8_t chunk[64];
 while(pos<size){
  unsigned control=src[pos++],count,back=0;
  if(control<128){count=control+1;if(count>size-pos)return KFB_ARGUMENT;}
  else{count=(control&127)+3;if(size-pos<2)return KFB_ARGUMENT;back=1u+src[pos]+((unsigned)src[pos+1]<<8);pos+=2;if(back>32768||back>written)return KFB_ARGUMENT;}
  if(written>expected||count>expected-written)return KFB_ARGUMENT;
  for(unsigned i=0;i<count;i++){
   uint8_t value=back?history[(written-back)&32767]:src[pos++];
   history[written&32767]=value;chunk[written&63]=value;written++;
   if(!(written&63)){int r=sink(ctx,chunk,64);if(r)return r;}
  }
 }
 if(written!=expected)return KFB_ARGUMENT;
 if(written&63)return sink(ctx,chunk,written&63);
 return 0;
}
#ifdef MT_COMPRESSED_BGM
#include "../generated/bgm-lz.inc"
typedef struct {kfb_device *gpu;uint32_t address;} uploader;
static int upload_chunk(void *ctx,const uint8_t *data,uint32_t n){
 uploader *u=ctx;uint8_t actual[64];int r=kfb_write_bytes(u->gpu,u->address,data,n);
 if(!r)r=kfb_read_bytes(u->gpu,u->address,actual,n);
 if(!r&&memcmp(data,actual,n))r=KFB_DEVICE;
 if(!r)u->address+=n;
 return r;
}
int mt_upload_bgm(kfb_device *gpu){uploader u={gpu,0x80000};return mt_lz_decode(bgm_lz,sizeof bgm_lz,384000,upload_chunk,&u);}
#endif
