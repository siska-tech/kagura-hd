#include "bridge.h"
#include "keyboard.h"
#include <assert.h>
#include <stdio.h>
static unsigned downs,ups;
static void edge(uint8_t usage,uint8_t modifiers,bool down) {
    (void)usage;(void)modifiers;if(down)downs++;else ups++;
}
int main(void) {
    assert(hd_keycode(4,0,false)=='a');assert(hd_keycode(4,2,false)=='A');
    assert(hd_keycode(4,0,true)=='A');assert(hd_keycode(4,2,true)=='a');
    assert(hd_keycode(0x1f,2,false)=='"');assert(hd_keycode(0x23,2,false)=='&');
    assert(hd_keycode(0x87,2,false)=='|');assert(hd_keycode(0x28,0,false)==13);
    assert(hd_repeatable(4));assert(!hd_repeatable(0x39));assert(!hd_repeatable(0xe0));
    keyboard_report_t empty={0},held={.keys={4,4,0,0,0,0}};
    keyboard_report_diff(&empty,&held,edge);assert(downs==1);
    keyboard_report_diff(&held,&empty,edge);assert(ups==1);
    puts("HD keymap/repeat/edge tests PASS");
}
