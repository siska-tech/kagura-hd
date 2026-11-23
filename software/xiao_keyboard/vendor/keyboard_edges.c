#include "keyboard.h"

#include <stddef.h>
#include <string.h>

bool keyboard_report_has_key(const keyboard_report_t *report, uint8_t usage)
{
    return usage != 0u && memchr(report->keys, usage, sizeof(report->keys)) != NULL;
}

void keyboard_report_diff(const keyboard_report_t *previous,
                          const keyboard_report_t *current,
                          keyboard_edge_fn emit)
{
    for (uint8_t bit = 0; bit < 8u; ++bit) {
        const uint8_t mask = (uint8_t)(1u << bit);
        if ((previous->modifiers ^ current->modifiers) & mask)
            emit((uint8_t)(0xe0u + bit), current->modifiers,
                 (current->modifiers & mask) != 0);
    }

    for (size_t i = 0; i < sizeof(previous->keys); ++i) {
        const uint8_t usage = previous->keys[i];
        if (usage && !keyboard_report_has_key(current, usage) &&
            memchr(previous->keys, usage, i) == NULL)
            emit(usage, current->modifiers, false);
    }
    for (size_t i = 0; i < sizeof(current->keys); ++i) {
        const uint8_t usage = current->keys[i];
        if (usage && !keyboard_report_has_key(previous, usage) &&
            memchr(current->keys, usage, i) == NULL)
            emit(usage, current->modifiers, true);
    }
}
