---
id: verification/portable_stimulus
skill: portable_stimulus
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | Hosokawa (Canon U.S.A.), Portable Stimulus Standard Tutorial, DVCon proceedings, open access [PSSTut] | https://dvcon-proceedings.org/wp-content/uploads/Tutorial3-Portable-Stimulus-Standard-Tutorial.pdf
licence_check: original writing that summarises and cites; no text, table, figure or code copied from the source
export_screen: clear
writer: IP-W2-K8 session (wave 2 knowledge batch, plan row W2-K8, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Knowledge only: no tool run backs this.

# Portable stimulus

How a scenario is described once and then realised on more than one
execution platform, from one open DVCon tutorial on the Accellera Portable Test
and Stimulus Standard (PSS). Tags in brackets name the source above;
"inference" marks this document's own reasoning. This skill's card holds no
tool (src/nirmaan/company/skills.py:394-400), and nothing here has been run.
The tutorial is the only source read for this document, so everything below
is one author's account of the standard, not the standard itself.

## What a model holds

- The tutorial describes PSS as declarative: it brings constrained-random
  generation to the scenario level, and states rules (scheduling between
  actions, data flow between actions, data constraints, target resource
  constraints) that define the set of possible scenarios [PSSTut].
- Its vocabulary: behaviour is an action, a schedule is an activity,
  sequential data is a buffer, parallel data is a stream, and state
  information is a state [PSSTut]. Resources are claimed by actions; the
  tutorial's DMA example locks a channel resource and takes a memory buffer
  as input [PSSTut].
- A model has two layers: the abstract model (what the test does) and the
  realisation layer (how it does it, meaning the functions called and the
  values passed) [PSSTut]. Atomic actions map to target code in exec blocks
  [PSSTut].
- The tutorial calls PSS a complement to UVM, not a replacement. Inside UVM
  it can create a set of sequences that run in an existing environment
  [PSSTut].

## Constraints and requirements

- Constraints can sit at the scenario, action or object level, they compose,
  and all relevant constraints are applied across the activity [PSSTut].
- Rules let a scenario be inferred from a partial specification: a model can
  require that an IP is initialised before use, and the tool then infers a
  valid initialisation action, or reports an error if none exists to infer
  [PSSTut].
- The tutorial's pattern is a state object that initialisation actions move
  out of its initial state, and behaviour actions that require a non-initial
  state; common requirements go into an abstract base action [PSSTut].
- The tutorial says the solver keeps a scenario "correct by construction": it
  does not over-use available resources and inserts synchronisation points
  where needed [PSSTut]. An allocation error is reported when concurrent
  memory claims cannot be satisfied, while sequential claims can recycle the
  same memory [PSSTut].

## Mapping a scenario to a platform

- The tutorial lists targets as simulation (coreless with bus functional
  models, or processor driven), emulation, and post-silicon boards or ATE
  that are processor driven [PSSTut].
- Three ways to write the exec blocks are shown: target templates, one
  block per target language with holes for generated values; a procedural
  interface that maps to functions or tasks in the target language; and
  procedural constructs that move complex control flow into the model
  [PSSTut]. The tutorial says the second needs one exec block per action type
  and the third makes moving between languages simpler [PSSTut].
- The same abstract action can have a register-level realisation and a
  driver-level one (the tutorial's UART transmit action, written once against
  registers and once against a C driver API), using `extend` to supply the
  second realisation [PSSTut].
- Registers are reached through a register access layer defined in the PSS
  core library, with read and write by value, by field and by masked
  read-modify-write [PSSTut]. The tutorial lists IP-XACT, SystemRDL and
  custom formats as inputs to tools that generate such a layer [PSSTut].
- For a UVM or SystemVerilog target, memory and register access routines are
  implemented in terms of the testbench: directly to a bus functional model,
  or through the UVM register model at address level [PSSTut].
- Environment specifics (memory map, access mechanism) go in a top-level
  component, so the IP component stays environment independent [PSSTut].

## Reuse across levels

- The tutorial's block-level content initialises the IP in chosen modes
  (fully random, fixed sanity, or fixed along some axes), exercises key
  operations, and collects coverage on the initialisation modes [PSSTut].
- At sub-system and SoC level the same IP components are combined with
  activities such as parallel traffic, and the tool schedules and allocates
  [PSSTut]. The tutorial names three ownership choices for IP models: the SoC
  team uses IP test vectors, the SoC team owns the models, or IP teams own
  them. It lists a cost and a benefit for each [PSSTut].
- Coverage is defined on scenario attributes with coverpoints, bins and
  crosses, and the tutorial says tools can predict it at generation time
  because scenarios are solved up front [PSSTut]. PSS 3.0, then in public
  review, adds behavioural coverage: a cover statement asks whether a temporal
  scenario occurred in a stream of action executions [PSSTut].

## Common failure modes

- A scenario whose realisation exists for one platform only (the card). The
  tutorial's remedy is a second exec block or realisation for each target
  [PSSTut].
- A behaviour action that does not require initialisation, so a scenario can
  use an IP that was never set up. The tutorial states that requiring it lets
  tools detect the omission [PSSTut].
- Modelling every IP at the finest detail before any scenario is needed. The
  tutorial says IP models may be coarse (a vector of an existing test) or
  fine grained [PSSTut]; which to choose is a project decision (inference).
- A realisation whose observation is invisible on the target. The tutorial
  says portability is a critical enabler for fast platforms with low
  observability (ATE, emulation, silicon boards, bare metal), and, as a
  separate point, that tools can predict coverage at generation time because
  PSS scenarios are declarative [PSSTut]; this document adds that each
  scenario should name what is observed on its target (inference).

## How a result is checked

- Each scenario traces to a plan item and names its target platform (the
  card's own check). The tutorial supplies the second half: a target is a
  named platform in its list above [PSSTut]. The trace to a plan item is this
  document's reading of the card and is not stated by the source (inference).
- Coverage on the scenario space is read at generation time or after the run;
  the tutorial states it can be predicted before tests run, which this
  document does not claim for any tool in this repository [PSSTut].
- The tutorial is a conference presentation. It does not state limits of the
  standard or a failure rate for any approach, so no such claim is made here.

## Sources

- [PSSTut] The whole tutorial: concepts, block-level modelling, SoC-level
  modelling, coverage and the PSS 3.0 preview.
