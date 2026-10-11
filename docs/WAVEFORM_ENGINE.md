# Waveform Intelligence Engine (Milestone 6)

Status: IMPLEMENTED in v0.6.0. This began as the design contract for M6 (reviewed
and approved before any Python was written) and is now the milestone's permanent
architecture doc, mirroring `REASONING_ENGINE.md`, `KNOWLEDGE_ENGINE.md`, and
`REGRESSION_INTELLIGENCE.md`. The design below matches what shipped; the ten
review refinements (provenance, categories, capabilities, the two laws, and so
on) are folded in throughout.

---

## 1. The one-sentence thesis

The Waveform Intelligence Engine does not read waveforms; it understands them.
It turns simulator-specific waveform artifacts into a small set of normalized
**engineering observations** ("handshake never completed", "clock stopped
toggling", "FSM stalled", "outstanding transaction never retired") that enter
the Evidence Graph as ordinary evidence, so every existing layer (correlation,
knowledge matching, reasoning, report, AI) consumes them without knowing a
waveform format ever existed.

## 2. Why this fits the platform without new architecture

`ArtifactType.WAVEFORM_METADATA` has been reserved since M2 with no producer.
M6 supplies that producer. Everything M6 needs is an existing, test-enforced
extension category:

| M6 need | Existing seam it uses |
| --- | --- |
| Ingest a waveform artifact | `Parser` ABC + `@register` (parser registry) |
| Emit observations as evidence | `Parser.emit_evidence()` -> `GraphFragment` |
| Link observations to failures | new correlation pass in `GraphBuilder.build()` |
| Influence hypothesis ranking | `ReasoningRule` subclasses, composed in `pipeline` |
| Appear in the report | additive `Optional` field on `AnalysisReport` |
| Support a new simulator later | new `WaveformAdapter` subclass only |

The knowledge engine (M5) proved this exact shape: a whole subsystem reached
reasoning as "just more rules" with zero reasoning-engine changes. M6 copies
that discipline.

## 3. The two-part split (the heart of the design)

The task's non-negotiable property is: *a future engineer adds a new simulator
by writing only a new adapter*. That is achievable only if reading a format and
understanding a waveform are different jobs in different modules.

```
  waveform artifact (.vcd, .fsdb, .wave.json, ...)
          |
          v
  [ WaveformAdapter ]   <- the ONLY format-aware code. One per format.
          |                 Produces normalized WaveformMetadata. Never
          |                 touches the Evidence Graph, reasoning, or AI.
          v
  WaveformMetadata      <- simulator-independent normalized model.
          |
          v
  [ WaveformEngine ]    <- format-AGNOSTIC. Runs ObservationDetectors over
          |                 WaveformMetadata to produce WaveformObservations.
          |                 Never imports an adapter, never reads a file,
          |                 never sees the string "vcd".
          v
  WaveformObservation[] -> EvidenceNode[] (artifact_type = WAVEFORM_METADATA)
          |
          v
     Evidence Graph  (correlation, knowledge, reasoning, report all follow)
```

**Adapters isolate simulator differences. The engine isolates verification
reasoning about waveforms. Neither knows the other's domain.** This is the
line that must never be crossed, and section 8 pins it with tests.

## 4. Normalized data model (`waveform/model.py`)

All fields are simulator-independent. An adapter's whole job is to fill this
in; different simulators, same model.

```python
class SignalRole(str, Enum):
    CLOCK, RESET, VALID, READY, REQ, ACK, STATE, DATA, OTHER

class WaveformSignal(BaseModel):
    name: str                      # leaf name, e.g. "arvalid"
    scope: str                     # hierarchical path, e.g. "tb.dut.axi_if"
    width: int = 1
    role: SignalRole = OTHER       # semantic tag (from manifest, or inferred)
    first_edge: int | None         # first transition time, None if never toggled
    last_edge: int | None          # last transition time
    toggle_count: int = 0          # number of transitions in the dump window
    is_constant: bool              # derived: toggle_count == 0
    metadata: dict[str, Any]

class HandshakeRef(BaseModel):     # a declared or inferred req/ack pair
    name: str
    initiator: str                 # signal name that requests (valid/req)
    responder: str                 # signal name that grants (ready/ack)

class TransactionRef(BaseModel):   # optional higher-level activity
    id: str
    kind: str                      # "read", "write", "snoop", ...
    start: int
    end: int | None                # None => never retired within the window
    retry_count: int = 0

class WaveformMetadata(BaseModel):
    source_path: str
    format: str                    # "manifest", "vcd", ... (provenance only)
    adapter: str                   # adapter name that produced this
    simulator: str | None
    timescale: str | None
    dump_start: int | None
    dump_end: int | None
    signals: list[WaveformSignal]
    handshakes: list[HandshakeRef]
    transactions: list[TransactionRef]
    capabilities: frozenset[WaveformCapability]   # what the adapter could resolve
```

Note what is deliberately absent: **there is no list of value changes.** We
keep counts, first/last edge times, and the dump window. We never retain the
transition stream. This is the "metadata not data" rule and it is also what
keeps the Evidence Graph small (see the Architecture Review, bottleneck 3.1):
the graph grows by tens of observations, not thousands of signals.

**Adapter invariant (refinement 1/7, now an architectural law):**

> An adapter may inspect raw waveform data, but it may only emit normalized
> metadata. Raw transitions are never retained, cached, or exposed outside the
> adapter. The contract is Raw -> Normalize -> Discard, never Raw -> Cache ->
> Normalize.

This is what stops a future contributor from quietly turning VeriTriage into a
waveform viewer.

## 5. The observation layer (`waveform/observations.py`, `waveform/engine.py`)

An `ObservationDetector` is a pure function of `WaveformMetadata` that yields
`WaveformObservation`s. This mirrors `ReasoningRule` and the graph correlation
passes: small, deterministic, independently testable, list-registered.

```python
class ObservationCategory(str, Enum):     # refinement 4: classify, don't just type
    ACTIVITY, TIMING, PROTOCOL, FSM, CLOCK, RESET, TRANSACTION, INTEGRITY

class ObservationKind(str, Enum):
    SIGNAL_NEVER_TOGGLED
    CLOCK_STOPPED
    HANDSHAKE_INCOMPLETE
    HANDSHAKE_COMPLETED         # positive evidence of progress
    FSM_STALLED
    TRANSACTION_NOT_RETIRED
    UNEXPECTED_RESET
    REPEATED_RETRIES
    PROTOCOL_SEQUENCE_INCOMPLETE

class WaveformObservation(BaseModel):
    # --- identity + provenance (refinements 3 and 5) ---
    observation_id: str        # deterministic content hash
    detector: str              # generation method: which detector produced it
    source_adapter: str        # adapter/format the input metadata came from
    input_signals: list[str]   # metadata objects this was derived from
    # --- content ---
    kind: ObservationKind
    category: ObservationCategory
    description: str           # engineering statement for the report
    severity: Severity        # maps into EvidenceNode.severity
    confidence: float         # propagated to evidence and hypotheses (refinement 9)
    scope: str | None         # for correlation to failing modules
    sim_time_start: int | None
    sim_time_end: int | None
    attributes: dict[str, Any]  # e.g. toggle_count, last_edge
```

**Provenance chain (refinements 3 and 5).** Every observation records *what
created it* (`detector`, `source_adapter`) and *what it was derived from*
(`input_signals`, plus the metadata values in `attributes`). When an
observation becomes an `EvidenceNode`, those provenance fields ride along in
`node.attributes` (`observation_id`, `detector`, `source_adapter`,
`waveform_kind`, `waveform_category`). The full trace is therefore machine
walkable end to end:

```
WaveformMetadata.signal  ->  WaveformObservation  ->  EvidenceNode  ->  ReasoningSignal  ->  Hypothesis
   (toggle_count=0)          (CLOCK_STOPPED, 0.98)     (conf 0.98)       (cited evidence)     (conf trace)
```

Each layer already knows "which object created me" without knowing the
previous layer's implementation: the node cites `observation_id`, the signal
cites `node.id`, the hypothesis's `ConfidenceTrace` cites the signal. Nothing
new is invented here; M6 just extends the citation discipline the reasoning
engine already has.

**Confidence propagation (refinement 9).** Each detector assigns a confidence
reflecting how unambiguous the metadata is: `CLOCK_STOPPED` from
`toggle_count == 0` is ~0.98 (a fact), `FSM_STALLED` from a heuristic on
last-edge timing is ~0.8. That confidence becomes `EvidenceNode.confidence`,
then `ReasoningSignal.confidence`, then flows into the hypothesis confidence
exactly like every other signal.

v1 detectors (each a few lines, each fixture-tested):

| Detector | Fires when | Severity |
| --- | --- | --- |
| `SignalNeverToggledDetector` | a VALID/READY/REQ/ACK/STATE signal has `toggle_count == 0` over a non-empty window | ERROR for clock, else WARNING |
| `ClockStoppedDetector` | a CLOCK signal's `last_edge` is well before `dump_end` | ERROR |
| `HandshakeDetector` | for each `HandshakeRef`: initiator toggled but responder never asserted -> INCOMPLETE; both progressed -> COMPLETED | ERROR / INFO |
| `FsmStalledDetector` | a STATE signal's `last_edge` far precedes `dump_end` while activity continued elsewhere | WARNING |
| `TransactionRetireDetector` | a `TransactionRef` with `end is None` inside the window | ERROR |
| `UnexpectedResetDetector` | a RESET signal has an edge after t=0 (asserted mid-run) | WARNING |
| `RepeatedRetriesDetector` | a `TransactionRef.retry_count` exceeds a fixed threshold | WARNING |

`WaveformEngine.observe(metadata) -> list[WaveformObservation]` runs the
detector list in deterministic order. The engine imports only `model`,
`observations`, and `Severity`. It has no adapter import and no file I/O. That
is asserted by a source-inspection test, exactly like the AI boundary is.

Detectors are the extension point for *smarter waveform understanding* later
(more observation kinds), independent of adapters (more formats). Two
orthogonal axes, neither coupled to the other.

## 6. Adapters (`waveform/adapters/`)

```python
class WaveformCapability(str, Enum):     # refinement 8: honest, not silent
    ACTIVITY               # per-signal toggle counts / first-last edge
    CLOCK_DETECTION
    RESET_DETECTION
    FSM
    TRANSACTIONS
    HIERARCHY
    PROTOCOL_ANNOTATIONS   # declared handshakes / protocol phase tags

class WaveformAdapter(ABC):
    name: ClassVar[str]
    format: ClassVar[str]
    file_patterns: ClassVar[tuple[str, ...]]
    capabilities: ClassVar[frozenset[WaveformCapability]]
    @classmethod
    def can_handle(cls, path: Path) -> bool: ...
    @abstractmethod
    def extract(self, path: Path) -> WaveformMetadata: ...
```

**Capability declaration and honest degradation (refinement 8).** Each adapter
declares what it can resolve. A detector requiring a capability the adapter did
not provide is *not run*, and the report says so explicitly ("Transaction
retirement analysis unavailable: the vcd adapter does not resolve
TRANSACTIONS") instead of silently reporting "no problem found." The v1
capability map:

| Capability | manifest | vcd |
| --- | --- | --- |
| ACTIVITY | yes | yes |
| CLOCK_DETECTION | yes | yes |
| RESET_DETECTION | yes | yes |
| FSM | yes | yes |
| HIERARCHY | yes | yes |
| TRANSACTIONS | yes | no (raw VCD has no transaction DB) |
| PROTOCOL_ANNOTATIONS | yes | no (raw VCD has no declared handshakes) |

So the VCD fixture demonstrates the capability system live: it reports rich
activity/clock/reset/FSM observations and honestly declares transaction and
protocol-handshake analysis unavailable. The manifest fixture, being the
canonical full-fidelity format, exercises every detector.

Registered via `@register_adapter` into `waveform/adapters/registry.py`
(`find_adapter(path)`, `available_adapters()`, `all_patterns()`), the same
registry shape as parsers and knowledge packs.

**v1 ships two adapters (per the approved scope):**

1. `manifest.py` (`format="manifest"`, `*.wave.json`, `waveform*.json`): the
   canonical, simulator-independent JSON metadata format. This is the
   reference contract every future exporter can target, and it makes fixtures
   trivial and fully deterministic. It reads the JSON straight into
   `WaveformMetadata`.

2. `vcd.py` (`format="vcd"`, `*.vcd`): parses the VCD **header** (`$timescale`,
   `$scope`, `$var`, `$enddefinitions`) for the signal list and structure, then
   does one bounded streaming pass over the value-change section that keeps
   **only per-signal counters** (toggle count, first edge, last edge) and the
   final timestamp. It never stores the transition stream, so memory is O(number
   of signals), not O(number of transitions). Roles are inferred from signal
   names (e.g. `*clk*` -> CLOCK, `*rst*`/`*reset*` -> RESET, `*valid` / `*ready`
   -> VALID/READY) with a conservative default of OTHER.

Future adapters (FSDB, FST, WLF, transaction DBs) are documented as "write one
class"; section 8's test proves nothing else has to change.

## 7. Integration points (exactly which existing files M6 touches, all additively)

M6 is a new subsystem plus a small, sanctioned set of additive edits to the
composition points every prior milestone also touched. No existing engine logic
is modified; passes and fields are *added*.

- `graph/model.py`: **no change** (`WAVEFORM_METADATA` already exists).
- `waveform/parser.py`: new `WaveformParser(Parser)`. Its `parse()` dispatches
  to `find_adapter(path).extract(path)` and stashes the `WaveformMetadata` in
  `ParseResult.metadata`; its `emit_evidence()` runs `WaveformEngine.observe()`
  and turns each observation into an `EvidenceNode` (deterministic
  `make_node_id`) plus intra-artifact edges. This is how waveform evidence
  enters the graph through the ordinary parser seam, so `pipeline.analyze()`
  handles a `.vcd` file with no pipeline change at all.
- `graph/builder.py`: **add** one correlation pass
  `_link_waveform_observations_to_failures` (observation scope matches a failing
  node's module -> `CORRELATES_WITH` edge) and call it in `build()`. This is the
  documented "new artifact types add new correlation passes here" extension.
  This is the payoff for M5: knowledge packs' `suggested_signals` (today just
  names) now resolve to real, linked waveform observations.
- `waveform/inference.py`: `waveform_reasoning_rules()` returning
  `WaveformObservationRule`s (one per observation kind, or one per observation),
  each a standard `ReasoningRule` that emits an evidence-cited `ReasoningSignal`
  with category weights (e.g. HANDSHAKE_INCOMPLETE and TRANSACTION_NOT_RETIRED
  lean rtl_bug; UNEXPECTED_RESET can lean testbench/infrastructure). Composed in
  `pipeline.py` beside `knowledge_reasoning_rules`. The reasoning engine keeps
  zero waveform dependency.
- `models/waveform.py`: new report-facing `WaveformContext` (+ observation
  views). Plain data, imports no graph/waveform package, obeys the
  "models below graph" rule. Exported from `models/__init__.py`.
- `models/report.py`: **add** `waveform: WaveformContext | None`; bump
  `schema_version` "5" -> "6".
- `pipeline.py`: import `veritriage.waveform` (side-effect registration of the
  parser + built-in adapters), build the `WaveformContext` from the graph's
  waveform nodes, and compose `waveform_reasoning_rules()` into the reasoning
  rule list. (Parsers must not depend on the waveform subsystem, so registration
  is triggered at the composition root, exactly as the pipeline already imports
  knowledge.)
- `reports/html.py` (+ template): **add** a "Waveform Intelligence" section
  (observations, linked signals, dump window). Additive, like the M5 knowledge
  section.
- `cli/main.py`: **add** a `waveform` command listing registered adapters and
  the formats they claim (mirrors `parsers` and `knowledge`). `analyze` needs no
  change; waveform files are just artifacts.
- `test_cli.py:35`: the schema-version assertion updates "5" -> "6" (expected on
  any schema bump; the test exists to force exactly this acknowledgement).

## 8. Tests and the executable proof of the success criterion

Unit tests:
- Each adapter: manifest round-trips a JSON fixture into `WaveformMetadata`;
  VCD header + activity scan produces correct counts / first / last edges on a
  small `.vcd` fixture.
- Each observation detector: a crafted `WaveformMetadata` produces exactly the
  expected observation (and does NOT fire when it should not).
- Correlation: a waveform observation in a failing scope produces a
  `CORRELATES_WITH` edge.
- Reasoning bridge: a waveform observation shifts ranking and appears in the
  winning hypothesis's `ConfidenceTrace` (same assertion style as the knowledge
  bridge test).
- Schema well-formedness: every `ObservationKind` maps to a detector; every
  detector cites the signals it fired on.

Architecture guards (the reason M6 is worth doing carefully):
- `test_waveform_engine_is_format_agnostic`: source of `engine.py` /
  `observations.py` / `model.py` contains no adapter import, no `read_text`, no
  `open(`, no format string like `"vcd"`.
- `test_reasoning_has_no_waveform_dependency`: extend the existing
  reasoning/rules import guard to also forbid `veritriage.waveform`.
- `test_waveform_never_depends_on_ai`: no `anthropic` / `AIReasoner` in the
  waveform package (same guard shape as knowledge).
- **`test_new_simulator_needs_only_an_adapter` (the crown jewel):** the test
  defines a throwaway `_FakeFstAdapter` for a fake `.fakewave` format *inside
  the test*, registers it, and runs the full `pipeline.analyze()` on a fake
  file. It asserts observations appear as evidence, reach the report, and
  influence reasoning, **without importing or editing any core module.** If a
  future change makes a new simulator require touching the graph, engine,
  reasoning, knowledge, regression, report, or AI layer, this test fails. It is
  the machine-checkable form of the milestone's success criterion.

Fixtures: `tests/fixtures/axi_handshake_stall.wave.json` (canonical manifest:
clock, reset, an AR valid/ready handshake where ready never asserts, an FSM
state signal that stalls, one non-retired read transaction) and a small
matching `tests/fixtures/axi_handshake_stall.vcd`. Extra per-detector manifest
fixtures as needed.

## 8b. Report schema lineage (refinement 2)

```
Report Schema
  v1  Logs
  v2  Evidence Graph
  v3  Reasoning
  v4  History
  v5  Knowledge
  v6  Waveform Intelligence   <- this milestone
```

## 8c. Two permanent architecture laws (refinements 7 and 10)

Both are written verbatim into `docs/ARCHITECTURE.md` and each is pinned by an
architecture test so a violation two years from now fails CI, not a review:

1. **Core-format isolation.** No component beyond a Waveform Adapter may
   reference a waveform format, parser, file extension, or simulator API. The
   Verification Intelligence Core operates exclusively on normalized metadata
   and evidence.

2. **Lossy-by-design ingestion.** An adapter normalizes and discards; it never
   caches or exposes raw transitions. Raw waveform data does not exist outside
   the adapter boundary.

## 8d. A note on naming room (refinements 5 and 6)

M6 does not introduce a separate "signal graph." Observations flow into the
existing Evidence Graph, which stays the single runtime source of truth. The
normalized model is deliberately entity-oriented rather than signal-only:
today it carries signals, handshakes, and transactions; the same shape leaves
room for FSM, assertion, coverage, and knowledge-pattern entities to become
first-class later without a rename. The Evidence Graph is the runtime graph;
the richer semantic "verification event" model, if it ever materializes, sits
underneath it and is a later milestone, not this one.

## 9. Determinism and philosophy check

- Every observation is a pure function of normalized metadata; same artifact,
  same observations, byte for byte. No AI anywhere in the waveform package.
- Observations are *engineering conclusions in evidence form*, not transitions.
  The report shows "handshake on tb.dut.axi_if never completed: arvalid
  asserted at 40ns, arready never observed", not a signal dump.
- The AI layer, if enabled, still only explains what the deterministic stack
  (now including waveform observations) already concluded. The AI boundary is
  unchanged: waveform observations are graph nodes, so they reach AI only
  through `to_reasoning_view()`, already pinned by `test_ai_boundary.py`.

## 10. Out of scope for M6 (deliberately)

- Full waveform rendering or a value viewer (this is a metadata engine).
- Numeric-threshold / performance observations that would need a new
  `EvidenceClause` variant (that is the matcher change `docs/history/context-before-M43.md` section 5.1 wants
  confirmed separately; M6 stays additive).
- FSDB/FST/WLF adapters (documented as the next adapters; the architecture test
  proves they need no core change).
- Inferring handshakes/transactions from raw VCD when the manifest does not
  declare them beyond the simple name-based role inference; richer inference is
  a later detector-layer improvement, orthogonal to adapters.

## 11. Deliverable checklist (on approval)

1. `waveform/` package: `model.py`, `engine.py`, `observations.py`,
   `parser.py`, `inference.py`, `adapters/{base,registry,manifest,vcd}.py`,
   `__init__.py`.
2. `models/waveform.py` + `models/__init__.py` export.
3. Additive edits: `graph/builder.py`, `models/report.py` (schema "6"),
   `pipeline.py`, `reports/html.py`, `cli/main.py`.
4. Tests + fixtures per section 8.
5. Docs: this file finalized, `README.md` roadmap tick, the M6 entry (now
   `docs/history/M06-waveform-engine.md`) + the architecture map update, light `ARCHITECTURE.md` pass.
6. Full suite green (target: current 161 plus the new M6 tests), no em/en
   dashes, then a single milestone commit.
