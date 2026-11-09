# SPDX-License-Identifier: Apache-2.0
# Kagura-FB standalone integration target. Run prepare-hdmi-stream.py first.
set root [file normalize [file join [file dirname [info script]] ..]]
set transport [expr {[llength $argv]>0 ? [lindex $argv 0] : "qspi"}]
if {$transport ni {spi qspi}} { error "Expected spi or qspi" }
set place_option [expr {[llength $argv]>1 ? [lindex $argv 1] : 1}]
set route_option [expr {[llength $argv]>2 ? [lindex $argv 2] : 2}]
if {$place_option ni {0 1 2 3 4} || $route_option ni {0 1 2}} {
    error "Invalid placement/routing option"
}
set queue_depth [expr {[llength $argv]>3 ? [lindex $argv 3] : 1}]
if {$queue_depth ni {1 2 4 8}} { error "Expected queue depth 1, 2, 4 or 8" }
set audio_credits [expr {[llength $argv]>4 ? [lindex $argv 4] : 0}]
if {$audio_credits ni {0 1}} { error "Expected audio credit predicate 0 or 1" }
set packet_first [expr {[llength $argv]>5 ? [lindex $argv 5] : 0}]
if {$packet_first ni {0 1}} { error "Expected packet first replication 0 or 1" }
set opt_goal [expr {[llength $argv]>6 ? [lindex $argv 6] : "auto"}]
if {$opt_goal ni {auto area timing}} { error "Expected synthesis goal auto, area or timing" }
puts "KAGURA_BUILD transport=$transport place_option=$place_option route_option=$route_option queue_depth=$queue_depth"
set config [file join [pwd] kagura_fb_config.sv]
set configfile [open $config w]
puts $configfile "package kagura_fb_config; localparam integer HOST_LANES=[expr {$transport eq {qspi} ? 4 : 1}], GPU_QUEUE_DEPTH=$queue_depth, GPU_AUDIO_CREDITS=$audio_credits, GPU_PACKET_FIRST=$packet_first; endpackage"
close $configfile
add_file -type verilog $config
set_device -name GW1NR-9C GW1NR-LV9QN88PC6/I5
set_option -verilog_std sysv2017
set_option -opt_goal $opt_goal
set listfile [open [file join $root rtl fb sources.f] r]
foreach path [split [read $listfile] "\n"] {
    set path [string trim $path]
    if {$path eq ""} continue
    # SPI only: rtl/spi/ files replace the frozen RTL of the same name
    # (rtl/spi/README.md). QSPI always uses the frozen files.
    set overlay [file join $root rtl spi [file tail $path]]
    if {$transport eq {spi} && [file exists $overlay]} {
        puts "KAGURA_SPI_OVERLAY $path -> rtl/spi/[file tail $path]"
        set path [file join rtl spi [file tail $path]]
    }
    add_file -type verilog [file join $root $path]
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
set_option -place_option $place_option
set_option -route_option $route_option
set_option -top_module kagura_fb_top
set_option -output_base_name kagura_fb
foreach feature {sspi mspi ready done cpu} { set_option -use_${feature}_as_gpio 1 }
run all
