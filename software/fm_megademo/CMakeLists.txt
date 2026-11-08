# SPDX-License-Identifier: Apache-2.0
# FOUR OPERATORS: RAM-only RP2040 ELF (no Flash target). With KAGURA_RELEASE_UF2=ON:
# the same program as a copy_to_ram Flash image (copied to SRAM at boot) that starts without a host.
cmake_minimum_required(VERSION 3.13)
include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)
project(four_operators C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()
set(SW "${CMAKE_CURRENT_SOURCE_DIR}/..")
set(MT "${SW}/midnight_terminal")
set(QSPI "${SW}/beyond16/src")
set(PIO_HEADER "${CMAKE_CURRENT_BINARY_DIR}/kagura_host.pio.h")
add_custom_command(OUTPUT "${PIO_HEADER}"
    COMMAND "${MT}/out/pioasm/pioasm.exe" -o c-sdk "${MT}/vendor/kagura_host.pio" "${PIO_HEADER}"
    DEPENDS "${MT}/vendor/kagura_host.pio" VERBATIM)
add_executable(four_operators
    src/rp2040_main.c src/fm.c src/font.c src/demo.c src/stream.c
    "${QSPI}/b16_qspi.c" "${SW}/kagura_fb/kagura_fb.c" "${PIO_HEADER}")
target_include_directories(four_operators PRIVATE "${QSPI}" "${CMAKE_CURRENT_BINARY_DIR}")
target_compile_definitions(four_operators PRIVATE KFB_PACK_DESCRIPTOR=1)
target_link_libraries(four_operators pico_stdlib pico_multicore hardware_pio)
target_compile_options(four_operators PRIVATE -Wall -Wextra -O2)
pico_enable_stdio_uart(four_operators 0)
pico_enable_stdio_usb(four_operators 1)
option(KAGURA_RELEASE_UF2 "Release image: Flash copy_to_ram, start without a host" OFF)
if(KAGURA_RELEASE_UF2)
    pico_set_binary_type(four_operators copy_to_ram)
    target_compile_definitions(four_operators PRIVATE KAGURA_AUTOSTART_MS=5000)
else()
    pico_set_binary_type(four_operators no_flash)
endif()
