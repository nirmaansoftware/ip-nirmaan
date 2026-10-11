# IP Nirmaan - Project Context

This file holds **current facts only**: what the system is, where every piece
lives, how to work on it, and the conventions. It lets work resume in a new
session without re-deriving decisions. How the project got here is in
**`docs/history/`**, one file per milestone, indexed by
`docs/history/README.md`; what comes next is in `docs/ROADMAP.md`.

Milestones do not append here (M43, `docs/STATUS_DOCS.md`): a milestone adds
its own `docs/history/MNN-<slug>.md`. Edit this file only when a current fact
changes, and keep it under 400 lines (a test enforces it). Counts (units,
workflows, tools, tests) are not written here; they are generated into the
"Counts" block of `docs/ROADMAP.md` by `scripts/status.py`.

Repo: https://github.com/nirmaansoftware/ip-nirmaan (public, Apache-2.0).
Earlier names `veritriage` and `nirmaan-ip`; transferred from `patel-om` to
`nirmaansoftware` on 2026-09-28. GitHub redirects the old URLs.
Current version: **1.23.0** (distribution `ip-nirmaan`; packages `nirmaan` and
`veritriage`; CLIs `nirmaan` and `veritriage`).
Landing page: https://ip.nirmaan.online (`site/`).

---

## 1. What the system is

IP Nirmaan is two packages in one distribution.

**Nirmaan** (`src/nirmaan/`, since M19) is an organizational operating system
for semiconductor IP work. A semiconductor company is declared as data (units,
derived roles, skills, capabilities, tools, workflows, gates, an authority
matrix, and a constitution). A requirement is analyzed against declared
vocabulary and planned into an owned, reviewed, gated task graph. A task
engine is the only way state changes: it enforces a lifecycle, the authority
matrix, and the constitution, and hash-chains every change into an audit
trail. The assurance ladder is PLANNED < EXECUTED < VERIFIED < APPROVED, and a
human approves the gates marked human-required.

Workers (people, scripted runtimes, or language-model seats) act only through
the engine, and tools act only through a broker that records real runs. Open
source EDA makes the checks real: lint, simulation, synthesis, formal (with
covers), DFT (scan, ATPG, MBIST), firmware (host co-simulation and RV32I on
PicoRV32 or SERV against the RTL), register maps, and physical design (OpenSTA,
OpenROAD, KLayout in CI). Seats are evaluated by cases whose judges are real
tool runs (`evals/`). Model calls are selected by capability and recorded with
tokens and cost.

**VeriTriage** (`src/veritriage/`, M1 to M18) is the verification-intelligence
engine inside it. Parsers turn logs, waveforms, and manifests into an Evidence
Graph; rules, Knowledge Packs, and a reasoning pipeline explain failures over
it, with lenses (waveform, engineering context, project model, design graph)
and platform layers (workspace services, MCP, orchestration, collaboration,
agents, learning, planning, conversation, AI providers, automation) above it.

**Design laws, enforced by tests:**
- VeriTriage never imports Nirmaan; inside Nirmaan only
  `integrations/veritriage.py` imports VeriTriage.
- The AI layer never reads raw artifact text and never originates a technical
  conclusion; providers render, they do not reason.
- The organization is data (`src/nirmaan/company/`); the orchestrator names no
  unit, skill, role, or protocol.
- Nothing claims a tool ran, or that work was verified or approved, without a
  record the engine can substantiate. New tools start as `CONTRACT_ONLY`.
- Every extension point is a registry, proven by a crown-jewel test that adds
  an extension with zero core changes.

---

## 2. Architecture map

### 2.1 Nirmaan (`src/nirmaan/`)

```
models/          Frozen pydantic vocabulary only (org, governance, workflow, work,
                 deliverable, evaluation, modelcall, regmap, frozen containers).
                 Imports nothing but pydantic (test-enforced).
company/         The company as data: org chart, skills, capabilities, tools (with
                 AVAILABLE / CONTRACT_ONLY status and typed parameter contracts),
                 workflows, governance (authority, escalation, gates, constitution),
                 vocabulary, deliverables, traceability, model profiles, learning
                 thresholds.
org/             Derived roles, validation, AuthorityService, escalation routing.
orchestrator/    analyze (requirement to analysis, or an honest "unrecognized"),
                 router (scored owners and reviewers), planner (task graph).
work/            TaskEngine (the only writer of state), policy (evidence
                 requirements and constitution checks), audit (hash chain), store
                 (JSON per project), blockers, management, trace, budget.
runtime/         AgentRuntime protocol and registry; run_task / review_task with
                 repair; ModelRuntime for every seat; the typed WorkPacket; prompts
                 with citation tokens; file blocks; ToolBroker with bindings and
                 probes; model selection; the claude-code runtime; the unattended
                 loop (`nirmaan drive`, concurrent and budgeted).
integrations/    veritriage.py (the only VeriTriage import site); EDA backends
                 registered through register_backend: eda (lint, sim, synth,
                 formal, covers and antecedents), physical (OpenSTA, OpenROAD,
                 KLayout), dft (scan, ATPG, MBIST), firmware (host and RISC-V SoC
                 harnesses, vendored cores), regmap, vplan. Parsers are pure.
evals/           Seat evaluation: cases as data, scorers, the runner.
mcp/             Nirmaan's own MCP tool table and stdio server (never VeriTriage's).
*.py views       engineering (requirement to evidence graph, `nirmaan gaps`),
                 export (numbered deliverable tree), events (audit-projected),
                 records (decisions and failures), regmap, vplan, costs,
                 proposals and eval_proposals (learning proposals), views,
                 dashboard, demos, cli.
```

The CLI (`nirmaan`) covers the organization (`org tree|stats|unit|role|skills|
skill|tools|tool|validate|export`), planning and work (`plan`, `task ...`,
`run`, `drive`, `budget`, `decide`), views (`status`, `why`, `gaps`,
`decisions`, `failures`, `costs`, `export`), evaluation (`eval list|run`),
learning (`learn`), register maps (`regmap check|lower`), and verification
plans (`vplan import|export`). `nirmaan --help` is authoritative.

### 2.2 VeriTriage (`src/veritriage/`)

```
models/          Shared pydantic vocabulary; never imports graph at runtime.
graph/           EvidenceGraph, content-hashed nodes and edges, GraphBuilder and
                 correlation passes, to_reasoning_view() (the AI boundary).
parsers/         Parser ABC and registry: simulation_log, compile_log, coverage,
                 test_metadata, formal_result.
rules/           Graph-native deterministic classification rules.
reasoning/       Selection, signals, hypotheses, recommendations, ai.py (legacy
                 AI review); no knowledge or history dependency.
knowledge/       Knowledge Pack schema, registry, built-in packs, matcher, engine.
waveform/        Format adapters (the only format-aware code) and detectors.
engineering/     Context providers (the only git call site), impact, ownership.
project/         The Project Model and its providers; never enters the graph.
design/          The Design Graph, derived from the Project Model, never source.
workspace/       WorkspaceServices: the public API every client uses.
mcp/             VeriTriage's MCP tool table and stdio server (`veritriage mcp`).
orchestrator/    Investigation steps and profiles.
collab/          Bundles, review, annotation, comparison.
agents/          Domain specialists and the Coordinator (a second opinion).
learning/        Learners over recorded history (a separate SQLite file).
planning/        DebugPlan from conclusions; never executes.
conversation/    Navigation over existing artifacts; AI-free.
ai/              LLMProvider registry, prompts, grounding, renderers.
automation/      Event bus, triggers, rules as data; decides, never executes.
history/, signatures/, similarity/, storage/, analytics/, feedback/, dashboard/,
reports/         Regression database, similarity search, analytics, HTML output.
cli/main.py      The `veritriage` CLI, a WorkspaceServices client.
pipeline.py      analyze(): parse, graph, classify, knowledge, reason. Pure.
```

Each package's design doc is in `docs/` (for example `docs/EVIDENCE_GRAPH.md`,
`docs/KNOWLEDGE_ENGINE.md`); the full pre-M43 map with call order and report
schema history is in `docs/history/context-before-M43.md`.

### 2.3 Other top-level folders

- `docs/`: one design doc per milestone; `docs/architecture/` holds the
  structural review (current state, target state, its tracker
  `REVIEW_PLAN.md`); `docs/history/` holds the milestone history.
- `evals/`: evaluation cases (`evals/README.md`).
- `site/`: the landing page; its numbers come from `site/stats.json`.
- `scripts/`: `check_dashes.py` (CI) and `status.py` (counts).
- `tests/`: the suite; `tests/fixtures/` holds logs, RTL blocks, PD and
  firmware fixtures. Real-tool tests skip when their executable is absent,
  unless it is named in `NIRMAAN_REQUIRE_EDA`.

---

## 3. Operational notes

**Where to work.** The owner's checkout is `~/Documents/IP Nirmaan`, synced by
iCloud. macOS evicts files to "dataless" placeholders, so imports can hang in
`importlib` and git can fail with `mmap failed`. Agents work in a fresh clone
outside iCloud (for example a scratchpad), push every commit early, and run
`git pull` before trusting a local `main`.

**Environment.**
```
python3.11 -m venv .venv && .venv/bin/pip install -e ".[ai,dev]"
```
EDA tools on macOS come from Homebrew (`verilator`, `icarus-verilog`, `yosys`,
`sby`, `yices2`, `riscv64-elf-gcc`). OpenROAD, OpenSTA, and KLayout are not
supported on macOS arm64 (M34): their tests run only in CI.

**Running tests.**
```
NIRMAAN_REQUIRE_EDA="verilator iverilog vvp yosys cc make sby yices-smt2 riscv64-elf-gcc" \
PYTHONPYCACHEPREFIX=/tmp/nirmaan-pycache .venv/bin/python -m pytest -q \
  --deselect tests/test_ai_boundary.py::test_missing_sdk_raises_clean_error
```
Expect everything to pass except 7 skips (the physical design tests). The
deselected test imports the `anthropic` SDK and can stall while iCloud
downloads it; run it separately when the venv is local. `python3
scripts/check_dashes.py` must also pass.

**CI** (`.github/workflows/ci.yml`), on every PR and push to `main`; actions
pinned by SHA, runners `ubuntu-24.04`, older PR runs cancelled (M46,
`docs/TEST_CI_HARDENING.md`):
- `test` on Python 3.12: apt Verilator, Icarus, Yosys; SymbiYosys and Yices
  from the pinned, cached OSS CAD Suite (`.github/actions/oss-cad-suite`);
  the RISC-V GCC; the full suite with the tools required.
- `no-tools` on Python 3.11: no EDA tool and no `anthropic`; the full suite,
  where every test passes or skips.
- `physical-design`: in a pinned OpenROAD-flow-scripts image, standalone
  OpenSTA (cached), the sky130hd corner libraries (pinned by sha256), and the
  physical design and STA tests on Nangate45 and sky130hd.
- `test-union`: fails if a test was skipped in every job.
- `dashes`: `scripts/check_dashes.py`.

**Counts.** `python scripts/status.py` prints the counts; `--check` fails on
drift; `--write` rewrites the roadmap block after adding a workflow, tool,
unit, skill, or principle; `--release` refreshes the test count,
`site/stats.json`, and the site at a version release.

**Releases.** Bump `pyproject.toml` and the version line above, run
`scripts/status.py --release`, add `docs/history/release-vX.Y.Z.md` and its
index line, and tag. No GitHub releases exist yet; v1.23.0 is tagged.

**Live models.** No Anthropic API credits are bought. The `claude-code` runtime
runs seats through `claude -p` on the owner's Claude plan; the default seat is
the null runtime, and the suite never calls a model (`MockLLM` and replay).
`nirmaan eval run --runtime claude-code` is the live path.

**Landing page.** Vercel project `ip-nirmaan` in the Nirmaan team, deployed on
every merge to `main`; DNS is a CNAME at Hostinger. `site/nirmaan.css`,
`site.js`, and `hero.js` are nirmaan.online's files copied unchanged: change
them in `nirmaansoftware/Nirmaan` first, never restyle them here. See
`site/README.md`.

**Standing offers, not executed.** Publishing to PyPI to reserve the
`ip-nirmaan` name needs the owner's explicit go-ahead. Moving the repo out of
iCloud would remove the hangs; the owner keeps it in `~/Documents` for now.

---

## 4. Conventions

- `CLAUDE.md` is the rulebook for agents; it wins over anything here.
- **No em or en dashes** anywhere (code, docs, comments, commit messages,
  generated report text). CI checks tracked files.
- **Milestones ship complete:** a number reserved in `docs/ROADMAP.md`
  ("Milestone numbers") before the branch is cut, a design doc in `docs/`,
  failing tests first, the code with a crown-jewel extension test, and a
  `docs/history/MNN-<slug>.md` entry with its index line. Never an entry
  appended here.
- **Branches and PRs.** Work on `mNN/<slug>`, open a PR, get CI green. Never
  amend or force-push. Commit messages end with the session's Co-Authored-By
  line.
- **Names.** The project is IP Nirmaan; the `nirmaan` package and CLI keep
  their short name; VeriTriage keeps its name as the verification engine
  inside. Do not suggest renaming without the owner raising it.
- **Status numbers** are generated, never typed: see `docs/STATUS_DOCS.md`.
