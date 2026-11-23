// KAGURA-HD variant of the kagura-6502 XIAO USB keyboard host.
// No CPU supervisor, NMI/reset outputs, boot images or filesystem writes.
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/bootrom.h"
#include "hardware/clocks.h"
#include "hardware/uart.h"
#include "hardware/watchdog.h"
#include "tusb.h"
#include "keyboard.h"
#include "usb_host.h"
#include "xlink.h"
#include "bridge.h"
#include <string.h>

static bool tx_enabled, enabled=true, caps;
static uint32_t high_since, repeat_due;
static uint8_t repeat_usage;
static uint16_t delay_ms=500, period_ms=33;
static keyboard_report_t held;

bool xlink_send_frame(uint8_t type, const uint8_t *data, uint8_t n) {
    if(!tx_enabled) return false;
    uint8_t crc=xlink_crc8_update(xlink_crc8_update(0,type),n);
    uart_putc_raw(uart0,0x7e);uart_putc_raw(uart0,type);uart_putc_raw(uart0,n);
    for(unsigned i=0;i<n;i++){uart_putc_raw(uart0,data[i]);crc=xlink_crc8_update(crc,data[i]);}
    uart_putc_raw(uart0,crc);
    return true;
}
static void status(void) {
    const uint8_t payload[]={'K','H','D','K',1,usb_host_keyboard_connected()};
    xlink_send_frame(HD_STATUS,payload,sizeof payload);
}
static void key(uint8_t usage,uint8_t modifiers,bool down,bool repeat) {
    if(!enabled || !tx_enabled) return;
    uint8_t flags=(down?1:0)|(repeat?2:0)|((modifiers&0x22)?4:0)|((modifiers&0x11)?8:0)|((modifiers&0x44)?16:0);
    const uint8_t payload[]={usage,modifiers,flags,hd_keycode(usage,modifiers,caps)};
    xlink_send_frame(HD_KEY,payload,4);
}
static void edge(uint8_t usage,uint8_t modifiers,bool down) {
    if(usage==0x39 && down) caps=!caps;
    key(usage,modifiers,down,false);
    if(down && hd_repeatable(usage)) {repeat_usage=usage;repeat_due=to_ms_since_boot(get_absolute_time())+delay_ms;}
    else if(!down && repeat_usage==usage) repeat_usage=0;
}
int main(void) {
    set_sys_clock_khz(120000,true);
    uart_init(uart0,115200);
    uart_set_format(uart0,8,1,UART_PARITY_NONE);
    uart_set_fifo_enabled(uart0,true);
    gpio_init(0);gpio_set_dir(0,GPIO_IN);gpio_pull_down(0);
    gpio_init(1);gpio_pull_down(1);gpio_set_function(1,GPIO_FUNC_UART);
    keyboard_init();usb_pointer_init();
    xlink_decoder_t decoder;xlink_decoder_init(&decoder);
    tud_init(0);
    multicore_launch_core1(usb_host_task);
    watchdog_enable(3000,true);
    uint32_t last_status=0,last_rx=0;
    char cdc_command[16];unsigned cdc_length=0;
    while(true) {
        watchdog_update();tud_task();
        uint32_t now=to_ms_since_boot(get_absolute_time());
        if(!tx_enabled) {
            if(!gpio_get(1)) high_since=now;
            else if((uint32_t)(now-high_since)>=5) {
                gpio_set_function(0,GPIO_FUNC_UART);tx_enabled=true;
                keyboard_report_t empty={0};keyboard_report_diff(&empty,&held,edge);status();
            }
        }
        while(uart_is_readable(uart0)) {
            uint8_t byte=uart_getc(uart0);
            if((uint32_t)(now-last_rx)>100) xlink_decoder_init(&decoder);
            last_rx=now;
            xlink_frame_t frame;
            if(xlink_decoder_push(&decoder,byte,&frame)==XLINK_DECODE_FRAME) {
                if(frame.type==HD_HELLO && frame.length==4 && !memcmp(frame.payload,"KHD1",4)) status();
                if(frame.type==HD_CONFIG && frame.length==7) {
                    unsigned delay=frame.payload[2]|(frame.payload[3]<<8),period=frame.payload[4]|(frame.payload[5]<<8);
                    if(frame.payload[0]<=1 && frame.payload[1]==1 && !frame.payload[6] && delay>=250 && delay<=2000 && period>=10 && period<=500) {
                        enabled=frame.payload[0];delay_ms=delay;period_ms=period;repeat_usage=0;status();
                    }
                }
            }
        }
        keyboard_report_t report;
        int result=keyboard_report_pop(&report);
        if(result) {
            if(result<0) memset(&report,0,sizeof report);
            keyboard_report_diff(&held,&report,edge);held=report;
        }
        if(tx_enabled && enabled && repeat_usage && keyboard_report_has_key(&held,repeat_usage) && (int32_t)(now-repeat_due)>=0) {
            key(repeat_usage,held.modifiers,true,true);repeat_due=now+period_ms;
        }
        uint8_t pointer[7];usb_pointer_pop(pointer); // discard mouse packets; no REPL pointer protocol
        if(tx_enabled && (uint32_t)(now-last_status)>=1000){status();last_status=now;}
        while(tud_cdc_available()) {
            int ch=tud_cdc_read_char();
            if(ch=='\n') {
                cdc_command[cdc_length]=0;
                if(!strcmp(cdc_command,"BOOTSEL")) {tud_cdc_write_str("BOOTSEL\r\n");tud_cdc_write_flush();sleep_ms(50);reset_usb_boot(0,0);}
                else {tud_cdc_write_str("KAGURA-HD XIAO keyboard bridge v1\r\n");tud_cdc_write_flush();}
                cdc_length=0;
            } else if(ch!='\r' && cdc_length<sizeof(cdc_command)-1) cdc_command[cdc_length++]=(char)ch;
        }
        tight_loop_contents();
    }
}
