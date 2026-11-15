---
id: verification/log_analysis
skill: log_analysis
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | Zhu et al., Tools and Benchmarks for Automated Log Parsing, ICSE-SEIP 2019 (arXiv 1811.03509) [LogParse] | https://arxiv.org/abs/1811.03509
  - open | Glerum et al., Debugging in the (Very) Large: Ten Years of Implementation and Experience, SOSP 2009 (conference copy) [WER] | https://www.sigops.org/s/conferences/sosp/2009/papers/glerum-sosp09.pdf
  - open | Andreas Zeller, The Debugging Book: Introduction to Debugging (CC BY-NC-SA 4.0) [ZIntro] | https://www.debuggingbook.org/html/Intro_Debugging.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K5 session (wave 2 knowledge batch, plan row W2-K5, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the VeriTriage tools this skill holds are available; this document is knowledge, not evidence.

# Log analysis

Reading simulation and regression logs as structured events before
reasoning about them, and what the two VeriTriage tools return. Tags in
brackets name the sources above; "inference" marks this document's own
reasoning; "gate" names the repository code that backs a line. No tool log is
committed, so no line here states a measured tool result as fact.

## Parse before reading

- Each log message has a header set by the logging framework, such as the
  time, the level and the component, and a content written by a developer
  [LogParse].
- The content is a constant part, the event template, plus variable
  parameters; log parsing turns each message into its template and its
  parameters [LogParse].
- Parsing messages into a structured format enables efficient search,
  filtering, grouping and counting of logs [LogParse].
- The volume of logs makes manual inspection impractical, even with search
  and grep [LogParse].
- Hand-written regular expressions for parsing are slow to write and
  error-prone, and need regular revision as the logging code changes
  [LogParse].
- A parser should handle every message: ignoring an important event may miss
  the root cause [LogParse].
- Before parsing, a simple preprocessing step replaces common variable values,
  such as IP addresses and numbers, using regular expressions [LogParse]. In
  a simulation log the same applies to times, seeds, addresses and data
  values (inference).
- In Huawei's deployment, messages were partitioned by level and component,
  because messages of different levels or components always come from
  different logging statements [LogParse].
- Current parsers cannot tell a state value, such as "ok" against "error",
  from other parameters [LogParse]. So keep the parameters: in "expected 3,
  got 5" the values are the evidence (inference).
- No parser performed well on every kind of log; the authors advise trying
  parsers on your own logs first [LogParse].

## Reading a simulation log

- A failure is where a fault becomes visible; the defect that caused it ran
  earlier, and the fault propagated from there [ZIntro].
- So the first error line in a log marks the first check that saw the fault,
  not the defect, and the last fatal line is often a consequence, such as a
  timeout after the design stopped responding (inference).
- WER found that a bug it reported was 4.5 to 5.1 times more likely to be
  fixed than one reported by a person, and notes that its reports document
  internal state while people's document external symptoms [WER]. A check that
  prints the signal, the expected and the actual value, and the cycle, gives a
  log that can be analysed (inference).
- Office tags each assert with a permanent identifier, so its failures are
  grouped by that tag even as the assert moves in the source [WER]. Give each
  testbench check a stable label for the same reason (inference).
- Scattering print statements through code and reading their output line
  by line is inefficient: a long input gives as many lines to read [ZIntro].
- A failed assertion makes the failure appear earlier, closer to the fault
  [ZIntro].

## What the tools return

- veritriage.explain_log takes one path to a file; a missing path or a
  directory is refused (gate: src/nirmaan/integrations/veritriage.py:72-79).
- It returns annotated regions, each with a line number, an origin, a phase
  and the line's text (gate: src/nirmaan/integrations/veritriage.py:77-79).
- veritriage.investigate reports a classification, a confidence, a count of
  evidence nodes and a top hypothesis, and saves a session whose id it returns
  (gate: src/nirmaan/integrations/veritriage.py:58-68).
- A low-confidence class is a lead, not a finding (inference).
- simulator.run reads the testbench's verdict line, `NIRMAAN-SIM <nonce> <n>
  passed, <m> failed`, carrying the run's nonce (gate:
  src/nirmaan/integrations/eda_parsers.py:128-129).

## Common failure modes

- Grepping for the first ERROR (card: src/nirmaan/company/skills.py:500).
- Reading the last fatal line as the cause, when it is the timeout that
  followed (inference).
- Comparing two logs by their raw text, so different times and seeds make
  identical failures look different (inference).
- Dropping the parameter that carries the evidence while normalising
  (inference).
- Taking a low-confidence classification as the finding (inference).

## How a result is checked

- Findings cite log lines (card: src/nirmaan/company/skills.py:500), by
  file and line number, as explain_log's regions give them.
- Every error and fatal message in the log is accounted for: the one chosen
  as the cause, and why each other one is a consequence or unrelated
  (inference).
- The conclusion holds when the same check is read on a second failing run
  with a different seed (inference).
