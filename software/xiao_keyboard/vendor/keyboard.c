#include "keyboard.h"

#include "pico/critical_section.h"

#include <stdbool.h>
#include <string.h>

static critical_section_t report_lock;
static keyboard_report_t reports[KEYBOARD_REPORT_QUEUE_SIZE];
static uint8_t report_head;
static uint8_t report_tail;
static bool report_overflow;

void keyboard_init(void)
{
    critical_section_init(&report_lock);
    report_head = 0;
    report_tail = 0;
    report_overflow = false;
}

void keyboard_report_received(const keyboard_report_t *report)
{
    critical_section_enter_blocking(&report_lock);
    const uint8_t next =
        (uint8_t)((report_tail + 1u) % KEYBOARD_REPORT_QUEUE_SIZE);
    if (next == report_head) {
        report_head = (uint8_t)((report_head + 1u) % KEYBOARD_REPORT_QUEUE_SIZE);
        report_overflow = true;
    }
    reports[report_tail] = *report;
    report_tail = next;
    critical_section_exit(&report_lock);
}

int keyboard_report_pop(keyboard_report_t *report)
{
    int result = 0;
    critical_section_enter_blocking(&report_lock);
    if (report_overflow) {
        report_overflow = false;
        result = -1;
    } else if (report_head != report_tail) {
        *report = reports[report_head];
        report_head = (uint8_t)((report_head + 1u) % KEYBOARD_REPORT_QUEUE_SIZE);
        result = 1;
    }
    critical_section_exit(&report_lock);
    return result;
}
