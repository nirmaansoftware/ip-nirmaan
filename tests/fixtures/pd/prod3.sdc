# Timing constraints for the M37 timing-closure fixture (tests/fixtures/rtl/prod3).
# A 1.8 ns clock on clk: both multiplies in one cycle do not fit on Nangate45, one does.
# Inputs are registered at once and the output leaves a register, so the
# register-to-register path through the multiplies is the one that matters.
set clk_period 1.8
set clk_port [get_ports clk]
create_clock -name clk -period $clk_period $clk_port
set non_clock_inputs [lsearch -inline -all -not -exact [all_inputs] $clk_port]
set_input_delay 0 -clock clk $non_clock_inputs
set_output_delay 0 -clock clk [all_outputs]
