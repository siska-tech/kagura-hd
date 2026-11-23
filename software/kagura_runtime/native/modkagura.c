// SPDX-License-Identifier: Apache-2.0
// Generic GPU/PCM/FM services. No scenes, dialogue or playback loop live here.
#include "py/runtime.h"
#include "py/mpthread.h"
#include "hardware/clocks.h"
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "transport.h"
#include "fm.h"
#include "pcm_stream.h"
#include <string.h>
#if !MICROPY_PY_THREAD || MICROPY_PY_THREAD_GIL
#error "KAGURA TERMINAL requires rp2 threading without a GIL"
#endif
static kfb_device gpu;
static volatile bool synthesizing;
static bool opened, bus_ready, thread_owned, stream_attempted, playing;
static int bus_error;
static bool audio_configured;
static uint8_t capabilities;
static bool cursor_ready;
static unsigned cursor_bank, cursor_cell, cursor_height;
static uint32_t ownership_generation;
static mp_obj_t backend_generation(void) { return mp_obj_new_int_from_uint(ownership_generation); }
static MP_DEFINE_CONST_FUN_OBJ_0(backend_generation_obj,backend_generation);
static mp_obj_t backend_is_open(void) { return mp_obj_new_bool(opened); }
static MP_DEFINE_CONST_FUN_OBJ_0(backend_is_open_obj,backend_is_open);
// Scheduled Python callbacks normally print and consume uncaught exceptions.
// Keep Ctrl-C pending for the foreground VM instead of losing it in a timer.
typedef struct { mp_obj_base_t base; mp_obj_t callback,recovery; } interrupt_guard_t;
static mp_obj_t interrupt_guard_call(mp_obj_t self_in,size_t n_args,size_t n_kw,const mp_obj_t *args) {
    interrupt_guard_t *self=MP_OBJ_TO_PTR(self_in);
    nlr_buf_t nlr;
    if(nlr_push(&nlr)==0) {
        mp_obj_t result=mp_call_function_n_kw(self->callback,n_args,n_kw,args);
        nlr_pop(); return result;
    }
    if(mp_obj_exception_match(MP_OBJ_FROM_PTR(nlr.ret_val),MP_OBJ_FROM_PTR(&mp_type_KeyboardInterrupt))) {
        if(self->recovery!=mp_const_none) mp_call_function_0(self->recovery);
        mp_sched_keyboard_interrupt(); return mp_const_none;
    }
    nlr_raise(nlr.ret_val);
}
static MP_DEFINE_CONST_OBJ_TYPE(interrupt_guard_type,MP_QSTR_InterruptGuard,MP_TYPE_FLAG_NONE,call,interrupt_guard_call);
static mp_obj_t backend_interrupt_guard(size_t n_args,const mp_obj_t *args) {
    if(!mp_obj_is_callable(args[0]) || (n_args>1 && args[1]!=mp_const_none && !mp_obj_is_callable(args[1])))
        mp_raise_TypeError(MP_ERROR_TEXT("callbacks must be callable"));
    interrupt_guard_t *guard=mp_obj_malloc(interrupt_guard_t,&interrupt_guard_type);
    guard->callback=args[0]; guard->recovery=n_args>1?args[1]:mp_const_none;
    return MP_OBJ_FROM_PTR(guard);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(backend_interrupt_guard_obj,1,2,backend_interrupt_guard);
static void check(int rc) {
    if (rc) { bus_error = rc; mp_raise_msg_varg(&mp_type_OSError, MP_ERROR_TEXT("KAGURA backend error %d"), rc); }
}
static void require_open(void) {
    if (get_core_num() != 0 || !opened) mp_raise_msg(&mp_type_OSError, MP_ERROR_TEXT("open backend on core0 first"));
    if (bus_error) mp_raise_msg(&mp_type_OSError, MP_ERROR_TEXT("backend faulted; close before reopening"));
}
static void pump(void) { if (playing) check(stream_service()); }
static void *synth(void *unused) {
    (void)unused;
    while (synthesizing) {
        uint32_t p = stream_produced; __mem_fence_acquire();
        if (p-stream_consumed >= STREAM_LEAD) { tight_loop_contents(); continue; }
        fm_render(stream_ring_l+p%STREAM_RING, stream_ring_r+p%STREAM_RING, 256);
        __mem_fence_release(); stream_produced = p+256;
    }
    return NULL;
}
static mp_obj_t backend_close(void) {
    if (get_core_num() != 0) mp_raise_msg(&mp_type_OSError, MP_ERROR_TEXT("close on core0 only"));
    if (!opened) return mp_const_none;
    int rc = 0;
    if (cursor_ready && !bus_error) {
        rc = kfb_cursor_move(&gpu, 0, 0, cursor_bank, false);
        if (!rc) rc = kfb_cursor_wait(&gpu, NULL);
    }
    if (stream_attempted && bus_error != KFB_IO && bus_error != KFB_TIMEOUT && bus_error != KFB_TRANSPORT) rc = stream_stop();
    synthesizing = false; __mem_fence_release();
    if (!thread_owned && core1_entry == synth) core1_entry = NULL;
    if (thread_owned) {
        while (__atomic_load_n(&core1_entry, __ATOMIC_ACQUIRE) != NULL) tight_loop_contents();
        // rp2 GC stops rooting the thread stack when core1_entry becomes NULL.
        // The SDK's returned-thread WFI loop and FIFO lockout IRQ still use it.
        // Park core1 in ROM before that heap allocation can be reused by Python.
        multicore_reset_core1();
    }
    if (bus_ready) kg_transport_deinit();
    opened = bus_ready = thread_owned = stream_attempted = playing = false;
    cursor_ready = audio_configured = false;
    MP_STATE_VM(kagura_schedule)=MP_OBJ_NULL;
    check(rc); return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(backend_close_obj, backend_close);
void kagura_soft_reset(void) {
    nlr_buf_t nlr;
    if (nlr_push(&nlr) == 0) { backend_close(); nlr_pop(); }
    // backend_close releases its thread and PIO before reporting cleanup errors.
}
static mp_obj_t backend_display_open(void) {
    if (get_core_num()!=0 || opened) mp_raise_msg(&mp_type_OSError, MP_ERROR_TEXT("GPU must be opened on core0"));
    if (clock_get_hz(clk_sys)!=KAGURA_SYS_HZ) mp_raise_ValueError(MP_ERROR_TEXT("set machine.freq(120000000) first"));
    bus_error=0; cursor_ready=false;
    nlr_buf_t nlr;
    if (nlr_push(&nlr)==0) {
        check(kg_transport_init()); bus_ready=true;
        check(kfb_init(&gpu,kg_transport_io(),500)); check(kfb_probe(&gpu));
        check(gpu.io.read(gpu.io.context,6,false,&capabilities,1));
        opened=true; ownership_generation++; nlr_pop();
    } else {
        if (bus_ready) kg_transport_deinit();
        bus_ready=false; nlr_raise(nlr.ret_val);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(backend_display_open_obj,backend_display_open);
static mp_obj_t backend_open(size_t n_args,const mp_obj_t *args) {
    (void)n_args;
    if(get_core_num()!=0 || opened || core1_entry!=NULL) mp_raise_msg(&mp_type_OSError,MP_ERROR_TEXT("core0 and unused core1 required"));
    if(clock_get_hz(clk_sys)!=KAGURA_SYS_HZ) mp_raise_ValueError(MP_ERROR_TEXT("set machine.freq(120000000) first"));
    mp_buffer_info_t patches,events;
    bool paged=mp_obj_is_type(args[1],&mp_type_tuple) || mp_obj_is_type(args[1],&mp_type_list);
    const uint8_t *pages[128]; size_t page_count=0,total=0;
    mp_obj_t immutable;
    if(paged) {
        mp_obj_t *items,safe[128]={0}; mp_obj_get_array(args[1],&page_count,&items);
        if(page_count>128) mp_raise_ValueError(MP_ERROR_TEXT("too many schedule pages"));
        for(size_t i=0;i<page_count;i++) {
            mp_get_buffer_raise(items[i],&events,MP_BUFFER_READ);
            if(events.len==0 || events.len>1024 || events.len%16 || (i+1<page_count && events.len!=1024)) mp_raise_ValueError(MP_ERROR_TEXT("invalid schedule page"));
            safe[i]=mp_obj_is_type(items[i],&mp_type_bytes)?items[i]:mp_obj_new_bytes(events.buf,events.len);
            total+=events.len;
        }
        immutable=mp_obj_new_tuple(page_count,safe);
    } else {
        mp_get_buffer_raise(args[1],&events,MP_BUFFER_READ);
        if(events.len>131072) mp_raise_ValueError(MP_ERROR_TEXT("schedule too large"));
        immutable=mp_obj_is_type(args[1],&mp_type_bytes)?args[1]:mp_obj_new_bytes(events.buf,events.len);
        total=events.len;
    }
    // Pin the immutable owner before extracting interior buffer pointers.
    // No Python allocations may occur between extracting pages and configuring DSP.
    MP_STATE_VM(kagura_schedule)=immutable;
    fm_init();
    if(n_args==3) {
        mp_buffer_info_t effects;
        mp_get_buffer_raise(args[2],&effects,MP_BUFFER_READ);
        if(!fm_effects(effects.buf,effects.len)) {
            MP_STATE_VM(kagura_schedule)=MP_OBJ_NULL;
            mp_raise_ValueError(MP_ERROR_TEXT("invalid DSP parameters"));
        }
    }
    mp_get_buffer_raise(args[0],&patches,MP_BUFFER_READ);
    if(paged) {
        mp_obj_t *items; size_t count;
        mp_obj_get_array(immutable,&count,&items);
        for(size_t i=0;i<count;i++) {
            mp_get_buffer_raise(items[i],&events,MP_BUFFER_READ); pages[i]=events.buf;
        }
    } else mp_get_buffer_raise(immutable,&events,MP_BUFFER_READ);
    bool valid=paged?fm_configure_pages(patches.buf,patches.len,pages,page_count,total):fm_configure(patches.buf,patches.len,events.buf,total);
    if(!valid) {
        const uint8_t *bad=fm_configuration_event(); uint32_t words[4]={0};
        if(bad) memcpy(words,bad,sizeof words);
        MP_STATE_VM(kagura_schedule)=MP_OBJ_NULL;
        mp_raise_msg_varg(&mp_type_ValueError,MP_ERROR_TEXT("invalid FM event %d: %08x %08x %08x %08x"),fm_configuration_error(),words[0],words[1],words[2],words[3]);
    }
    MP_STATE_VM(kagura_schedule)=immutable;
    bus_error=0; stream_produced=stream_consumed=0; cursor_ready=false;
    nlr_buf_t nlr;
    if(nlr_push(&nlr)==0) {
        check(kg_transport_init()); bus_ready=true;
        check(kfb_init(&gpu,kg_transport_io(),500)); check(kfb_probe(&gpu));
        uint8_t id; check(kfb_audio_read(&gpu,0xe3,&id));
        if(id!=0x51) mp_raise_ValueError(MP_ERROR_TEXT("PCM STREAM FPGA image required"));
        check(gpu.io.read(gpu.io.context,6,false,&capabilities,1));
        opened=audio_configured=true; ownership_generation++; nlr_pop();
    } else {
        if(bus_ready) kg_transport_deinit();
        bus_ready=false; MP_STATE_VM(kagura_schedule)=MP_OBJ_NULL; nlr_raise(nlr.ret_val);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(backend_open_obj,2,3,backend_open);
static mp_obj_t backend_start(void) {
    require_open();
    if(!audio_configured) mp_raise_msg(&mp_type_OSError,MP_ERROR_TEXT("configure audio first"));
    if (thread_owned || stream_attempted) mp_raise_msg(&mp_type_OSError, MP_ERROR_TEXT("audio already started"));
    // Native-only worker: no Python VM frames execute on this stack.
    synthesizing = true; size_t stack = 2048;
    mp_thread_create(synth, NULL, &stack); thread_owned = true;
    uint64_t deadline = time_us_64()+2000000;
    while (stream_produced < 2*STREAM_HALF) {
        mp_handle_pending(true);
        if (time_us_64() >= deadline) mp_raise_msg(&mp_type_OSError, MP_ERROR_TEXT("FM startup timeout"));
    }
    stream_attempted = true; check(stream_start(&gpu)); playing = true; return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(backend_start_obj, backend_start);
static mp_obj_t backend_service(void) { require_open(); pump(); return mp_const_none; }
static MP_DEFINE_CONST_FUN_OBJ_0(backend_service_obj, backend_service);
static uint32_t elapsed_us(void) {
    require_open();
    if (!playing) mp_raise_msg(&mp_type_OSError, MP_ERROR_TEXT("start audio first"));
    return (uint32_t)(time_us_64()-stream_statistics()->start_us);
}
static mp_obj_t backend_elapsed(void) { return mp_obj_new_int_from_uint(elapsed_us()); }
static MP_DEFINE_CONST_FUN_OBJ_0(backend_elapsed_obj, backend_elapsed);
static mp_obj_t backend_wait(mp_obj_t until_obj) {
    mp_int_t until = mp_obj_get_int(until_obj);
    if (until < 0) mp_raise_ValueError(MP_ERROR_TEXT("negative deadline"));
    require_open();
    do { pump(); mp_handle_pending(true); } while (elapsed_us() < (uint32_t)until);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(backend_wait_obj, backend_wait);
static mp_obj_t backend_check(void) {
    require_open();
    if (!playing) mp_raise_msg(&mp_type_OSError, MP_ERROR_TEXT("start audio first"));
    uint8_t l, r, h; check(stream_check(&l, &r, &h));
    if (((l|r)&0x38) || (h&6)) check(-25);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(backend_check_obj, backend_check);
static mp_obj_t backend_stats(void) {
    const stream_stats *s = stream_statistics();
    mp_obj_t v[] = {mp_obj_new_int_from_uint(s->halves), mp_obj_new_int_from_uint(s->worst_latency_us), mp_obj_new_int_from_uint(fm_peak()), mp_obj_new_int_from_uint(fm_clipped())};
    return mp_obj_new_tuple(MP_ARRAY_SIZE(v), v);
}
static MP_DEFINE_CONST_FUN_OBJ_0(backend_stats_obj, backend_stats);
static mp_obj_t backend_note(size_t n_args, const mp_obj_t *a) {
    require_open();
    if(!audio_configured) mp_raise_msg(&mp_type_OSError,MP_ERROR_TEXT("configure audio first"));
    int v=mp_obj_get_int(a[0]), p=mp_obj_get_int(a[1]), n=mp_obj_get_int(a[2]), vel=mp_obj_get_int(a[3]), gate=n_args==5?mp_obj_get_int(a[4]):0;
    if (v<0 || v>=7 || p<0 || p>=16 || n<0 || n>127 || vel<0 || vel>255 || gate<0 || gate>60000) mp_raise_ValueError(MP_ERROR_TEXT("invalid FM note"));
    if (!fm_note_on(v,p,n,vel,gate)) mp_raise_msg(&mp_type_OSError, MP_ERROR_TEXT("FM command queue full; service audio"));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(backend_note_obj, 4, 5, backend_note);
static mp_obj_t backend_off(mp_obj_t voice) {
    require_open(); int v=mp_obj_get_int(voice);
    if(!audio_configured) mp_raise_msg(&mp_type_OSError,MP_ERROR_TEXT("configure audio first"));
    if (v<0 || v>=7) mp_raise_ValueError(MP_ERROR_TEXT("voice must be 0..6"));
    if (!fm_note_off(v)) mp_raise_msg(&mp_type_OSError, MP_ERROR_TEXT("FM command queue full"));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(backend_off_obj, backend_off);
static mp_obj_t backend_all_off(void) {
    require_open();
    if(!audio_configured) mp_raise_msg(&mp_type_OSError,MP_ERROR_TEXT("configure audio first"));
    if (!fm_all_off()) mp_raise_msg(&mp_type_OSError, MP_ERROR_TEXT("FM command queue full"));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(backend_all_off_obj, backend_all_off);
static mp_obj_t backend_command(size_t n,const mp_obj_t *a) {
    (void)n; require_open();
    if(!audio_configured) mp_raise_msg(&mp_type_OSError,MP_ERROR_TEXT("configure audio first"));
    unsigned v[6];
    for(unsigned i=0;i<6;i++) { mp_int_t x=mp_obj_get_int(a[i]); if(x<0) mp_raise_ValueError(MP_ERROR_TEXT("negative FM command field")); v[i]=x; }
    if(!fm_command(v[0],v[1],v[2],v[3],v[4],v[5])) mp_raise_msg(&mp_type_OSError,MP_ERROR_TEXT("invalid FM command or queue full"));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(backend_command_obj,6,6,backend_command);
static mp_obj_t backend_fence(void) { require_open(); pump(); check(kfb_fence(&gpu)); return mp_const_none; }
static MP_DEFINE_CONST_FUN_OBJ_0(backend_fence_obj,backend_fence);
static void ints(size_t n,const mp_obj_t *a,int *v) { for(size_t i=0;i<n;i++) v[i]=mp_obj_get_int(a[i]); }
static mp_obj_t backend_fill(size_t n,const mp_obj_t *a) {
    (void)n; require_open(); int v[6]; ints(6,a,v);
    if(v[3]>0 && v[4]>0) { pump(); check(kfb_fill_rect(&gpu,v[0],v[1],v[2],v[3],v[4],v[5])); }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(backend_fill_obj,6,6,backend_fill);
static mp_obj_t backend_copy(size_t n,const mp_obj_t *a) {
    (void)n; require_open(); int v[8]; ints(8,a,v); pump();
    check(kfb_copy_rect(&gpu,v[0],v[1],v[2],v[3],v[4],v[5],v[6],v[7])); return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(backend_copy_obj,8,8,backend_copy);
static mp_obj_t backend_palette(mp_obj_t index,mp_obj_t rgb) {
    require_open(); int i=mp_obj_get_int(index),c=mp_obj_get_int(rgb); pump(); check(kfb_palette(&gpu,i,c)); return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(backend_palette_obj,backend_palette);
static mp_obj_t backend_present(mp_obj_t page) {
    require_open(); int p=mp_obj_get_int(page); pump(); check(kfb_present(&gpu,p)); return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(backend_present_obj,backend_present);
static int write_bytes(uint32_t address,const uint8_t *data,size_t n) {
    while(n) {
        int rc=playing?stream_service():0; if(rc) return rc;
        size_t take=n<64?n:64; rc=kfb_write_bytes(&gpu,address,data,take); if(rc) return rc;
        address+=take; data+=take; n-=take;
    }
    return 0;
}
static mp_obj_t backend_write(mp_obj_t address,mp_obj_t data) {
    require_open(); mp_int_t a=mp_obj_get_int(address);
    mp_buffer_info_t b; mp_get_buffer_raise(data,&b,MP_BUFFER_READ);
    if(a<0 || a>0x400000 || b.len>0x400000u-a) mp_raise_ValueError(MP_ERROR_TEXT("write outside PSRAM"));
    check(write_bytes(a,b.buf,b.len)); return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(backend_write_obj,backend_write);
static mp_obj_t backend_read(mp_obj_t address,mp_obj_t data) {
    require_open(); mp_int_t a=mp_obj_get_int(address);
    mp_buffer_info_t b; mp_get_buffer_raise(data,&b,MP_BUFFER_WRITE);
    if(a<0 || a>0x400000 || b.len>0x400000u-a) mp_raise_ValueError(MP_ERROR_TEXT("read outside PSRAM"));
    size_t left=b.len; uint8_t *d=b.buf;
    while(left) { size_t n=left<64?left:64; pump(); check(kfb_read_bytes(&gpu,a,d,n)); a+=n; d+=n; left-=n; }
    return mp_obj_new_int_from_uint(b.len);
}
static MP_DEFINE_CONST_FUN_OBJ_2(backend_read_obj,backend_read);
static mp_obj_t backend_copy_bytes(size_t n,const mp_obj_t *a) {
    (void)n; require_open(); int v[3]; ints(3,a,v);
    int src=v[0],dst=v[1],len=v[2];
    if(src<0 || dst<0 || len<0 || src>0x400000 || dst>0x400000 || len>0x400000-src || len>0x400000-dst ||
       (len && src<dst+len && dst<src+len)) mp_raise_ValueError(MP_ERROR_TEXT("invalid or overlapping byte copy"));
    uint8_t block[64];
    while(len) {
        unsigned take=len<64?len:64;
        pump(); check(kfb_read_bytes(&gpu,src,block,take)); check(write_bytes(dst,block,take));
        src+=take; dst+=take; len-=take;
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(backend_copy_bytes_obj,3,3,backend_copy_bytes);
static mp_obj_t backend_bitmap(size_t n,const mp_obj_t *a) {
    (void)n; require_open(); int v[6]; ints(6,a,v);
    int page=v[0],x=v[1],y=v[2],w=v[3],h=v[4],stride=v[5],fg=mp_obj_get_int(a[7]),bg=mp_obj_get_int(a[8]);
    mp_buffer_info_t b; mp_get_buffer_raise(a[6],&b,MP_BUFFER_READ);
    if(page<0 || page>1 || x<0 || x>640 || y<0 || y>360 || w<1 || w>32 || (x|w)&1 || w>640-x || h<1 || h>32 || h>360-y || stride<1 || stride>4 || w>stride*8 || b.len!=(size_t)(stride*h) || fg<0 || fg>15 || bg<0 || bg>15) mp_raise_ValueError(MP_ERROR_TEXT("invalid mono bitmap"));
    const uint8_t *bits=b.buf; uint8_t row[16];
    for(int r=0;r<h;r++) {
        memset(row,bg*17,w/2);
        for(int c=0;c<w;c++) if(bits[r*stride+c/8]&(128>>(c&7))) row[c/2]=c&1?(row[c/2]&0xf0)|fg:(row[c/2]&15)|(fg<<4);
        check(write_bytes(page*115200u+(y+r)*320u+x/2,row,w/2));
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(backend_bitmap_obj,9,9,backend_bitmap);
static mp_obj_t backend_glyphs(size_t n,const mp_obj_t *a) {
    (void)n; require_open();
    int page=mp_obj_get_int(a[0]),x=mp_obj_get_int(a[1]),y=mp_obj_get_int(a[2]);
    mp_buffer_info_t glyphs,advances,bitmaps;
    mp_get_buffer_raise(a[3],&glyphs,MP_BUFFER_READ); mp_get_buffer_raise(a[4],&advances,MP_BUFFER_READ);
    mp_get_buffer_raise(a[5],&bitmaps,MP_BUFFER_READ);
    int height=mp_obj_get_int(a[6]),first=mp_obj_get_int(a[7]),last=mp_obj_get_int(a[8]);
    int fg=mp_obj_get_int(a[9]),bg=mp_obj_get_int(a[10]),scale=mp_obj_get_int(a[11]);
    if(page<0 || page>1 || x<0 || x>=640 || (x&1) || y<0 || height<1 || height>32 || scale<1 || scale>8 || y+height*scale>360 || fg<0 || fg>15 || bg<0 || bg>15 || first<0 || last<first || (size_t)last>glyphs.len || last>1024 || advances.len<1 || advances.len>256 || bitmaps.len!=advances.len*height*2) mp_raise_ValueError(MP_ERROR_TEXT("invalid glyph run"));
    const uint8_t *adv=advances.buf,*gl=glyphs.buf,*rows=bitmaps.buf;
    unsigned skip=0,width=0;
    for(int i=0;i<last;i++) {
        if(gl[i]>=advances.len || adv[gl[i]]<2 || adv[gl[i]]>16 || (adv[gl[i]]&1)) mp_raise_ValueError(MP_ERROR_TEXT("invalid glyph metrics"));
        if(i<first) skip+=adv[gl[i]]*scale; else width+=adv[gl[i]]*scale;
    }
    if(skip>=(unsigned)(640-x) || !width) return mp_const_none;
    x+=skip; if(width>(unsigned)(640-x)) width=640-x;
    uint8_t line[320];
    for(int r=0;r<height*scale;r++) {
        memset(line,bg*17,width/2); unsigned px=0;
        for(int i=first;i<last && px<width;i++) {
            const uint8_t *p=rows+2*(gl[i]*height+r/scale); unsigned bits=p[0]|((unsigned)p[1]<<8),advance=adv[gl[i]];
            for(unsigned c=0;c<advance*scale && px<width;c++,px++)
                if(bits>>(advance-1-c/scale)&1) line[px/2]=px&1?(line[px/2]&0xf0)|fg:(line[px/2]&15)|(fg<<4);
        }
        check(write_bytes(page*115200u+(y+r)*320u+x/2,line,width/2));
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(backend_glyphs_obj,12,12,backend_glyphs);
static mp_obj_t backend_cursor(size_t n,const mp_obj_t *a) {
    (void)n; require_open(); int v[4]; ints(4,a,v); bool visible=mp_obj_is_true(a[4]);
    if(!(capabilities&32)) return mp_const_false;
    int x=v[0],y=v[1],cell=v[2],height=v[3];
    if(x<0 || x>=640 || y<0 || y>=360 || cell<1 || cell>16 || height<2 || height>32) mp_raise_ValueError(MP_ERROR_TEXT("invalid cursor"));
    if(!cursor_ready || cursor_cell!=(unsigned)cell || cursor_height!=(unsigned)height) {
        uint8_t status; check(kfb_cursor_wait(&gpu,NULL)); check(kfb_cursor_status(&gpu,&status,NULL));
        cursor_bank=1-((status>>1)&1);
        uint8_t shape[256]={0}; const uint16_t colors[3]={0xfff,0,0};
        for(int r=height-2;r<height;r++) for(int c=0;c<cell;c++) shape[r*8+c/4]|=1u<<((3-c%4)*2);
        check(kfb_cursor_shape(&gpu,cursor_bank,shape,colors,0,0));
        cursor_cell=cell; cursor_height=height; cursor_ready=true;
    }
    check(kfb_cursor_move(&gpu,x,y,cursor_bank,visible)); check(kfb_cursor_wait(&gpu,NULL));
    return mp_const_true;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(backend_cursor_obj,5,5,backend_cursor);
#define ENTRY(name,obj) {MP_ROM_QSTR(MP_QSTR_##name),MP_ROM_PTR(&obj##_obj)}
static const mp_rom_map_elem_t globals[]={
    {MP_ROM_QSTR(MP_QSTR___name__),MP_ROM_QSTR(MP_QSTR__kagura)},
    ENTRY(open,backend_open),ENTRY(close,backend_close),ENTRY(start,backend_start),ENTRY(service,backend_service),
    ENTRY(elapsed_us,backend_elapsed),ENTRY(wait_until,backend_wait),ENTRY(check,backend_check),ENTRY(stats,backend_stats),
    ENTRY(note_on,backend_note),ENTRY(note_off,backend_off),ENTRY(all_off,backend_all_off),ENTRY(fill,backend_fill),
    ENTRY(copy,backend_copy),ENTRY(palette,backend_palette),ENTRY(present,backend_present),
    ENTRY(display_open,backend_display_open),ENTRY(write,backend_write),ENTRY(copy_bytes,backend_copy_bytes),
    ENTRY(bitmap,backend_bitmap),ENTRY(cursor,backend_cursor),
    ENTRY(command,backend_command),ENTRY(read_into,backend_read),ENTRY(fence,backend_fence),
    ENTRY(glyph_run,backend_glyphs),
    ENTRY(interrupt_guard,backend_interrupt_guard),
    ENTRY(generation,backend_generation),
    ENTRY(is_open,backend_is_open),
};
static MP_DEFINE_CONST_DICT(globals_dict,globals);
const mp_obj_module_t kagura_module={.base={&mp_type_module},.globals=(mp_obj_dict_t *)&globals_dict};
MP_REGISTER_MODULE(MP_QSTR__kagura,kagura_module);

MP_REGISTER_ROOT_POINTER(mp_obj_t kagura_schedule);
