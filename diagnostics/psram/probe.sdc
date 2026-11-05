create_clock -name clk27 -period 37.037 [get_ports {clk27}]
create_generated_clock -name sys54 -source [get_ports {clk27}] -multiply_by 2 [get_pins {pll/CLKOUT}]
create_generated_clock -name ck54 -source [get_ports {clk27}] -multiply_by 2 -phase 67.5 [get_pins {pll/CLKOUTP}]
set_false_path -from [get_ports {reset_n}]
# Async trigger to first synchronizer only. Subsequent stages remain timed.
set_false_path -from [get_ports {trigger_n}] -to [get_pins {trigger_sync_0_s0/D}]
set_false_path -to [get_ports {led_n[*]}]
# UART is an asynchronous, registered 115200-baud output, not a synchronous bus.
set_false_path -to [get_ports {uart_tx}]
