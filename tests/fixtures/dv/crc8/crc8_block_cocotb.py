"""Python (cocotb) tests for crc8_block.v (W2-E6), the reference answer of the eval case dv/cocotb-crc.

The tests are written from interface_spec.md, with a model of the specification
in Python (the byte XORed into the running value, then eight shift-and-reduce
steps, the check value inverted). They cover the value after reset and after a
reload, three messages with known byte order and polynomial behaviour, a hold
with valid low, a reload that meets a byte, and a constrained-random run from
a fixed seed that compares `crc` after every edge and fails itself when the run
never reached init with valid, an idle cycle or a mid-frame reset. Not a
pytest module: cocotb imports it inside the simulator.
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer

POLY = 0x07
START = 0xFF


def take(state, byte):
    """The running value after one byte: bit 7 first, no reflection."""
    state ^= byte
    for _ in range(8):
        state = ((state << 1) ^ POLY) & 0xFF if state & 0x80 else (state << 1) & 0xFF
    return state


class Model:
    """The specification's running value and its check value."""

    def __init__(self):
        self.state = START

    def edge(self, rst_n, init, valid, data):
        if not rst_n or init:
            self.state = START
        elif valid:
            self.state = take(self.state, data)

    @property
    def crc(self):
        return self.state ^ 0xFF


async def start(dut):
    """Start the clock and hold reset for two edges."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.init.value = 0
    dut.valid.value = 0
    dut.data.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)


async def step(dut, model, rst_n, init, valid, data, what):
    """One edge with these inputs: drive, let the model take them, compare `crc` after the edge."""
    dut.rst_n.value = rst_n
    dut.init.value = init
    dut.valid.value = valid
    dut.data.value = data
    await RisingEdge(dut.clk)
    model.edge(rst_n, init, valid, data)
    await ReadOnly()
    got = int(dut.crc.value)
    assert got == model.crc, f"{what}: crc 0x{got:02x}, expected 0x{model.crc:02x}"
    await Timer(1, unit="ns")


@cocotb.test()
async def empty_after_reset_and_reload(dut):
    """Right after reset or a reload, with no byte taken, crc is 0x00."""
    await start(dut)
    model = Model()
    await step(dut, model, 0, 0, 0, 0, "reset")
    assert int(dut.crc.value) == 0, f"crc 0x{int(dut.crc.value):02x} after reset"
    await step(dut, model, 1, 0, 1, 0xA5, "first byte")
    await step(dut, model, 1, 1, 0, 0x00, "reload")
    assert int(dut.crc.value) == 0, f"crc 0x{int(dut.crc.value):02x} after a reload"


@cocotb.test()
async def messages_take_bit_seven_first(dut):
    """Single bytes and a short message, each against the model, from a reload."""
    await start(dut)
    model = Model()
    for message in ([0x01], [0x80], [0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39], [0xFF, 0x00, 0x07]):
        await step(dut, model, 1, 1, 0, 0x00, "reload")
        for byte in message:
            await step(dut, model, 1, 0, 1, byte, f"byte 0x{byte:02x}")


@cocotb.test()
async def valid_low_holds_and_init_wins_over_a_byte(dut):
    """With valid low nothing changes; a reload that meets a byte takes no byte."""
    await start(dut)
    model = Model()
    await step(dut, model, 1, 1, 0, 0x00, "reload")
    await step(dut, model, 1, 0, 1, 0x5A, "byte")
    for byte in (0x00, 0xFF, 0x13):
        await step(dut, model, 1, 0, 0, byte, "valid low")
    await step(dut, model, 1, 1, 1, 0x5A, "reload meets a byte")
    assert int(dut.crc.value) == 0, "a reload offered with a byte took the byte"


@cocotb.test()
async def constrained_random_run(dut):
    """Random bytes, init, valid and resets from a fixed seed, compared after every edge."""
    await start(dut)
    model = Model()
    rng = random.Random(0x1BADC0DE)
    corners = (0x00, 0xFF, 0x80, 0x01, 0x07)
    both = idle = resets = taken = 0
    for _ in range(3000):
        rst_n = 0 if rng.randrange(256) == 0 else 1
        init = 1 if rng.randrange(16) == 0 else 0
        valid = 0 if rng.randrange(4) == 0 else 1
        data = rng.choice(corners) if rng.randrange(4) == 0 else rng.randrange(256)
        both += init and valid
        idle += (not init) and (not valid)
        resets += not rst_n
        taken += rst_n and (not init) and valid
        await step(dut, model, rst_n, init, valid, data, "random")
    assert both >= 10 and idle >= 50 and resets >= 3 and taken >= 1000, (
        f"random run too thin: both={both} idle={idle} resets={resets} taken={taken}")
