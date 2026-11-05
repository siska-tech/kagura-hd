cmake_minimum_required(VERSION 3.13)
include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)
project(midnight_terminal C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()
set(MT_PIOASM "${CMAKE_CURRENT_SOURCE_DIR}/out/pioasm/pioasm.exe" CACHE FILEPATH "Host pioasm executable")
add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/kagura_host.pio.h
 COMMAND ${MT_PIOASM} -o c-sdk ${CMAKE_CURRENT_SOURCE_DIR}/vendor/kagura_host.pio ${CMAKE_CURRENT_BINARY_DIR}/kagura_host.pio.h
 DEPENDS vendor/kagura_host.pio VERBATIM)
add_executable(midnight_terminal src/mt.c src/mt_device.c src/mt_qspi.c src/mt_preflight.c src/mt_lz.c src/rp2040_main.c ../kagura_fb/kagura_fb.c ${CMAKE_CURRENT_BINARY_DIR}/kagura_host.pio.h)
target_include_directories(midnight_terminal PRIVATE src ../kagura_fb ${CMAKE_CURRENT_BINARY_DIR})
target_link_libraries(midnight_terminal pico_stdlib hardware_pio)
target_compile_options(midnight_terminal PRIVATE -Wall -Wextra -fstack-usage)
target_compile_definitions(midnight_terminal PRIVATE PICO_STACK_SIZE=0x1000 MT_COMPRESSED_BGM=1)
pico_enable_stdio_uart(midnight_terminal 1)
pico_enable_stdio_usb(midnight_terminal 1)
# ELF/bin only: deliberately no UF2/program/upload/flash target.
add_custom_command(TARGET midnight_terminal POST_BUILD COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:midnight_terminal> ${CMAKE_CURRENT_BINARY_DIR}/midnight_terminal.bin)
