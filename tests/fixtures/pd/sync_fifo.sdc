# Timing constraints for the synchronous FIFO (tests/fixtures/rtl/sync_fifo), the M79 SKY130 pilot.
# A 100 MHz clock on clk; inputs arrive, and outputs must leave, 20% into the period.
set clk_period 10.0
set clk_port [get_ports clk]
create_clock -name clk -period $clk_period $clk_port
set non_clock_inputs [lsearch -inline -all -not -exact [all_inputs] $clk_port]
set_input_delay [expr $clk_period * 0.2] -clock clk $non_clock_inputs
set_output_delay [expr $clk_period * 0.2] -clock clk [all_outputs]
