# Platform Completion (Milestone 19)

The milestone with no new subsystem. Every previous one added a layer;
this one closes the four items `context.md` section 5 had been carrying as
"designed, not built", and fixes a performance bug that had been hiding
behind them.

Four small pieces, one theme: **things the platform already knew but had
never been asked.**

---

## 1. The last two open interconnects

`knowledge/packs/ocp.py` and `knowledge/packs/wishbone.py`.

Nothing outside `knowledge/packs/` changed, which is the entire claim the
Knowledge Pack seam has been making since M5. Both packs are ordinary data:
concepts, a transfer state machine, failure patterns with playbooks and
specification references.

**OCP** (Accellera 3.0) covers the four things that are never optional in a
protocol where nearly everything else is configurable:

| Pattern | What it catches |
| --- | --- |
| `ocp.request-not-accepted` | MCmd presented, SCmdAccept never raised |
| `ocp.response-error` | SResp of ERR or FAIL consumed as valid data |
| `ocp.burst-length-mismatch` | precise burst delivering a length it did not declare |
| `ocp.thread-ordering-violation` | out-of-order response inside one MThreadID |

**Wishbone** (B4) covers the consequences of its single framing rule, that a
slave ends every phase with exactly one of ACK, ERR or RTY:

| Pattern | What it catches |
| --- | --- |
| `wishbone.no-termination` | phase strobed, no termination signal ever asserted |
| `wishbone.err-ignored` | ERR consumed as data |
| `wishbone.rty-livelock` | busy bus making no forward progress |
| `wishbone.cyc-stb-violation` | STB outside an open CYC, or CYC withdrawn mid-phase |

Eight fixtures, one per pattern, because a pattern that only validates
against the schema has not been shown to fire on anything.

**44 packs, 100 patterns.** No protocol on the original M5 list is missing.

---

## 2. The learning feedback loop

M4 shipped `FeedbackRecord` with `diagnosis`, `actual_root_cause`,
`useful_recommendations` and `false_recommendations`, and deliberately built
no reader. M13 built the readers for the votes and stopped short of acting on
them, saying in as many words that whether a recommendation is surfaced is
"a presentation decision made later". This is that decision, plus the reader
for the verdicts.

### Rule gaps

`learning/learners/gaps.py`. Groups failures by signature digest, counts
engineer overrules, and speaks only after **two judgments and two
overrules**, because one overrule is an anecdote.

What it deliberately does not do: propose a rule, edit a pack, or adjust any
confidence. A gap is an argument for human attention. Turning one into a
pattern is design work, not arithmetic.

Surfaced in the dashboard as **Needs a New Rule**, computed there straight
from history through the same free function the learner uses, so the
dashboard still needs no learning store.

### Recommendation reweighting

`feedback/reweight.py`. Votes become a weight table; the table reorders the
advice a run produced. Three properties make this safe to apply to a
deterministic platform:

* **Reorder only.** No action is added, removed, reworded or
  re-rationalized.
* **Deterministic.** A stable sort on (learned usefulness, original
  priority). Ties and unrated actions keep their order, so the deterministic
  ranking stays the backbone and feedback only perturbs it.
* **Inert without history.** An empty table returns the input list
  unchanged, so a platform with no learning store behaves exactly as it did
  before this module existed.

Applied in the pipeline only when a learning context was recalled.

### The guarantee

Advice may move. The Evidence Graph, the classification, the reasoning
signals and the ranked hypotheses may not. `test_feedback.py` asserts this
directly rather than trusting the layering.

---

## 3. Reference resolution

`references/`. `Reference.uri` had been a hook since M5 with nothing behind
it.

The two things that would use it pull in opposite directions. A company wants
its internal spec database to answer, and that adapter cannot ship here: it
is site-specific and usually behind authentication. The public standards have
stable landing pages, but fetching them during an analysis would put a
network call in the middle of a deterministic pipeline, which this platform
does nowhere else.

A registry settles both:

```python
@register_resolver
class AcmeSpecDatabase(ReferenceResolver):
    resolver_id = "acme-specs"
    priority = 10          # above the public catalogue

    def resolve(self, reference: Reference) -> str | None:
        return MIRROR.get(reference.source)
```

The built-in resolver is a static offline catalogue of public standards
(AMBA, RISC-V, PCIe, CXL, UCIe, USB, JEDEC, MIPI, IEEE, Accellera,
OpenCores), so resolution stays a pure function. A test parses every module
in the package and fails if it ever imports `urllib`, `requests`, `httpx`,
`socket` or `subprocess`.

Matching is on the longest matching source fragment, so "AMBA AXI-Stream"
does not resolve through the shorter "AMBA AXI" entry. Resolution happens at
the report boundary and returns copies, because packs are process-wide
constants shared by every analysis. A reference that already carries a URI
keeps it.

---

## 4. Cross-regression diffing

`engineering/regression_diff.py`. The first question a verification engineer
asks, and the one the platform could not answer: **it worked yesterday, what
landed since?**

Both halves existed and had never been introduced. The regression database
has recorded `execution.git_commit` for every run since v0.4.0. The M7
provider seam can list normalized commits. This is the join, and it stays
behind the seam, so a Perforce or Gerrit shop gets the same analysis by
registering a provider.

New `ContextCapability.CHANGE_RANGE` and an optional `changes_between()` on
`ContextProvider`, defaulting to `None` so every existing provider keeps
working untouched. The manifest provider explicitly stopped claiming every
capability: a static export carries recorded context but cannot answer a live
range query, and a provider must not declare what it cannot do.

### The honesty rule that drove the design

| Situation | Answer |
| --- | --- |
| No green run recorded, or a run with no commit | `None` |
| No provider that can resolve a range | `None` |
| Commits unknown to this checkout (shallow clone, pruned branch) | `None` |
| Both runs built from the same code | `RegressionDiff` with `commits == []` |

The last row is a real and useful answer: nothing changed, so look at the
environment rather than the RTL. It must not look like a failure. Keeping the
two distinguishable required a raw git runner, because the existing
`_run_git` collapses "succeeded with no output" into `None`.

Commits touching a module the failure signature implicates are flagged
`suspect_commits`. A name overlap and nothing cleverer: it narrows where to
look, it does not claim to have found the bug. Lossy by design still holds,
with a test asserting no patch text crosses the provider boundary.

Reachable as `WorkspaceServices.changes_since_last_green()`.

---

## 5. The bug this milestone found

There is one reasoning rule per failure pattern, and every rule called
`match_patterns` itself and then filtered for its own row. One analysis
therefore ran a full pass over every pattern, every clause and every node
**once per pattern**: roughly 100 passes to use one row of each.

Quadratic in pattern count, and invisible for eighteen milestones because the
library grew slowly. Eight new patterns made the test suite time jump from 49
seconds to over three minutes, which is how it surfaced.

Rules built together now share one match pass, memoized on the Evidence Graph
by **weak reference and compared by identity**, so the cache can neither
serve a stale result nor keep a graph alive after the run that produced it. A
rule constructed on its own still gets its own pass, so the old construction
path is unchanged.

```
analyze() x10    0.863s  ->  0.095s     (about 9x)
full test suite   48.9s  ->   23.5s     (while gaining 65 tests)
```

`test_pattern_rules_share_a_single_match_pass` fails if the passes come back.

---

## What this milestone did not do

* **No learned models.** Both feedback readers are deterministic
  aggregations. The M4 non-goal (no retraining, no embedding fine-tuning)
  did not move.
* **No network in the pipeline.** Reference resolution is an offline
  catalogue, guarded by a test.
* **No new registry pattern.** The resolver registry is the same shape as
  the pack, learner, parser, adapter, provider, step, agent, handler and
  trigger registries already in the platform.
* **No PyPI release.** Still a standing offer requiring explicit
  confirmation.
