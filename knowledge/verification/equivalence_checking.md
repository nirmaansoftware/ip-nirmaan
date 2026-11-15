---
id: verification/equivalence_checking
skill: equivalence_checking
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | YosysHQ, EQY documentation: Getting Started [EqyQuick] | https://yosyshq.readthedocs.io/projects/eqy/en/latest/quickstart.html
  - open | YosysHQ, EQY documentation: Reference for the .eqy file format [EqyConfig] | https://yosyshq.readthedocs.io/projects/eqy/en/latest/config.html
  - open | YosysHQ, EQY documentation: EQY Strategies [EqyStrat] | https://yosyshq.readthedocs.io/projects/eqy/en/latest/strategies.html
  - open | YosysHQ, EQY documentation: Equivalence and X-Propagation [EqyX] | https://yosyshq.readthedocs.io/projects/eqy/en/latest/xprop.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K2 session (wave 2 knowledge batch, plan row W2-K2, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the equivalence tool this skill holds is available; this document is knowledge, not evidence.

# Equivalence checking

Showing that a refactored or resynthesised design behaves like the original,
with eqy, and how this repository's equivalence gate reads the result. Tags in
brackets name the sources above; a line marked "inference" is this document's
own reasoning; a line marked "gate" names the repository code that backs it.

## What the check is for

- eqy checks that two designs are equivalent, for example that a synthesis tool
  added no functional change, or that a refactor preserves behaviour in all
  conditions [EqyQuick].
- It is a comparison of two versions, not a check against the specification.
  Both versions can be wrong in the same way and still be equivalent
  (inference). Where the specification matters, use a proof or a testbench
  written from it.
- The relation is a refinement, not a symmetric one. The gate design may show
  only behaviour the gold design can show for the same inputs, so properties
  that hold for gold also hold for gate; swapping the roles can change the
  answer when flip-flops start unknown or don't-care bits are resolved [EqyX].

## How a setup is written

- A `.eqy` file is a set of sections [EqyConfig]. `[gold]` and `[gate]` each hold
  a Yosys script that reads and elaborates that version; `[script]` lines are
  added to both [EqyConfig].
- Both sides must be elaborated to the same top and in comparable form. The
  getting-started example reads each version, runs `prep -top` on both, and
  turns a register file into flip-flops with `memory_map` [EqyQuick].
- eqy matches signals of the two designs by name and cuts the combined design
  into partitions at the matched points; each partition is proved on its own
  [EqyConfig] [EqyQuick]. A signal that matches nothing proves nothing about
  that signal (inference).
- `[collect]` sections group bits that belong together, such as a register file
  or an immediate field, into one partition [EqyConfig] [EqyQuick]. `[match]`
  sections give name rules where synthesis renamed a signal, and `[recode]`
  sections give the state encodings when a tool recoded an FSM [EqyConfig].
- A `[strategy]` section picks how partitions are proved. The `sat` strategy
  runs a k-induction proof with Yosys's own `sat` command; it is quick for
  small partitions, cannot prove some partitions equal, and does not apply to
  partitions with memories. The `sby` strategy always uses SymbiYosys in prove
  mode, with a chosen engine and solver, and is the more general choice
  [EqyStrat]. `depth` is the unrolling the proof may use [EqyStrat].
- eqy interprets gold with Yosys's three-valued semantics and gate with
  two-valued semantics in which each unknown bit is an arbitrary value, and the
  miter treats an unknown gold output as equal to any gate value [EqyX].

## What the equivalence gate demands

- `equivalence.run` takes the setup in `eqy`, and optionally the RTL it must
  read in `sources` (gate: src/nirmaan/company/tools.py:170-175).
- A setup is refused, and nothing runs, when a script line reaches outside
  Yosys (a shell, `exec`, `tcl`, `python`, `script`, `plugin`), when a script
  writes a file (`write_*`, `tee`, `dump`), when `[gold]` or `[gate]` is
  missing, when the two scripts are the same so that a design is compared with
  itself, or when it reads a file by an absolute path, outside its own folder,
  or one that is not there (gate: src/nirmaan/integrations/equivalence.py:77-101).
- Given `sources`, the setup must read every one of them, compared by resolved
  path (gate: equivalence.py:109-117).
- The run copies the setup and the files it reads into its own directory, so a
  write cannot change the submitted files, and it records the files each side
  read (gate: equivalence.py:120-132).
- A run passes only when eqy exited 0, said `DONE (PASS)` and that the designs
  were proved equivalent, proved at least one partition, and failed none. A
  setup that proves no partition fails, and the summary says that nothing was
  proved; one whose
  partition was not proved fails and names the first partition (gate:
  src/nirmaan/integrations/eda_parsers.py:461-514).
- The result names the gold and the gate files, so a pass says which two
  versions were compared (gate: eda_parsers.py:497-499).

## Common failure modes

- Gold and gate running the same commands, or only the original: the gate
  refuses a setup whose `[gold]` and `[gate]` sections hold identical command
  lists, because it would compare a design with itself (gate:
  src/nirmaan/integrations/equivalence.py:91-93); lines under `[script]` are
  shared and are not part of that comparison. It does not refuse two sides that
  read the same file with different commands, which it accepts (inference from
  the same check, which compares scripts and not file names). Naming only the
  original leaves nothing to compare.
- Comparing before elaborating to the same top, or with different parameters,
  so the signal names do not line up.
- A setup that proves a few matched points while the output cone is unmatched.
  The gate counts partitions, not outputs, so read which partitions were
  proved (inference).
- A depth too small for a design whose outputs agree for the first steps and
  differ later. The `sat` strategy proves equality only if the outputs agree
  for the initial depth steps and for every later step that follows depth
  agreeing steps [EqyStrat].
- Missing recode or match rules after synthesis changed an FSM encoding or a
  name, which leaves partitions that cannot be proved [EqyConfig].
- A bug in gold carried into gate, which equivalence cannot see.

## How a result is checked

- Read the gold and gate file names and the partition count in the summary
  (gate: eda_parsers.py:497-503).
- Run the same setup against a gate version with one behaviour changed, such as
  one wrong bit, an off-by-one in a flag or a wrong reset value. A setup that
  still reports equivalence is not looking at that behaviour (inference).
- On a failure, eqy writes a trace of the failing case; the getting-started
  example found a shifter that used six bits of a shift amount where the
  instruction set uses five [EqyQuick].
