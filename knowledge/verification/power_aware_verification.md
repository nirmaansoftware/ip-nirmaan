---
id: verification/power_aware_verification
skill: power_aware_verification
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | IEEE P1801 working group members, Low Power Design, Verification, and Implementation with IEEE 1801 UPF, tutorial slides hosted by Accellera, 2013 [UPFTut] | https://accellera.org/images/resources/videos/Low_Power_with_UPF_2013.pdf
  - open | Bhargava and Gairola, Power State to PST Conversion: Simplifying static analysis and debugging of power aware designs, DVCon proceedings, open access [PST] | https://dvcon-proceedings.org/wp-content/uploads/power-state-to-pst-conversion-simplifying-static-analysis-and-debugging-of-power-aware-designs.pdf
  - open | Burns, Chidolue and Boillet, Comprehensive Metrics-Based Methodology to Achieve Low-Power System-on-Chips, DVCon tutorial, 2018, open access [LPMet] | https://dvcon-proceedings.org/wp-content/uploads/comprehensive-metrics-based-methodology-to-achieve-low-power-system-on-chips.pdf
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K8 session (wave 2 knowledge batch, plan row W2-K8, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Knowledge only: no tool run backs this.

# Power-aware verification

Checking a design against its power intent: isolation, retention, power
switching and power states, with UPF (IEEE 1801) as the power-intent format.
The sources are three open slide sets and papers (two from vendors, one from
the standard's working group) and one open project's methodology page. The
standard itself was not read (it is recorded in the wanted-sources list), so
what follows is the sources' account of UPF, not the language reference. Tags
in brackets name the sources above; "inference" marks this document's own
reasoning. This skill's card holds no tool
(src/nirmaan/company/skills.py:425-430), and nothing here has been run. The
vendor decks name commercial tools; those names are not recommendations and
none is claimed to run here.

## What the power intent holds

- UPF is a standard format for power intent and an extension of Tcl; it drives
  verification and implementation from RTL to layout [UPFTut]. It is defined
  separately from the HDL [LPMet]. Power intent covers domains, supply rails, power switches,
  isolation, retention, level shifters and power state tables, where the
  functional intent in RTL does not [UPFTut].
- A power domain is a collection of instances managed as a group, and
  usually sharing a primary supply set [UPFTut]. A supply set groups related
  supply nets by function [UPFTut].
- An isolation cell passes values in normal mode and clamps its output to a
  specified value when a control signal is asserted; its use is to stop
  unknown values in powered-off logic reaching live logic [UPFTut].
- A retention register keeps its value while powered off, with a save and a
  restore control [UPFTut]. In the slide example the save and restore events
  are the two edges of one control signal [UPFTut].
- A level shifter changes a signal from one voltage level to another [UPFTut].
- In the 2013 deck's first-generation subset, the control signals for
  isolation and retention must already exist in the HDL; the second
  generation lets UPF create logic ports and nets for them [UPFTut].
- The versions named across the sources: Accellera UPF 1.0 (2007), IEEE
  1801-2009, 1801-2013, 1801a-2014 and 1801-2015 (UPF 3.0) [LPMet]. A 2018 deck
  lists a further revision as planned [LPMet]; check the version a project
  uses before applying any command from this document (inference).

## Power states, transitions and simulation state

- A power state table (PST) lists the legal combinations of supply port
  states [PST]. Later versions define states with `add_power_state` on supply
  sets and power domains, in terms of supply and logic expressions, and any
  state can be marked legal or illegal [PST]. `describe_state_transition`
  marks a transition between two states legal or illegal [PST] [UPFTut].
- A supply-set state can carry a simulation state that says how logic it
  powers behaves in simulation, from normal to corrupt, with intermediate
  values that corrupt on change or on activity [PST] [UPFTut]. In the decks'
  examples the off state is given the corrupt simulation state [UPFTut].
- The 2013 deck's top-level example defines states such as all on, partial
  off and all off, and marks some transitions illegal, for example all off
  directly to all on [UPFTut]. In the 2018 deck, a power state defined
  with `-complete` makes every unspecified state illegal [LPMet].
- The 2018 deck says states at the same level of refinement are mutually
  exclusive, and an error state is entered when two such states are active at
  once [LPMet].
- The PST paper warns that complex state definitions are hard to read and
  hard for tools to analyse; its guidelines include referring only to control
  signals, supply-set states and child-domain states in a domain's logic
  expression, and avoiding the `||` operator there because it leaves
  don't-care cells [PST].

## What gets checked, statically and dynamically

- Static: the PST paper describes how a tool finds domain-crossing signals,
  reads the operating voltages or the switched supply on each side, and
  compares that with the declared level-shifter or isolation strategy to call
  each one valid, missing or redundant; for level shifters only, comparing
  the properties of the specified and required cell also finds an incorrect
  one [PST]. The 2018 deck lists
  RTL checks (missing, redundant or back-to-back cells) and gate-level checks
  (cells match the strategies; control signals come from an always-on
  domain) [LPMet].
- Dynamic: the testbench drives the supply ports; the 2013 deck shows a
  package of supply on and off functions called with a supply name and a
  voltage [UPFTut]. In its system example, the testbench models off-chip
  supplies with switchable values [UPFTut].
- The 2018 deck lists what dynamic verification covers: power up and down
  sequencing of each block (save on power down, reset or restore on power up),
  isolation and level shifting on interfaces, retention protocols, and that
  non-retention flops may need a reset on power up [LPMet]. It also lists tool
  checkers for common sequencing errors and a debug view that marks corrupted
  values in the waveform [LPMet].
- At run time a tool can report an illegal power state; the PST paper shows
  such a message and explains that finding why the state was reached is hard
  when the definition mixes several signals [PST].
- The 2018 deck's emulation example is a system whose power controller was
  software: two cores each read an active-process counter, both decremented
  it, and a peripheral stayed on. It was traced with software and hardware
  events together [LPMet]. This is one case, not a rule; it shows power bugs
  can live in software-driven control (inference).

## Coverage of power states

- The 2018 deck asks whether every legal power state and every legal
  transition combination has been exercised [LPMet]. Its coverage list
  includes states and transitions of domains, supply sets and supply ports,
  retention save and restore events, the control and acknowledge signals of
  isolation, retention and switches, and whether built-in checks were active
  [LPMet].
- OpenTitan's methodology says power-aware tests must be added once power
  requirements such as retention or power collapse are specified for the
  product [OTDV]. That page does not describe how.

## Common failure modes

- Power intent never switched in simulation (the card): states defined but no
  test drives the supplies into them, so isolation and retention are never
  exercised. The sources' answer is power-state and transition coverage
  [LPMet].
- A transition never marked legal or illegal, so nothing says whether it is
  allowed. State both the legal and illegal sets (inference from the
  examples).
- An isolation or retention control signal missing or driven wrongly. The
  2018 deck lists control-signal checks and sequencing checks for this
  [LPMet].
- Power state definitions too complex to debug [PST].

## How a result is checked

- Every power state transition is exercised and checked (the card's own
  check). Read it as: each legal transition appears in the coverage report
  with its checks passing, and each illegal one is reported if reached
  (inference from [LPMet] and [PST]).
- Isolation, retention and power-up sequence results are read against the
  stated intent, not against the RTL alone (inference).
- A pass with the simulator's power-aware mode off proves nothing about
  power intent (inference); the sources assume the UPF is loaded.
