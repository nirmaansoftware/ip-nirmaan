# Knowledge Base Expansion program (post-1.0, content-only)

A user-approved drive to make the Verification Knowledge Engine *elite in
breadth*: grow from 13 packs toward a broad, deep library across four domain
tiers. Every tier is additive content exactly like the M5.1 expansion - new
`knowledge/packs/` modules plus one realistic fixture per pattern - with zero
change to `EvidenceClause`, the matcher, the Knowledge Graph, reasoning, or
the report. Backward compatible; minor-version releases.

- **Tier 1 (v1.1.0) - RISC-V & CPU/ISA depth.** Six new packs beside the
  existing `riscv-privilege`: `riscv-atomics` (LR/SC forward progress, AMO
  aq/rl ordering), `riscv-vector` (illegal vtype, tail/mask undisturbed
  policy, vl element-count), `riscv-memory-model` (RVWMO ordering, FENCE
  enforcement), `riscv-interrupts` (PLIC priority inversion, claim/complete
  gateway, mie/mip masking), `riscv-pmp` (access-fault miss, NAPOT/TOR
  boundary decode), `riscv-debug` (abstract-command cmderr, halt-request
  timeout). 14 new patterns/playbooks, 3 new state machines, 14 fixtures.
  Breadth floors in `test_knowledge.py` raised (>=18 packs, >=40 patterns/
  playbooks/concepts). 19 packs / 44 patterns total; 298 tests (up from 278).
- **Tier 2 (v1.2.0) - Interconnect & NoC.** Five new packs: `axi-stream`
  (TLAST packet framing, backpressure deadlock), `ace` (snoop CR response,
  barrier ordering), `noc` (routing deadlock, credit underflow, HOL blocking
  + packet-lifecycle state machine), `cxl` (Flex Bus negotiation, CXL.mem
  completion), `ucie` (die-to-die training, lane repair/degrade). 11 new
  patterns/playbooks, 1 state machine, 11 fixtures. Floors raised (>=24
  packs, >=55 patterns). 24 packs / 55 patterns / 53 playbooks / 54 concepts;
  314 tests.
- **Tier 3 (v1.3.0) - Memory & Serial IO.** Nine new packs: `ddr` (command
  timing, refresh discipline), `hbm` (channel decode, per-channel refresh),
  `usb` (transaction handshake, USB3 LTSSM), `ethernet` (MAC FCS, PCS block
  lock), `mipi` (D-PHY HS sync, CSI-2 ECC/CRC), `i2c-i3c` (I2C ACK, I3C IBI),
  `spi` (CPOL/CPHA, CS framing), `uart` (framing, RX overrun), `jtag` (TAP FSM
  + IR/DR scan, with a TAP state machine). 18 new patterns/playbooks, 1 state
  machine, 18 fixtures. As planned, only presence-expressible failure modes
  ship; memory-timing SLA and performance patterns still wait on the future
  numeric-clause upgrade (5.1) - each such pack notes this in its docstring.
  Floors raised (>=33 packs, >=72 patterns). 33 packs / 73 patterns / 71
  playbooks / 72 concepts; 341 tests.
- **Tier 4 (v1.4.0) - Methodology & fundamentals depth.** Seven new packs:
  `uvm-ral` (mirror/prediction, field access policy), `uvm-phasing`
  (objection leak, phase order), `uvm-tlm` (port connectivity, analysis
  drop), `formal` (counterexample, vacuous pass, inconclusive bound),
  `low-power` (isolation, retention + the On/Isolate/Retain/Off power-domain
  state machine), `dft` (scan-chain integrity, MBIST signature),
  `x-propagation` (uninitialized-X read, X through control). 15 new
  patterns/playbooks, 1 state machine, 15 fixtures. As flagged: `low-power`
  ships the new power-domain state machine; `formal` reads formal-tool *log
  results* only (native proof-artifact ingestion still wants a dedicated
  ArtifactType, 5.1). Floors raised (>=40 packs, >=86 patterns). Final:
  **40 packs / 88 patterns / 86 playbooks / 86 concepts / 15 state machines**;
  363 tests.

**Knowledge Base Expansion (Tiers 1-4, v1.1.0-v1.4.0).** The engine grew from
13 packs to 40 across six domains (interconnect, CPU/ISA, memory, serial IO,
coherency, methodology/fundamentals) with no change to `EvidenceClause`, the
matcher, the Knowledge Graph, reasoning, or the report - proving the M5
registry architecture scales to elite breadth on content alone.
