# Milestone 6 (v0.6.0) - Waveform Intelligence Engine
The reserved `ArtifactType.WAVEFORM_METADATA` (idle since M2) finally has a
producer. New `waveform/` package with the load-bearing split the milestone
demanded: **adapters** are the only format-aware code (`adapters/base.py`
`WaveformAdapter` ABC + capabilities, `adapters/registry.py` `@register_adapter`,
`adapters/manifest.py` for a simulator-independent JSON manifest, `adapters/vcd.py`
for VCD via header parse plus a bounded counter-only activity scan that never
retains transitions), and the **observation engine** (`model.py` normalized
`WaveformMetadata`, `observations.py` deterministic `ObservationDetector`s,
`engine.py` `WaveformEngine`) is format-agnostic: it consumes only normalized
metadata and turns it into engineering observations (dead clock, stalled FSM,
incomplete handshake, unretired transaction, unexpected reset, repeated retries,
sequence-never-started). Observations carry full provenance (detector,
source_adapter, input_signals, deterministic observation_id) and a confidence
that propagates into evidence and hypotheses; each has an `ObservationCategory`.
`waveform/parser.py` `WaveformParser` is an ordinary registered `Parser` (so
`pipeline.analyze()` handles a `.vcd`/`.wave.json` with no pipeline change),
dispatching to the adapter and projecting observations into evidence nodes.
`waveform/inference.py` mirrors the M5 knowledge bridge exactly:
`waveform_reasoning_rules()` wraps each ranking-relevant observation kind as a
standard `ReasoningRule`, and `build_waveform_context()` assembles the
report-facing `WaveformContext`. Additive edits only: one correlation pass
(`_link_waveform_observations_to_failures`) in `graph/builder.py` (links an
observation to a failure sharing a scope segment, making M5 `suggested_signals`
actionable), an optional `waveform` field on `AnalysisReport` (schema `5` -> `6`),
`pipeline.py` composition, a report section, a `waveform` CLI command,
`models/waveform.py` report views. **Adapter capabilities** give honest
degradation: VCD declares no TRANSACTIONS/PROTOCOL_ANNOTATIONS, so those
detectors are reported unavailable rather than silently passing. Two permanent
architecture laws written into `docs/ARCHITECTURE.md` and pinned by tests:
core-format isolation and lossy-by-design ingestion. The crown-jewel test
`test_new_simulator_needs_only_an_adapter` registers a throwaway fake-format
adapter inside the test and proves it reaches evidence, reasoning, and the
report with zero core changes. 28 new tests (189 total, up from 161 actual at
the M5.1 head; note the M5.1 entry's "166" was optimistic, the real count was
161). Design doc: `docs/WAVEFORM_ENGINE.md`. User-approved refinements folded
in: observation provenance, categories, adapter capability declaration,
confidence propagation, and the two laws.
