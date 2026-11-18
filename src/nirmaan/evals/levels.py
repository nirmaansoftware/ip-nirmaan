"""Evidence levels (M63): Knowledge, Practised and Proven, only from committed records.

The capability build-out council record of 2026-10-18 (section 9;
council/records/2026-10-18-capability-buildout.md) sets the scale. A level is never typed:
``scripts/capability_levels.py`` computes it from files in the repository and writes ``capability/levels.json``, and a test
fails when the committed file differs from what the records give.

* **Knowledge**: the skill's document ``knowledge/<division>/<skill_id>.md``
  exists and passes the M62 checks, and a check record ``capability/records/knowledge/<skill_id>.json``
  names it by its current sha256, with a checker who is not the writer and the
  sources the checker read, and in a record checked from 2026-11-15 its ``gate_claims``.
  A document changed since its check is stale.
* **Practised**: committed, tool-judged eval result records under
  ``evals/results/`` (M45, M58), counted per model, per skill digest (card
  plus document) and per harness (M73, ``docs/HARNESS.md``). Only a case's own ``skills`` get credit. A group counts when
  it has at least ``MIN_TRIALS`` trials, a 95 percent Wilson lower bound of at
  least ``MIN_LOWER``, a clean re-judge of every trial (``rejudge.json`` in the
  record, written by ``nirmaan eval rejudge --write``), and, for a design or
  verification skill, a must-fail control in every case it rests on. A group
  whose digest is not the skill's current one is stale and never counts, and
  so is a group whose harness is not the current one; a trial that records no
  harness (a record written before M73) never counts. The harness of a trial on
  the claude-code runtime carries the Claude Code version it ran, so trials from
  two versions are two groups, each checked against the current harness at its
  own version, and a version that could not be read never counts.
  Replays and attested trials are refused (``load_evidence``); a trial of a
  case not judged by a tool is listed apart and never counts. On a tool-judged
  case, a trial that no judge ran on (the work was blocked, declined or refused
  before review) is a failed trial of its group, never left out: leaving it out
  would turn 4 of 5 into 4 of 4. A trial run without
  knowledge documents (M67, the ablation: ``knowledge: off`` in its run
  manifest or in the trial itself) is listed apart with the reason and never
  counts toward any level. A calibration record or trial (``purpose:
  calibration`` in its manifest or the trial: M76, an outside benchmark, or
  ``eval run --purpose calibration`` on our own cases) is listed under
  ``calibration``, as "outside calibration" when its manifest names an outside
  source and as "calibration" otherwise, and never counts. A trial run
  on a named harness variant (M74, ``eval run --harness <name>``: any name but
  ``default`` in its run manifest or in the trial) is listed under
  ``variants`` with the name and never counts. A whole-flow trial (M87, ``flow: whole`` in its run manifest
  or in the trial; council record 2026-11-17) is checked first, before every label above: it credits no skill,
  is listed under ``whole_flow`` by group, and never counts toward any level. A record that mixes whole-flow and
  single-seat trials is refused.
* **Proven**: only from the product's own seat run records on delivered work
  that passed review. No such record kind exists yet, so no skill is Proven.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Any

from nirmaan.company.evidence import MUST_FAIL_DOMAINS
from nirmaan.evals.cases import EvalError, load_cases, skill_digest
from nirmaan.evals.records import (MANIFEST, calibration_labels, flow_labels, is_whole_flow, knowledge_off,
                                   load_evidence, load_record, variant_labels, wilson)
from nirmaan.evals.scorers import scorer_spec
from nirmaan.models import EvalCase
from nirmaan.org import Organization
from nirmaan.org.knowledge_files import check_document
from nirmaan.runtime.claude_code import UNKNOWN_VERSION
from nirmaan.runtime.harness import harness_sha256

FORMAT = "nirmaan.capability-levels"
KNOWLEDGE_CHECK_FORMAT = "nirmaan.knowledge-check"
LEVELS = Path("capability") / "levels.json"
CHECKS = Path("capability") / "records" / "knowledge"
RESULTS = Path("evals") / "results"
REJUDGE = "rejudge.json"
REJUDGE_FORMAT = "nirmaan.eval-rejudge"
GATE_CLAIMS_FROM = "2026-11-15"  # a check record dated on or after this day carries ``gate_claims``
_GATE_EVIDENCE = re.compile(r"^(\S+:\d+|\S+::\S+|unverified)$")  # path:line, a test id, or "unverified"
MIN_TRIALS = 5
MIN_LOWER = 0.5
#: M87 (council record 2026-11-17, decision 1): a whole-flow group's count is stated only from this many trials.
#: Its own constant: it is not a level's minimum and never moves with ``MIN_TRIALS``.
WHOLE_FLOW_MIN = 10
WHOLE_FLOW_REASON = "whole-flow trial: credits no skill and never counts toward a level"


class Level(str, Enum):
    KNOWLEDGE = "knowledge"
    PRACTISED = "practised"
    PROVEN = "proven"


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path, repo: Path) -> str:
    return path.resolve().relative_to(repo.resolve()).as_posix()


# --- Knowledge -------------------------------------------------------------------------------


def _gate_claim_problems(data: dict[str, Any]) -> list[str]:
    """Problems with a check record's ``gate_claims`` (council 2026-11-14, decision 3).

    Required when ``checked_at`` is on or after ``GATE_CLAIMS_FROM``; a record before that day
    may omit it (it counts as not checked for gate claims) and, when it carries one, is held
    to the same shape.
    """
    claims = data.get("gate_claims")
    if claims is None:
        checked = data.get("checked_at")
        if isinstance(checked, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", checked) and checked < GATE_CLAIMS_FROM:
            return []
        return [f"the check record has no gate_claims (required for a record checked on or after {GATE_CLAIMS_FROM})"]
    if not isinstance(claims, list) or not claims:
        return ["gate_claims must be a non-empty list"]
    problems: list[str] = []
    for i, item in enumerate(claims, 1):
        claim = item.get("claim") if isinstance(item, dict) else None
        evidence = item.get("evidence") if isinstance(item, dict) else None
        if not isinstance(claim, str) or not claim.strip():
            problems.append(f"gate_claims[{i}] has no claim")
        if not isinstance(evidence, str) or not _GATE_EVIDENCE.match(evidence):
            problems.append(f"gate_claims[{i}] evidence must be path:line, a test id (path::name) or unverified")
    return problems


def knowledge(org: Organization, skill_id: str, repo: Path) -> dict[str, Any] | None:
    """The skill's knowledge evidence, or None when it has neither a document nor a check record."""
    docs = sorted((repo / "knowledge").glob(f"*/{skill_id}.md"))
    check = repo / CHECKS / f"{skill_id}.json"
    if not docs and not check.is_file():
        return None
    problems: list[str] = []
    entry: dict[str, Any] = {"knowledge_document": _rel(docs[0], repo) if docs else None,
                             "check_record": _rel(check, repo) if check.is_file() else None}
    if len(docs) != 1:
        problems.append(f"{len(docs)} documents for {skill_id}; there must be one")
    for doc in docs:  # M62: a document that fails its own checks raises no level
        problems += [f"{_rel(doc, repo)}: {p}" for p in check_document(doc, org.skills, org.tools)[0]]
    if not check.is_file():
        problems.append("no check record")
    else:
        try:
            data = json.loads(check.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
            problems.append("the check record is not JSON")
        if data.get("format") != KNOWLEDGE_CHECK_FORMAT:
            problems.append(f"the check record's format is not {KNOWLEDGE_CHECK_FORMAT}")
        if data.get("skill") != skill_id:
            problems.append(f"the check record is for {data.get('skill')!r}")
        if docs and data.get("knowledge_document") != entry["knowledge_document"]:
            named, path = data.get("knowledge_document"), entry["knowledge_document"]
            problems.append(f"the check record names {named!r}, not {path}")
        writer, checker = data.get("writer"), data.get("checker")
        if not writer or not checker or writer == checker:
            problems.append("a check record needs a writer and a different checker")
        if not data.get("sources_read"):
            problems.append("the check record lists no source the checker read")
        if docs and data.get("document_sha256") != _sha256(docs[0]):
            problems.append("stale: the document changed after its check")
        problems += _gate_claim_problems(data)
    entry["counts"] = not problems
    entry["problems"] = problems
    return entry


# --- Practised -------------------------------------------------------------------------------


def _tool_judged(case: EvalCase) -> bool:
    specs = [scorer_spec(c.scorer) for c in case.held_out]
    return bool(specs) and all(s is not None and s.requires_tool for s in specs)


def _must_fail(case: EvalCase) -> bool:
    return any(check.mutants for check in case.held_out)


def _harness(trial) -> str | None:
    """The harness a trial records (M73): on its result and on every answer alike, else None."""
    recorded = trial.result.harness
    return recorded if all(a.harness == recorded for a in trial.answers) else None


def _rejudged(record_dir: Path) -> dict[tuple[str, int], bool]:
    path = record_dir / REJUDGE
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    if data.get("format") != REJUDGE_FORMAT:
        return {}
    return {(t["case"], int(t["trial"])): bool(t.get("same")) for t in data.get("trials", [])}


def _whole_flow_groups(trials: list[tuple[Any, Any, str]]) -> list[dict[str, Any]]:
    """M87: whole-flow trials by group (case digest, model, harness, CLI, flow digest; and purpose, so a
    calibration trial is never pooled with evidence), each trial listed one by one. A group's count (``n``,
    ``passed``, ``unjudged`` and the 95 percent Wilson interval) is stated only from ``WHOLE_FLOW_MIN`` trials;
    whether the group's planned count is complete is the committed plan's, which this file does not hold. A trial
    no judge ran on is a failed trial of its group."""
    groups: dict[tuple, dict[str, Any]] = {}
    for manifest, trial, where in trials:
        judged = bool(trial.judge_runs)
        off = knowledge_off(manifest, trial)
        purpose = trial.purpose if trial.purpose != "evidence" else manifest.purpose
        key = (trial.result.case, trial.result.case_digest, trial.model, _harness(trial), trial.result.cli,
               trial.flow_digest, purpose)
        group = groups.setdefault(key, {"case": key[0], "case_digest": key[1], "model": key[2], "harness": key[3],
                                        "cli": key[4], "flow_digest": key[5], "purpose": key[6], "trials": []})
        named = " and ".join(flow_labels(manifest, trial))
        group["trials"].append({"record": where, "case": trial.result.case, "trial": trial.trial,
                                "passed": judged and trial.result.passed, "judged": judged,
                                "knowledge": "off" if off else "on", "flow_digest": trial.flow_digest,
                                "reason": f"{WHOLE_FLOW_REASON} (labelled in {named})"})
    out = []
    for key in sorted(groups, key=lambda k: tuple(str(x) for x in k)):
        group = groups[key]
        group["trials"].sort(key=lambda t: (t["record"], t["trial"]))
        n = len(group["trials"])
        if n >= WHOLE_FLOW_MIN:
            passed = sum(t["passed"] for t in group["trials"])
            low, high = wilson(passed, n) or (0.0, 0.0)
            group["count"] = {"n": n, "passed": passed, "unjudged": sum(not t["judged"] for t in group["trials"]),
                              "low": round(low, 4), "high": round(high, 4)}
        out.append(group)
    return out


def practised(org: Organization, repo: Path,
              cases: dict[str, EvalCase]) -> tuple[dict[str, list], list[str], list, list, list, list, list]:
    """Per skill, every (model, digest, harness, CLI version) group of tool-judged cases' trials, a trial no judge
    ran on counted as failed; the refused records; trials of cases not tool-judged; trials run without knowledge
    documents (M67), calibration trials (M76 and ``eval run --purpose calibration``) and trials on a named
    harness variant (M74), which never count; and whole-flow trials (M87) by group, which never count either."""
    groups: dict[tuple[str, str | None, str | None, str | None, str | None], dict[str, Any]] = {}
    refused: list[str] = []
    not_tool_judged: list[dict[str, Any]] = []
    without_knowledge: list[dict[str, Any]] = []
    calibration: list[dict[str, Any]] = []
    variants: list[dict[str, Any]] = []
    whole_flow: list[tuple[Any, Any, str]] = []
    for manifest in sorted((repo / RESULTS).rglob(MANIFEST)):
        try:
            record = load_record(manifest.parent)
            if is_whole_flow(record):
                # M87: first, before every other label and the skill loop, so a whole-flow trial lands here and
                # in no other list. A replay or an attested whole-flow record is refused like any other.
                record = load_evidence(manifest.parent)
                whole_flow += [(record.manifest, t, _rel(manifest.parent, repo)) for t in record.trials]
                continue
            labelled = [bool(calibration_labels(record.manifest, t)) for t in record.trials]
            if any(labelled) and not all(labelled):
                # M76: one record never mixes the two; a stray label cannot take the other trials out of the levels
                kind = "outside calibration" if record.manifest.source else "calibration"
                raise EvalError(f"the record mixes {kind} trials with evidence trials: "
                                "each trial is one or the other, so the record is refused")
            if any(labelled) or (not record.trials and record.manifest.purpose != "evidence"):
                # M76: a calibration record is listed, never judged as evidence (a replay of it is no refusal)
                where = _rel(manifest.parent, repo)
                kind = "outside calibration" if record.manifest.source else "calibration"
                for trial in record.trials:
                    named = " and ".join(calibration_labels(record.manifest, trial))
                    calibration.append({"record": where, "case": trial.result.case, "trial": trial.trial,
                                        "passed": trial.result.passed,
                                        "reason": f"{kind} (labelled in {named}): never counts toward a level"})
                continue
            record = load_evidence(manifest.parent)
        except (EvalError, OSError, ValueError) as exc:
            refused.append(f"{_rel(manifest.parent, repo)}: {exc}")
            continue
        rejudged = _rejudged(manifest.parent)
        where = _rel(manifest.parent, repo)
        for trial in record.trials:
            off = knowledge_off(record.manifest, trial)
            if off:  # M67: the ablation measures the documents' effect; it is never evidence of a skill
                without_knowledge.append({"record": where, "case": trial.result.case, "trial": trial.trial,
                                          "passed": trial.result.passed,
                                          "reason": f"run without knowledge documents (knowledge: off in "
                                                    f"{' and '.join(off)}): never counts toward a level"})
                continue
            on_variant = variant_labels(record.manifest, trial)
            if on_variant:  # M74: a variant is compared with the default, never evidence of a skill
                variants.append({"record": where, "case": trial.result.case, "trial": trial.trial,
                                 "passed": trial.result.passed,
                                 "reason": f"run on a harness variant (labelled in {' and '.join(on_variant)}): "
                                           "never counts toward a level"})
                continue
            case = cases.get(trial.result.case)
            if case is None:
                refused.append(f"{where}: case {trial.result.case} is not among the eval cases")
                continue
            if not _tool_judged(case):
                not_tool_judged.append({"record": where, "case": case.id, "trial": trial.trial,
                                        "passed": trial.result.passed})
                continue
            # Record section 9, item 6: a tool-judged case's trial that never reached a judge stays in its group
            # as a failure, whatever it claims, so a blocked trial cannot drop out of the count.
            judged = bool(trial.judge_runs)
            for skill in case.skills:  # only the skills the case names get credit
                key = (skill, trial.model, trial.skills.get(skill), _harness(trial), trial.result.cli)
                g = groups.setdefault(key, {"n": 0, "passed": 0, "unjudged": 0, "records": set(), "cases": set(),
                                            "unrejudged": 0, "no_must_fail": set()})
                g["n"] += 1
                g["passed"] += int(judged and trial.result.passed)
                g["unjudged"] += int(not judged)
                g["records"].add(where)
                g["cases"].add(case.id)
                if not rejudged.get((case.id, trial.trial), False):
                    g["unrejudged"] += 1
                if not _must_fail(case):
                    g["no_must_fail"].add(case.id)
    out: dict[str, list] = defaultdict(list)
    for (skill, model, digest, recorded, cli), g in sorted(groups.items(),
                                                          key=lambda kv: tuple(str(x) for x in kv[0])):
        # M73: the current harness, with no run options but the CLI version the trials ran (docs/HARNESS.md)
        current_harness = harness_sha256(cli=cli)
        low = (wilson(g["passed"], g["n"]) or (0.0, 0.0))[0]
        current = skill_digest(org, skill, repo) if skill in org.skills else None
        reasons = []
        if skill not in org.skills:
            reasons.append("the skill is not in the catalog")
        if digest != current:
            reasons.append("stale: the skill card or document changed after these trials")
        if recorded is None:
            reasons.append("harness not recorded: the trials carry no harness, or their answers disagree")
        elif recorded != current_harness:
            reasons.append("stale: the harness changed after these trials (docs/HARNESS.md)")
        if cli == UNKNOWN_VERSION:
            reasons.append("the CLI version the trials ran was not read")
        if model is None:
            reasons.append("no model is recorded")
        if g["n"] < MIN_TRIALS:
            reasons.append(f"{g['n']} trials, fewer than {MIN_TRIALS}")
        if low < MIN_LOWER:
            reasons.append(f"Wilson lower bound {low:.3f}, under {MIN_LOWER}")
        if g["unrejudged"]:
            reasons.append(f"{g['unrejudged']} trials without a clean re-judge")
        if skill in org.skills and org.skills[skill].domain in MUST_FAIL_DOMAINS and g["no_must_fail"]:
            reasons.append(f"no must-fail control in {', '.join(sorted(g['no_must_fail']))}")
        out[skill].append({"model": model, "digest": digest, "harness": recorded, "cli": cli, "n": g["n"],
                           "passed": g["passed"],
                           "unjudged": g["unjudged"], "lower": round(low, 4), "records": sorted(g["records"]),
                           "cases": sorted(g["cases"]), "counts": not reasons, "reasons": reasons})
    whole = _whole_flow_groups(whole_flow)
    return dict(out), refused, not_tool_judged, without_knowledge, calibration, variants, whole


# --- Levels ----------------------------------------------------------------------------------


def compute(org: Organization, repo: Path) -> dict[str, Any]:
    """Every skill's evidence level from the repository's committed records, as ``capability/levels.json``."""
    repo = Path(repo)
    cases = {c.id: c for c in load_cases(repo / "evals")} if (repo / "evals").is_dir() else {}
    (groups, refused, not_tool_judged, without_knowledge, calibration, variants,
     whole_flow) = practised(org, repo, cases)
    skills: dict[str, Any] = {}
    for skill_id in sorted(set(org.skills) | set(groups)):
        know = knowledge(org, skill_id, repo)
        practice = groups.get(skill_id, [])
        if know is None and not practice:
            continue
        level = (Level.PRACTISED if any(g["counts"] for g in practice)
                 else Level.KNOWLEDGE if know and know["counts"] else None)
        skills[skill_id] = {"level": level.value if level else None, "knowledge": know, "practised": practice}
    totals = {lvl.value: sum(1 for s in skills.values() if s["level"] == lvl.value) for lvl in Level}
    return {"format": FORMAT, "totals": totals, "skills": skills,
            "refused_records": refused, "not_tool_judged": not_tool_judged, "without_knowledge": without_knowledge,
            "calibration": calibration, "variants": variants, "whole_flow": whole_flow,
            "proven": "No skill is Proven: no product seat run record of delivered work exists yet."}


def render(levels: dict[str, Any]) -> str:
    return json.dumps(levels, indent=2, sort_keys=True) + "\n"


def write_rejudge(record_dir: Path, record_id: str, outcomes) -> Path:
    """Write ``rejudge.json`` beside a run record: each trial's re-judge, same or with its differences."""
    from nirmaan import __version__

    data = {"format": REJUDGE_FORMAT, "record": record_id, "nirmaan_version": __version__,
            "trials": [{"case": o.trial.result.case, "trial": o.trial.trial, "same": o.same,
                        "differences": list(o.differences)} for o in outcomes]}
    path = Path(record_dir) / REJUDGE
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path
