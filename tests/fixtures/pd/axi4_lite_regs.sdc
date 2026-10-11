# Timing constraints for the AXI4-Lite register block (tests/fixtures/rtl/axi4_lite).
# A 100 MHz clock on aclk; inputs arrive, and outputs must leave, 20% into the period.
set clk_period 10.0
set clk_port [get_ports aclk]
create_clock -name aclk -period $clk_period $clk_port
set non_clock_inputs [lsearch -inline -all -not -exact [all_inputs] $clk_port]
set_input_delay [expr $clk_period * 0.2] -clock aclk $non_clock_inputs
set_output_delay [expr $clk_period * 0.2] -clock aclk [all_outputs]
