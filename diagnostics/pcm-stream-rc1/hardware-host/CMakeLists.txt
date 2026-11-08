# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.13)
include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)
project(pcm_stream_hw C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()
set(SW "${CMAKE_CURRENT_SOURCE_DIR}/../../../software")
set(MT "${SW}/midnight_terminal")
set(QSPI "${SW}/beyond16/src")
set(PIO_HEADER "${CMAKE_CURRENT_BINARY_DIR}/kagura_host.pio.h")
add_custom_command(OUTPUT "${PIO_HEADER}"
    COMMAND "${MT}/out/pioasm/pioasm.exe" -o c-sdk "${MT}/vendor/kagura_host.pio" "${PIO_HEADER}"
    DEPENDS "${MT}/vendor/kagura_host.pio" VERBATIM)
add_executable(pcm_stream_hw main.c "${QSPI}/b16_qspi.c"
    "${SW}/kagura_fb/kagura_fb.c" "${PIO_HEADER}")
target_include_directories(pcm_stream_hw PRIVATE "${QSPI}" "${CMAKE_CURRENT_BINARY_DIR}")
target_link_libraries(pcm_stream_hw pico_stdlib hardware_pio)
target_compile_options(pcm_stream_hw PRIVATE -Wall -Wextra)
pico_enable_stdio_uart(pcm_stream_hw 0)
pico_enable_stdio_usb(pcm_stream_hw 1)
pico_set_binary_type(pcm_stream_hw no_flash)

option(STREAM_DRAWING_TESTS "Include the BEYOND BLIT STORM and megademo renderer" OFF)
if(STREAM_DRAWING_TESTS)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    set(DEMO_SOURCE "${CMAKE_CURRENT_BINARY_DIR}/b16-stream.c")
    add_custom_command(OUTPUT "${DEMO_SOURCE}"
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/prepare-demo.py" "${QSPI}/b16.c" "${DEMO_SOURCE}"
        DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/prepare-demo.py" "${QSPI}/b16.c" VERBATIM)
    set_source_files_properties("${DEMO_SOURCE}" PROPERTIES COMPILE_DEFINITIONS
        "kfb_copy_rect=stream_copy_rect;kfb_fill_rect=stream_fill_rect;kfb_palette=stream_palette;kfb_present=stream_present")
    target_sources(pcm_stream_hw PRIVATE "${DEMO_SOURCE}" "${MT}/src/mt_lz.c")
    target_include_directories(pcm_stream_hw PRIVATE "${MT}/src" "${SW}/beyond16/generated")
    target_compile_definitions(pcm_stream_hw PRIVATE STREAM_DRAWING_TESTS=1)
endif()
