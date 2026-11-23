#include "keymap.h"

#include <stdbool.h>

#define HID_MOD_SHIFT 0x22u
uint8_t keyboard_usage_to_code(uint8_t usage, uint8_t modifiers)
{
    static const char letters[] = "abcdefghijklmnopqrstuvwxyz";
    static const char digits[] = "1234567890";
    const bool shift = (modifiers & HID_MOD_SHIFT) != 0u;

    if (usage >= 0x04u && usage <= 0x1du) {
        char ch = letters[usage - 0x04u];
        if (shift) {
            ch = (char)(ch - ('a' - 'A'));
        }
        return (uint8_t)ch;
    }
    if (usage >= 0x1eu && usage <= 0x27u) {
        static const char shifted[] = "!@#$%^&*()";
        return (uint8_t)(shift ? shifted[usage - 0x1eu] : digits[usage - 0x1eu]);
    }

    switch (usage) {
    case 0x28: return 0x0d;
    case 0x29: return 0x1b;
    case 0x2a: return 0x08;
    case 0x2b: return 0x09;
    case 0x2c: return ' ';
    case 0x2d: return shift ? '=' : '-';
    case 0x2e: return shift ? '~' : '^';
    case 0x2f: return shift ? '`' : '@';
    case 0x30: return shift ? '{' : '[';
    case 0x31: return shift ? '}' : ']';
    case 0x32: return shift ? '_' : '\\';
    case 0x33: return shift ? '+' : ';';
    case 0x34: return shift ? '*' : ':';
    case 0x35: return 0xa1;
    case 0x36: return shift ? '<' : ',';
    case 0x37: return shift ? '>' : '.';
    case 0x38: return shift ? '?' : '/';
    case 0x4f: return 0x82;
    case 0x50: return 0x80;
    case 0x51: return 0x83;
    case 0x52: return 0x81;
    case 0x87: return shift ? '|' : '\\';
    case 0x89: return 0xa0;
    case 0x8a: return 0xa1;
    case 0x8b: return 0xa0;
    default:
        if (usage >= 0x3au && usage <= 0x45u) {
            return (uint8_t)(0x90u + usage - 0x3au);
        }
        return 0;
    }
}
