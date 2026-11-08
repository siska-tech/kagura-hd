// SPDX-License-Identifier: Apache-2.0
// Queue8 FILL/fence reproducer. No asset preload, COPY, PRESENT or PCM setup.
#include "b16_qspi.h"
#include "b16_profile.h"
#include "b16_queue.h"
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "hardware/clocks.h"
#include <stdio.h>
static kfb_io raw;
static unsigned writes;
uint64_t b16_queue_clock_us(void){return time_us_64();}
static int read_io(void *ctx,uint8_t reg,bool inc,uint8_t *data,size_t size){
    (void)ctx;
    return raw.read(raw.context,reg,inc,data,size);
}
static int write_io(void *ctx,uint8_t reg,bool inc,const uint8_t *data,size_t size){
    (void)ctx;
    int rc=raw.write(raw.context,reg,inc,data,size);
    writes++;
    if(rc)return rc;
    uint8_t sticky=0;
    rc=raw.read(raw.context,7,false,&sticky,1);
    if(!rc && sticky){
        printf("REPRO_WRITE_ERROR call=%u reg=%u inc=%u size=%u sticky=%u data=",
            writes,reg,inc,(unsigned)size,sticky);
        for(size_t i=0;i<size;i++)printf("%02x",data[i]);
        printf("\n");
        return -1;
    }
    return rc;
}
static uint32_t now_io(void *ctx){(void)ctx;return raw.now_ms(raw.context);}
int main(void){
    set_sys_clock_khz(120000,true);
    stdio_init_all();
    while(!stdio_usb_connected())sleep_ms(10);
    printf("BEYOND 16 COLORS / minimal Queue8 / g=150s FILL+fence / no automatic start\n");
    while(getchar_timeout_us(100000)!='g'){}
    b16_profile_init(time_us_64);
    int rc=mt_qspi_init();
    raw=mt_qspi_io();
    kfb_device gpu;
    kfb_io io={NULL,read_io,write_io,now_io};
    if(!rc)rc=kfb_init(&gpu,io,2000);
    if(!rc)rc=kfb_probe(&gpu);
    uint64_t begin=time_us_64(),logged=begin;
    unsigned rounds=0;
    while(!rc && time_us_64()-begin<150000000u){
        for(unsigned i=0;i<8&&!rc;i++)
            rc=kfb_fill_rect(&gpu,0,(rounds*6+i*8)%600,(rounds*3)%320,32,32,(rounds+i)&15);
        if(!rc)rc=kfb_fence(&gpu);
        rounds++;
        if(time_us_64()-logged>=1000000){
            const b16_queue_stats *q=b16_queue_statistics();
            printf("REPRO ms=%llu rounds=%u submitted=%lu retired=%lu pending=%lu errors=%lu\n",
                (unsigned long long)((time_us_64()-begin)/1000),rounds,
                (unsigned long)q->submitted,(unsigned long)q->retired,
                (unsigned long)q->pending,(unsigned long)q->errors);
            logged=time_us_64();
        }
    }
    printf("STOP rc=%d; no retry; release_ready=false\n",rc);
    mt_qspi_deinit();
    while(true)tight_loop_contents();
}
