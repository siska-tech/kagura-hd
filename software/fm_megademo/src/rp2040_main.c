// SPDX-License-Identifier: Apache-2.0
// FOUR OPERATORS on RP2040 (RAM-only ELF): core 1 = FM synthesizer,
// core 0 = KFB drawing + PCM stream refill over the PIO QSPI host.
#include "b16_qspi.h"
#include "demo.h"
#include "fm.h"
#include "stream.h"
#include "hardware/clocks.h"
#include "pico/multicore.h"
#include "pico/stdio_usb.h"
#include "pico/stdlib.h"
#include <stdio.h>

// KAGURA_AUTOSTART_MS (release UF2 only; 0 = host-driven build): start on power-up
// unless a terminal opens the USB serial port within that time, in which case the
// demo waits for g as usual. The summary is printed again whenever a terminal connects.
#ifndef KAGURA_AUTOSTART_MS
#define KAGURA_AUTOSTART_MS 0
#endif

#define FRAME_US 33333u
#define TRY(x) do { int rc_=(x); if (rc_) return rc_; } while (0)

static kfb_device gpu;
static volatile bool synth_run=true;
static volatile uint32_t synth_busy_us;

static void core1_main(void) {
    uint64_t busy=0;
    while (synth_run) {
        uint32_t p=stream_produced;
        if (p-stream_consumed>=STREAM_LEAD) { tight_loop_contents(); continue; }
        uint64_t t=time_us_64();
        fm_render(stream_ring_l+(p%STREAM_RING),stream_ring_r+(p%STREAM_RING),256);
        busy+=time_us_64()-t; synth_busy_us=(uint32_t)busy;
        __mem_fence_release();
        stream_produced=p+256;
    }
}
static int8_t sample_at(uint32_t frame) {
    uint32_t p=stream_produced;
    if (frame>=p || p-frame>STREAM_RING-1024) return 0;
    unsigned i=frame%STREAM_RING;
    return (int8_t)((stream_ring_l[i]+stream_ring_r[i])/2);
}
static const demo_platform platform={stream_service,sample_at,fm_snapshot_at};
static const char *phase="idle";

static int run(void) {
    phase="qspi_init"; TRY(mt_qspi_init());
    phase="identify";
    TRY(kfb_init(&gpu,mt_qspi_io(),500));
    TRY(kfb_probe(&gpu));
    uint8_t id; TRY(kfb_audio_read(&gpu,0xe3,&id));
    if (id!=0x51) { printf("NOT A PCM STREAM IMAGE: E3=0x%02x\n",id); return KFB_VERSION; }
    phase="demo_init"; TRY(demo_init(&gpu,&platform));
    while (stream_produced<2*STREAM_HALF) tight_loop_contents();
    phase="stream_start"; TRY(stream_start(&gpu));
    const stream_stats *ss=stream_statistics();
    uint64_t next=ss->start_us, last_log=0;
    uint32_t worst_frame=0;
    phase="demo";
    for (;;) {
        uint64_t now=time_us_64();
        uint32_t ms=(uint32_t)((now-ss->start_us)/1000u);
        if (ms>=DEMO_END_MS) break;
        if (getchar_timeout_us(0)=='q') { phase="cancelled"; return -23; }
        TRY(demo_frame(ms));
        uint32_t took=(uint32_t)(time_us_64()-now); if (took>worst_frame) worst_frame=took;
        next+=FRAME_US; if (next<time_us_64()) next=time_us_64();
        while (time_us_64()<next) TRY(stream_service());
        if (ms-last_log>=1000) {
            last_log=ms;
            const demo_stats *d=demo_statistics();
            const mt_qspi_stats *q=mt_qspi_statistics();
            printf("PERF ms=%lu scene=%u frames=%lu commands=%lu halves=%lu worst_latency_us=%lu worst_poll_gap_us=%lu "
                   "synth_waits=%lu synth_busy_ms=%lu worst_frame_us=%lu transactions=%llu timeouts=%lu\n",
                   (unsigned long)ms,d->scene,(unsigned long)d->frames,(unsigned long)d->commands,(unsigned long)ss->halves,
                   (unsigned long)ss->worst_latency_us,(unsigned long)ss->worst_poll_gap_us,(unsigned long)ss->synth_waits,
                   (unsigned long)(synth_busy_us/1000u),(unsigned long)worst_frame,(unsigned long long)q->transactions,
                   (unsigned long)q->timeouts);
            worst_frame=0;
        }
    }
    phase="check";
    uint8_t l,r,h; TRY(stream_check(&l,&r,&h));
    printf("PCM_STATUS left=0x%02x right=0x%02x hdmi=0x%02x\n",l,r,h);
    phase="stop"; TRY(stream_stop());
    if ((l|r)&0x38 || h&6) return -25;
    return 0;
}

#define PRINT_SUMMARY() do { \
    printf("SCENES"); \
    for (unsigned i=0;i<DEMO_SCENES;i++) printf(" %lu",(unsigned long)d->scene_frames[i]); \
    printf("\nSTOP rc=%d phase=%s frames=%lu halves=%lu wraps=%lu worst_latency_us=%lu synth_waits=%lu " \
    "synth_busy_ms=%lu fm_peak=%lu fm_clipped=%lu timeouts=%lu device_error=%u\n", \
    rc,result_phase,(unsigned long)d->frames,(unsigned long)ss->halves,(unsigned long)ss->wraps, \
    (unsigned long)ss->worst_latency_us,(unsigned long)ss->synth_waits,(unsigned long)(synth_busy_us/1000u), \
    (unsigned long)fm_peak(),(unsigned long)fm_clipped(),(unsigned long)q->timeouts,gpu.last_device_error); \
} while (0)

int main(void) {
    set_sys_clock_khz(120000,true);
    stdio_init_all();
#if KAGURA_AUTOSTART_MS
    absolute_time_t autostart = make_timeout_time_ms(KAGURA_AUTOSTART_MS);
    while (!stdio_usb_connected() && !time_reached(autostart)) sleep_ms(10);
    if (stdio_usb_connected()) {
        puts("FOUR OPERATORS / FM MEGADEMO / RAM ELF / g=start q=stop");
        int key=0;
        while (key!='g') key=getchar_timeout_us(100000);
    }
#else
    while (!stdio_usb_connected()) sleep_ms(10);
    puts("FOUR OPERATORS / FM MEGADEMO / RAM ELF / g=start q=stop");
    int key=0;
    while (key!='g') key=getchar_timeout_us(100000);
#endif
    fm_init();
    multicore_launch_core1(core1_main);
    int rc=run();
    const char *result_phase=phase;
    if (rc && rc!=KFB_IO && rc!=KFB_TIMEOUT) (void)stream_stop();
    synth_run=false;
    const demo_stats *d=demo_statistics();
    const stream_stats *ss=stream_statistics();
    const mt_qspi_stats *q=mt_qspi_statistics();
    PRINT_SUMMARY();
    mt_qspi_deinit();
#if KAGURA_AUTOSTART_MS
    for (bool was = true;; sleep_ms(100)) {
        bool now = stdio_usb_connected();
        if (now && !was) { sleep_ms(500); PRINT_SUMMARY(); }
        was = now;
    }
#else
    for (;;) sleep_ms(1000);
#endif
}
