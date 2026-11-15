---
id: verification/emulation_prototyping
skill: emulation_prototyping
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | FireSim project, FireSim Basics (documentation) [FSBasics] | https://docs.fires.im/en/stable/firesim-basics/
  - open | FireSim project, Debugging and Profiling on the FPGA [FSDebug] | https://docs.fires.im/en/stable/advanced-usage/debugging-and-profiling-on-fpga/
  - open | FireSim project, Debugging a Hanging Simulator [FSHang] | https://docs.fires.im/en/stable/advanced-usage/debugging-and-profiling-on-fpga/debugging-hanging-simulators/
  - open | FireSim project, AutoILA: Simple Integrated Logic Analyzer Insertion [FSILA] | https://docs.fires.im/en/stable/advanced-usage/debugging-and-profiling-on-fpga/debugging-hardware-using-ila/
  - open | FireSim project, Printf Synthesis [FSPrintf] | https://docs.fires.im/en/stable/advanced-usage/debugging-and-profiling-on-fpga/printf-synthesis/
  - open | FireSim project, Assertion Synthesis [FSAssert] | https://docs.fires.im/en/stable/advanced-usage/debugging-and-profiling-on-fpga/assertion-synthesis/
  - open | FireSim project, Debugging and Testing with Metasimulation [FSMeta] | https://docs.fires.im/en/stable/advanced-usage/debugging-in-software/rtl-simulation/
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K7 session (wave 2 knowledge batch, plan row W2-K7, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Knowledge only: no tool run backs this.

# Emulation and prototyping

Deciding which tests move from software simulation to FPGA-hosted simulation,
and what debug access to plan before the move. The only open source read for
this document is the FireSim documentation, so it describes one open
FPGA-accelerated simulation platform, not commercial emulators. Tags in
brackets name the sources above; "inference" marks this document's own
reasoning. This skill's card holds no tool
(src/nirmaan/company/skills.py:428-432), and nothing here has been run.

## What the source covers

- FireSim is an open-source FPGA-accelerated full-system simulation platform
  for validating, profiling and debugging RTL at tens to hundreds of MHz
  [FSBasics]. On an on-premises FPGA a single SoC target runs at 150 MHz or
  more [FSBasics]. It scales from one desktop FPGA to many cloud FPGAs
  [FSBasics].
- Its recommended use is with the Chipyard SoC generator; it can also be used
  without it [FSBasics]. Its debug annotations are written in Chisel
  [FSILA] [FSPrintf]. Whether they apply to hand-written Verilog was not read
  (inference: check before planning).
- Commercial emulators and board-level prototypes of other kinds have no
  open source read here; the gap is recorded in the wanted-sources list.

## Which tests move

- FireSim's documentation puts software simulation first. Metasimulation
  (simulating the FireSim simulator's RTL with Verilator or VCS) is, in its
  words, the most productive way to catch bugs before building the FPGA image,
  and a way to reproduce bugs seen on the FPGA [FSMeta].
- Target behaviour seen on the FPGA should be exactly reproducible in
  metasimulation, because FireSim simulations are insensitive to timing
  differences across hosts [FSMeta]. Metasimulation is generally only slightly
  slower than target-level simulation [FSMeta].
- The FPGA is for runs that RTL simulators take too long for [FSILA], such as
  full benchmark suites with reference inputs [FSBasics].
- A rule that follows (inference): move a test only when its length makes
  software simulation impractical, and keep a short version of it in
  simulation so a failure on the FPGA can be reproduced there.

## Plan the debug access before the move

- The source states the problem: debugging and profiling a system once it is
  on the FPGA is difficult, and FireSim provides tools to look inside a
  running design [FSDebug]. Its list includes instruction tracing, assertion
  synthesis, printf synthesis, an integrated logic analyzer insertion tool,
  performance counters, co-simulation with the Spike reference model and
  hang debugging with a heartbeat [FSDebug] [FSHang].
- Assertion synthesis: assertions that would be lost in the FPGA flow are
  turned into hardware. On a hit the driver reports the cause, the instance
  path, a source location and the cycle, then ends the simulation. Rerunning
  with identical inputs fires the same assertion at the same cycle [FSAssert].
- Printf synthesis: each printf to capture is annotated by hand. Synthesizing
  many frequently active printfs slows the simulator [FSPrintf]. A start and
  end cycle can be set so capture begins at the region of interest while the
  rest runs at full speed [FSPrintf].
- Logic analyzer: signals are annotated in the source and wired to an ILA when the
  design is built. The depth is the number of cycles captured around a trigger; a
  larger depth eases debugging and uses more FPGA resources; the default is
  1024 [FSILA]. Because annotation is at build time, choosing which signals
  to watch is part of the plan, not something to add after a failure
  (inference).
- Board support differs. On the Vitis-based and V80 flows, bridges that use DMA
  (the instruction tracer and printf synthesis are named) do not work, and on
  AWS F2 those bridges run slower [FSBasics]. Check that the chosen board
  supports the planned debug tools (inference).

## Reading a failure on the FPGA

- A hanging run has three cases in the source. A target hang: output stops
  but simulated time advances, so the target RTL or a bridge is suspect and the
  debug tools still work. Token starvation: the driver loop spins and the run is
  torn down for lack of progress; a bridge bug is suspected and this case is
  called the trickiest. A driver deadlock: all output including the heartbeat
  file stops [FSHang].
- The simulation driver writes a heartbeat file with the target cycle count and
  a timestamp, which tells the first case from the third [FSHang].
- In a metasimulation waveform the host time between target clock edges is not
  proportional to target time, because target clocks are gated from one host
  clock and bridges can stall. Stalls can be found by filtering on the
  channel valid and ready signals of the hub model [FSMeta]. A waveform from
  such a run is not read like a conventional one (inference).

## Common failure modes

- Moving to the FPGA with no debug visibility planned, so the first failure
  gives only a hang (the card).
- Debug tools chosen that the board does not support [FSBasics].
- Capturing every printf from cycle zero and losing the speed that made the
  move worthwhile [FSPrintf].
- A failure seen only on the FPGA with no way to reproduce it in software; the
  source encourages metasimulation to reproduce a failure [FSHang] [FSMeta].

## How a result is checked

- Each test moved to the FPGA names what the move adds (for example more
  cycles) and what debug access stays (which of the tools above are built in,
  the signals annotated, the capture window) (the card's own check).
- The seed or inputs are recorded so a failure can be rerun (inference; the
  source states identical inputs give the same assertion cycle [FSAssert]).
- The run on the FPGA is paired with a metasimulation of a shorter version of
  the same test (inference from [FSMeta]).

## Sources

- [FSBasics] What the platform is, speeds, supported boards and bridge limits.
- [FSDebug], [FSHang], [FSILA], [FSPrintf], [FSAssert] The on-FPGA debug tools
  and hang cases.
- [FSMeta] Metasimulation as the first step and as the reproduction path, and
  how its waveforms differ.
