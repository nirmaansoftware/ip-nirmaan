---
id: verification/verification_planning
skill: verification_planning
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
  - open | lowRISC, OpenTitan DVSIM testplanner tool (Apache 2.0) [OTPlan] | https://opentitan.org/book/util/dvsim/doc/testplanner.html
  - open | lowRISC, OpenTitan Hardware Development Stages (Apache 2.0) [OTStage] | https://opentitan.org/book/doc/project_governance/development_stages.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K4 session (wave 2 knowledge batch, plan row W2-K4, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the plan check tool this skill holds is available; this document is knowledge, not evidence.

# Verification planning

Turning a specification into a list of what will be verified and how, and what
this repository's plan check does and does not test. Tags in brackets name the
sources above; a line marked "inference" is this document's own reasoning; a
line marked "gate" names the repository code that backs it.

## What a plan is for

- OpenTitan keeps two things per block. A testplan lists the tests planned to
  verify every feature in the design specification, and a functional coverage
  plan lists the cover points and crosses that show those tests reached the
  features [OTDV].
- The testplan is machine-readable (Hjson), so that it can be inserted into the
  block's DV document as a table and used to annotate regression results with
  progress against the plan [OTDV].
- The plan is written before the testbench is finished. OpenTitan's first
  verification stage ends once the environment can run tests and a testplan and
  a functional coverage plan exist [OTStage].
- The plan is a statement of intent. It does not show that anything passed
  (inference; this repository's tool says the same, see below).

## How the plan is built

- One entry per design feature, named for the feature, not for the test: the
  OpenTitan testplanner maps each planned test to exactly one feature of the
  design [OTPlan].
- An entry's description may state its goal, stimulus and check; the page
  calls these recommended, but not always necessary [OTPlan]. Each entry also
  has the list of written tests that satisfy it. The list starts empty and fills as
  tests are written; one written test may serve several entries, and one entry
  may need several tests [OTPlan].
- Also plan the focus areas that apply to most blocks: a smoke test, register
  access tests, and tests for illegal and error stimulus, performance
  requirements, security and stress [OTDV]. Which apply to a given block is
  decided in review (inference).
- Entries carry a target stage and may carry tags for the conditions a test
  must also run under, for example gate level or power aware runs [OTPlan].
- Covergroups are planned separately, by name and description, and the name
  must match the written covergroup so results can be audited against the plan
  [OTPlan].
- Planned test names must be unique across the plan and everything it imports
  [OTPlan].
- OpenTitan reviews the testplan with the designer, DV peers, leads, the people
  who integrate the block, software and the architect, so that gaps in the
  specification and in the plan are found early [OTDV].

## The plan file's format

The tool description for `vplan.check` says only "the verification plan file
or files" (gate: src/nirmaan/company/tools.py:160-164), so the format is
written here. The reader is src/nirmaan/vplan.py; every line below is what it
accepts or refuses.

- The file is one JSON object, parsed as JSON whatever the file's extension:
  the reader takes the file's text and decodes JSON, and a decode error is
  reported with its line (gate: src/nirmaan/vplan.py:174-181, 394). A
  YAML file fails here unless it is also valid JSON (inference from the
  reader). Two committed records show the refusal: both seats wrote YAML and
  the first `vplan.check` said the file did not parse (records
  2026-11-18-claude-code-claude-opus-5-5-30 and -44, causes.md).
- The object has `format`, `version` and `requirements`, and may have `items`
  and `retired`. `format` is exactly the string `nirmaan.vplan` and `version`
  is exactly the number 1 (gate: src/nirmaan/vplan.py:41-42, 182-187). The
  value `vplan` for `format` was refused in record
  2026-11-18-claude-code-claude-opus-5-5-30.
- Any field the format does not name is refused. This covers a plan-level
  `plan` or `description` key as well as the result words (`status`, `passed`,
  `result`, `run`, `evidence` and the like), which carry an extra reason: a
  plan declares and never records a result (gate: src/nirmaan/vplan.py:49,
  155-163).
- A requirement has `id`, `text` and `source`, and may have `section` (gate:
  src/nirmaan/vplan.py:198). `source` is the file name of the approved
  specification and `text` is the tagged requirement without its `[req:ID]`
  tag (gate: src/nirmaan/vplan.py:282-318, 345-348; the check compares text
  after collapsing whitespace).
- An item has `id`, `kind`, `file`, `name` and `proves`, and may have
  `rationale` (gate: src/nirmaan/vplan.py:219). Both `id` and `name` are
  required, so the free-text field the OpenTitan testplan calls a description
  has no place: put that prose in `rationale`. The plan-check records show a
  seat that wrote `description` and no `name`, then items with no `id` (record
  2026-11-18-claude-code-claude-opus-5-5-44, causes.md).
- An ID, for a requirement or an item, starts with a letter and then uses
  letters, digits, `_`, `.` and `-`; an ID used twice is refused (gate:
  src/nirmaan/vplan.py:47, 202-205, 223-226). `kind` is one of `test`,
  `assertion`, `coverage_point` (gate: src/nirmaan/vplan.py:228-230;
  src/nirmaan/company/traceability.py:47-54). `proves` is a non-empty list of
  requirement IDs from the same plan (gate: src/nirmaan/vplan.py:231-235).
- `retired` is optional. Each entry names one requirement or one item and a
  `reason` (gate: src/nirmaan/vplan.py:242-258).
- A smallest accepted shape is the committed fixture
  tests/fixtures/vplan/verification_plan.json: `format`, `version`,
  `requirements` of `id`, `text`, `source`, `section`, and `items` of `id`,
  `kind`, `file`, `name`, `proves`, `rationale`.
- A seat that has nothing in its inputs naming the format guesses it. In record
  2026-11-18-claude-code-claude-opus-5-5-30 the seat's own claims say the
  schema was an assumption because its inputs did not give the format.
  Writing the file in this shape on the first try saves the attempts for the
  content errors the check reports next: a requirement not quoted, one missing
  from the plan (inference).

## What the repository's plan check does

- `vplan.check` takes a plan file and the approved specification file or files
  (gate: src/nirmaan/company/tools.py:160-164). Both are required and each is
  a list of paths.
- A specification tags a requirement with `[req:ID]` in the Markdown list item
  or paragraph that states it (gate: src/nirmaan/company/traceability.py:58;
  src/nirmaan/vplan.py:282-318).
- The plan passes only when it covers exactly the tagged requirements: each
  plan requirement must name the specification file as its source, be tagged
  there, and quote the tagged text (compared after collapsing whitespace); a
  tagged requirement missing from the plan fails; a specification that tags
  nothing fails; a requirement tagged twice fails (gate:
  src/nirmaan/vplan.py:321-350).
- An item must name a plain file name, with no directory part (gate:
  src/nirmaan/vplan.py:351-352).
- An item has a kind from the registered list (`test`, `assertion`,
  `coverage_point`), a non-empty `proves` list naming requirement IDs in the
  same plan, and may not claim a result such as `passed` or `status` (gate:
  src/nirmaan/vplan.py:49, 155-163, 219-235; src/nirmaan/company/traceability.py:47-54).
- The check does not require every requirement to have an item. A requirement
  with no item only adds "no item yet for ..." to the summary of a passing run
  (gate: src/nirmaan/vplan.py:404-408). A plan with no items at all can pass.
  Say in the plan which requirements still have no item and why (inference).
- Nothing in the plan is backed by being planned: the module states that only
  a passing, cited run backs a requirement (gate: src/nirmaan/vplan.py:21).
  The kinds say what such a run is: a simulation of the file that holds a
  test, a formal run or a quiet simulation for an assertion, and a coverage
  measurement for a cover point (gate:
  src/nirmaan/company/traceability.py:47-54).
- Cover points are proven by `coverage.read` only. That tool reads the
  coverage of design files (gate:
  src/nirmaan/integrations/eda_parsers.py:555-594).

## Common failure modes

- A requirement paraphrased instead of quoted: the quote check fails it (gate:
  src/nirmaan/vplan.py:345-348). A changed source is failed earlier, as a
  source that is not the approved spec (vplan.py:340-342) or an ID the source
  does not tag (vplan.py:343-344).
- A requirement added from general knowledge of the block type that the
  specification does not tag: the check fails it (gate: src/nirmaan/vplan.py:343-344).
- A feature with a testpoint but no way to tell if it passed, because the
  planned test checks nothing. Plan the check along with the stimulus (inference).
- An item whose `proves` names a requirement it does not exercise. The check
  reads IDs, not meaning, so a reviewer must compare each item to the
  requirement text (inference).
- Planning only what is easy to simulate. A requirement that needs a proof
  gets an `assertion` item on a formal run, not a test (inference).

## How a plan is checked

- Run `vplan.check` against the approved specification before review, then fix
  every listed problem. A problem about a plan entry names that entry's line
  (gate: src/nirmaan/vplan.py:341, 344, 347), but a specification that tags no
  requirement is reported without a line (gate: src/nirmaan/vplan.py:332).
- Read the summary line for "no item yet" and decide, for each such
  requirement, whether the plan is incomplete or the requirement is verified
  another way (inference).
- Read each item against its requirement. The check cannot tell whether a
  planned test would catch the requirement failing (inference).

## Sources

- [OTDV] Testplan and DV document sections, and the key test focus areas.
- [OTPlan] Testpoints, covergroups and the rules for tests and names.
- [OTStage] The verification stages and what the first one requires.
