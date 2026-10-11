# Timing constraints for the M37 timing-closure fixture (tests/fixtures/rtl/prod3).
# A 2.2 ns clock on clk: both multiplies in one cycle do not fit on Nangate45, one does.
# Inputs arrive 0.2 ns after the edge (a 0 ns input delay fails hold at the input
# registers by 3 ps) and are registered at once; the output leaves a register. So the
# register-to-register path through the multiplies is the one that matters.
set clk_period 2.2
set clk_port [get_ports clk]
create_clock -name clk -period $clk_period $clk_port
set non_clock_inputs [lsearch -inline -all -not -exact [all_inputs] $clk_port]
set_input_delay 0.2 -clock clk $non_clock_inputs
set_output_delay 0 -clock clk [all_outputs]
