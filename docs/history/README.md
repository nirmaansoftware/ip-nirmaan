# Milestone history

One file per milestone, part, side work, and release, in milestone order. Until
M43 these were the entries of `context.md` section 2; they moved here verbatim
(only each heading went from `###` to `#`, and the `---` separators were
dropped). `context.md` now holds current facts only. See `docs/STATUS_DOCS.md`.

**Adding an entry.** A milestone adds its own `MNN-<slug>.md` here and one line
to this index, in milestone order. It does not append to `context.md`. Reserve
the number in `docs/ROADMAP.md` ("Milestone numbers") before cutting a branch.
Parts of one numbered batch take a letter after the number (`M27-c-...`), and
work between milestones is `MNN-side-<n>-...` after the milestone it followed.

The original preface of the section:

> The project was built "brick by brick" - each milestone is a complete,
> tested, documented, shippable increment. Do not skip ahead of the current
> milestone without the user asking.

## Entries

- [M01-traceiq](M01-traceiq.md): Milestone 1 (v0.1.0) - `f8f5698` - originally named TraceIQ
- [M02-evidence-graph](M02-evidence-graph.md): Milestone 2 (v0.2.0) - `1985e5f`
- [M03-reasoning-engine](M03-reasoning-engine.md): Milestone 3 (v0.3.0) - `47b1f57`
- [M04-regression-history](M04-regression-history.md): Milestone 4 (v0.4.0) - `675c8d0`
- [M05-a-knowledge-engine](M05-a-knowledge-engine.md): Milestone 5 (v0.5.0) - `8df1652` - architecture, initially thin content
- [M05-b-knowledge-base-breadth](M05-b-knowledge-base-breadth.md): Milestone 5 follow-up (v0.5.1) - `6d59aad` - knowledge base breadth
- [M06-waveform-engine](M06-waveform-engine.md): Milestone 6 (v0.6.0) - Waveform Intelligence Engine
- [M07-engineering-context](M07-engineering-context.md): Milestone 7 (v0.7.0) - Engineering Context Engine
- [M08-workspace-mcp](M08-workspace-mcp.md): Milestone 8 (v0.8.0) - Verification Workspace & MCP Platform
- [M09-investigation-orchestrator](M09-investigation-orchestrator.md): Milestone 9 (v0.9.0) - Investigation Orchestrator
- [M10-collaboration](M10-collaboration.md): Milestone 10 (v1.0.0) - Collaborative Investigation Platform
- [M10-side-1-knowledge-base-expansion](M10-side-1-knowledge-base-expansion.md): Knowledge Base Expansion program (post-1.0, content-only)
- [M10-side-2-clause-expressiveness](M10-side-2-clause-expressiveness.md): Clause expressiveness upgrade (v1.5.0) - the one sanctioned matcher change
- [M10-side-3-formal-result-ingestion](M10-side-3-formal-result-ingestion.md): Native formal-result ingestion (v1.6.0) - the last 5.1 knowledge item
- [M11-project-intelligence](M11-project-intelligence.md): Milestone 11 (v1.7.0) - Verification Project Intelligence (manifest-first)
- [M12-agent-framework](M12-agent-framework.md): Milestone 12 (v1.8.0) - Agent Framework and Coordinator
- [M13-learning-engine](M13-learning-engine.md): Milestone 13 (v1.9.0) - Learning Engine
- [M14-planning-engine](M14-planning-engine.md): Milestone 14 (v1.10.0) - Planning Engine
- [M15-design-intelligence](M15-design-intelligence.md): Milestone 15 (v1.11.0) - Design Intelligence
- [M16-conversation-engine](M16-conversation-engine.md): Milestone 16 (v1.12.0) - Conversation Engine
- [M17-generative-ai](M17-generative-ai.md): Milestone 17 (v1.13.0) - Generative AI providers
- [M18-automation-engine](M18-automation-engine.md): Milestone 18 (v1.14.0) - Automation Engine
- [M19-organizational-os](M19-organizational-os.md): Milestone 19 (v1.15.0) - IP Nirmaan: the Organizational Operating System
- [M19-side-1-landing-page](M19-side-1-landing-page.md): Landing page (side work, 2026-09-28) - `site/` for ip.nirmaan.online
- [M19-side-2-continuous-integration](M19-side-2-continuous-integration.md): Continuous integration (side work, Stage 0) - `.github/workflows/ci.yml`
- [M20-ai-workers](M20-ai-workers.md): Milestone 20 - AI workers in verification seats (roadmap Stage 1)
- [M21-real-eda](M21-real-eda.md): Milestone 21 - Real design tools through open-source EDA (roadmap Stage 2)
- [M22-nirmaan-mcp-events](M22-nirmaan-mcp-events.md): Milestone 22 - IP Nirmaan over MCP, and organizational events (roadmap Stage 3)
- [M23-a-axi4-lite-fixtures](M23-a-axi4-lite-fixtures.md): Milestone 23 fixtures - AXI4-Lite reference design (roadmap Stage 4)
- [M23-b-design-agents](M23-b-design-agents.md): Milestone 23 - Architecture and RTL agents (roadmap Stage 4)
- [M23-c-deliverable-export](M23-c-deliverable-export.md): Milestone 23 (part) - The project deliverable export (roadmap Stage 4)
- [M24-engineering-graph](M24-engineering-graph.md): Milestone 24 - The cross-domain engineering graph (roadmap Stage 5)
- [M25-a-physical-design](M25-a-physical-design.md): Milestone 25 (part) - Physical design through OpenSTA and OpenROAD (roadmap Stage 6)
- [M25-b-firmware](M25-b-firmware.md): Milestone 25 (firmware part) - A driver run on the approved RTL (roadmap Stage 6)
- [M25-c-dft](M25-c-dft.md): Milestone 25 (DFT part) - Design for test through Yosys and Icarus (roadmap Stage 6)
- [M26-a-repair-loop](M26-a-repair-loop.md): Milestone 26 - The repair loop (post-roadmap)
- [M26-b-ip-blocks](M26-b-ip-blocks.md): Milestone 26 (blocks) - FIFO, arbiter, and APB register block on the design flow (post-roadmap)
- [M26-c-formal-gate](M26-c-formal-gate.md): Milestone 26 (formal gate) - Synthesis and formal before review, formal in CI (after Stage 6)
- [M27-a-review-repair](M27-a-review-repair.md): Milestone 27 - Repair after review, and retry limits per stage (after Stage 6)
- [M27-b-physical-design-ci](M27-b-physical-design-ci.md): Milestone 27 (physical design) - OpenROAD and OpenSTA run for real in CI (after Stage 6)
- [M27-c-gates-everywhere](M27-c-gates-everywhere.md): Milestone 27 (gates everywhere) - The design gates on every RTL workflow, and non-vacuous proofs (after Stage 6)
- [M27-d-riscv-firmware](M27-d-riscv-firmware.md): Milestone 27 (RISC-V firmware) - the driver on a core against the RTL (after Stage 6)
- [M27-e-dft-advanced](M27-e-dft-advanced.md): Milestone 27 (DFT) - ATPG, multiple scan chains, and MBIST (after Stage 6)
- [release-v1.21.0](release-v1.21.0.md): v1.21.0 - the five M27 parts
- [M27-f-seat-evaluation](M27-f-seat-evaluation.md): Milestone 27 (seat evaluation) - Structural review, and seat evaluation
- [M28-tool-contracts](M28-tool-contracts.md): Milestone 28 - Tool contracts (structural review, milestone 2)
- [M29-a-verification-plan](M29-a-verification-plan.md): Milestone 29 (verification plan) - Plans loaded from a file, and a plan seat (after Stage 6)
- [M29-b-auto-loop](M29-b-auto-loop.md): Milestone 29 - An unattended owner and reviewer loop in one command (after Stage 6)
- [M29-c-engineering-records](M29-c-engineering-records.md): Milestone 29 (engineering records) - Decisions and failures, as views (structural review, milestone 3)
- [M29-d-gates-rest](M29-d-gates-rest.md): Milestone 29 (gates) - The RTL gates on the remaining workflows, and automatic antecedent covers (after Stage 6)
- [M29-e-dft-next](M29-e-dft-next.md): Milestone 29 (DFT) - Transition ATPG, lockup latches, and an MBIST stage (after Stage 6)
- [M29-f-riscv-next](M29-f-riscv-next.md): Milestone 29 (RISC-V) - interrupts, a second core, a code-size gate, and APB (after Stage 6)
- [M29-g-pd-signoff](M29-g-pd-signoff.md): Milestone 29 (PD signoff) - Power grid, CTS, extraction, and signoff STA on the SPEF (after Stage 6)
- [M30-register-map](M30-register-map.md): Milestone 30 - The register map as data
- [M31-model-selection](M31-model-selection.md): Milestone 31 - Model selection by capability, and every model call counted
- [M32-scalable-state](M32-scalable-state.md): Milestone 32 - Scalable state: hidden edits impossible, chains verified once
- [M33-learning-proposals](M33-learning-proposals.md): Milestone 33 - Learning proposals: recurring failures propose, a person decides
- [M33-side-claude-code-live-eval](M33-side-claude-code-live-eval.md): Claude Code runtime, and the first live evaluation (after v1.22.0)
- [release-v1.22.0](release-v1.22.0.md): v1.22.0 - the structural review and the M29 parts
- [M34-pd-final](M34-pd-final.md): Milestone 34 - Multi-corner timing, KLayout DRC and LVS, and metal fill (after Stage 6)
- [M35-firmware-irq-traps](M35-firmware-irq-traps.md): Milestone 35 - Interrupts in host co-simulation, and precise bus-error traps (after Stage 6)
- [M36-loop-concurrency](M36-loop-concurrency.md): Milestone 36 - Concurrent tasks and a project wide call budget in the unattended loop (after Stage 6)
- [M37-sta-and-antecedents](M37-sta-and-antecedents.md): Milestone 37 - Real STA on timing re-analysis, and antecedents of named properties and macros (after Stage 6)
- [M38-verification-plan-more](M38-verification-plan-more.md): Milestone 38 - Checked plans on `new-ip` and `feature-addition`, and amending a recorded plan (after Stage 6)
- [M39-typed-values](M39-typed-values.md): Milestone 39 - Typed values end to end, and the typed work packet (after Stage 6)
- [M40-decisions-cli-mcp](M40-decisions-cli-mcp.md): Milestone 40 - Recording explicit decisions from the CLI and over MCP (after Stage 6)
- [M41-register-map-adoption](M41-register-map-adoption.md): Milestone 41 - The register map in `block-design`, bit fields, and an APB host harness (after Stage 6)
- [M42-eval-proposals](M42-eval-proposals.md): Milestone 42 - Learning proposals from evaluation results (after Stage 6)
- [release-v1.23.0](release-v1.23.0.md): v1.23.0 (2026-10-11) - the M34 to M42 batch
- [M43-status-docs](M43-status-docs.md): Milestone 43 - Status documents that stop colliding and stop drifting
- [M45-live-eval-evidence](M45-live-eval-evidence.md): Milestone 45 - Live evaluation as recorded, repeatable evidence
- [M47-review-cleanups](M47-review-cleanups.md): Milestone 47 - Small cleanups found by the principal-engineer review

## Before M43

- [context-before-M43](context-before-M43.md): the old `context.md` sections 1, 3, 4, and 5 (the VeriTriage description, the architecture map, operational notes, and VeriTriage-era future work), verbatim
