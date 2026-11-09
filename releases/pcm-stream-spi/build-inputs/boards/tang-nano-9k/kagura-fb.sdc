create_clock -name clk27 -period 37.037 [get_ports {clk27}]
create_generated_clock -name serial371 -source [get_ports {clk27}] -multiply_by 55 -divide_by 4 [get_pins {clocks/video_pll/CLKOUT}]
create_generated_clock -name pixel74 -source [get_pins {clocks/video_pll/CLKOUT}] -divide_by 5 [get_pins {clocks/pixel_div/CLKOUT}]
create_generated_clock -name system54 -source [get_ports {clk27}] -multiply_by 2 [get_pins {clocks/system_pll/CLKOUT}]
create_generated_clock -name psram54 -source [get_ports {clk27}] -multiply_by 2 -phase 67.5 [get_pins {clocks/system_pll/CLKOUTP}]
set_false_path -from [get_ports {reset_n}]
set_false_path -to [get_ports {led_n[*]}]
# Initial draft: first-stage control synchronizers, plus bundled mailbox and
# Gray-pointer payloads held stable through acknowledgement. Clock-domain
# crossings receive an absolute delay bound instead of phase-related setup.
# This file is not a complete PSRAM external IO timing specification.
set_max_delay 10.000 -from [get_clocks {system54}] -to [get_clocks {pixel74}]
set_max_delay 10.000 -from [get_clocks {pixel74}] -to [get_clocks {system54}]
set_false_path -hold -from [get_clocks {system54}] -to [get_clocks {pixel74}]
set_false_path -hold -from [get_clocks {pixel74}] -to [get_clocks {system54}]

# Host signals use the inherited 2FF oversampling transport. Host SCK has no
# phase relationship to system54; board-level setup/hold needs measurement.
set_false_path -from [get_ports {host_sck host_cs_n host_io[*]}]
set_false_path -to [get_ports {host_io[*] host_busy host_ready host_irq_n sd_hiz[*]}]
