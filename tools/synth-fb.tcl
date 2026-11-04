# SPDX-License-Identifier: Apache-2.0
# Synthesis only. Internal interfaces are not board pin assignments.
set root [file normalize [file join [file dirname [info script]] ..]]
set top [lindex $argv 0]
if {$top ni {kagura_fb_fill kagura_fb_byte_port kagura_fb_burst_ctrl kagura_fb_arbiter kagura_fb_line_fetch kagura_fb_line_banks}} { error "unsupported FB top" }
set_device -name GW1NR-9C GW1NR-LV9QN88PC6/I5
set_option -verilog_std sysv2017
add_file -type verilog [file join $root rtl fb ${top}.sv]
if {$top eq "kagura_fb_line_banks"} {
    add_file -type verilog [file join $root rtl memory kagura_ram_tdp.sv]
}
set_option -top_module $top
set_option -output_base_name $top
run syn
