"""M72: a cocotb testbench for the M21 counter (tests/fixtures/rtl/counter.v).

It passes on the counter and must fail on each single-change mutant in
tests/fixtures/eqy: counter_wraps_early.v (fails counts_and_wraps) and
counter_reset_ignored.v (fails reset_clears_while_idle). Not a pytest module:
cocotb imports it inside the simulator.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge


async def reset(dut):
    """Start the clock and hold reset for two cycles, with en high (reset wins)."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    dut.en.value = 1
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst.value = 0
    dut.en.value = 0


@cocotb.test()
async def counts_and_wraps(dut):
    """With en high the count steps 1, 2, ... up to LIMIT, then wraps to 0."""
    await reset(dut)
    limit = int(dut.LIMIT.value)
    dut.en.value = 1
    for want in range(1, limit + 1):
        await RisingEdge(dut.clk)
        await ReadOnly()
        assert int(dut.count.value) == want, f"count {int(dut.count.value)}, expected {want}"
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert int(dut.count.value) == 0, "the count did not wrap to 0 after LIMIT"


@cocotb.test()
async def reset_clears_while_idle(dut):
    """Reset clears the count even while en is low."""
    await reset(dut)
    dut.en.value = 1
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.en.value = 0
    dut.rst.value = 1
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert int(dut.count.value) == 0, f"count {int(dut.count.value)} after reset with en low"
