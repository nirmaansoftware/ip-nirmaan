---
id: verification/vip_integration
skill: vip_integration
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | lowRISC, OpenTitan JTAG DV UVM Agent (Apache 2.0) [OTJtag] | https://opentitan.org/book/hw/dv/sv/jtag_agent/index.html
  - open | lowRISC, OpenTitan Alert agent (Apache 2.0) [OTAlert] | https://opentitan.org/book/hw/dv/sv/alert_agent/index.html
  - open | lowRISC, OpenTitan TileLink UVM Agent, I2C DV UVM Agent and UART agent pages (Apache 2.0) [OTStub] | https://opentitan.org/book/hw/dv/sv/tl_agent/index.html and https://opentitan.org/book/hw/dv/sv/i2c_agent/index.html and https://opentitan.org/book/hw/dv/sv/uart_agent/index.html
  - open | lowRISC, OpenTitan Comportable IP Testbench Architecture, cip_lib (Apache 2.0) [OTCip] | https://opentitan.org/book/hw/dv/sv/cip_lib/index.html
  - open | lowRISC, OpenTitan UART DV document (Apache 2.0) [OTUart] | https://opentitan.org/book/hw/ip/uart/dv/index.html
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
  - open | lowRISC, OpenTitan DV Library Classes (Apache 2.0) [OTLib] | https://opentitan.org/book/hw/dv/sv/dv_lib/index.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K8 session (wave 2 knowledge batch, plan row W2-K8, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Knowledge only: no tool run backs this.

# VIP integration

How a reusable verification component (an interface agent, called a VIP or UVC
here) is brought into a testbench and set to match the interface it watches.
The sources are one open project's agent pages and its testbench library
(OpenTitan, SystemVerilog and UVM). They are open agents written by the
project team, not commercial VIP, and no commercial VIP manual was read (this
is recorded in the wanted-sources list). Tags in brackets name the sources
above; "inference" marks this document's own reasoning. This skill's card
holds no tool (src/nirmaan/company/skills.py:477-480), and nothing here has
been run.

## What a VIP holds

- OpenTitan's agents extend the project's DV library agent classes, which
  provide common knobs and verification logic so that an interface agent is
  less work to write [OTJtag] [OTAlert]. The library page itself leaves its
  agent-extension section as a to-do [OTLib].
- The JTAG agent lists its parts: a driving and monitoring interface, a
  simpler monitor-only interface for when JTAG is not continuously connected,
  a register model of the debug transport registers, a register adapter, a
  configuration class, a transaction class, a driver and a monitor [OTJtag].
- Its register model is hand-written from the RISC-V debug specification
  (chapter 6 of version 0.13.2) because the register set is small [OTJtag].
  It mirrors the design registers, so the testbench can predict what was
  written and compare with what the design returns [OTJtag].
- The JTAG transaction carries instruction-register and data-register lengths.
  A length of zero means that kind of update is not driven or monitored, and
  the driver reports an error if both are zero [OTJtag]. The driver is
  implemented only in host mode [OTJtag].
- The alert agent implements the alert interface protocol and can be a sender
  (host mode) or a receiver (device mode) [OTAlert].
- The OpenTitan pages for the TileLink agent and the UART agent are a to-do
  marker, and the I2C agent page is one sentence saying it extends the library
  agent classes [OTStub]. Where a source page is empty, nothing is claimed
  about that agent here.

## Configuring a VIP

- An agent configuration object holds the handle to the interface and the
  settings. For JTAG it is created outside the agent and passed in through
  the UVM configuration database; the agent then sets the handle in all its
  sub-components [OTJtag].
- In the project's comportable-IP library, the environment configuration
  holds the interface handles and the downstream agent configurations, so one
  object carries the settings for the environment and every agent [OTCip]. The
  test creates it in the build phase and passes it through the configuration
  database [OTCip].
- The environment uses those settings to adjust each agent's configuration
  as needed [OTCip]. The UART bench follows this: its environment creates the
  UART agent and can change its settings from the environment configuration
  [OTCip].
- The TileLink host agent is created in the base environment. Alert device
  agents are created if the module has alerts, and by default are configured
  as device mode, asynchronous and active, with ping coverage off [OTCip].
- To add alert agents the library page gives these steps: list the alert names
  and count in the environment package, assign the list in the configuration
  before calling the base initialisation, and add the alert-interface macro
  in the testbench top so the interfaces are wired to the design and set in
  the configuration database [OTCip]. The alert names and their order must be
  correct [OTCip].
- The testbench top instantiates the interfaces, connects them to the design
  and sets their handles in the configuration database [OTUart].
- The UART agent drives and monitors UART items and gives basic coverage on
  data, parity and baud rate; the page lists the baud rates the design
  supports [OTUart].

## Connecting a VIP to checking and coverage

- A scoreboard gets items from each agent monitor through analysis FIFOs. The
  UART scoreboard takes the bus address and data channel items and the UART
  transmit and receive items [OTUart].
- The environment connects the agent to the virtual sequencer and the
  scoreboard [OTCip].
- Coverage is sampled in reactive components such as monitors and
  scoreboards [OTDV]. A VIP with a detailed coverage model can cover options
  the design does not support. OpenTitan's coverage-exclusion rule names this
  case: a TileLink agent covering the full range of burst sizes while the
  design supports a subset is excluded as UNSUPPORTED, and the explanation is
  mandatory [OTDV].
- Idle channels are driven to unknown values so that X-propagation checks
  have something to catch: the project's TileLink interface code drives address,
  data and control to unknown when the valid bit is clear [OTDV].
- The generator script for a new design environment can also generate the
  skeleton of a new agent [OTDV].

## Common failure modes

- A VIP left at its defaults while the interface spec says otherwise (the
  card). The sources show where the settings live (the configuration object
  and the environment's override of it) but give no list of risky defaults
  [OTJtag] [OTCip].
- An alert list in the wrong order or incomplete, so signals are wired to
  the wrong agent. The page says the names and order must be correct; the
  consequence is this document's reading (inference from [OTCip]).
- A passive mode needed but an active one used (inference): the JTAG agent has
  a separate monitor-only interface for the case where it does not drive the
  signals [OTJtag].
- Coverage items in the VIP that the design cannot reach, left uncovered
  without a reason [OTDV].
- A VIP configured identically for several interfaces. Not a failure any
  source states; it is a risk of copying the configuration (inference).

## How a result is checked

- Each VIP setting traces to a line of the interface spec (the card's own
  check). The sources' one example of such a trace is the JTAG register model,
  which names the specification chapter it came from [OTJtag]. For any other
  setting, record the spec clause beside the configuration line (inference).
- The VIP's monitor reaches a scoreboard, and the scoreboard compared at least
  one item in a smoke run (inference, consistent with [OTUart]).
- Settings the design does not support are either not driven or excluded from
  coverage with a reason [OTDV].

## Sources

- [OTJtag], [OTAlert] The two agent descriptions read in full.
- [OTStub] The agent pages that are stubs, read in full.
- [OTCip], [OTUart] How agents are created, configured and checked in a bench.
- [OTDV] Coverage exclusion categories and X-propagation practice.
- [OTLib] The base classes the agents extend.
