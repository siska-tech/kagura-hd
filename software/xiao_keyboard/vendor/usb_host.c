#include "usb_host.h"

#include "keyboard.h"
#include "pio_usb.h"
#include "pico/flash.h"
#include "tusb.h"

#include <stdatomic.h>
#include "pico/critical_section.h"
#include "pointer.h"
#include <string.h>

static critical_section_t mouse_lock;
static uint8_t mouse_dev, mouse_instance;
static uint8_t mouse_reports[16][POINTER_SIZE];
static unsigned mouse_read, mouse_write;
static bool mouse_reset;
static uint8_t mouse_buttons;

void usb_pointer_init(void)
{
    critical_section_init(&mouse_lock);
}

bool usb_pointer_pop(uint8_t *packet)
{
    bool ready = true;
    critical_section_enter_blocking(&mouse_lock);
    if (mouse_reset) {
        memset(packet, 0, POINTER_SIZE);
        packet[0] = POINTER_RESET;
        packet[1] = mouse_buttons;
        mouse_reset = false;
    } else if (mouse_read != mouse_write) {
        memcpy(packet, mouse_reports[mouse_read], POINTER_SIZE);
        mouse_read = (mouse_read + 1) % 16;
    } else {
        ready = false;
    }
    critical_section_exit(&mouse_lock);
    return ready;
}

static void mouse_clear(void)
{
    critical_section_enter_blocking(&mouse_lock);
    mouse_buttons = 0;
    mouse_read = mouse_write;
    mouse_reset = true;
    critical_section_exit(&mouse_lock);
}

static void mouse_report(const uint8_t *report, uint16_t length)
{
    if (!report || length < 3) return;
    critical_section_enter_blocking(&mouse_lock);
    const uint8_t buttons = report[0] & 7u;
    if (mouse_buttons == buttons && !report[1] && !report[2] &&
        (length < 4 || !report[3])) {
        critical_section_exit(&mouse_lock);
        return;
    }
    mouse_buttons = buttons;
    const unsigned next = (mouse_write + 1) % 16;
    if (mouse_reset || next == mouse_read) {
        mouse_read = mouse_write;
        mouse_reset = true;
    } else {
        const uint8_t packet[POINTER_SIZE] = {0, buttons,
            report[1], report[1] & 128 ? 255 : 0,
            report[2], report[2] & 128 ? 255 : 0, length >= 4 ? report[3] : 0};
        memcpy(mouse_reports[mouse_write], packet, sizeof(packet));
        mouse_write = next;
    }
    critical_section_exit(&mouse_lock);
}

static atomic_bool keyboard_connected;
static atomic_int flash_safe_state;
static uint8_t keyboard_dev_addr;
static uint8_t keyboard_instance;

bool usb_host_keyboard_connected(void)
{
    return atomic_load(&keyboard_connected);
}

int usb_host_flash_safe_state(void)
{
    return atomic_load(&flash_safe_state);
}

void tuh_hid_mount_cb(
    uint8_t dev_addr,
    uint8_t instance,
    uint8_t const *desc_report,
    uint16_t desc_len)
{
    (void)desc_report;
    (void)desc_len;
    if (tuh_hid_interface_protocol(dev_addr, instance) == HID_ITF_PROTOCOL_MOUSE) {
        if (!mouse_dev && tuh_hid_receive_report(dev_addr, instance)) {
            mouse_dev = dev_addr;
            mouse_instance = instance;
            mouse_clear();
        }
        return;
    }
    if (tuh_hid_interface_protocol(dev_addr, instance) !=
        HID_ITF_PROTOCOL_KEYBOARD) {
        return;
    }
    if (atomic_load(&keyboard_connected)) {
        return;
    }

    atomic_store(&keyboard_connected, true);
    keyboard_dev_addr = dev_addr;
    keyboard_instance = instance;
    const keyboard_report_t empty = {0};
    keyboard_report_received(&empty);
    if (!tuh_hid_receive_report(dev_addr, instance)) {
        atomic_store(&keyboard_connected, false);
    }
}

void tuh_hid_umount_cb(uint8_t dev_addr, uint8_t instance)
{
    if (mouse_dev == dev_addr && mouse_instance == instance) {
        mouse_dev = 0;
        mouse_clear();
        return;
    }
    if (!atomic_load(&keyboard_connected) || keyboard_dev_addr != dev_addr ||
        keyboard_instance != instance) {
        return;
    }

    atomic_store(&keyboard_connected, false);
    const keyboard_report_t empty = {0};
    keyboard_report_received(&empty);
}

void tuh_hid_report_received_cb(
    uint8_t dev_addr,
    uint8_t instance,
    uint8_t const *report,
    uint16_t length)
{
    if (mouse_dev == dev_addr && mouse_instance == instance) {
        mouse_report(report, length);
        if (!tuh_hid_receive_report(dev_addr, instance))
            tuh_hid_umount_cb(dev_addr, instance);
        return;
    }
    if (!atomic_load(&keyboard_connected) || keyboard_dev_addr != dev_addr ||
        keyboard_instance != instance ||
        tuh_hid_interface_protocol(dev_addr, instance) !=
            HID_ITF_PROTOCOL_KEYBOARD) {
        return;
    }

    // TinyUSB starts keyboard interfaces in boot protocol. This adapter does
    // not decode report IDs, NKRO, or vendor-defined report layouts.
    if (report != NULL && length >= sizeof(hid_keyboard_report_t)) {
        const hid_keyboard_report_t *hid =
            (const hid_keyboard_report_t *)report;
        if (hid->keycode[0] != 1u && hid->keycode[1] != 1u &&
            hid->keycode[2] != 1u && hid->keycode[3] != 1u &&
            hid->keycode[4] != 1u && hid->keycode[5] != 1u) {
            keyboard_report_t state = {0};
            state.modifiers = hid->modifier;
            memcpy(state.keys, hid->keycode, sizeof(state.keys));
            keyboard_report_received(&state);
        }
    }

    if (!tuh_hid_receive_report(dev_addr, instance)) {
        // No further reports can be expected from this interface.
        tuh_hid_umount_cb(dev_addr, instance);
    }
}

void usb_host_task(void)
{
    atomic_store(&flash_safe_state, 1);

    pio_usb_configuration_t config = PIO_USB_DEFAULT_CONFIG;
    config.pin_dp = 6;
    tuh_configure(1, TUH_CFGID_RPI_PIO_USB_CONFIGURATION, &config);
    while (!tuh_init(1)) {
        sleep_ms(1000);
    }

    while (true) {
        tuh_task();
        tight_loop_contents();
    }
}
