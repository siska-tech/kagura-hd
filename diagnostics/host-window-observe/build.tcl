set root [file normalize [file join [file dirname [info script]] ../..]]
if {![string match "[file join $root build]/*" [file normalize [pwd]]]} {error "Run under build/"}
if {[file exists impl]} {error "Refusing existing build"}
set_device -name GW1NR-9C GW1NR-LV9QN88PC6/I5
set_option -verilog_std sysv2017
foreach path {
    rtl/bus/kagura_spi_adapter.sv
    rtl/fb/kagura_fb_registers.sv
    rtl/fb/kagura_fb_upload_word.sv
    rtl/fb/kagura_fb_commands.sv
    rtl/fb/kagura_fb_fill_burst.sv
    diagnostics/psram/psram_probe_uart.sv
    diagnostics/host-window-observe/kagura_fb_host_observe.sv
    diagnostics/host-window-observe/window_observe_core.sv
    diagnostics/host-window-observe/window_snapshot.sv
    diagnostics/host-window-observe/host_isolation_top.sv
} {add_file -type verilog [file join $root $path]}
add_file -type cst [file join $root diagnostics psram-isolation host-isolation.cst]
add_file -type sdc [file join $root diagnostics psram-isolation host-isolation.sdc]
set_option -top_module host_isolation_top
set_option -output_base_name host_isolation
set_option -place_option 1
set_option -route_option 2
foreach feature {sspi mspi ready done cpu} {set_option -use_${feature}_as_gpio 1}
run all
