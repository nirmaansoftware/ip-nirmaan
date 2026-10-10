// Assertion macros (M37 fixture): an implication written as a guarded immediate assertion.
`ifndef ASSERT_MACROS_VH
`define ASSERT_MACROS_VH
`define ASSERT_IMPL(a, b) if (a) assert (b)
`endif
