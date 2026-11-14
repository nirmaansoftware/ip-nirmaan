---
id: design/rtl_design
skill: rtl_design
as_of: 2026-10-31
review_by: 2027-04-30
sources:
  - open | lowRISC, Verilog Coding Style Guide (CC BY 4.0) [lowRISC] | https://github.com/lowRISC/style-guides/blob/master/VerilogCodingStyle.md
  - open | YosysHQ, Yosys command reference: Converting process blocks (the proc passes) [Yosys] | https://yosyshq.readthedocs.io/projects/yosys/en/latest/cmd/index_passes_proc.html
  - open | Verilator manual: Input Languages [Verilator] | https://verilator.org/guide/latest/languages.html
  - open | YosysHQ, SBY documentation: Reference for .sby file format, and Formal extensions to Verilog [SBY] | https://yosyshq.readthedocs.io/projects/sby/en/latest/reference.html and https://yosyshq.readthedocs.io/projects/sby/en/latest/verilog.html
  - open | Gisselquist, AXI Handshaking Rules, ZipCPU blog, 2021 [ZipCPU] | https://zipcpu.com/blog/2021/08/28/axi-rules.html
  - open | IP Nirmaan, formal gate: docs/FORMAL_GATE.md section 3 and src/nirmaan/integrations/eda.py L644-L760 [Gate] | this repository
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-P3-K1 session (P3 pilot, item K1, 2026-10-31)
checker: pending, a different session reads the sources in P3-C1 and writes the check record
---
Practising: the lint, simulation, synthesis and formal tools this skill names are run by the platform; the seat has none [Gate]; this document is knowledge, not evidence.

# RTL design

Synthesizable, single-clock RTL for small blocks, its self-checking testbench
and its proof setup. Tags in brackets name the sources above. A line marked
"inference" is this document's own reasoning from the cited source.

## Coding style

- Sequential blocks use only nonblocking assignments, combinational blocks
  only blocking ones, and one block never mixes the two: mixed blocks can
  simulate wrongly, with values skipping a register [lowRISC].
- Combinational logic uses `always_comb`, or `always @*` in Verilog-2001,
  never a hand-written sensitivity list [lowRISC]. Verilator evaluates an
  incomplete list as synthesis would, where a compliant simulator does not,
  so a hand list can make two simulators disagree [Verilator].
- Keep the register block to its reset value and `q <= d` (or a load
  enable); compute next state in a separate combinational block, and do not
  assign the same bit twice in one block except a default then an override
  [lowRISC].
- No `#` delay in a design module, not even `#0` [lowRISC].
- Declare every signal (no implicit nets), size every literal, match port
  widths, and compare a multi-bit value with zero rather than using it as a
  boolean [lowRISC].
- No `X` assignments as "don't care" and no hierarchical references in
  synthesizable code [lowRISC].
- State machines: an enum of states, a combinational block whose default next
  state is the current state, and a state register that holds only reset and
  the update [lowRISC].

## No latches

- A combinational block infers a latch when some path leaves a variable
  unassigned. Give every output a default at the top of the block, or assign
  every variable in every branch including `default` [lowRISC].
- Give every `case` a `default`, even when all values are listed: in
  simulation an `X` selector matches no item and holds its old value like a
  latch, so simulation and synthesis differ [lowRISC].
- Never use the `full_case` or `parallel_case` pragmas [lowRISC]. Verilator
  proves such a directive, or a `unique` or `priority` case, or checks it at
  run time [Verilator].
- A function must not infer a latch; assign every local on every path
  [lowRISC].
- Checking: Yosys's `proc_dlatch` finds latches, and its `-latches` option
  reports each as info, warn (the default) or error [Yosys]. The platform's synthesis script is fixed, so you
  cannot pass `error`; any latch fails the gate [Gate].

## Reset every flop

- Every flop that holds state gets its value in the reset branch of the
  register block [lowRISC]. Use the reset the block's spec names; lowRISC's
  own default is an active-low asynchronous reset [lowRISC].
- Why it matters: Verilator is mostly two-state. It gives uninitialised state
  a value set by `--x-initial` (typically random) and an assigned `X` a value
  set by `--x-assign`, where a four-state simulator would show `X` [Verilator].
  An unreset flop can therefore pass in one simulator and fail in another
  (inference). Verilator suggests running with state started at zeros, then
  ones, then random values: matching results show reset works [Verilator].
- An `initial` value is not a reset. Initialising at declaration is
  synthesizable only on some FPGA tools [lowRISC], and Yosys turns `initial`
  blocks into `init` attributes [Yosys], so a formal run may start from values
  a reset-only flop never has (inference).

## Self-checking testbench

- The card's procedures fix the verdict line and who may call `$finish`; this
  document does not restate them. Under Verilator, `$value$plusargs` works
  only when the wrapper registers the command line, or with `--binary` or
  `--main` [Verilator].
- Compute each expected value in the testbench from the stimulus, and check
  every output the spec defines, not only the data path (inference).
- Every coverage goal the testbench asserts needs stimulus that drives it (an
  arbiter: a no-request cycle); check each goal against the directed
  sequence (inference).
- Write the expected-value model step for step with the RTL, and run your own
  testbench and reconcile every mismatch first (inference).
- Drive the cases a quiet test never reaches: wait states, back-pressure,
  back-to-back transfers, illegal inputs and reset during traffic
  (inference).
- A test is worth what it catches: break the design on purpose (invert a
  condition, drop an assignment) and confirm the test fails before relying on
  it (inference).

## Proof setup

- Submit one `.sby` with no `[tasks]`: a setup with `[tasks]` is refused and
  nothing runs [Gate]. `[options]` needs `mode prove`; `bmc` is a bounded
  check and fails [Gate]. Add `[engines]`, `[script]`
  (read the sources, then `prep -top`) and `[files]` listing every RTL file
  you submit, by path from the `.sby`'s directory [Gate]. `depth` defaults to
  20 and is the induction depth in `prove` mode [SBY]. The platform runs the
  cover separately in cover mode: write at least
  one `cover`, and every cover and every assertion's antecedent must be
  reachable [Gate].
- `read -formal` defines `FORMAL`, so properties sit inside `` `ifdef FORMAL ``
  next to the logic [SBY].
- `assume` narrows what the solver examines, `assert` is what it tries to
  break, `cover` asks for a reachable trace. A `bmc` pass holds only up to
  the depth; `prove` can end unknown when the induction step fails; a cover
  fails if it cannot be reached within the depth, or only by breaking an
  assertion [SBY].
- `$past` works only in a clocked block and is undefined on the first clock
  [SBY]. Use a register that is 0 at the start and 1 after the first edge to
  guard such checks, and assume reset is active on that first cycle
  [ZipCPU].
- A clocked assertion is checked at the next edge, so a trace's fault lies one
  step before its end; an `always @(*)` assertion that rests on a clocked
  assumption can fail before the assumption applies [SBY].
- `(* anyconst *)` gives a solver-chosen constant, for example one address
  whose register is then checked against a model [SBY].
- Cover the behaviour the spec promises (each register written and read
  back), so a proof cannot pass because assumptions ruled everything out
  (inference from [SBY]).

## Common failure modes

- A latch from a missing default or an unassigned branch [lowRISC].
- A flop with no reset value (inference from [Verilator]).
- Blocking assignments in a clocked block [lowRISC].
- A proof that passes only up to its depth, reported as if unbounded [SBY].
