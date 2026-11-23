// SPDX-License-Identifier: Apache-2.0
#include "pico/stdlib.h"
#include "pico/bootrom.h"
#include "hardware/clocks.h"
#include "b16_qspi.h"
#include <stdio.h>
#include <string.h>

enum { SIZE = 16384, SCRATCH = 0x3f0000 };
static uint8_t saved[SIZE], tx[SIZE], rx[SIZE];
static kfb_device dev;
static kfb_io io;
int bench_divider(unsigned div256);

static int connect_at(unsigned div256) {
    int rc = bench_divider(div256);
    io = mt_qspi_io();
    if (!rc) rc=kfb_init(&dev, io, 1000);
    return rc ? rc : kfb_probe(&dev);
}
static int reg_write(uint8_t reg, const uint8_t *data, unsigned n) {
    return io.write(io.context, reg, false, data, n);
}
static int reg_read(uint8_t reg, uint8_t *data, unsigned n) {
    return io.read(io.context, reg, false, data, n);
}
static void pattern(unsigned round) {
    uint32_t seed = 0x6d2b79f5u ^ round;
    for (unsigned i=0; i<SIZE; i++) {
        seed ^= seed<<13; seed ^= seed>>17; seed ^= seed<<5;
        tx[i] = round==0 ? 0 : round==1 ? 255 : round==2 ? (i&1 ? 0x55 : 0xaa) : round==3 ? (1u<<(i&7)) : seed;
    }
}
static int test(unsigned div256, unsigned rounds, const char *kind) {
    int rc = connect_at(div256);
    unsigned identities=0, staging=0, completed=0;
    uint64_t write_us=0, read_us=0, wire_us=0;
    uint8_t id[7], data[64], zero=0;
    static const uint8_t expected[7]={'K','F','B','1',1,4,255};
    const char *phase="connect";
    for (unsigned i=0; !rc && i<1024; i++) {
        phase="identity";
        rc=io.read(io.context,0,true,id,7);
        if (!rc && memcmp(id,expected,7)) rc=-100;
        if (!rc) identities++;
    }
    for (unsigned i=0; !rc && i<256; i++) {
        phase="staging";
        pattern(i);
        rc=reg_write(25,&zero,1);
        uint64_t t=time_us_64();
        if(!rc) rc=reg_write(24,tx,64);
        wire_us += time_us_64()-t;
        if(!rc) rc=reg_write(25,&zero,1);
        if(!rc) rc=reg_read(24,data,64);
        if(!rc && memcmp(tx,data,64)) rc=-101;
        if(!rc) staging++;
    }
    for (unsigned i=0; !rc && i<rounds; i++) {
        pattern(i);
        phase="memory_write";
        uint64_t t=time_us_64();
        rc=kfb_write_bytes(&dev,SCRATCH,tx,SIZE);
        write_us += time_us_64()-t;
        phase="memory_read";
        t=time_us_64();
        if(!rc) rc=kfb_read_bytes(&dev,SCRATCH,rx,SIZE);
        read_us += time_us_64()-t;
        if(!rc && memcmp(tx,rx,SIZE)) {rc=-102; phase="memory_compare";}
        if(!rc) completed++;
    }
    uint8_t status=0,error=0;
    if(!rc) rc=reg_read(27,&status,1);
    if(!rc) rc=reg_read(7,&error,1);
    if(!rc && ((status&128)||error)) {rc=-103;phase="status";}
    const mt_qspi_stats *s=mt_qspi_statistics();
    printf("RESULT {\"kind\":\"%s\",\"div256\":%u,\"sck_hz\":%u,\"rc\":%d,\"phase\":\"%s\",\"identities\":%u,\"staging_blocks\":%u,\"rounds\":%u,\"bytes_each_direction\":%u,\"write_us\":%llu,\"read_us\":%llu,\"staging_write_us\":%llu,\"status\":%u,\"device_error\":%u,\"timeouts\":%u,\"wire_bytes\":%llu,\"dma_transfers\":%llu,\"dma_errors\":%u}\n",
        kind,div256,2560000000u/div256,rc,phase,identities,staging,completed,completed*SIZE,
        write_us,read_us,wire_us,status,error,(unsigned)s->timeouts,s->wire_bytes,s->dma_transfers,(unsigned)s->dma_errors);
    stdio_flush();
    return rc;
}

int main(void) {
    set_sys_clock_khz(120000,true);
    stdio_init_all();
    while (!stdio_usb_connected()) sleep_ms(10);
    puts("READY QSPI RAM benchmark; g=start, r=BOOTSEL");
    int key;
    do { key=getchar_timeout_us(100000); } while(key!='g' && key!='r');
    if(key=='r') reset_usb_boot(0,0);
    int rc=connect_at(2560);
    if(!rc) rc=kfb_read_bytes(&dev,SCRATCH,saved,SIZE);
    bool backed=rc==0;
    printf("BACKUP {\"rc\":%d,\"scratch\":%u,\"bytes\":%u}\n",rc,SCRATCH,SIZE);
    unsigned last=0;
    const unsigned divs[]={2560,1280,640,512,448,384,320,256};
    for(unsigned i=0; !rc && i<sizeof(divs)/sizeof(divs[0]); i++) {
        rc=test(divs[i],8,"sweep");
        if(!rc) last=divs[i];
    }
    // A separate longer run at the last passing setting, after a clean baseline probe.
    if(last && !connect_at(2560)) {
        int soak=test(last,128,"soak");
        if(soak && !rc) rc=soak;
    }
    int restore=backed ? connect_at(2560) : -200;
    if(!restore) restore=kfb_write_bytes(&dev,SCRATCH,saved,SIZE);
    if(!restore) restore=kfb_read_bytes(&dev,SCRATCH,rx,SIZE);
    if(!restore && memcmp(saved,rx,SIZE)) restore=-201;
    mt_qspi_deinit();
    gpio_init(7);gpio_set_dir(7,GPIO_OUT);gpio_put(7,1);
    gpio_init(6);gpio_set_dir(6,GPIO_OUT);gpio_put(6,0);
    printf("DONE {\"test_rc\":%d,\"restore_rc\":%d,\"last_pass_div256\":%u,\"cpu_hz\":%u}\n",rc,restore,last,(unsigned)clock_get_hz(clk_sys));
    stdio_flush();
    while(getchar_timeout_us(100000)!='r') sleep_ms(10);
    reset_usb_boot(0,0);
}
