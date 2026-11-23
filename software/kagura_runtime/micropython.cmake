# Generic KAGURA-HD MicroPython firmware. No application sources or assets.
set(KAGURA_RUNTIME ${CMAKE_CURRENT_LIST_DIR})
set(KAGURA_NATIVE ${KAGURA_RUNTIME}/native)
set(KAGURA_HOST_LANES 4 CACHE STRING "GPU host lanes (1 SPI, 4 QSPI)")
if(NOT KAGURA_HOST_LANES MATCHES "^(1|4)$")
    message(FATAL_ERROR "KAGURA_HOST_LANES must be 1 or 4")
endif()
set(MICROPY_MANIFEST_KAGURA_BOOT_DIR "${CMAKE_CURRENT_BINARY_DIR}/kagura_boot")
file(MAKE_DIRECTORY "${MICROPY_MANIFEST_KAGURA_BOOT_DIR}")
file(READ "${MICROPY_DIR}/ports/rp2/modules/_boot.py" KAGURA_UPSTREAM_BOOT)
file(WRITE "${MICROPY_MANIFEST_KAGURA_BOOT_DIR}/_boot.py"
    "${KAGURA_UPSTREAM_BOOT}\nimport kagura_repl\nkagura_repl.autostart()\n")
add_library(usermod_kagura INTERFACE)
target_sources(usermod_kagura INTERFACE ${KAGURA_NATIVE}/modkagura.c
    ${KAGURA_NATIVE}/fm.c ${KAGURA_NATIVE}/pcm_stream.c ${KAGURA_NATIVE}/transport.c
    ${KAGURA_RUNTIME}/../kagura_fb/kagura_fb.c)
target_include_directories(usermod_kagura INTERFACE ${KAGURA_NATIVE})
target_compile_definitions(usermod_kagura INTERFACE KFB_PACK_DESCRIPTOR=1 KAGURA_RAMFUNC=1 KAGURA_HOST_LANES=${KAGURA_HOST_LANES})
set_source_files_properties(${KAGURA_NATIVE}/fm.c ${KAGURA_NATIVE}/pcm_stream.c
    ${KAGURA_NATIVE}/transport.c ${KAGURA_RUNTIME}/../kagura_fb/kagura_fb.c
    PROPERTIES COMPILE_OPTIONS "-O2")
if(KAGURA_PIOASM_EXECUTABLE AND NOT TARGET pioasm)
    add_executable(pioasm IMPORTED GLOBAL)
    set_target_properties(pioasm PROPERTIES IMPORTED_LOCATION "${KAGURA_PIOASM_EXECUTABLE}")
endif()
pico_generate_pio_header(usermod_kagura ${KAGURA_NATIVE}/kagura_host.pio)
target_link_libraries(usermod_kagura INTERFACE pico_multicore hardware_pio)
target_link_libraries(usermod INTERFACE usermod_kagura)
