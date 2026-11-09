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
# Host transport, build-time exclusive like the FPGA build: 4 = QSPI (selected
# bitstream), 1 = SPI (tools/build-fb.tcl spi). KAGURA_SPI_PIO_DIV overrides the
# SPI PIO divider (default: the QSPI divider, 5 MHz SCK).
set(KAGURA_HOST_LANES 4 CACHE STRING "Host lanes: 4 QSPI or 1 SPI")
set(KAGURA_SPI_PIO_DIV "" CACHE STRING "SPI PIO clock divider (empty: QSPI divider)")
if(NOT KAGURA_HOST_LANES MATCHES "^(1|4)$")
    message(FATAL_ERROR "KAGURA_HOST_LANES must be 1 or 4")
endif()
target_compile_definitions(midnight_terminal PRIVATE B16_HOST_LANES=${KAGURA_HOST_LANES})
if(KAGURA_SPI_PIO_DIV)
    target_compile_definitions(midnight_terminal PRIVATE B16_SPI_PIO_DIV=${KAGURA_SPI_PIO_DIV}f)
endif()
pico_enable_stdio_uart(midnight_terminal 0)
pico_enable_stdio_usb(midnight_terminal 1)
pico_add_extra_outputs(midnight_terminal)
option(KAGURA_RELEASE_UF2 "Release image: start without a host" OFF)
if(KAGURA_RELEASE_UF2)
    target_compile_definitions(midnight_terminal PRIVATE KAGURA_AUTOSTART_MS=5000)
endif()
