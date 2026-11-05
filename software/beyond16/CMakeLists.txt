cmake_minimum_required(VERSION 3.13)
include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)
project(beyond16 C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()
set(MT_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../midnight_terminal")
set(MT_PIOASM "${MT_ROOT}/out/pioasm/pioasm.exe" CACHE FILEPATH "Existing host pioasm")
add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/kagura_host.pio.h
 COMMAND ${MT_PIOASM} -o c-sdk ${MT_ROOT}/vendor/kagura_host.pio ${CMAKE_CURRENT_BINARY_DIR}/kagura_host.pio.h
 DEPENDS ${MT_ROOT}/vendor/kagura_host.pio VERBATIM)
add_executable(beyond16 src/b16.c src/rp2040_main.c ${MT_ROOT}/src/mt_qspi.c ${MT_ROOT}/src/mt_lz.c ../kagura_fb/kagura_fb.c ${CMAKE_CURRENT_BINARY_DIR}/kagura_host.pio.h)
target_include_directories(beyond16 PRIVATE src ${CMAKE_CURRENT_BINARY_DIR})
target_link_libraries(beyond16 pico_stdlib hardware_pio)
target_compile_options(beyond16 PRIVATE -Wall -Wextra -fstack-usage)
target_compile_definitions(beyond16 PRIVATE PICO_STACK_SIZE=0x2000 KFB_PACK_DESCRIPTOR=1)
pico_enable_stdio_uart(beyond16 1)
pico_enable_stdio_usb(beyond16 1)
add_custom_command(TARGET beyond16 POST_BUILD COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:beyond16> ${CMAKE_CURRENT_BINARY_DIR}/beyond16.bin)
# No upload, flash, UF2, SRAM load or device discovery target.
