// SPDX-License-Identifier: Apache-2.0
#include "mt_device.h"
#include <stdio.h>
#include <string.h>
/* One bounded campaign. First mismatch stops; no stimulus replay. */
int mt_preflight(kfb_device *gpu){
 uint8_t id[7];int r=kfb_probe(gpu);if(r)return r;
 if(gpu->io.read(gpu->io.context,0,true,id,7))return KFB_IO;
 printf("IDENTITY %.4s ABI=%u.%u CAPS=%02x\n",id,id[4],id[5],id[6]);
 if(memcmp(id,"KFB1",4)||id[4]!=1||id[5]!=4||id[6]!=255)return KFB_VERSION;
 const unsigned offsets[]={0,1,2,3,30,31,32,60,61,62,63,64};
 const unsigned lengths[]={1,3,4,8,32,64};
 uint8_t expected[256],actual[256],data[64];unsigned cases=0;
 for(unsigned i=0;i<12;i++)for(unsigned j=0;j<6;j++){
  memset(expected,0xa5,sizeof expected);
  r=kfb_write_bytes(gpu,0x3e000,expected,sizeof expected);if(r)return r;
  for(unsigned k=0;k<lengths[j];k++)data[k]=(uint8_t)((k*73+offsets[i]*11+lengths[j])^0x5a);
  memcpy(expected+offsets[i],data,lengths[j]);
  r=kfb_write_bytes(gpu,0x3e000+offsets[i],data,lengths[j]);if(r)return r;
  r=kfb_read_bytes(gpu,0x3e000,actual,sizeof actual);if(r)return r;
  for(unsigned k=0;k<sizeof actual;k++)if(expected[k]!=actual[k]){
   printf("PREFLIGHT FAIL case=%u offset=%u length=%u byte=%u expected=%02x actual=%02x\n",cases,offsets[i],lengths[j],k,expected[k],actual[k]);return KFB_DEVICE;
  }
  cases++;
 }
 printf("PREFLIGHT PSRAM PASS cases=%u guards=256 scratch=0x3e000\n",cases);
 r=kfb_fill_rect(gpu,0,0,0,16,8,0);if(r)return r;
 r=kfb_fill_rect(gpu,0,1,1,3,2,7);if(r)return r;
 for(unsigned y=0;y<4;y++){
  r=kfb_read_bytes(gpu,y*320,actual,8);if(r)return r;
  memset(expected,0,8);if(y==1||y==2){expected[0]=7;expected[1]=0x77;}
  if(memcmp(expected,actual,8)){printf("PREFLIGHT FILL FAIL y=%u\n",y);return KFB_DEVICE;}
 }
 r=kfb_copy_rect(gpu,0,0,0,1,8,8,8,4);if(r)return r;
 for(unsigned y=0;y<4;y++){
  r=kfb_read_bytes(gpu,y*320,expected,4);if(r)return r;
  r=kfb_read_bytes(gpu,115200+(8+y)*320+4,actual,4);if(r)return r;
  if(memcmp(expected,actual,4)){printf("PREFLIGHT BLIT FAIL y=%u\n",y);return KFB_DEVICE;}
 }
 printf("PREFLIGHT GPU PASS odd_x_fill=1 page_blit=1\n");return 0;
}
