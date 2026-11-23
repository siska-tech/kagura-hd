#include "bridge.h"
#include "keymap.h"
uint8_t hd_keycode(uint8_t usage, uint8_t modifiers, bool caps) {
    if (usage >= 4 && usage <= 0x1d) {
        bool upper = ((modifiers & 0x22) != 0) != caps;
        return (uint8_t)((upper ? 'A' : 'a') + usage - 4);
    }
    // JIS 109 digit row, rather than the US shifted symbols of the old mapper.
    if (usage >= 0x1e && usage <= 0x27 && (modifiers & 0x22)) {
        static const char shifted[] = "!\"#$%&'()0";
        return (uint8_t)shifted[usage - 0x1e];
    }
    return keyboard_usage_to_code(usage, modifiers);
}
bool hd_repeatable(uint8_t usage) {
    return usage >= 4 && usage < 0x65 && usage != 0x39;
}
