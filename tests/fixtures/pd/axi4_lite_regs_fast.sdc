# The AXI4-Lite register block at 5 GHz: a clock no 45 nm library can meet, so
# static timing reports negative slack (the violated case the tests need).
set clk_period 0.2
set clk_port [get_ports aclk]
create_clock -name aclk -period $clk_period $clk_port
set non_clock_inputs [lsearch -inline -all -not -exact [all_inputs] $clk_port]
set_input_delay [expr $clk_period * 0.2] -clock aclk $non_clock_inputs
set_output_delay [expr $clk_period * 0.2] -clock aclk [all_outputs]
