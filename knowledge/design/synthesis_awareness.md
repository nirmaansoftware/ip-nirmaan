---
id: design/synthesis_awareness
skill: synthesis_awareness
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | YosysHQ, Yosys documentation: Synth commands, and the synth command reference [Synth] | https://yosyshq.readthedocs.io/projects/yosys/en/latest/cmd/index_passes_synth.html
  - open | YosysHQ, Yosys command reference: Converting process blocks (the proc passes) [Proc] | https://yosyshq.readthedocs.io/projects/yosys/en/latest/cmd/index_passes_proc.html
  - open | YosysHQ, Yosys command reference: Optimization passes [Opt] | https://yosyshq.readthedocs.io/projects/yosys/en/latest/cmd/index_passes_opt.html
  - open | YosysHQ, Yosys documentation: A primer on digital circuit synthesis [Primer] | https://yosyshq.readthedocs.io/projects/yosys/en/latest/appendix/primer.html
  - open | YosysHQ, Yosys documentation: Notes on Verilog support in Yosys [Verilog] | https://yosyshq.readthedocs.io/projects/yosys/en/latest/using_yosys/verilog.html
  - open | Gisselquist, Strategies for pipelining logic, ZipCPU blog, 2017 [Pipe] | https://zipcpu.com/blog/2017/08/14/strategies-for-pipelining.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: RETRO-A5 session (retrospective action A5, item P3-K3, 2026-11-15)
checker: pending, a different session reads the sources in P3-C3 and writes the check record
---
Knowledge only: no tool run backs this.

# Synthesis awareness

What a synthesis tool does with RTL, which constructs it cannot or should not
be given, and how to read the cell counts the repository's synthesis gate
reports. Tags in brackets name the sources above; a line marked "inference" is
this document's own reasoning; a line marked "gate" names the repository code
that backs it. This card holds no tool; the tool it points to is `synth.run`.

## What synthesis does

- Yosys reads the RTL, turns each `always` block into multiplexers,
  flip-flops and latches (the `proc` passes), then runs coarse optimisations,
  finite-state-machine extraction, memory handling and technology mapping
  [Synth] [Proc]. The generic `synth` script lists these steps, from `hierarchy`
  and `proc` through `opt`, `fsm`, `wreduce` and `techmap` [Synth].
- `proc` finds asynchronous resets, flip-flops, latches and memory writes
  in processes [Proc]. Which kind of storage you get follows from how the block
  is written: a clocked block gives flip-flops, a combinational block not
  assigned on every path gives a latch [Proc] [Primer].
- Only a few forms of `always` are in the synthesis standard: combinational
  or latched logic with the full sensitivity list (`@*`), clocked logic
  with a synchronous reset, and clocked logic with an asynchronous reset,
  whose sensitivity list holds only the clock and reset edges and whose
  reset values are constants (`always @(posedge clk, posedge reset)`).
  Write new designs inside them [Primer].
- The optimiser removes unused cells and wires, merges identical cells and
  folds constants [Opt]. Logic whose result nothing reads is removed, so a
  block that appears missing from the netlist may simply be unused
  (inference from [Opt]).
- Yosys does not support the non-synthesizable language features of the
  Verilog synthesis standard, the `tri` net types, or `config` and `disable`
  [Verilog]. Loops and generate conditions must unroll to constants at
  elaboration [Primer].

## What the repository's synthesis gate reports

- The default `synth.run` backend reads the sources and runs `synth -top <top>`
  then `stat -json`, with no flatten and no technology library (gate:
  src/nirmaan/integrations/eda.py:602-607, registered at eda.py:812). It
  needs a top module (gate: src/nirmaan/company/tools.py:177-178).
- The backend passes on exit 0 and no `ERROR` line. Warnings, including the
  latch warning, do not fail the backend (gate: eda_parsers.py:263-287; the
  pass test at line 287 reads only the exit status and the errors, and latches
  are only counted, at lines 282-283). The rtl stage's gate does fail a
  latch: it requires the latch count to be at most 0 (gate:
  src/nirmaan/company/workflows.py:114). So a latch passes the backend but
  not that stage; read the latch count in the result.
- The numbers it keeps are the cell count, wire count, cells by type, and
  the flip-flop and latch counts, taken from type names that contain `FF` or
  `LATCH` (gate: eda_parsers.py:263-283). With the generic script the cells
  are Yosys's internal gate types, not a library's cells, so the count is a
  relative size, not an area in a unit, and there is no delay figure
  (inference from [Synth]; gate lines above).
- The `yosys-liberty` backend, when a Liberty file is given, maps flip-flops
  and logic to library cells and also records an area figure from
  `stat -liberty` and writes a netlist (gate: src/nirmaan/integrations/physical.py:160-197,
  backend registered at physical.py:540). Timing comes from a separate tool,
  `sta.run` (gate: src/nirmaan/company/tools.py:183), not from synthesis.

## Estimating depth and area before a run

- Logic depth is the number of gate levels between two registers. Anything
  combinational that must finish in one clock adds to it, so keep the chain
  between registers short, and register where a path grows (inference from [Pipe]).
- A combinational ready or busy signal that passes back through many stages
  adds up from stage to stage and can set the clock period; registering it
  breaks the chain at the cost of a buffer or a lost cycle [Pipe].
- Wide arithmetic is area. A multiplier costs far more cells than an adder of
  the same width, and its cell count grows roughly with the product of the
  operand widths (inference, no run record is committed for a measured figure).
  Share one unit across cycles where the throughput allows (inference).
- Yosys has passes that restructure cascades of adders and multipliers into
  trees to improve timing [Opt]; do not write an arithmetic chain assuming
  the tool will balance it without checking the result (inference).
- State encoding, memories and shift registers change area: arrays that cannot
  be inferred as a memory become individual registers with large multiplexers
  [Primer], and a state register can be re-encoded by the `fsm` pass [Synth].

## Constructs to avoid

- Latches from incomplete assignment in combinational blocks; write a default
  or use `always_latch` when a latch is intended [Primer] [Proc].
- Delays, `initial` values as the only reset, and testbench-only constructs in
  RTL. Yosys carries an `initial` value as an `init` attribute rather than as
  reset logic [Verilog] (inference: do not rely on it for reset).
- Attributes such as `full_case` and `parallel_case`, and the `translate_off`
  directives: Yosys honours them [Verilog], but they let simulation and
  synthesis disagree; use a default case and `ifdef` (inference).
- Asynchronous or multi-driver structures that make the register inference
  ambiguous: one `always` block per register group (inference).

## Common failure modes

- Timing surprises from a long combinational path found late (card).
- A latch inferred by a missed `else` or case item.
- Simulation and synthesis disagreeing, from blocking and non-blocking
  assignments mixed in one block (inference).
- Reading a cell count as a speed or area result. It is neither.

## How a result is checked

- Run the synthesis gate on the final sources and read the flip-flop and
  latch counts as well as the pass line; an unexpected latch is a defect
  (inference).
- Compare the flip-flop count with the registers the design describes.
- Run lint first; most latch and width findings appear there, earlier and
  cheaper (inference; see the `rtl_lint` document).
- For timing, a separate static timing run with a library is needed; this
  skill does not provide one.
