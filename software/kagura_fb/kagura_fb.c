// SPDX-License-Identifier: Apache-2.0
#include "kagura_fb.h"
#include <string.h>
#ifdef B16_KFB_PROFILE
#include "b16_profile.h"
#include <stdio.h>
#else
#define b16_present_mark(r) ((void)0)
#define BPUSH(r) ((void)0)
#define BPOP() ((void)0)
#endif
#define MEMORY_BYTES 4194304u
#if B16_GPU_QUEUE > 1
#include "b16_queue.h"
static int b16_queue_drain(kfb_device *dev);
#endif

static int read_regs(kfb_device *dev,uint8_t reg,bool inc,uint8_t *data,size_t size) {
    return dev->io.read(dev->io.context,reg,inc,data,size)==0 ? KFB_OK : KFB_IO;
}
static int write_regs(kfb_device *dev,uint8_t reg,bool inc,const uint8_t *data,size_t size) {
    return dev->io.write(dev->io.context,reg,inc,data,size)==0 ? KFB_OK : KFB_IO;
}
static int write_one(kfb_device *dev,uint8_t reg,uint8_t value) {
    return write_regs(dev,reg,false,&value,1);
}
static void put16(uint8_t *dst,uint16_t value) {
    dst[0]=(uint8_t)value; dst[1]=(uint8_t)(value>>8);
}
static void put32(uint8_t *dst,uint32_t value) {
    for(unsigned i=0;i<4;i++) dst[i]=(uint8_t)(value>>(i*8));
}
static int wait_idle(kfb_device *dev) {
    uint32_t started=dev->io.now_ms(dev->io.context);
    for(;;) {
        uint8_t status;
        int result=read_regs(dev,27,false,&status,1);
        if(result!=0) return result;
        if(status&128) return KFB_TRANSPORT;
        if((status&3)==2) return KFB_OK;
        if((uint32_t)(dev->io.now_ms(dev->io.context)-started)>=dev->timeout_ms) return KFB_TIMEOUT;
    }
}
static int submit_profile_inner(kfb_device *dev,uint8_t command[16],const uint8_t *payload,size_t size,uint16_t *submitted_tag) {
    if(dev==NULL || !dev->connected) return KFB_ARGUMENT;
    int result=wait_idle(dev);
    if(result!=0) return result;
    uint16_t tag=dev->next_tag++;
    *submitted_tag=tag;
    put16(command+2,tag);
    dev->last_device_error=0;
#ifndef KFB_PACK_DESCRIPTOR
#define KFB_PACK_DESCRIPTOR 0
#endif
#if !KFB_PACK_DESCRIPTOR
    result=write_one(dev,7,0);
#endif
    if(result==0 && payload!=NULL) result=write_one(dev,25,0);
    if(result==0 && payload!=NULL) result=write_regs(dev,24,false,payload,size);
#if KFB_PACK_DESCRIPTOR
    /* Opt-in ABI-preserving burst: sticky clear (7), then descriptor (8..23).
     * wait_idle has completed; no submission occurs until the separate reg26.
     * Default SDK behavior remains unchanged for existing applications. */
    if(result==0) {
        uint8_t burst[17]; burst[0]=0; memcpy(burst+1,command,16);
        result=write_regs(dev,7,true,burst,sizeof burst);
    }
#else
    if(result==0) result=write_regs(dev,8,true,command,16);
#endif
    if(result==0) result=write_one(dev,26,1);
    if(result!=0) return result; // Never automatically resend an uncertain submission.
    return KFB_OK;
}
static int submit_inner(kfb_device *dev,uint8_t command[16],const uint8_t *payload,size_t size,uint16_t *tag){BPUSH(B16_SUBMIT);int r=submit_profile_inner(dev,command,payload,size,tag);BPOP();return r;}
int kfb_submit(kfb_device *dev,const uint8_t descriptor[16],const uint8_t *payload,size_t size,uint16_t *tag) {
    if(descriptor==NULL || tag==NULL || size>64 || (size>0 && payload==NULL)) return KFB_ARGUMENT;
#if B16_GPU_QUEUE > 1
    int drained=b16_queue_drain(dev);if(drained) return drained;
#endif
    BPUSH(B16_DESCRIPTOR);uint8_t command[16];memcpy(command,descriptor,16);BPOP();
    return submit_inner(dev,command,size>0 ? payload : NULL,size,tag);
}
#if B16_COOP
extern void b16_gpu_wait_work(void);
static bool b16_in_present;
#endif
static int wait_inner(kfb_device *dev,uint16_t tag) {
    if(dev==NULL || !dev->connected) return KFB_ARGUMENT;
#if B16_GPU_QUEUE > 1 && B16_QUEUE_METRICS
    uint64_t q_start=b16_queue_sample_reason>=0 ? b16_queue_clock_us() : 0;
#endif
    uint32_t started=dev->io.now_ms(dev->io.context);
#if B16_GPU_QUEUE > 1 && B16_COMPLETION_BURST
    const bool burst_enabled=b16_queue_retiring!=0;
    bool first_poll=burst_enabled;
#endif
    for(;;) {
        uint8_t status,completion[3],sticky;
        int result;
#if B16_GPU_QUEUE > 1 && B16_COMPLETION_BURST
        bool captured=false;
        if(first_poll){
            uint8_t snapshot[4];first_poll=false;
            result=read_regs(dev,27,true,snapshot,sizeof snapshot);
            if(result!=0)return result; // Never replay a failed snapshot read.
            status=snapshot[0];memcpy(completion,snapshot+1,3);captured=true;
#if B16_QUEUE_METRICS
            b16_queue_burst_observe((status&16)!=0);
#endif
        }else result=read_regs(dev,27,false,&status,1);
#else
        result=read_regs(dev,27,false,&status,1);
#endif
        if(result!=0) return result;
        if(status&128) return KFB_TRANSPORT;
#if B16_GPU_QUEUE > 1
        if(status&16) { // BUSY means admission-full, not completion unavailable.
#else
        if((status&17)==16) {
#endif
#if B16_GPU_QUEUE > 1 && B16_QUEUE_METRICS
            uint64_t q_done=b16_queue_sample_reason>=0 ? b16_queue_clock_us() : 0;
#endif
#if B16_GPU_QUEUE > 1 && B16_COMPLETION_BURST
            if(!captured){
#if B16_QUEUE_METRICS
                if(burst_enabled)b16_queue_fallback_observe();
#endif
                result=read_regs(dev,28,true,completion,3);
            }
#else
            result=read_regs(dev,28,true,completion,3);
#endif
            if(result!=0) return result;
            if(((uint16_t)completion[0]|((uint16_t)completion[1]<<8))==tag) {
                result=read_regs(dev,7,false,&sticky,1);
                if(result!=0) return result;
                dev->last_device_error=completion[2]!=0 ? completion[2] : sticky;
#ifdef B16_KFB_PROFILE
                if(dev->last_device_error)
                    printf("GPU_RET_ERROR expected=%u received=%u status=%u completion_error=%u sticky=%u\n",
                        (unsigned)tag,(unsigned)((uint16_t)completion[0]|((uint16_t)completion[1]<<8)),
                        (unsigned)status,(unsigned)completion[2],(unsigned)sticky);
#endif
#if B16_GPU_QUEUE > 1 && B16_QUEUE_METRICS
                uint64_t q_ack=b16_queue_sample_reason>=0 ? b16_queue_clock_us() : 0;
#endif
                result=write_one(dev,31,1);
#if B16_GPU_QUEUE > 1 && B16_QUEUE_METRICS
                if(b16_queue_sample_reason>=0 && result==0)
                    b16_queue_observe(q_done-q_start,q_ack-q_done,b16_queue_clock_us()-q_ack);
#endif
                if(result!=0) return result;
                return dev->last_device_error!=0 ? KFB_DEVICE : KFB_OK;
            }
#if B16_GPU_QUEUE > 1
#ifdef B16_KFB_PROFILE
            printf("GPU_RET_TAG expected=%u received=%u status=%u completion_error=%u\n",
                (unsigned)tag,(unsigned)((uint16_t)completion[0]|((uint16_t)completion[1]<<8)),
                (unsigned)status,(unsigned)completion[2]);
#endif
            return KFB_DEVICE; // Unexpected FIFO tag: stop, never ACK or replay it.
#endif
        }
        if((uint32_t)(dev->io.now_ms(dev->io.context)-started)>=dev->timeout_ms) return KFB_TIMEOUT;
#if B16_COOP
        if((status&1)&&!b16_in_present)b16_gpu_wait_work();
#endif
    }
}
int kfb_wait(kfb_device *dev,uint16_t tag){BPUSH(B16_DONE);int r=wait_inner(dev,tag);BPOP();return r;}
#if B16_GPU_QUEUE > 1
#include "b16_queue.inc"
#endif
static int execute(kfb_device *dev,uint8_t command[16],const uint8_t *payload,size_t size) {
#if B16_GPU_QUEUE > 1
    if((command[0]==1 || command[0]==2) && payload==NULL && size==0)
        return b16_queue_enqueue(dev,command);
    return b16_queue_execute_sync(dev,command,payload,size);
#else
    uint16_t tag;
    int rc=submit_inner(dev,command,payload,size,&tag);
    return rc==0 ? kfb_wait(dev,tag) : rc;
#endif
}
int kfb_init(kfb_device *dev,kfb_io io,uint32_t timeout_ms) {
    if(dev==NULL || io.read==NULL || io.write==NULL || io.now_ms==NULL || timeout_ms>60000u) return KFB_ARGUMENT;
    memset(dev,0,sizeof(*dev)); dev->io=io; dev->timeout_ms=timeout_ms;
    return KFB_OK;
}
int kfb_probe(kfb_device *dev) {
    if(dev==NULL || dev->io.read==NULL || dev->io.write==NULL || dev->io.now_ms==NULL) return KFB_ARGUMENT;
    dev->connected=false;
    int result=wait_idle(dev);
    uint8_t id[7],tag[2];
    if(result==0) result=read_regs(dev,0,true,id,7);
    if(result!=0) return result;
    if(memcmp(id,"KFB1",4)!=0 || id[4]!=1 || (id[6]&31)!=31) return KFB_VERSION;
    result=read_regs(dev,28,true,tag,2);
    if(result!=0) return result;
    dev->next_tag=(uint16_t)(((uint16_t)tag[0]|((uint16_t)tag[1]<<8))+1u);
    dev->connected=true;
    return KFB_OK;
}
int kfb_fence(kfb_device *dev) {
    uint8_t command[16]={0}; return execute(dev,command,NULL,0);
}
static int kfb_fill_rect_profile_inner(kfb_device *dev,unsigned page,int32_t x,int32_t y,int32_t width,int32_t height,unsigned color) {
    if(dev==NULL || !dev->connected || page>1 || color>15) return KFB_ARGUMENT;
    if(width<=0 || height<=0) return KFB_OK;
    int64_t right=(int64_t)x+width,bottom=(int64_t)y+height;
    if(x>=640 || y>=360 || right<=0 || bottom<=0) return KFB_OK;
    int32_t left=x<0 ? 0 : x,top=y<0 ? 0 : y;
    if(right>640) right=640;
    if(bottom>360) bottom=360;
    uint8_t command[16]={1,(uint8_t)page};
    put16(command+4,(uint16_t)left); put16(command+6,(uint16_t)top);
    put16(command+8,(uint16_t)(right-left)); put16(command+10,(uint16_t)(bottom-top));
    command[12]=(uint8_t)color;
    return execute(dev,command,NULL,0);
}
static int kfb_copy_rect_profile_inner(kfb_device *dev,unsigned src_page,int32_t sx,int32_t sy,unsigned dst_page,int32_t dx,int32_t dy,int32_t width,int32_t height) {
    if(dev==NULL || !dev->connected || src_page>1 || dst_page>1 ||
       sx<0 || sx>=640 || dx<0 || dx>=640 || sy<0 || sy>=360 || dy<0 || dy>=360 || width<0 || height<0 ||
       (int64_t)sx+width>640 || (int64_t)dx+width>640 || (int64_t)sy+height>360 || (int64_t)dy+height>360 ||
       ((sx|dx|width)&1) || ((sx^dx)&7)) return KFB_ARGUMENT;
    if(width==0 || height==0 || (src_page==dst_page && sx==dx && sy==dy)) return KFB_OK;
    uint8_t caps;
    int rc=read_regs(dev,6,false,&caps,1);
    if(rc!=0) return rc;
    if(!(caps&64)) return KFB_VERSION;
    uint8_t command[16]={6,(uint8_t)(src_page|(dst_page<<1))};
    put16(command+4,(uint16_t)sx);put16(command+6,(uint16_t)sy);
    put16(command+8,(uint16_t)dx);put16(command+10,(uint16_t)dy);
    put16(command+12,(uint16_t)width);put16(command+14,(uint16_t)height);
    return execute(dev,command,NULL,0);
}
static int kfb_palette_profile_inner(kfb_device *dev,unsigned index,unsigned rgb444) {
    if(index>15 || rgb444>4095) return KFB_ARGUMENT;
    uint8_t command[16]={2,(uint8_t)index}; put16(command+4,(uint16_t)rgb444);
    return execute(dev,command,NULL,0);
}
int kfb_present(kfb_device *dev,unsigned page) {
    if(page>1) return KFB_ARGUMENT;
    uint8_t command[16]={3,(uint8_t)page}; BPUSH(B16_PRESENT);b16_present_mark(0);
#if B16_COOP
    b16_in_present=true;
#endif
    int r=execute(dev,command,NULL,0);if(!r)b16_present_mark(1);
#if B16_COOP
    b16_in_present=false;
#endif
    BPOP();return r;
}
static int transfer_bytes(kfb_device *dev,uint32_t address,uint8_t *out,const uint8_t *in,size_t size) {
    if(dev==NULL || !dev->connected || address>MEMORY_BYTES || size>MEMORY_BYTES-address) return KFB_ARGUMENT;
    while(size!=0) {
        uint32_t aligned=address&~3u;
        unsigned prefix=address&3u;
        size_t count=size<64u-prefix ? size : 64u-prefix;
        size_t span=(prefix+count+3u)&~3u;
        uint8_t command[16]={0},scratch[64]={0};
        command[0]=in!=NULL ? 4 : 5; command[1]=(uint8_t)(span/4);
        put32(command+4,aligned);
        if(in!=NULL) {
            uint64_t mask=UINT64_MAX;
            for(size_t i=0;i<count;i++) { scratch[prefix+i]=in[i]; mask&=~(UINT64_C(1)<<(prefix+i)); }
            for(unsigned i=0;i<8;i++) command[8+i]=(uint8_t)(mask>>(i*8));
        }
        int result=execute(dev,command,in!=NULL ? scratch : NULL,span);
        if(result!=0) return result;
        if(out!=NULL) {
            result=write_one(dev,25,0);
            if(result==0) result=read_regs(dev,24,false,scratch,span);
            if(result!=0) return result;
            memcpy(out,scratch+prefix,count); out+=count;
        }
        if(in!=NULL) in+=count;
        address+=(uint32_t)count; size-=count;
    }
    return KFB_OK;
}
int kfb_write_bytes(kfb_device *dev,uint32_t address,const uint8_t *data,size_t size) {
    if(data==NULL && size!=0) return KFB_ARGUMENT;
    return transfer_bytes(dev,address,NULL,data,size);
}
int kfb_read_bytes(kfb_device *dev,uint32_t address,uint8_t *data,size_t size) {
    if(data==NULL && size!=0) return KFB_ARGUMENT;
    return transfer_bytes(dev,address,data,NULL,size);
}

static int cursor_available(kfb_device *dev) {
    if(dev==NULL || !dev->connected) return KFB_ARGUMENT;
    uint8_t caps,status;
    int rc=read_regs(dev,6,false,&caps,1);
    if(rc!=0) return rc;
    if(!(caps&32)) return KFB_VERSION;
    rc=read_regs(dev,27,false,&status,1);
    if(rc!=0) return rc;
    return status&128 ? KFB_TRANSPORT : KFB_OK;
}
static int cursor_error(kfb_device *dev) {
    uint8_t error;
    int rc=read_regs(dev,53,false,&error,1);
    if(rc!=0) return rc;
    dev->last_device_error=error;
    return error ? KFB_DEVICE : KFB_OK;
}
static int cursor_begin(kfb_device *dev) {
#if B16_GPU_QUEUE > 1
    int drained=b16_queue_drain(dev);if(drained) return drained;
#endif
    int rc=cursor_available(dev);
    if(rc==0) { dev->last_device_error=0;rc=write_one(dev,53,0); }
    return rc;
}
int kfb_cursor_status(kfb_device *dev,uint8_t *status,uint16_t *generation) {
    if(status==NULL) return KFB_ARGUMENT;
    int rc=cursor_available(dev);
    if(rc==0) rc=read_regs(dev,50,false,status,1);
    if(rc==0 && generation!=NULL) {
        uint8_t bytes[2];rc=read_regs(dev,51,true,bytes,2);
        if(rc==0) *generation=(uint16_t)((uint16_t)bytes[0]|((uint16_t)bytes[1]<<8));
    }
    return rc==0 ? cursor_error(dev) : rc;
}
int kfb_cursor_shape(kfb_device *dev,unsigned bank,const uint8_t shape[256],const uint16_t colors[3],unsigned hx,unsigned hy) {
    if(bank>1 || shape==NULL || colors==NULL || hx>31 || hy>31) return KFB_ARGUMENT;
    for(unsigned i=0;i<3;i++) if(colors[i]>4095) return KFB_ARGUMENT;
    int rc=cursor_begin(dev);
    uint8_t status;
    if(rc==0) rc=read_regs(dev,50,false,&status,1);
    if(rc!=0) return rc;
    if((status&1) || ((status>>1)&1)==bank) { dev->last_device_error=1;return KFB_DEVICE; }
    uint8_t address[2]={0,(uint8_t)bank},hotspot[2]={(uint8_t)hx,(uint8_t)hy},palette[6];
    for(unsigned i=0;i<3;i++) put16(palette+2*i,colors[i]);
    rc=write_regs(dev,46,true,address,2);
    if(rc==0) rc=write_regs(dev,37,true,hotspot,2);
    if(rc==0) rc=write_regs(dev,39,true,palette,6);
    for(unsigned i=0;rc==0 && i<256;i+=64) rc=write_regs(dev,48,false,shape+i,64);
    return rc==0 ? cursor_error(dev) : rc;
}
int kfb_cursor_move(kfb_device *dev,int32_t x,int32_t y,unsigned bank,bool visible) {
    if(x< -1024 || x>1023 || y< -1024 || y>1023 || bank>1) return KFB_ARGUMENT;
    int rc=cursor_begin(dev);
    uint8_t pose[5]={(uint8_t)((bank<<1)|(visible ? 1u : 0u)),0,0,0,0};
    put16(pose+1,(uint16_t)x);put16(pose+3,(uint16_t)y);
    if(rc==0) rc=write_regs(dev,32,true,pose,5);
    if(rc==0) rc=write_one(dev,49,1);
    return rc==0 ? cursor_error(dev) : rc; // No retry after an uncertain transfer.
}
int kfb_cursor_wait(kfb_device *dev,uint16_t *generation) {
    int rc=cursor_available(dev);
    if(rc!=0) return rc;
    uint32_t started=dev->io.now_ms(dev->io.context);
    for(;;) {
        uint8_t status;
        rc=read_regs(dev,50,false,&status,1);
        if(rc==0) rc=cursor_error(dev);
        if(rc!=0) return rc;
        if(!(status&1)) {
            if(generation!=NULL) {
                uint8_t bytes[2];rc=read_regs(dev,51,true,bytes,2);
                if(rc==0) *generation=(uint16_t)((uint16_t)bytes[0]|((uint16_t)bytes[1]<<8));
            }
            if(rc==0) rc=write_one(dev,50,64);
            return rc;
        }
        if((uint32_t)(dev->io.now_ms(dev->io.context)-started)>=dev->timeout_ms) return KFB_TIMEOUT;
    }
}

static int audio_available(kfb_device *dev) {
#if B16_GPU_QUEUE > 1
    int drained=b16_queue_drain(dev);if(drained) return drained;
#endif
    if(dev==NULL || !dev->connected) return KFB_ARGUMENT;
    uint8_t id[7];
    int rc=read_regs(dev,0,true,id,7);
    if(rc!=0) return rc;
    return memcmp(id,"KFB1",4)==0 && id[4]==1 && id[5]>=4 && (id[6]&128) ? KFB_OK : KFB_VERSION;
}
static int audio_check(kfb_device *dev) {
    uint8_t error;
    int rc=read_regs(dev,7,false,&error,1);
    if(rc!=0) return rc;
    dev->last_device_error=error;
    return error ? KFB_DEVICE : KFB_OK;
}
int kfb_audio_write(kfb_device *dev,uint8_t index,uint8_t value) {
    if(index<0x60) return KFB_ARGUMENT;
    int rc=audio_available(dev);
    if(rc==0) rc=audio_check(dev);
    uint8_t pair[2]={index,value};
    if(rc==0) rc=write_regs(dev,54,true,pair,2);
    if(rc==0) rc=audio_check(dev);
    return rc;
}
int kfb_audio_read(kfb_device *dev,uint8_t index,uint8_t *value) {
    if(value==NULL || index<0x60) return KFB_ARGUMENT;
    int rc=audio_available(dev);
    if(rc==0) rc=write_one(dev,54,index);
    if(rc==0) rc=read_regs(dev,55,false,value,1);
    if(rc==0) rc=audio_check(dev);
    return rc;
}
int kfb_audio_commit(kfb_device *dev,uint16_t *tag) {
    if(tag==NULL) return KFB_ARGUMENT;
    int rc=audio_available(dev);
    if(rc==0) rc=audio_check(dev);
    uint8_t command[16]={7};
    if(rc==0) rc=kfb_submit(dev,command,NULL,0,tag);
    return rc;
}

int kfb_fill_rect(kfb_device *dev,unsigned page,int32_t x,int32_t y,int32_t width,int32_t height,unsigned color){BPUSH(B16_DESCRIPTOR);int r=kfb_fill_rect_profile_inner(dev,page,x,y,width,height,color);BPOP();return r;}

int kfb_copy_rect(kfb_device *dev,unsigned src_page,int32_t sx,int32_t sy,unsigned dst_page,int32_t dx,int32_t dy,int32_t width,int32_t height){BPUSH(B16_DESCRIPTOR);int r=kfb_copy_rect_profile_inner(dev,src_page,sx,sy,dst_page,dx,dy,width,height);BPOP();return r;}

int kfb_palette(kfb_device *dev,unsigned index,unsigned rgb444){BPUSH(B16_DESCRIPTOR);int r=kfb_palette_profile_inner(dev,index,rgb444);BPOP();return r;}
