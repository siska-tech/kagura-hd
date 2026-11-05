create_clock -name clk27 -period 37.037 [get_ports {clk27}]
create_generated_clock -name sys54 -source [get_ports {clk27}] -multiply_by 2 [get_pins {pll/CLKOUT}]
set_false_path -from [get_ports {reset_n}]
# External host is asynchronous. Only pad -> first synchronizer FF is excepted.
set_false_path -from [get_ports {host_sck}] -to [get_pins {core/endpoint/transport/sck_sync_0_s0/D}]
set_false_path -from [get_ports {host_cs_n}] -to [get_pins {core/endpoint/transport/cs_sync_0_s0/D}]
set_false_path -from [get_ports {host_io[0]}] -to [get_pins {core/endpoint/transport/io_sync0_0_s0/D}]
set_false_path -from [get_ports {host_io[1]}] -to [get_pins {core/endpoint/transport/io_sync0_1_s0/D}]
set_false_path -from [get_ports {host_io[2]}] -to [get_pins {core/endpoint/transport/io_sync0_2_s0/D}]
set_false_path -from [get_ports {host_io[3]}] -to [get_pins {core/endpoint/transport/io_sync0_3_s0/D}]
# Asynchronous protocol outputs, verified at limited host SCK by pin simulation.
# This is not a claim of board-level host IO min/max closure.
set_false_path -to [get_ports {host_io[*] host_busy host_ready host_irq_n uart_tx led_n[*]}]
# PSRAM outputs are constants, and DQ/RWDS/SD are undriven; no PSRAM timing paths.
