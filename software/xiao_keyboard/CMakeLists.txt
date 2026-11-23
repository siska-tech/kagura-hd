cmake_minimum_required(VERSION 3.13)
include(${PICO_SDK_PATH}/external/pico_sdk_import.cmake)
project(kagura_hd_xiao C CXX ASM)
set(PICO_FLASH_SIZE_BYTES 262144 CACHE STRING "Preserve the existing storage above 256 KiB" FORCE)
pico_sdk_init()
include(FetchContent)
FetchContent_Declare(pico_pio_usb
    GIT_REPOSITORY https://github.com/sekigon-gonnoc/Pico-PIO-USB.git
    GIT_TAG b186e36bea0f3bcc2ee94ca1fa81e7f71281443a GIT_SHALLOW FALSE)
FetchContent_MakeAvailable(pico_pio_usb)
add_executable(kagura_hd_xiao main.c bridge.c vendor/xlink.c vendor/keyboard.c
    vendor/keyboard_edges.c vendor/keymap.c vendor/usb_host.c vendor/usb_descriptors.c
    ${PICO_TINYUSB_PATH}/src/portable/raspberrypi/pio_usb/dcd_pio_usb.c
    ${PICO_TINYUSB_PATH}/src/portable/raspberrypi/pio_usb/hcd_pio_usb.c)
target_include_directories(kagura_hd_xiao PRIVATE vendor)
target_compile_definitions(kagura_hd_xiao PRIVATE PIO_USB_USE_TINYUSB)
target_compile_options(kagura_hd_xiao PRIVATE -Wall -Wextra)
set_source_files_properties(main.c bridge.c PROPERTIES COMPILE_OPTIONS -Werror)
target_link_libraries(kagura_hd_xiao pico_stdlib pico_multicore pico_pio_usb
    hardware_uart tinyusb_device tinyusb_host)
pico_enable_stdio_usb(kagura_hd_xiao 0)
pico_enable_stdio_uart(kagura_hd_xiao 0)
option(XIAO_BRIDGE_RAM "Build a RAM-only test image" OFF)
if(XIAO_BRIDGE_RAM)
    pico_set_binary_type(kagura_hd_xiao no_flash)
endif()
pico_add_extra_outputs(kagura_hd_xiao)
