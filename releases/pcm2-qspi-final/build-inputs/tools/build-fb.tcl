# SPDX-License-Identifier: Apache-2.0
# Kagura-FB standalone integration target. Run prepare-hdmi-stream.py first.
set root [file normalize [file join [file dirname [info script]] ..]]
set transport [expr {[llength $argv]>0 ? [lindex $argv 0] : "spi"}]
if {$transport ni {spi qspi}} { error "Expected spi or qspi" }
set config [file join [pwd] kagura_fb_config.sv]
set configfile [open $config w]
puts $configfile "package kagura_fb_config; localparam integer HOST_LANES=[expr {$transport eq {qspi} ? 4 : 1}]; endpackage"
close $configfile
add_file -type verilog $config
set_device -name GW1NR-9C GW1NR-LV9QN88PC6/I5
set_option -verilog_std sysv2017
set listfile [open [file join $root rtl fb sources.f] r]
foreach path [split [read $listfile] "\n"] {
    set path [string trim $path]
    if {$path ne ""} { add_file -type verilog [file join $root $path] }
}
close $listfile
foreach path {
    rtl/platform/kagura_gowin_serializer.sv
    rtl/platform/kagura_nano9k_clocks.sv
    rtl/memory/kagura_hyperram_phy_gowin.sv
    boards/tang-nano-9k/kagura_fb_top.sv
} { add_file -type verilog [file join $root $path] }
# Gowin uses one active CST; combine video and host pin assignments.
set cst [file join [pwd] kagura_fb.cst]
set cstfile [open $cst w]
foreach fragment {phase1.cst host.cst} {
    set sourcefile [open [file join $root boards tang-nano-9k $fragment] r]
    puts $cstfile [read $sourcefile]
    close $sourcefile
}
close $cstfile
add_file -type cst $cst
add_file -type sdc [file join $root boards tang-nano-9k kagura-fb.sdc]
set_option -place_option 1
set_option -route_option 2
set_option -top_module kagura_fb_top
set_option -output_base_name kagura_fb
foreach feature {sspi mspi ready done cpu} { set_option -use_${feature}_as_gpio 1 }
run all
