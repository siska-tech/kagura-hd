# SPDX-License-Identifier: Apache-2.0
# MIDNIGHT TERMINAL: RP2040 Flash image. Artwork/fonts stay in Flash (XIP);
# the synthesizer inner loops are placed in RAM (.time_critical).
cmake_minimum_required(VERSION 3.13)
include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)
project(midnight_terminal C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()
set(SW "${CMAKE_CURRENT_SOURCE_DIR}/..")
set(MT "${SW}/midnight_terminal")
set(QSPI "${SW}/beyond16/src")
set(PIO_HEADER "${CMAKE_CURRENT_BINARY_DIR}/kagura_host.pio.h")
add_custom_command(OUTPUT "${PIO_HEADER}"
    COMMAND "${MT}/out/pioasm/pioasm.exe" -o c-sdk "${MT}/vendor/kagura_host.pio" "${PIO_HEADER}"
    DEPENDS "${MT}/vendor/kagura_host.pio" VERBATIM)
add_executable(midnight_terminal
    src/rp2040_main.c src/mt_fm.c src/mt_show.c src/mt_inflate.c src/stream.c generated/assets.c "${SW}/fm_megademo/src/font.c"
    "${QSPI}/b16_qspi.c" "${SW}/kagura_fb/kagura_fb.c" "${PIO_HEADER}")
target_include_directories(midnight_terminal PRIVATE "${QSPI}" "${CMAKE_CURRENT_BINARY_DIR}" src generated)
target_compile_definitions(midnight_terminal PRIVATE KFB_PACK_DESCRIPTOR=1 MT_RAMFUNC=1)
target_link_libraries(midnight_terminal pico_stdlib pico_multicore hardware_pio)
target_compile_options(midnight_terminal PRIVATE -Wall -Wextra -O2)
pico_enable_stdio_uart(midnight_terminal 0)
pico_enable_stdio_usb(midnight_terminal 1)
pico_add_extra_outputs(midnight_terminal)
