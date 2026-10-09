# IP Nirmaan roadmap

The plan for what comes after v1.22.0. Read this together with `context.md`
(what exists and why) and `CLAUDE.md` (how to work here). Each stage ships the
way every milestone has:
- a design doc approved before code,
- the implementation with a crown-jewel extension test,
- a `context.md` entry,
- a PR merged into `main`.

## Where we are (v1.22.0, 2026-10-09)

| Built | Not yet |
|---|---|
| Organization model: 207 units, 685 derived roles, skills, authority, a 12-principle constitution | `sta.run` and `pnr.run` on the development machine (they run in CI only, M27; standalone OpenSTA and sky130hd run there too: M29) |
| Planner: requirement to owned, reviewed, gated task graph; 9 workflows | Multi-corner timing (no platform in the image ships a second corner), a signoff DRC/LVS deck, metal fill (power grid, CTS, and extracted parasitics into signoff STA: M29) |
| Task engine: lifecycle, reviews, approvals, human gates, hash-chained audit | Transition-fault ATPG, lockup latches across clock domains, a memory stage for MBIST (stuck-at ATPG, multiple chains, and March C- MBIST: M27); precise bus-error traps and interrupts in host co-simulation (RV32I on PicoRV32: M27; interrupts, SERV as a second core, a code-size gate, and APB: M29) |
| VeriTriage as a real, evidence-producing tool (`veritriage.investigate`) | Concurrent tasks and a project wide call budget in the unattended loop (one command drives owner, review, and repair to the human approval: M29) |
| AI workers in three verification seats, off by default, on Opus 5.5 (M20) | A real `sta.run` (not an attestation) on `timing-closure` `reanalysis`; antecedents of named properties and macros (the RTL gates on every RTL stage and automatic antecedent covers: M29) |
| Design agents: spec, microarchitecture, and RTL seats; RTL gated on real lint and simulation; the AXI4-Lite register block end to end (M23) | |
| `nirmaan export`: the numbered `01_requirement` to `10_signoff` deliverable tree (M23) | Verification plans: YAML or spreadsheet readers, non-Markdown requirement tags, several independent plans per project (checked plans on `new-ip` and `feature-addition`, and amending a recorded plan: M38) |
| Engineering graph: artifacts linked to Design Graph nodes from their real bytes; `nirmaan gaps` names every requirement not backed by a passing run (M24) | |
| DFT: real mux-D scan insertion, testability rules, and chain simulation through Yosys and Icarus (M25); multiple chains per clock domain, stuck-at ATPG graded by Icarus fault simulation, and March C- MBIST (M27); transition ATPG, lockup latches across clock domains, and an MBIST stage (M29) | |
| Firmware: a driver built strict and run against the approved RTL through a Verilator model (M25); on a RISC-V request, also cross-built for RV32I and run on PicoRV32 or SERV against the RTL, with interrupts, APB, and a code-size limit (M27, M29) | |
| Physical design: OpenSTA and OpenROAD bindings and a `physical-implementation` workflow (M25), run for real in CI on Nangate45: STA, and place and route to 0 DRC (M27) | |
| Real lint, simulation, synthesis, and formal via open-source EDA (M21) | |
| Synthesis (no latches) and formal (when the seat writes a `.sby`) before review; formal in CI via the OSS CAD Suite (M26) | |
| A bounded repair loop: failed before-review checks go back to the seat as evidence, opt-in per capability or `--attempts` (M26) | |
| Repair after review: a sent-back submission is superseded and the seat reruns with the findings; retry limits per stage and a budget across runs, with escalation when spent (M27) | |
| The design gates on every RTL workflow (`new-ip`, `feature-addition`, `rtl-change`), and proofs that must reach every cover (M27) | |
| A synchronous FIFO, a round-robin arbiter, and an APB register block, each with proofs and designed end to end by agents (M26) | |
| Seat evaluation: cases as data, judged by real tool runs including held-out reference testbenches; `nirmaan eval` (M27) | Formal proofs written by the seat; more cases |
| Tool contracts: every bound tool declares its parameters, and the broker refuses undeclared or ill-typed ones before running; `nirmaan org tool` (M28) | Typed values end to end; the typed work packet |
| Engineering records: decisions (alternatives, choice, rationale, evidence, consequences) and classified failures, as views; `nirmaan decisions` / `failures` (M29) | Recording explicit decisions from the CLI or MCP |
| The register map as data: validated, lowered (C header, spec table), and judging RTL through a generated co-simulation test; `nirmaan regmap` (M30) | Adopting the map in `block-design`; an APB harness; bit fields |
| Model selection by capability (`auto` runtime) and every model call recorded with tokens and cost; `nirmaan costs` (M31) | |
| Scalable state: an engine operation costs the same on a large project (0.25 ms at 5,000 runs, from 95 ms); state cannot be edited in place (M32) | An append-only store, if saves ever dominate |
| Learning proposals: failures recurring across projects propose skill changes, citing every record; a person adopts or rejects as a recorded decision; `nirmaan learn` (M33) | Proposals from evaluation results |
| First live evaluation: Claude Opus 5.5 passed all four RTL cases, judged by held-out checks, through a `claude-code` runtime on the owner's plan; it found that the RTL seat lacked the interface spec (fixed) | Formal proofs written by the seat; more cases |
| IP Nirmaan over MCP; organizational events on the M18 bus (M22) | |
| CI on Python 3.11 and 3.12, plus a dash check (Stage 0) | |
| 1430 tests; CLI `nirmaan`; HTML dashboard; landing page live at https://ip.nirmaan.online | |

## Resume checklist (after the folder rename)

The owner is renaming the working folder from `~/Documents/veritriage` to a new
name inside `~/Documents` and restarting the session. The editable install
records absolute paths, so rebuild the venv first:

```
cd ~/Documents/<new-folder-name>
rm -rf .venv && python3.11 -m venv .venv && .venv/bin/pip install -e ".[ai,dev]"
git remote -v                       # expect https://github.com/nirmaansoftware/ip-nirmaan.git
PYTHONPYCACHEPREFIX=/tmp/nirmaan-pycache .venv/bin/python -m pytest -q \
  --deselect tests/test_ai_boundary.py::test_missing_sdk_raises_clean_error
```

Expect 1430 passing (3 skipped: OpenROAD is not installed locally; the CI `physical-design` job runs those three). The folder is still in iCloud, so the eviction hangs
described in `context.md` section 4 still apply. If imports stall, pre-read the tree:

```
find src tests -flags +dataless -type f -print0 | xargs -0 cat > /dev/null
```

Then continue with **Stage 0** below.

---

## Stage 0: Continuous integration (DONE)

**Status:** done. `.github/workflows/ci.yml` runs the suite on Python 3.11 and
3.12, and `scripts/check_dashes.py` runs as a separate job. See `context.md`
section 2.

**Why:** every PR so far was verified only on one laptop with iCloud trouble.
CI makes "tests pass" a public, repeatable fact, which fits the project's own
"evidence or it did not happen" rule.

**Scope:**
- A GitHub Actions workflow running the full suite on Python 3.11 and 3.12 for every PR and push to `main`.
- An extra CI step that fails on em or en dashes in tracked text files.
- The README badge.

**Done when:** a PR shows a green check, and a deliberately broken test turns it red.

## Stage 1 (M20): The first AI workers, in verification seats (DONE)

**Status:** done on branch `m20/ai-workers`. Design: `docs/AI_WORKERS.md`
(the provider is exposed through the bridge). History: the M20 entry in
`context.md`. Try it: `nirmaan run <project> triage --runtime mock-llm
--input paths=<log>`.

**Why:** the organization plans and enforces, but nobody works. Verification is
the right first department because VeriTriage already produces real evidence
there, so agent output can be checked rather than trusted.

**Scope:**
- **A model-backed `AgentRuntime`** that goes through the M17 LLM provider registry (`veritriage.ai`), so one vendor registry still serves the whole platform. It stays off by default, and the null runtime remains the default seat.
  - Only the bridge module may import `veritriage`. Either expose the provider through `integrations/veritriage.py`, or give the runtime its own thin adapter. Decide this in the design doc.
  - Check the `claude-api` skill for current model IDs and API usage before writing it; do not work from memory.
- **Seat three roles:** failure triage (runs `veritriage.investigate`), root cause (reads the triage evidence and concludes one of the declared outcomes), and debug review (an independent reviewer, a different seat and model call).
- **Work packets become prompts.** Only the packet's four scopes (company, domain, project, task) are rendered, and every artifact must cite evidence IDs. Reuse M17's grounding enforcement idea: strip citations the packet did not contain.
- **A `nirmaan run PROJECT TASK --runtime <id>` command**, with a `--dry-run` that shows the exact prompt.
- **A deterministic `MockLLM` runtime for tests**, so the suite never calls an API.

**Done when:**
- Demo 4 ("Investigate a regression failure...") runs triage, root cause, and review with agents, on fixture logs, ending at a human approval.
- A test proves an agent citing a tool run that never happened is refused (P5), and that an agent cannot review its own output (P6).
- Nothing changes for users who never configure a model.

## Stage 2 (M21): Real design tools, through open-source EDA

**Status: done**, except the optional `sta.run` (OpenSTA), which stays
`CONTRACT_ONLY`. Design doc: `docs/EDA_TOOLS.md`. The "in CI" half of Done-when
depends on the Stage 0 workflow installing `verilator iverilog yosys` (apt)
and setting `NIRMAAN_REQUIRE_EDA`; locally all five bindings, formal included,
were exercised against the real tools.

**Why:** most evidence requirements (lint, simulation, formal, synthesis,
timing) can today only be met by a human attesting. Open-source EDA can make
them real without licenses.

**Scope:** broker bindings, each one moving a tool from `CONTRACT_ONLY` to `AVAILABLE`:

| Tool ID | Open-source backend |
|---|---|
| `lint.run` | Verilator `--lint-only` |
| `simulator.run` / `test.run` | Verilator or Icarus Verilog |
| `synth.run` | Yosys |
| `formal.run` | SymbiYosys |
| `sta.run` | OpenSTA (optional, later) |

Rules for each binding:
- It only works when its executable is found on `PATH`; otherwise the tool stays refused and says why.
- Its output is parsed into a structured result, and failures are recorded runs, never exceptions.
- Simulation logs feed straight into `veritriage.investigate`.

**Done when:** a tiny fixture RTL module (checked into `tests/fixtures/rtl/`) passes a real `lint.run` and `synth.run` in CI. Its evidence substantiates the RTL lint requirement with no human attestation. A crown-jewel test adds a fake tool binding with zero core changes.

## Stage 3 (M22): IP Nirmaan over MCP, and events

**Status: done (M22).** Design and decisions in `docs/NIRMAAN_MCP.md`; history in `context.md`.

**Scope:**
- A separate MCP tool table for Nirmaan (plan, status, why, task actions). It must not be added to VeriTriage's table, which would break the import law.
- Publish organizational events (task completed, gate approved, escalation raised) to the M18 event bus through the bridge, so VeriTriage automation rules can react.

**Done when:** Claude Code or Cursor can plan a project and ask "why is this blocked?" over MCP.

## Stage 4 (M23): Architecture and RTL agents (spec Phase 6)

**Status: done (M23).** Design: `docs/DESIGN_AGENTS.md`; history: the M23
entries in `context.md`. Approved-inputs-only seats, files in model answers as
artifacts with a digest, and RTL gated on real lint and simulation before
review. `test_the_axi4_lite_register_block_is_designed_by_agents` runs the
AXI4-Lite register block end to end against the fixture set in
`tests/fixtures/rtl/axi4_lite/`, locally and in CI.

**Why:** with real tools in place (Stage 2), design work can be verified, not just claimed.

**Scope:**
- Agents for interface specification, microarchitecture, and RTL implementation, each working from approved upstream artifacts only.
- RTL agents must pass real lint and simulation (Stage 2) before review.
- Start with small, self-contained blocks. The first IP is an AXI4-Lite register block (four 32-bit registers behind the five AXI4-Lite channels); a FIFO, a round-robin arbiter, and an APB register block follow as later blocks on the same workflow.

**Done when:** "Create an AXI4-Lite register block" produces an interface spec, a microarchitecture, RTL, a testbench, and a passing simulation, reviewed and approved through the engine, with every claim backed by a recorded tool run.

**Status:** the project deliverable export lands as part of M23: `nirmaan export PROJECT --out DIR` writes the numbered tree (`01_requirement/` to `10_signoff/`) from recorded state, never raising assurance, listing missing deliverables as missing, and flagging a broken audit chain. See `docs/DELIVERABLE_EXPORT.md`.

## Stage 5 (M24): The cross-domain engineering graph (spec Phase 8) (DONE)

**Status: done (M24).** Design: `docs/ENGINEERING_GRAPH.md`; history: the M24
entry in `context.md`. The single query is
`nirmaan.engineering.unbacked_requirements(state)`, also `nirmaan gaps PROJECT`
and `09_evidence/requirement_gaps.md` in the export.
`test_stage5_demo_on_the_axi4_lite_flow` shows it on the AXI4-Lite flow.

**Scope:**
- Link trace-graph artifacts to VeriTriage Design Graph nodes: an RTL artifact to its module, a test to the interface it covers.
- Requirement-to-coverage traceability: which requirement each coverage point proves.

**Done when:** "which requirements are not yet backed by passing verification evidence?" is a single query.

## Stage 6 (M25+): Physical design, DFT, firmware (spec Phase 7)

**Status: DFT, firmware, and physical design done and real** (physical design
runs in CI since M27). Details for each part follow.

**Physical design part:** bindings built in M25, run for real in CI since M27
(the `physical-design` job, in a pinned OpenROAD-flow-scripts image, on
Nangate45); on the development machine they refuse, since OpenROAD is not
installed there. What follows is the M25 state. `sta.run` (OpenSTA) and `pnr.run` (OpenROAD: one staged run, floorplan,
place, route, then timing) are `AVAILABLE` and refuse, with a reason, where the
executable or the PDK inputs are missing; neither tool is installed on the
development machine or in CI. `synth.run` gained a Liberty-mapped backend that
writes the netlist. The `physical-implementation` workflow plans constraints,
synthesis, floorplan, place and route, and STA signoff. Parser tests read
labelled synthetic samples. Next: run on a machine with OpenROAD and sky130,
replace the samples with captured logs, then CTS, power grid, and parasitic
extraction. Design doc: `docs/PHYSICAL_DESIGN.md`.

- OpenROAD bindings for floorplan, place, route, and timing.
- DFT and firmware agents.
- **DFT status (M25, done):** `dft.scan_insert` (Yosys: mux-D scan, one chain), `dft.check` (testability rules as a registry), and `dft.scan_sim` (Icarus: shift and capture through the chain) are real; the `block-design` workflow gains a `dft` stage gated on both checks before review. ATPG, multiple chains, and MBIST are deferred. See `docs/DFT.md`.
- This is the largest stage. Scope it only after Stage 4 has proven that agent work holds up under review.

**Firmware status (M25, firmware part):** done. Design: `docs/FIRMWARE.md`. `fw.build` (strict C11) and `fw.test` (the driver's own tests run against a Verilator model of the approved RTL, over real AXI4-Lite transactions) gate a firmware seat's driver before review; `test_the_firmware_seat_runs_its_driver_on_the_approved_rtl` runs it end to end on the AXI4-Lite block, locally and in CI.

## After Stage 6

- **Repair loop (M26):** a seat whose files fail their before-review checks is asked again, bounded by a capability's `max_attempts` (default 1, so off) or `nirmaan run --attempts N`, with the failed runs as citable evidence and log excerpts; refused attempts are recorded as `Attempt`s and never count. See `docs/REPAIR_LOOP.md`.
- **More blocks (M26):** a synchronous FIFO, a round-robin arbiter, and an APB4 register block (PSLVERR for unmapped addresses, as the AXI4-Lite block's SLVERR), each with real RTL, testbenches, and proofs, and each designed end to end by agents on `block-design` with no core change. See `docs/IP_BLOCKS.md`.
- **Formal gate (M26, done):** the `block-design` RTL stage goes to review only after real synthesis with no latches and, when the seat writes a `.sby`, a real SymbiYosys proof over the submitted RTL; CI installs `sby` and `yices-smt2` from a pinned OSS CAD Suite and runs formal instead of skipping it. See `docs/FORMAL_GATE.md`.
- **Repair after review (M27):** a submission a reviewer sends back is superseded into an `Attempt` (out of export, links, and approval), and the owner is run again with the review as a citable `[review:...]` record and the sent-back files; `max_attempts` and a new `max_review_rounds` are data on a capability or a workflow stage (CLI, then stage, then capability, then 1), counted from state across runs, and an exhausted budget escalates. See `docs/REVIEW_REPAIR.md`.
- **Real physical design runs (M27):** a `physical-design` CI job, in the pinned `openroad/orfs:26Q3-687-gc63a606f9` image, runs Nangate45-mapped synthesis, STA (through OpenROAD's embedded OpenSTA, a new `openroad-sta` backend), and place and route on the AXI4-Lite block for real: timing met at 100 MHz and violated at 5 GHz, routed with 0 DRC and 10783 um of wire. The first run's breakages are fixed, and the parser fixtures are captured logs, not synthetic ones. See `docs/PHYSICAL_DESIGN.md` sections 8 and 10.
- **Gates everywhere (M27, done):** the `new-ip`, `feature-addition`, and `rtl-change` RTL stages carry the `block-design` gates as data (approved inputs, now seen through gates; lint, simulation, synthesis with no latches, formal when a `.sby` is written), and a proof counts only if a cover run over the same setup reaches every cover (`formal.cover`); the fixture proofs carry real covers. See `docs/GATES_EVERYWHERE.md`.
- **DFT: ATPG, multiple chains, MBIST (M27):** `dft.scan_insert` takes `chains` and `max_chain_length` and cuts balanced chains per clock domain (`scan_in[k]` to `scan_out[k]`); `dft.atpg` generates stuck-at patterns (random, then PODEM) and measures coverage by an Icarus fault simulation through the scan protocol, refusing a pattern set whose claims or expected responses the simulation does not bear out; `dft.mbist` runs a generated March C- controller against a memory. The `block-design` `dft` stage now also needs 90% test coverage before review. See `docs/DFT_ADVANCED.md`.
- **RISC-V firmware (M27, done):** `fw.cross_build` compiles the driver and its tests strictly for bare-metal RV32I into an ELF with its code size, and `fw.soc_test` runs it on PicoRV32 (vendored, ISC) in one Verilator model with the approved RTL, so the driver's register accesses are CPU loads and stores on the real AXI4-Lite bus (SLVERR reaches the driver through a status register). A request that names RISC-V gates the firmware seat on both, through the new generic `EvidenceRequirement.when`; CI installs `gcc-riscv64-unknown-elf`. See `docs/RISCV_FIRMWARE.md`.
- **Verification plans (M29):** `nirmaan vplan import` and `export` load and save requirements and the items that prove them in a small versioned JSON format, all or nothing through the task engine, with line-level reasons; on a request for a plan, a `block-design` `dv-plan` seat writes one from the approved interface spec, a real `vplan.check` holds it to the spec's tagged requirements before review, and approval records it, so `nirmaan gaps` answers from the seat's plan. Neither ever makes anything backed. See `docs/VERIFICATION_PLAN.md`.

- **Verification plans, more (M38):** the `new-ip` and `feature-addition` `dv-plan` stages are checked plans: `vplan.check` holds the plan to the approved requirements spec before review and approval records it, so `nirmaan gaps` answers from it; a later plan version (a re-plan stage, or `nirmaan vplan import --amend`) adds, modifies, and retires requirements and items with a reason through the same check and approval, the superseded versions kept on the audit trail; an import may plan items whose files are not recorded yet. See `docs/VERIFICATION_PLAN_MORE.md`.
- **Learning proposals (M33, done):** a view over failure records proposes skill changes with full provenance; only a human decision, through the authority matrix, adopts one, and adopting edits no skill by itself. This completes the structural review's milestones. See `docs/LEARNING_PROPOSALS.md`.
- **Scalable state (M32, done):** P10 by construction (read-only containers) and identity, P11 verified once then per new entry; per-operation cost no longer grows with the project. See `docs/SCALABLE_STATE.md`.
- **Model selection and accounting (M31, done):** a seat's needs are derived from its work; `select_model` picks the cheapest profile that serves them or refuses with reasons; every model call is recorded by the engine with the provider's reported tokens and the profile's price, unknowns kept unknown. See `docs/MODEL_SELECTION.md`.
- **Register map as data (M30, done):** a `RegisterMap` is validated, lowered through a registry (a C header that compiles strict, and the spec's own table), and turned into a test that `regmap.verify` runs on the RTL through the AXI4-Lite co-simulation harness; the AXI4-Lite evaluation case uses it as a second held-out judge. See `docs/REGISTER_MAP.md`.
- **Engineering records (M29, done):** `nirmaan decisions` reads every decision task as a decision record (alternatives, choice, rationale, evidence, who and when, the branches it cancelled), and `nirmaan failures` classifies failed runs, refused or sent-back submissions, blocks, failures, and escalations with whether each was resolved, across projects too; both are in the export. Views only: nothing stored or inferred. See `docs/ENGINEERING_RECORDS.md`.
- **Tool contracts (M28, first part, done):** every tool with a binding declares its parameters (name, kind, required); the broker refuses an undeclared or ill-typed parameter, or a path containing a comma, before anything runs, and the runtime hands each tool only the inputs it declares. See `docs/TOOL_CONTRACTS.md`.
- **Seat evaluation (M27, done):** `evals/` cases fix a seat's upstream to reference documents and judge its work with held-out checks the seat never sees (the reference testbench on its RTL), each a recorded tool run; `nirmaan eval run (--runtime ID | --replay)`. See `docs/SEAT_EVALUATION.md`.
- **Unattended owner and reviewer loop (M29):** `nirmaan drive PROJECT [TASK] --runtime ID --reviewer-runtime ID` runs the owner seat (with its attempts), the independent reviewer seat, and the repair after a change request, until a person must act (an approval or a gate), a limit escalates, or the work is blocked or declined; it never approves or crosses a gate, decides each step from state (so it resumes by being run again), audits every step as `loop.step`, starts a step only if its worst case fits `--max-calls`, and prints the plan with `--dry-run`. With no TASK it drives every ready task in dependency order. See `docs/AUTO_LOOP.md`.
- **Gates on the rest, antecedent covers (M29):** every stage that produces RTL now carries `RTL_GATES` (adding `parameter-change` `rtl-change`, the `regression-investigation` and `timing-closure` `rtl-fix` stages, and `new-ip` `cdc-design`, whose capability now needs approved inputs and whose skill may run the gate tools); STA stays in `reanalysis`, not before review. The `formal.cover` run also derives a cover for every assertion's antecedent in a copy of the RTL (wrapping each procedural assertion so Yosys gives the cover its exact path condition), so an assertion that is never checked fails the proof; forms it cannot derive are refused with their line. See `docs/GATES_REST.md`.
- **DFT next steps (M29):** `dft.atpg_transition` generates slow-to-rise and slow-to-fall pattern pairs (launch on capture, over two time frames) and measures coverage by an Icarus fault simulation with a one-cycle delay at each site, active only in the at-speed cycle; `dft.scan_insert` takes `cross_domains=lockup` and puts a lockup latch on each clock crossing, which `dft.check` requires and `dft.scan_sim` proves with skewed clocks; stuck-at ATPG now covers designs that capture on both edges; a request for a block with memory plans an `mbist` stage that runs March C- on every memory of the approved RTL (including a declared, measured 2-cycle read latency) before review. See `docs/DFT_NEXT.md`.
- **RISC-V next (M29):** a design's `irq` output reaches the core (PicoRV32 `irq[3]`, SERV `i_timer_irq`, both entering at 0x10), with an interrupt API (`nirmaan_irq.h`) and an AXI4-Lite timer fixture whose tests prove the interrupt fires, is acknowledged by a register write, and stays silent when masked, and fail on broken IRQs; SERV 1.4.0 (vendored, ISC) runs the same SoC, firmware, and tests as PicoRV32, chosen by `core=` (`register_core`); an APB bridge chosen from the design's ports drives `apb_regs.v` from firmware; the gate limits code size with `max_text_bytes` 16384. Precise bus-error traps are not feasible on either core, so `STATUS` stays. See `docs/RISCV_NEXT.md`.
- **PD signoff (M29):** `pnr.run` adds tap and endcap cells, the PDK's power grid, repair after placement, clock-tree synthesis with repair, fillers, antenna, power-grid, and IR checks, and OpenRCX extraction to a SPEF, each enabled by its PDK input; signoff STA on that SPEF is workflow data (`max_unannotated_nets=0`), with a new `power-grid` stage; CI builds standalone OpenSTA and runs the full flow on Nangate45 and sky130hd (0 DRC, every supply pin connected, extracted slack reported). Multi-corner timing is not available: both platforms ship one corner. See `docs/PD_SIGNOFF.md`.

## Structural review milestones (from 2026-09-29)

The structural review (`docs/architecture/`) found the engine the brief asked
for already exists and ordered the real gaps. Seat evaluation (an M27 part) and
the first part of M28 (tool contracts) are done; the rest follow in this order,
each measured against the evaluation cases: M28 typed tool contracts and
work packet, M29 engineering records (decision records, artifact supersession,
failure categories), M30 a register-map IR checked against the RTL, M31
capability-based model selection with cost accounting, M32 scalable state,
M33 learning proposals through reviewed tasks. Details and reasons:
`docs/architecture/target-state.md` section 5.

## Side work (any time; owner-driven)

- **Landing page**: live at https://ip.nirmaan.online since 2026-09-28 (Vercel project `ip-nirmaan` in the Nirmaan team, deploys on every merge to `main`; DNS is a CNAME at Hostinger). See `site/README.md`.
- **Moving the repo out of iCloud** would remove the test hangs entirely. The owner has chosen to keep it in `~/Documents` for now.
- **The PyPI name** `ip-nirmaan`: publishing an initial release would reserve it. Needs the owner's explicit go-ahead.

## Principles that do not change

- VeriTriage stays standalone and never imports Nirmaan.
- The organization is data; routing never names a domain.
- Nothing is marked verified or approved without evidence the engine can substantiate.
- A human approves the gates marked human-required.
