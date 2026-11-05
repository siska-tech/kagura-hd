# SPDX-License-Identifier: Apache-2.0
# Run only from a fresh, isolated build directory. Does not program hardware.
set root [file normalize [file join [file dirname [info script]] ../..]]
if {![string match "[file join $root build]/*" [file normalize [pwd]]]} {
    error "Run from an isolated directory below build/, never repository root"
}
set_device -name GW1NR-9C GW1NR-LV9QN88PC6/I5
set_option -verilog_std sysv2017
foreach path {
    rtl/fb/kagura_fb_burst_ctrl.sv
    rtl/memory/kagura_hyperram_phy_gowin.sv
    diagnostics/psram-wrap-target/wrap_target_engine.sv
    diagnostics/psram/psram_probe_uart.sv
    diagnostics/psram-wrap-target/wrap_target_top.sv
} {add_file -type verilog [file join $root $path]}
add_file -type cst [file join $root diagnostics psram probe.cst]
add_file -type sdc [file join $root diagnostics psram probe.sdc]
set_option -top_module psram_wrap_target_top
set_option -output_base_name psram_wrap_target
set_option -place_option 1
set_option -route_option 2
foreach feature {sspi mspi ready done cpu} {set_option -use_${feature}_as_gpio 1}
run all
