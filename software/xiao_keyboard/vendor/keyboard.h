#ifndef KAGURA_KEYBOARD_H
#define KAGURA_KEYBOARD_H

#include <stdbool.h>
#include <stdint.h>

#define KEYBOARD_REPORT_QUEUE_SIZE 32u

typedef struct {
    uint8_t modifiers;
    uint8_t keys[6];
} keyboard_report_t;

typedef void (*keyboard_edge_fn)(uint8_t usage, uint8_t modifiers, bool down);
void keyboard_report_diff(const keyboard_report_t *previous,
                          const keyboard_report_t *current,
                          keyboard_edge_fn emit);
bool keyboard_report_has_key(const keyboard_report_t *report, uint8_t usage);
void keyboard_init(void);
void keyboard_report_received(const keyboard_report_t *report);
int keyboard_report_pop(keyboard_report_t *report);

#endif
