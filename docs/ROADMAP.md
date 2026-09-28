# IP Nirmaan roadmap

The plan for what comes after v1.18.0. Read this together with `context.md`
(what exists and why) and `CLAUDE.md` (how to work here). Each stage ships the
way every milestone has:
- a design doc approved before code,
- the implementation with a crown-jewel extension test,
- a `context.md` entry,
- a PR merged into `main`.

## Where we are (v1.18.0, 2026-09-28)

| Built | Not yet |
|---|---|
| Organization model: 207 units, 685 derived roles, skills, authority, a 12-principle constitution | A repair loop feeding lint and simulation logs back to the RTL seat |
| Planner: requirement to owned, reviewed, gated task graph; 8 workflows | FIFO, arbiter, and APB blocks; approved-inputs gating on the `new-ip` RTL stages |
| Task engine: lifecycle, reviews, approvals, human gates, hash-chained audit | `sta.run` (OpenSTA) is still `CONTRACT_ONLY`; formal and synthesis are not yet before-review checks |
| VeriTriage as a real, evidence-producing tool (`veritriage.investigate`) | Formal runs in CI (Ubuntu apt has no `sby`) |
| AI workers in three verification seats, off by default, on Opus 5.5 (M20) | The cross-domain engineering graph (Stage 5) |
| Design agents: spec, microarchitecture, and RTL seats; RTL gated on real lint and simulation; the AXI4-Lite register block end to end (M23) | Physical design, DFT, firmware (Stage 6) |
| `nirmaan export`: the numbered `01_requirement` to `10_signoff` deliverable tree (M23) | |
| Real lint, simulation, synthesis, and formal via open-source EDA (M21) | |
| IP Nirmaan over MCP; organizational events on the M18 bus (M22) | |
| CI on Python 3.11 and 3.12, plus a dash check (Stage 0) | |
| 984 tests; CLI `nirmaan`; HTML dashboard; landing page live at https://ip.nirmaan.online | |

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

Expect 984 passing. The folder is still in iCloud, so the eviction hangs
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

## Stage 5 (M24): The cross-domain engineering graph (spec Phase 8)

**Scope:**
- Link trace-graph artifacts to VeriTriage Design Graph nodes: an RTL artifact to its module, a test to the interface it covers.
- Requirement-to-coverage traceability: which requirement each coverage point proves.

**Done when:** "which requirements are not yet backed by passing verification evidence?" is a single query.

## Stage 6 (M25+): Physical design, DFT, firmware (spec Phase 7)

**Status (physical design part):** bindings built, not yet run against the real
tools. `sta.run` (OpenSTA) and `pnr.run` (OpenROAD: one staged run, floorplan,
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
- This is the largest stage. Scope it only after Stage 4 has proven that agent work holds up under review.

**Firmware status (M25, firmware part):** done on branch `m25/firmware`. Design: `docs/FIRMWARE.md`. `fw.build` (strict C11) and `fw.test` (the driver's own tests run against a Verilator model of the approved RTL, over real AXI4-Lite transactions) gate a firmware seat's driver before review; `test_the_firmware_seat_runs_its_driver_on_the_approved_rtl` runs it end to end on the AXI4-Lite block, locally and in CI.

## Side work (any time; owner-driven)

- **Landing page**: live at https://ip.nirmaan.online since 2026-09-28 (Vercel project `ip-nirmaan` in the Nirmaan team, deploys on every merge to `main`; DNS is a CNAME at Hostinger). See `site/README.md`.
- **Moving the repo out of iCloud** would remove the test hangs entirely. The owner has chosen to keep it in `~/Documents` for now.
- **The PyPI name** `ip-nirmaan`: publishing an initial release would reserve it. Needs the owner's explicit go-ahead.

## Principles that do not change

- VeriTriage stays standalone and never imports Nirmaan.
- The organization is data; routing never names a domain.
- Nothing is marked verified or approved without evidence the engine can substantiate.
- A human approves the gates marked human-required.
