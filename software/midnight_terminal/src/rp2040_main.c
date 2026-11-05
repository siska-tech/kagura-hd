// SPDX-License-Identifier: Apache-2.0
// RAM/Flash linked build ONLY. No bootloader, flash writer or pin setup until executed.
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "mt_device.h"
#include "mt_qspi.h"
#include "pico/stdio_usb.h"
#include <stdio.h>
int mt_preflight(kfb_device *gpu);
static uint32_t now(void *ctx){(void)ctx;return to_ms_since_boot(get_absolute_time());}
int main(void){
 // Reuse KAGURA-9's proven RP2040 clock; this does not change FPGA clocks.
 set_sys_clock_khz(120000,true);
 gpio_init(7);gpio_put(7,1);gpio_set_dir(7,GPIO_OUT);
 gpio_init(6);gpio_put(6,0);gpio_set_dir(6,GPIO_OUT);
 for(uint pin=2;pin<6;pin++){gpio_init(pin);gpio_set_dir(pin,GPIO_IN);}
 stdio_init_all();
 while(!stdio_usb_connected())sleep_ms(10);
 printf("MIDNIGHT TERMINAL / USB CONTROL / send g to run / q to stop / release_ready=false\n");
 int arm=0;while(arm!='g'){arm=getchar_timeout_us(100000);if(arm=='q'){printf("CANCELLED; no QSPI commands sent\n");while(true)tight_loop_contents();}}
 static kfb_device gpu;static mt_device device;static mt_engine engine;
 int rc=mt_qspi_init();bool device_ready=false;kfb_io io=mt_qspi_io();
 if(!rc)rc=kfb_init(&gpu,io,2000);
 if(!rc)rc=mt_preflight(&gpu);
 if(!rc)rc=mt_device_start(&device,&gpu);
 if(!rc)device_ready=true;
 if(!rc)rc=mt_init(&engine,mt_device_emit,&device,1);
 printf("QSPI PIO / SCK nominal=5000000 / RP2040=120000000 / release_ready=false\n");
 // Initial asset load precedes the logical autoplay clock.
 if(!rc)rc=mt_tick(&engine,0,0);
 if(!rc)printf("SCENE id=0 host_ms=0 DEMO_READY\n");
 uint32_t start=now(0),last=0;
 while(!rc){
  uint32_t t=now(0)-start;int k=getchar_timeout_us(0);
  if(k=='q')break;
  int key=k=='w'?1:k=='s'?2:k=='\r'||k=='\n'?3:0;
  int previous_scene=engine.scene;
  rc=mt_tick(&engine,t,key);
  if(engine.scene!=previous_scene)printf("SCENE id=%d host_ms=%lu\n",engine.scene,(unsigned long)t);
  if(t-last>=1000){
   mt_device_poll(&device);const mt_qspi_stats *q=mt_qspi_statistics();
   printf("host_ms=%lu frames=%lu bytes=%lu commands=%lu waits_ms=%lu audio_fault=%d release_ready=false\n",(unsigned long)t,(unsigned long)engine.frames,(unsigned long)engine.bytes,(unsigned long)engine.commands,(unsigned long)device.waits_ms,device.audio_error);
   printf("qspi_nominal_hz=5000000 wire_bytes=%llu transactions=%llu elapsed_us=%llu max_transaction_us=%lu timeouts=%lu\n",(unsigned long long)q->wire_bytes,(unsigned long long)q->transactions,(unsigned long long)q->elapsed_us,(unsigned long)q->max_transaction_us,(unsigned long)q->timeouts);
   last=t;
  }
  sleep_ms(1);
 }
 const mt_qspi_stats *stats=mt_qspi_statistics();
 if(!rc&&device_ready&&!stats->faulted){int32_t stop[]={-1,0};mt_device_emit(&device,MT_AUDIO,stop,0,0);}
 printf("STOP error=%d; wire_bytes=%llu transactions=%llu timeouts=%lu; no retry\n",rc,(unsigned long long)stats->wire_bytes,(unsigned long long)stats->transactions,(unsigned long)stats->timeouts);
 mt_qspi_deinit();while(true)tight_loop_contents();
}


