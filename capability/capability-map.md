# IP Nirmaan capability map

As of 2026-10-30. This is the P2 coverage map of the capability build-out
(council record `council/records/2026-10-18-capability-buildout.md`; plan
section 4 and the P2 exit in section 7). It lists every capability area at the
top two levels and says, for each, whether the company can practise it, can
only hold it as knowledge, or leaves it out, with a reason.

This file is coverage, not capability. A status here says whether the open
tools in this repository can run and judge the work; it is never an evidence
level. Levels come only from `capability/levels.json`, which
`scripts/capability_levels.py` computes from committed records
(`docs/CAPABILITY_LEVELS.md`). Nothing below raises or claims a level.

## Statuses

| Status | Meaning |
|---|---|
| P, practising | The open tools in this repository already run this work, and a tool-judged eval case exists or can be written against those runs. Most P rows still have no eval case. |
| K, knowledge only | No tool here runs or judges it, or it needs silicon, a lab, a fab, paid tools, paid specifications or real customers. "Free tool" in the notes names a free tool the research found would move the row towards P; "rubric" marks a row a review rubric could later judge. |
| O, out of scope | Not an IP Nirmaan activity even as knowledge. The reason is on the row. |

Columns: the catalog skill ids (`src/nirmaan/company/skills.py`) the area maps
to, and the units (`build_organization()`) or council seats that hold it today.
"none" means no skill id or no unit. A note "(NEW, round N)" marks a row the gap
hunter added; "widened" marks a row whose scope a gap-hunt round enlarged.

## Method in brief

1. **Reference taxonomies.** Four research notes (2026-10-30) built the first
   map from Appendix A of the plan and from open taxonomies: the ISSCC 2026
   topics, the IEEE CAS, MTT-S and EMC Society technical committees, the IEEE
   Photonics Conference topics, the IEEE EPS Heterogeneous Integration Roadmap
   (2024), the IRDS focus teams, the ITC 2026 topic list, the ICCAD and DAC
   calls, the ACM/IEEE Computer Engineering curricula (2016), university
   courses (Berkeley, MIT, Stanford, IISc, NPTEL), the AICTE VLSI model
   curriculum, Accellera working groups, and the semiconductor value chain
   reports of SIA and BCG. They gave 213 level-2 rows across 14 level-1 areas;
   four duplicates merged, leaving 209.
2. **Job market.** Public employer career pages and public aggregators, no
   login. The job-board connector the plan names was not available. Results
   are in aggregate below.
3. **Gap hunter, three rounds.** An adversarial pass whose only job is to find
   missing areas at the top two levels, repeated until a round finds nothing
   new:
   - round 1: 0 new at level 1, 4 new at level 2 (Accellera, JEDEC, ITC topics,
     ISSCC digital and memory, RISC-V committees, IRDS, IEEE 2427, DMTF, LAD
     and MLCAD calls, ASYNC, IISc, the National Qualifications Register);
   - round 2: 0 new at level 1, 1 new at level 2 (IEEE CEDA, DATE, ICCAD, DAC,
     SEMI, JEDEC JC-15 and JC-16, Electron Devices and Reliability societies,
     India Semiconductor Mission programmes, US and EU chips programmes, public
     job families, and a walk of one chip from market need to end of life);
   - round 3: 0 new at level 1, 0 new at level 2 (journal scopes of IEEE TCAD,
     JSSC and TVLSI and ACM TODAES and TECS, arXiv categories, CHIPS Alliance,
     FOSSi, OpenTitan, lowRISC, OpenHW, community shuttles, VLSI Society of
     India, IESA, NIELIT and AICTE curricula, and a boundary check with
     Nirmaan).
4. **Stop rule met on 2026-10-30.** Round 3 found nothing new at the top two
   levels. The map below applies the five new rows and every widening and
   merge from the three rounds: 214 level-2 rows.

Sources are cited only where an agent can read them in full and legitimately;
the research notes, job listings and source wish list stay in private notes.

## Summary

| Level-1 area | Rows | P | K | O |
|---|---|---|---|---|
| Foundations | 14 | 3 | 11 | 0 |
| Architecture | 15 | 8 | 7 | 0 |
| Design | 29 | 14 | 14 | 1 |
| FPGA | 9 | 0 | 8 | 1 |
| Verification | 19 | 7 | 11 | 1 |
| Implementation | 18 | 10 | 8 | 0 |
| Hardware software | 13 | 5 | 8 | 0 |
| Silicon lifecycle | 15 | 0 | 15 | 0 |
| Analog and mixed-signal | 13 | 0 | 12 | 1 |
| RF and photonics | 9 | 0 | 9 | 0 |
| Process and fab | 10 | 1 | 8 | 1 |
| Packaging and systems | 10 | 0 | 10 | 0 |
| Emerging compute | 6 | 0 | 6 | 0 |
| Business | 34 | 4 | 26 | 4 |
| Total | 214 | 52 | 153 | 9 |

The level-1 list is Appendix A's. Changes to it (promotions and splits) are
proposals for the council, listed after the tables.

## Foundations

Prerequisites that skills cite. No unit holds them as a practice.

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Digital logic and Boolean design | P | digital_design | none directly (reached through design.rtl and architecture.micro skills) | Icarus, Yosys and SBY run small logic; the RTL evals exercise it |
| Computer organisation and assembly | P | none | architecture.micro.cpu, software.firmware | RISC-V GCC with PicoRV32 and SERV in Verilator runs programs |
| CMOS digital circuits | K | none | none | No SPICE here. Free tool: ngspice |
| Circuit theory and basic electronics | K | none | none | No circuit simulator connected |
| Semiconductor device physics (basics) | K | none | none | TCAD and SPICE not connected; advanced devices sit in Process and fab |
| Signals and systems | K | none | architecture.micro.dsp (indirect) | No eval judge for mathematical answers yet |
| Control systems | K | none | none | Feeds PLL, DVFS and regulator loop design |
| Probability, statistics and linear algebra | K | none | none | Needed for ML hardware, yield and performance statistics |
| Information and coding theory | K | none | none | ECC hardware itself is under Signal processing and coding IP |
| Numerical methods | K | none | none | |
| Electromagnetics | K | none | none | Depth sits in the RF and packaging rows |
| Algorithms, optimisation and logic solvers | K | none | design.rtl.automation, infrastructure.eda.tooling | Python runs, but nothing judges algorithm work yet |
| Programming foundations | P | c_programming, python, build_systems | software, infrastructure.ai | GCC, Python and make run; the firmware eval judges C. Holds Tcl, Perl and C++ for EDA flows (job market) |
| Reading research papers and standards | K | none | documentation | Rubric only |

## Architecture

Units: architecture.system, architecture.micro, architecture.interface,
architecture.io. Planned placeholder in the record's chart: Architecture
Research (emerging compute, see Emerging compute).

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| SoC and system architecture | K | system_architecture, ip_architecture, software_architecture | architecture.system.soc, architecture.system.ip, architecture.system.software | No tool judges system trade-offs; a PicoRV32 SoC eval could make a slice practisable. Includes system-level HW/SW co-design and clock planning |
| ISA and CPU microarchitecture | P | cpu_microarchitecture, rtl_microarchitecture | architecture.micro.cpu | PicoRV32 and SERV run in Verilator; out-of-order only at block level. Widened: executable ISA specifications |
| Caches, memory consistency and coherence | P | cache_microarchitecture, ace, chi | architecture.micro.cache, architecture.interface.ace, architecture.interface.chi | Cache RTL with simulation and SBY protocol checks is writable |
| GPU architecture | K | gpu_microarchitecture | architecture.micro.gpu | No GPU RTL or simulator. Free tool: the Vortex open GPGPU |
| AI accelerator architecture | P | npu_microarchitecture | architecture.micro.npu | Block level: MAC and small systolic arrays simulate against a Python golden model; design-space exploration is K. Includes CGRAs and approximate computing |
| DSP architecture | P | dsp_microarchitecture | architecture.micro.dsp | Filter and FFT RTL checked against numpy vectors |
| Memory subsystem architecture | K | memory_architecture, memory_controller_microarchitecture, ddr | architecture.system.memory, architecture.micro.memctrl, architecture.io.ddr | No DRAM model here. Free tool: Ramulator or DRAMSim3 |
| Interconnect and NoC | P | noc_architecture, qos_architecture, noc_protocol, interconnect_design, arbitration, buffering_flow_control | architecture.system.interconnect, architecture.micro.noc, architecture.interface.noc, design.rtl.design.interconnect | The rr_arbiter eval exists; router RTL simulates |
| Performance and power modelling, benchmarking | K | performance_modeling | architecture.system.performance, software.performance | Free tool: gem5 or SystemC; CoreMark on PicoRV32 is the first slice |
| Computer arithmetic and number formats | P | arithmetic_design | design.rtl.design.arithmetic | Simulation, SBY and Yosys equivalence; Berkeley TestFloat vectors are free |
| Power management architecture | K | power_architecture | architecture.system.power | No open power-intent tool; power numbers need the physical flow |
| Security architecture | K | security_architecture | security.architecture | Rubric only. Includes CHERI and control-flow integrity |
| Peripheral, interrupt, DMA and debug architecture | P | peripheral_microarchitecture | architecture.micro.peripheral | A design interrupt reaches PicoRV32 and firmware tests it (M29). Includes debug and trace architecture |
| Specification and requirements | P | interface_specification, custom_interfaces, register_documentation | architecture.interface, architecture.io, documentation.specifications | The spec/axi4_lite_interface eval runs spec.check and regmap.check. Widened from interface and register specification to requirements and traceability |
| Chiplet and multi-die partitioning | K | none | none | Partitioning only; physical side in Packaging and systems, die-to-die RTL in Design |

## Design

Units: design.rtl, design.integration. Planned placeholder in the record's
chart: Domain IP (codecs and ISP, wireless baseband, networking silicon).

### Languages and methods

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| SystemVerilog and Verilog RTL | P | systemverilog, rtl_design | design.rtl | Four RTL evals with lint, simulation, synthesis and formal |
| VHDL | K | none | none | Free tool: GHDL |
| Generator and newer HDLs | K | none | none | Chisel, SpinalHDL, Amaranth, Bluespec. Free tool: Amaranth |
| High-level synthesis | K | none | none | Vendor HLS is proprietary. Free tool: Bambu, XLS or Calyx |
| RTL building blocks and microarchitecture practice | P | rtl_microarchitecture, datapath_design, control_logic_design, fsm_design, pipeline_design, memory_design, arbitration, buffering_flow_control, interconnect_design | design.rtl.architecture, design.rtl.design | The sync_fifo and rr_arbiter evals carry must-fail mutants. Not named in Appendix A |
| Clocks, resets, CDC and RDC | P | cdc_design, reset_design | design.rtl.cdc | Synchronisers and async FIFOs by simulation and formal; structural CDC signoff is K (cdc.run is contract only) |
| Low power design and power intent | K | low_power_design | design.rtl.low_power | No open UPF simulator or checker; clock-gating RTL alone is practisable |
| X-propagation and reset-state hygiene | P | none | none | Icarus is four-state and SBY checks reset values; the x-propagation knowledge pack is cited by no skill |
| Design quality: lint, standards, synthesis awareness, review | P | rtl_lint, coding_standards, synthesis_awareness, change_impact_analysis, code_review_practice | design.rtl.quality | Verilator lint and Yosys statistics gate every RTL eval |
| Register design and generation | P | register_documentation, register_programming, interface_specification | documentation.specifications.registers, software.registers | regmap.check and regmap.verify run; IP-XACT is K. Free tool: PeakRDL for SystemRDL |
| IP packaging and SoC integration | P | ip_integration, release_management, release_quality | design.integration.packaging (qualification and kits are placeholders) | fw.soc_test integrates a block on PicoRV32; packaging formats are K. Free tool: FuseSoC |
| Design automation and generators | P | design_automation | design.rtl.automation, infrastructure.eda.tooling | Python and the tool bindings run |
| Asynchronous and self-timed design (NEW, round 1) | K | none | none | Bundled data, QDI, handshake pipelines, asynchronous synthesis and test |

### Interface IP

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| On-chip buses | P | axi, axi_stream, ahb, apb, ace, chi | architecture.interface, design.rtl.interface | AXI4-Lite and APB evals exist; coherent ACE and CHI flows at scale are K; TileLink, Wishbone and OCP packs are cited by no skill. Not named in Appendix A |
| Low-speed serial and control | P | peripheral_microarchitecture | architecture.micro.peripheral | UART, SPI, I2C, SMBus, I3C, GPIO, I2S: controller RTL plus driver on PicoRV32 runs today |
| High-speed serial I/O controllers | K | pcie, cxl, usb, ethernet | architecture.io.pcie, architecture.io.cxl, architecture.io.usb, architecture.io.ethernet, design.rtl.interface | Gated or paid specifications, no open VIP; an Ethernet MAC is the practisable slice; the UCIe pack is cited by no skill |
| Memory interfaces | K | ddr, memory_controller_microarchitecture | architecture.io.ddr, architecture.micro.memctrl | JEDEC registration needed, no DRAM model. Widened: memory modules and buffer chips |
| Display, camera and media interfaces | K | none | none | MIPI, HDMI and DisplayPort specifications are member-only or paid; DVI timing is free and practisable as a small slice |
| Storage and host interfaces | K | none | none | NVMe, SATA, UFS, SD need PCIe or UniPro underneath. Widened: SSD and flash controllers |
| PHY boundary and digital PCS | P | none | none | Line codes, scramblers and CRC simulate against reference vectors; PIPE and DFI mark the controller and PHY split |
| Automotive and industrial buses | K | none | none | CAN, LIN, FlexRay, TSN; the ISO standards are paid, but a CAN controller is practisable from free Bosch documents |
| Proprietary interfaces without public specs | O | none | none | No legitimate public specification to learn from; reopen only with a licensed one |

### Domain IP

Each domain row includes the step from algorithm to bit-true model (widened in
round 2).

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Security IP | P | cryptography, hardware_security, secure_boot | security.crypto, security.hardware, security.secure_boot | Functional only: cipher and hash RTL checked against NIST vectors; side-channel resistance is K. Widened: accelerators for privacy-preserving computation |
| Video and image | K | none | none (planned Domain IP) | Codecs and ISP are large; only small kernels have a judge |
| Audio and speech | K | none | architecture.micro.dsp (indirect) | |
| Wireless baseband and MAC | K | none | none (planned Domain IP) | Needs RF and channel models. Renamed: lower MAC is IP; upper MAC and protocol stacks are software outside this map |
| Networking silicon | K | none | none (planned Domain IP) | Parsers are practisable at block level. Free tool: bmv2 and the P4 tools |
| Signal processing and coding IP | P | dsp_microarchitecture, arithmetic_design | architecture.micro.dsp, design.rtl.design.arithmetic | FIR, FFT, CORDIC, ECC codecs: RTL against numpy or C golden models |
| System and foundation digital IP | P | peripheral_microarchitecture | architecture.micro.peripheral | DMA, timers, watchdogs, interrupt controllers, debug module: the PicoRV32 SoC with interrupts runs these patterns |

## FPGA

Unit: design.fpga (placeholder, a director only). No FPGA skill id exists.

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| FPGA architecture and devices | K | none | design.fpga | |
| Open FPGA flow | K | none | design.fpga | No FPGA binding in eda.py; Yosys already has the FPGA passes. Free tool: nextpnr (the strongest upgrade candidate) |
| Vendor flows | K | none | design.fpga | Large proprietary installs whose licence terms the founder must accept |
| FPGA design methodology and timing closure | K | none | design.fpga | Free tool: nextpnr timing reports |
| SoC FPGAs and soft processors | K | none | design.fpga, software.firmware | Free tool: LiteX with Verilator simulation, no board needed |
| FPGA HLS and accelerator frameworks | K | none | design.fpga | Needs vendor tools and boards |
| FPGA debug and board bring-up | K | none | design.fpga | Needs physical boards |
| FPGA reliability and security | K | none | design.fpga, security.hardware | |
| FPGA CAD and eFPGA fabric design | O | none | none | A separate product line needing silicon characterisation, with no demand in the job pull; reopen if the commercial model asks for eFPGA IP |

## Verification

Units: verification. Seat: verification-lead.

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Planning, methodology and signoff | P | verification_planning, verification_architecture, verification_signoff, traceability | verification.planning, verification.architecture, verification.signoff, quality.reviews.verification_signoff | vplan.check runs against specification tags |
| Directed and self-checking testbenches | P | directed_testing, systemverilog | verification.simulation.systemverilog, verification.simulation.testbench | Icarus and Verilator run; the RTL evals hold must-fail testbench checks but credit rtl_design |
| UVM and constrained random | K | uvm, constrained_random, vip_integration | verification.simulation.uvm, verification.simulation.vip | No simulator here runs UVM. Free tool: a Verilator release with upstream UVM support |
| Python-based verification | K | none | none | Free tool: cocotb on Icarus or Verilator |
| Assertions and formal property checking | P | sva, formal_verification, model_checking, formal_coverage, assertion_coverage | verification.formal, verification.coverage.assertion | SBY proofs and covers run; open Yosys reads only a subset of SVA |
| Equivalence checking | K | equivalence_checking | verification.formal.equivalence | equivalence.run is contract only. Free tool: Yosys eqy |
| Coverage and closure | K | code_coverage, functional_coverage, assertion_coverage | verification.coverage | coverage.read is contract only; covergroups are unreliable in open simulators. Free tool: verilator_coverage. Includes UCIS |
| Debug, triage and regression | P | failure_triage, log_analysis, waveform_debug, root_cause_analysis, regression_intelligence, regression_management | verification.debug, verification.simulation.regression, infrastructure.eda.regression | veritriage.investigate runs on real simulation logs; replayed-failure evals are writable |
| CDC and RDC verification | K | cdc_verification | verification.cdc | cdc.run is contract only; no mature free structural CDC tool |
| Processor and ISA verification | K | none | none | The cores already run. Free tool: riscv-arch-test, riscv-dv, riscv-formal |
| Datapath and accelerator verification | K | none | none | Free tool: cocotb with Python golden models; Berkeley TestFloat |
| Hardware/software co-verification | P | embedded_firmware, device_drivers, register_programming | software.validation, software.registers | fw.test and fw.soc_test; the firmware/axi4_lite_driver eval |
| Gate-level simulation | P | none | none | Icarus simulates Yosys netlists in the DFT flow; SDF-annotated runs not yet |
| Power-aware verification | K | none | none | No free UPF-aware simulator |
| FPGA prototyping | K | none | design.fpga | Needs a board |
| Hardware emulation | O | none | none | Emulators are paid hardware |
| Security verification | K | security_verification | security.verification | Free tool: access-control properties in SBY and fuzzing on Verilator |
| System-level and portable stimulus | K | none | none | No free PSS tool here |
| AI-assisted verification | P | regression_intelligence | verification.debug.intelligence, infrastructure.ai | The eval harness and VeriTriage judge model output with real tool runs |

## Implementation

Units: implementation.pd, implementation.dft, implementation.foundation
(placeholder, no skill). Seats: physical-design-engineer, dft-engineer.

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Logic synthesis | P | synthesis, synthesis_awareness | implementation.pd.synthesis, design.rtl.quality.synthesis | Yosys and ABC map to Nangate45 and sky130 Liberty in CI |
| Timing constraints and STA | P | sta, timing_constraints | implementation.pd.sta | OpenSTA runs multi-corner on sky130 in CI; OCV derates and SI not yet |
| Floorplan and power grid | P | floorplanning, power_planning | implementation.pd.floorplan, implementation.pd.power_plan | OpenROAD floorplan, tap cells and PDN in CI |
| Placement, CTS and routing | P | place_and_route | implementation.pd.place_and_route | pnr.run reaches a routed, filled layout in CI |
| Extraction and signal integrity | P | none | implementation.pd.sta | OpenRCX extraction in CI; crosstalk and noise analysis is K |
| Power analysis and power integrity | P | power_analysis | implementation.pd.power | Static IR in pnr.run; EM is K. Free tool: OpenSTA power reports (power.run is contract only) |
| Low-power implementation | K | none | none | No UPF-aware free flow here |
| Timing closure and ECO | P | change_impact_analysis | implementation.pd.sta | A closure project (violated, then met) runs in CI; metal-only ECO is K |
| Physical verification and signoff | P | physical_verification, implementation_signoff | implementation.pd.signoff | KLayout DRC and LVS with the sky130hd decks in CI |
| Chip-level integration | K | none | none | The flow runs one block today. Free tool: OpenROAD macro support |
| DFT architecture, scan and ATPG | P | dft_architecture, scan_design, atpg, fault_modeling, test_compression, dft_verification | implementation.dft.scan_atpg, implementation.dft.test_access.compression, implementation.dft.test_access.verification | Scan, stuck-at and transition ATPG with measured coverage; compression and diagnosis are K |
| Memory test and repair | P | mbist | implementation.dft.memory_bist.mbist, implementation.dft.memory_bist.memory_test | March C- MBIST in simulation; repair is K |
| Logic BIST | K | lbist | implementation.dft.memory_bist.lbist | The in-repo fault simulator could judge an LBIST |
| Test access and core test standards | K | jtag | implementation.dft.test_access.jtag | IEEE 1149.1, 1500, 1687 and 1838, and known-good-die test. A TAP controller simulates. Free tool: OpenOCD |
| Standard cell libraries and characterisation | K | none | implementation.foundation | Free tool: CharLib or libretto with ngspice and sky130 models |
| Memory compilers, embedded memories and NVM macros | K | memory_design | implementation.foundation | Widened: OTP, eFuse, MTP, eFlash and MRAM macros; DRAM and NAND arrays are out of scope as a sub-topic. Free tool: OpenRAM, DFFRAM |
| I/O cells, ESD and latch-up | K | none | implementation.foundation | ESD needs foundry rules and silicon measurement |
| Custom and adaptive digital circuit design (NEW, round 1) | K | none | none | Transistor-level datapaths and hard macros, custom flops, clock distribution circuits, adaptive voltage and frequency, on-die PVT and droop sensors, digital LDOs, near-threshold design |

## Hardware software

Units: software, infrastructure.eda, infrastructure.ai. Seats:
firmware-engineer, eda-tooling, ai-engineer.

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Bare-metal firmware and HAL | P | embedded_firmware, c_programming, register_programming | software.firmware.hal, software.registers | fw.build, fw.cross_build and fw.soc_test on PicoRV32 and SERV |
| Device drivers | P | device_drivers | software.firmware.drivers | Bare-metal drivers (firmware/axi4_lite_driver eval); Linux drivers are K. Free tool: QEMU |
| Boot firmware and secure boot software | K | embedded_firmware, secure_boot | software.firmware.boot, security.secure_boot | Includes UEFI, ACPI, RISC-V SBI and RPMI. Free path: a boot flow on PicoRV32 in simulation |
| BSP, embedded Linux and RTOS | K | embedded_firmware | software.firmware.bsp | Includes WCET and scheduling. Free tool: Zephyr and Linux on QEMU or Renode |
| Pre-silicon software platforms | K | none | none | Owns SystemC and TLM. Free tool: QEMU, Spike, Renode, SystemC |
| CPU toolchains and compilers | K | developer_tools | software.tools.compiler, software.tools.sdk | The repo uses but does not develop compilers; compiler.run is contract only. Free tool: LLVM |
| Accelerator compilers and ML runtimes | K | developer_tools | software.tools.compiler | Free tools exist but no accelerator target here. Includes ML frameworks on our own accelerators |
| Debug and trace software | K | developer_tools | software.tools.debugger | debugger.attach is contract only. Free tool: OpenOCD to Verilator over remote bitbang |
| Diagnostics, validation and performance software | K | diagnostics_software, performance_modeling | software.diagnostics, software.validation, software.performance | Free path: suites run on PicoRV32 in simulation |
| CAD and flow engineering | P | eda_environment, design_automation, build_systems, ci_cd, regression_infrastructure | infrastructure.eda, design.rtl.automation, infrastructure.build | The backend registry and the pinned ORFS image run real flows. Widened: compute farms, licence servers and cloud runs |
| EDA tool and algorithm development | P | developer_tools, design_automation | infrastructure.eda.tooling | The repo's own PODEM ATPG, fault simulator and log parsers, judged by tests and real runs |
| Design data and configuration management | K | configuration_management, artifact_management, change_integration | quality.configuration, infrastructure.build.repositories, infrastructure.build.artifacts | Hardware data tools are paid. Free tool: Git LFS or DVC |
| AI for chip design (NEW, round 1) | P | none | infrastructure.ai | Model-written RTL is judged by real tool runs in evals/rtl; ML for physical design and design datasets and benchmarks are knowledge for now. Models come from Nirmaan's AI and ML department; IP owns the hardware data, tasks and judged evals |

## Silicon lifecycle

Units: none for test, product, reliability or safety engineering; security
rows sit in the security division. Planned placeholder in the record's chart:
Silicon Lifecycle (Post-silicon Validation, Production Test, Yield and
Reliability, Functional Safety). The record's DFT boundary: on-chip test
structures and pattern generation are Implementation; applying patterns to
silicon is here.

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Post-silicon validation and bring-up | K | diagnostics_software | software.validation (software side only) | No silicon. Widened: high-speed IP silicon validation and compliance test |
| Silicon debug infrastructure | K | jtag, debugging | none | Free path: debug-module RTL simulates |
| Production test | K | none | none | Needs ATE. Widened: system-level test, load boards, probe cards and sockets |
| Burn-in, qualification and screening | K | compliance | none | Needs parts and ovens. Includes AEC-Q100 |
| Yield and test analytics | K | none | none | No fab data; yield arithmetic is a rubric candidate. Includes semiconductor data analytics |
| Failure analysis | K | none | none | Reading reports helps diagnosis; doing it needs a lab |
| Reliability physics and design for reliability | K | power_analysis | implementation.pd.power.em | Includes reliability statistics |
| Soft errors, ECC and resilience | K | none | none | Includes radiation hardening by design and RAS features. Free path: ECC RTL with formal proofs |
| In-field test and lifecycle management | K | none | none | Widened: monitor analytics, prognostics and health management, unit traceability |
| Functional safety | K | compliance | quality.process.compliance | ISO 26262, IEC 61508, ISO/PAS 8800; the standards are paid; safety-mechanism RTL could be practised later |
| Avionics, space and harsh-environment assurance | K | none | none | Renamed and widened. Certification and beam tests are out of reach |
| Hardware security design | K | hardware_security, secure_boot, cryptography, security_architecture | security.hardware, security.secure_boot, security.crypto, security.architecture | Widened: device attestation (SPDM, Caliptra) and device life cycle and provisioning. Free path: cipher RTL against NIST known-answer vectors |
| Physical attacks and supply-chain threats | K | hardware_security, threat_modeling, security_verification | security.hardware, security.threats, security.verification | Lab evaluation needs hardware. Includes reverse engineering and counterfeits |
| Security assurance and certification | K | compliance, vulnerability_management, threat_modeling | security.vulnerabilities, security.platform, quality.process.compliance | Certification needs an accredited lab. Includes ISO 21434 |
| Analog, mixed-signal and high-speed I/O test and DFT (NEW, round 1) | K | none | none | Analog defect models and coverage, IEEE 2427, IEEE 1149.4, analog BIST, jitter and SerDes loopback test |

## Analog and mixed-signal

No catalog skill, unit, seat or eval covers this area. Planned placeholder in
the record's chart: Analog, RF and Photonics. One free tool image
(IIC-OSIC-TOOLS: Xschem, ngspice, Xyce, Magic, Netgen, OpenVAF and open PDKs)
would open most rows here and in RF and photonics.

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Analog circuit design fundamentals | K | none | none | Free tool: ngspice and Xschem with an open PDK |
| Circuit simulation and characterisation methods | K | none | none | Free tool: ngspice and CACE; periodic steady state needs Xyce |
| Data converters | K | none | none | Free path: Python behavioural models with FFT metrics; transistor level needs ngspice |
| Clocking and frequency synthesis | K | none | none | Free path: Python loop models and ngspice transient |
| Wireline and SerDes PHY | K | none | none | Controllers stay in Design. Free path: Python link models and scikit-rf |
| Power management ICs | K | none | none | Widened: digital control loops. Free tool: ngspice for LDO and converter checks |
| Board-level power electronics and wide-bandgap stages | O | none | none | Discrete power stages and magnetics are system products, not silicon IP; the on-chip parts are in Power management ICs |
| Battery management | K | none | none | Estimation algorithms are Python-checkable; no product need yet |
| Sensor interfaces, MEMS and biomedical front ends | K | none | none | MEMS devices need FEM and a process. Free tool: ngspice for readout circuits |
| Image sensors and display drivers | K | none | none | Pixel behaviour needs process data; only the readout chain simulates |
| Analog and custom layout | K | none | none | KLayout here checks digital cells only. Free tool: Magic, Netgen or klayout-pex |
| Mixed-signal integration and AMS verification | K | none | none | Free path: ngspice co-simulation with Verilator or Icarus, OpenVAF for Verilog-A |
| Analog design automation | K | none | none | Close to the AI-for-design business. Free tool: ALIGN, pygmid, CACE |

## RF and photonics

No catalog skill, unit, seat or eval. Planned placeholder: Analog, RF and
Photonics.

### RF and microwave

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| RF and microwave fundamentals | K | none | none | Free tool: scikit-rf and Qucs-S |
| RF transceiver IC design | K | none | none | Free tool: Xyce or Qucs-S with the IHP SG13G2 open SiGe PDK |
| EM simulation and passives | K | none | none | Free tool: openEMS, Palace, FastHenry2, FasterCap |
| mm-wave, THz, phased arrays and radar | K | none | none | Needs EM work plus measurement |
| Wireless systems, RF standards and regulation | K | none | none | Rubric only |
| RF measurement and test | K | none | none | Needs a lab and instruments |

### Photonics

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Integrated photonic devices | K | none | none | Free tool: Meep and mode solvers |
| Photonic layout, PDKs and design flow | K | none | none | The photonic row nearest to P: KLayout runs in CI. Free tool: SiEPIC-Tools, gdsfactory |
| Optical interconnect and transceivers | K | none | none | Driver and TIA electronics simulate in SPICE; the optics need a lab |

## Process and fab

No catalog skill or unit except the rule-deck work in physical signoff. Planned
placeholder: Technology and Packaging (Process and PDK use).

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Advanced devices and technology roadmaps | K | none | none | Reading and comparing technology data only |
| Compact models and device characterisation | K | none | none | Free tool: OpenVAF with ngspice and open PDK model cards |
| TCAD process and device simulation | K | none | none | No strong open process TCAD. Free tool: DEVSIM for devices |
| Process integration and unit processes | K | none | none | Needs a fab |
| Lithography, masks and OPC | K | none | none | No usable open OPC engine |
| DFM and yield-aware layout | K | physical_verification | implementation.pd.signoff.density | Near P: KLayout in CI runs density checks and could run DFM scripts; no DFM rule set here |
| PDKs and design-rule decks | P | physical_verification | implementation.pd.signoff | Narrow: KLayout DRC and LVS with the sky130hd decks in CI; device models, extraction and analog views are K |
| Specialty and compound processes | K | none | none | SiGe, SOI, BCD, GaN, SiC; discrete wide-bandgap devices are out of scope as a sub-topic |
| Fab operations, equipment, materials and metrology | O | none | none | A fabless IP company never runs a fab; what it needs from one sits in Yield and test analytics |
| DTCO and STCO, technology pathfinding (NEW, round 2) | K | none | none | Sets cell architecture, track height, metal stack and rules from block results. Free path: OpenROAD across open and predictive PDKs |

## Packaging and systems

No catalog skill or unit is about this area; the ids on two rows are
tangents. Planned placeholder: Technology and Packaging (Packaging, Board and
Systems).

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Package technologies and assembly | K | none | none | Package tools are paid; assembly needs an OSAT |
| Chiplets and die-to-die | K | none | none | Physical integration only; the adapter RTL would run on the simulators here but has no skill |
| 2.5D and 3D integration | K | none | none | Needs packaging PDKs and paid 3D tools. Widened: chip, package and board co-design |
| Thermal design and analysis | K | power_analysis | implementation.pd.power | Free tool: HotSpot or 3D-ICE on OpenROAD power numbers |
| Signal and power integrity | K | none | none | Free tool: scikit-rf, openEMS; IBIS parsing is scriptable |
| PCB design | K | none | none | Free tool: KiCad command-line ERC and DRC |
| EMC and product compliance | K | compliance | quality.process.compliance | Needs a chamber and an accredited lab. Includes RoHS and REACH |
| Board bring-up and hardware debug | K | jtag, debugging, diagnostics_software | software.validation | Needs boards; silicon bring-up is in Silicon lifecycle |
| Lab instruments and measurement automation | K | none | none | Free tool: PyVISA-sim for scripted instrument tests |
| Package and board reliability | K | none | none | Needs parts and test chambers |

## Emerging compute

Planned placeholder in the record's chart: Architecture Research (knowledge
only).

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Quantum computing hardware | K | none | none | Includes design automation for quantum. Free tool: KQCircuits or Qiskit Metal on KLayout |
| Cryogenic and superconducting electronics | K | none | none | Free tool: JoSIM |
| Neuromorphic computing | K | none | architecture.micro.npu (adjacent) | Free path: a digital spiking core runs on Verilator; Lava |
| In-memory and analog compute | K | none | architecture.micro.npu, design.rtl.design.memory (adjacent) | Free tool: NeuroSim or CrossSim |
| Optical and photonic compute | K | none | none | Algorithm-level simulation only; device work needs photonics tools |
| Other beyond-CMOS approaches | K | none | none | Research watch only: p-bits, spintronics, printed and flexible electronics, bio-CAD |

## Business

One level-1 area with five groups. Compliance-type rows are knowledge for
routing questions; they are not legal or tax advice, and every such question
goes to qualified advisers through the founder. Most units here are
placeholders with no engineer roles.

### Programme and tapeout

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Silicon programme management | K | program_management, project_management, risk_management | product.programs, product.projects | Rubric candidate on recorded facts |
| Release and deliverable management | P | release_management, release_quality, configuration_management | product.programs.release, quality.reviews.release, documentation.product.release_notes | `nirmaan export` builds a deterministic tree and checks the audit chain |
| Tapeout readiness and handoff | K | implementation_signoff | implementation, product.programs.release | A sky130 tapeout-package checklist is practisable from the CI flow; real submission is out of reach. Widened: community shuttle harnesses |
| Tapeout and NPI operations at the foundry | O | none | none | Needs a foundry account and a chip programme; reopen with a chip product |
| Engineering cost and capacity planning | K | business_operations | finance (placeholder) | Rubric candidate once engagement records exist |

### Foundry, OSAT, supply chain and die cost

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Foundry relations and technology selection | K | none | procurement (placeholder) | No foundry agreement; open PDKs show the shape of a PDK. Includes advice to customers on node choice |
| Foundry design enablement for IP vendors | K | ip_integration, implementation_signoff | design.integration.packaging, design.integration.kits, implementation.foundation | sky130 views can be checked by KLayout and OpenSTA today; foundry validation needs a foundry. Widened: test chips |
| OSAT and packaging operations | O | none | none | No parts to build; package technology is in Packaging and systems |
| Supply chain and capacity planning | O | none | operations, procurement (placeholders) | No product inventory; reopen with a chip product |
| Die and product cost modelling | P | none | none | Arithmetic only: die-per-wafer and yield models checked by a held-out script, every input a labelled assumption. Includes embodied carbon |
| Make vs buy and IP sourcing | K | ip_integration, competitive_analysis | product.management.competitive | Rubric candidate; it is also how buyers judge us |

### Applications and customer engineering

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Post-sale integration support | P | ip_integration, failure_triage, user_documentation, register_programming | design.integration.packaging, documentation.product, commercial.applications | A reference wrapper builds in Icarus or Verilator; an eval can reproduce a seeded integration bug |
| Field and pre-sales application engineering | K | requirements_engineering, competitive_analysis | product.management.customer, commercial.applications | Needs customers; the founder makes every contact |
| Application notes and technical collateral | K | technical_writing, user_documentation, specification_writing | documentation.product, documentation.specifications | A datasheet whose numbers trace to run records is tool-checkable; prose is rubric only |
| Customer support, errata and maintenance releases | K | failure_triage, root_cause_analysis, vulnerability_management, release_management | verification.debug, security.vulnerabilities, product.programs.release | Rubric candidate on seeded bugs. Includes end-of-life notices |
| Customer training delivery | K | technical_writing | documentation | On request only |
| Technical sales, business development and ecosystem partnerships | K | business_operations, competitive_analysis | commercial.sales | Widened: ecosystem partnerships. The founder contacts and signs |
| Customer success and account management | K | business_operations | commercial.customer_success | No customers yet |

### IP licensing and the IP business

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Customer evidence packs and IP qualification | P | release_quality, traceability, verification_signoff, ip_integration | quality.reviews, design.integration.packaging, design.integration.qualification, design.integration.kits | `nirmaan export` and `nirmaan audit` run; an eval can check that every claim maps to a run record |
| Licensing and commercial models | K | business_operations | finance; finance-licensing and legal-compliance seats | Terms are the founder's, with counsel |
| Pricing and engagement costing | K | business_operations | finance; finance-licensing seat | Rubric candidate for arithmetic and stated assumptions; nothing is published |
| Open-source programme: compliance, release and upstream contribution | K | compliance | quality.process.compliance; legal-compliance seat | Renamed and widened, including rights in training data for design AI. Free tool: reuse lint for SPDX and notices |
| IP protection | K | none | legal (placeholder) | |
| Contracts and engagement terms | K | none | legal-compliance and legal-counsel seats | Counsel reviews and the founder signs |
| Product management and marketing for IP | K | product_strategy, requirements_engineering, competitive_analysis | product.management, commercial.marketing | Rubric candidate: claims against evidence |
| Market research and competitive intelligence | K | competitive_analysis | product.management.competitive, commercial.marketing.research | Rubric candidate: every number sourced |
| India semiconductor programmes as channels | K | none | commercial.sales, commercial.marketing.research | Public facts only; any application is the founder's |

### Standards, export control and compliance

| Area | Status | Skill ids | Units | Notes |
|---|---|---|---|---|
| Standards bodies and specification access | K | none | legal-compliance seat | Membership would be new spending, a founder decision |
| Compliance and interoperability programmes | K | none | none | Logo programmes need membership and silicon |
| Export control and trade compliance | K | compliance | legal-compliance seat | Classifying a deliverable is counsel's call |
| Data protection and customer confidentiality | K | compliance, threat_modeling | security and legal-compliance seats | "No partner data in the repository" is scriptable |
| Tax and accounting for IP and services exports | K | none | tax-accounts seat | For a chartered accountant |
| Quality management systems and supplier certifications | K | compliance, engineering_audit, release_quality | quality.process | The standards are paid. Widened: customer quality and returns |
| General company functions | O | business_operations | finance, hr, procurement, operations (placeholders) | Finance, HR and procurement are not hardware capabilities; shared services with Nirmaan |

## Boundary with Nirmaan

Round 3 checked every capability each organisation might assume the other
holds. The rule stands: IP Nirmaan owns software whose correctness is defined
by its own RTL or register map; Nirmaan owns embedded applications on commodity
boards, ML on commodity GPUs, and model development; generic legal, finance and
tax are group services. Skills cross-link and never duplicate. Nothing is owned
by neither organisation except physical product engineering (enclosures,
industrial design, board assembly), which is out of scope for both because
neither sells a physical product. One note for the council: before any hosted
offer of an IP software product, name the operating owner.

## Job market (aggregate)

73 distinct job titles from 24 employers, read on 2026-10-30 from public career
pages and public aggregators: 4 EDA or IP vendors, 1 foundry, 10 large
semiconductor or systems companies, 6 startups and 3 India design or test
services firms. 47 of the 73 titles are in India. 11 listings were closed but
still show demand; 6 carried a title only. Each title was mapped to a role in
`build_organization()` or listed as having none. Employer names and listing
links stay in the private notes.

**Titles with no matching role**, by role family, and where each lands here:

| Role family | Titles | Map rows |
|---|---|---|
| Test, product and post-silicon engineering | 11 | Silicon lifecycle (validation, debug, production test, qualification, yield, reliability) and the analog test row |
| Applications and customer-facing engineering | 8 | Business: applications and customer engineering |
| IP business, finance and legal | 6 | Business: licensing, sourcing, export control; cost accounting and legal practice are general functions or outside the agent chart |
| Analog, layout, SI/PI and PDK | 6 | Analog and mixed-signal, Packaging and systems, Process and fab |
| Supply chain, foundry and tapeout operations | 5 | Business: programme and tapeout, foundry and supply chain |
| FPGA prototyping and emulation | 4 | Verification (prototyping, emulation) and FPGA |
| Processor and ISA verification | 2 | Verification: processor and ISA verification |
| Functional safety | 1 | Silicon lifecycle: functional safety |
| Virtual prototyping | 1 | Hardware software: pre-silicon software platforms |

**Top skills employers ask for that the catalog lacks**, by number of titles:
Tcl and Perl for EDA flows (13); post-silicon bring-up, validation and lab work
(11); customer-facing applications engineering (9); C++ (9); commercial EDA
flow fluency (8); analog design, analog layout and SPICE (6); production test,
ATE and characterisation (6); FPGA prototyping, emulation and vendor flows (5);
supply chain, foundry and tapeout operations (5); interface protocols outside
the catalog such as MIPI, UFS, I3C, SMBus, HBM, NVMe and Wi-Fi MAC (5). Every
item maps to a row above; none needed a new area at the top two levels. About
15 of the 73 titles map to a role whose only gap is a scripting or programming
language. What the catalog already covers well by the same listings: RTL design
with lint, CDC and synthesis awareness; UVM, constrained random, SVA and
coverage; AMBA, PCIe, DDR, USB and CXL; formal; programme management; scan,
ATPG and MBIST; firmware drivers.

## Proposals for the council (not decisions)

Everything in this section is a PROPOSAL from the research and gap-hunt rounds.
None is decided here, and this file changes no unit, role, seat or skill. Each
needs a council meeting or a later pull request of its own.

1. **Hardware security as a level-1 area.** Gather Hardware security design,
   Physical attacks and supply-chain threats, Security assurance and
   certification and Security verification, with Security architecture and
   Security IP moving or cross-linked. It spans three level-1 areas today, has
   its own division and seat, and matches the record's chart, where hardware
   security sits under VP Security rather than Silicon Lifecycle.
2. **Test and product engineering as a level-1 area.** Post-silicon validation
   and bring-up, silicon debug infrastructure, production test, burn-in and
   qualification, yield and test analytics, failure analysis, and the new
   analog and high-speed I/O test row. Reliability, soft errors, in-field
   management, functional safety and avionics stay in Silicon lifecycle. It is
   the largest job family with no role. The council would also set how this
   relates to the planned Silicon Lifecycle placeholder's departments.
3. **AI for chip design, possibly at level 1.** It is what the company sells.
   Option: fold AI-assisted verification and the AI side of analog design
   automation into it.
4. **Split RF and photonics** into two level-1 areas, RF and microwave and
   Photonics: different societies, tools, PDKs and job titles, cross-linked by
   optical interconnect and microwave photonics.
5. **Split Packaging and systems** into Packaging and heterogeneous integration
   (packages, chiplets, 2.5D and 3D, thermal, package reliability) and Boards,
   systems and lab (PCB, SI and PI, EMC, bring-up, lab automation).
6. **Name the missing Design rows in Appendix A** when the plan's next version
   is written: RTL building blocks and microarchitecture practice, and on-chip
   buses. They hold the catalog's strongest skills and all four RTL eval cases,
   yet Appendix A omits them. The same applies to the other rows the research
   added.
7. **Foundations as a prerequisite area**, held by no unit and cited by skills.
8. **One owner where two areas overlap:** register design and IP packaging
   (Design or Hardware software); SystemC and TLM (Hardware software, with
   Architecture cross-linking for performance models); chiplets by layer
   (Architecture partitions, Design builds the die-to-die RTL, Packaging
   integrates); AMS models (Analog owns models, Verification owns top-level
   checks); memory macros (the Implementation memory row); customer evidence
   packs (the placeholder design.integration.qualification is the natural
   holder); interface IP split into controller (Design) and PHY (Analog) at
   PIPE and DFI.
9. **Product-line tags** (record item 12) for skills when they are written:
   processor (ISA and CPU, processor verification), interface (on-chip buses,
   high-speed serial, memory interfaces, PHY and PCS), foundation (standard
   cells, memories and NVM macros, I/O cells, system and foundation digital
   IP), security (the hardware security rows), subsystems (SoC architecture,
   IP packaging and SoC integration).
10. **Areas for the planned placeholders** (record section 4), as each
    placeholder must declare the map area it holds: Domain IP holds video and
    image, audio and speech, wireless baseband and MAC, networking silicon;
    Architecture Research holds Emerging compute; Analog, RF and Photonics
    holds those two areas; Technology and Packaging holds Process and fab and
    Packaging and systems; Silicon Lifecycle holds the lifecycle rows (subject
    to proposals 1 and 2).
11. **Catalog gaps for later skill pull requests:** Tcl, Perl and C++ as
    skills; a "commercial flow equivalents" sub-topic per affected row rather
    than one skill per vendor; no skill yet for FPGA, VHDL, HLS, X-propagation,
    processor verification, standard cells, memory compilers, or any silicon
    lifecycle row other than security.
12. **Free tools that would move rows towards P** (a tool decision, no money):
    nextpnr, GHDL, Amaranth, cocotb, eqy, verilator_coverage, the RISC-V test
    suites, OpenOCD, QEMU or Renode, OpenRAM, the IIC-OSIC-TOOLS image, KiCad,
    and CoreMark on PicoRV32.
13. **Re-run the job pull** through the job-board connector when one is
    available; the rounds expect it to confirm rows, not add them.

## Open sources

Taxonomy and programme sources used for coverage, all openly readable:

- ISSCC 2026 topics of interest: https://www.isscc.org/topics-of-interest-26
- IEEE CAS technical committees: https://ieee-cas.org/society-involvement/technical-activities
- IEEE MTT-S technical committees: https://mtt.org/technical-committees/
- IEEE EMC Society technical committees: https://www.emcs.org/technical-committees/
- IEEE Photonics Conference topics: https://ieee-ipc.org/program/topics
- IEEE EPS Heterogeneous Integration Roadmap, 2024: https://eps.ieee.org/technology/heterogeneous-integration-roadmap/2024-edition/
- IRDS editions: https://irds.ieee.org/editions
- ITC 2026 call for papers: https://www.itctestweek.org/wp-content/uploads/2025/12/ITC_2026_CFP.pdf
- ICCAD 2026 call for papers: https://iccad.com/2026/call-for-papers
- DATE call for papers: https://www.date-conference.com/call-for-papers
- IEEE CEDA: https://ieee-ceda.org/about/about-ceda
- Accellera working groups: https://www.accellera.org/activities/working-groups
- RISC-V International technical committees: https://riscv.org/developers/technical-committees/
- CHIPS Alliance work groups: https://chipsalliance.org/workgroups/
- OpenTitan documentation: https://opentitan.org/book/
- arXiv category taxonomy: https://arxiv.org/category_taxonomy
- AICTE VLSI model curriculum: https://aicte.gov.in/sites/default/files/Revised%20Final%20VLSI_UG.pdf
- NPTEL Digital VLSI Testing: https://nptel.ac.in/courses/117105137
- Berkeley EECS 151: https://www2.eecs.berkeley.edu/Courses/EECS151
- India Semiconductor Mission, Design Linked Incentive: https://ism.gov.in/design-linked-incentive
- SIA and BCG semiconductor value chain report (2024): https://www.semiconductors.org/wp-content/uploads/2024/05/Report_Emerging-Resilience-in-the-Semiconductor-Supply-Chain.pdf

## Keeping the map current

The gap hunter runs again each quarter (plan phase P6). A pull request that
adds a skill, unit or eval for an area cites its row here; a row's status
changes only when the tool or eval behind it lands. Levels stay in
`capability/levels.json`.
