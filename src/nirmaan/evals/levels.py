"""Evidence levels (M63): Knowledge, Practised and Proven, only from committed records.

The capability build-out council record of 2026-10-18 (section 9) sets the
scale. A level is never typed: ``scripts/capability_levels.py`` computes it
from files in the repository and writes ``capability/levels.json``, and a test
fails when the committed file differs from what the records give.

* **Knowledge**: the skill's document ``knowledge/<division>/<skill_id>.md``
  exists, and a check record ``capability/records/knowledge/<skill_id>.json``
  names it by its current sha256, with a checker who is not the writer and the
  sources the checker read. A document changed since its check is stale.
* **Practised**: committed, tool-judged eval result records under
  ``evals/results/`` (M45, M58), counted per model and per skill digest (card
  plus document). Only a case's own ``skills`` get credit. A group counts when
  it has at least ``MIN_TRIALS`` trials, a 95 percent Wilson lower bound of at
  least ``MIN_LOWER``, a clean re-judge of every trial (``rejudge.json`` in the
  record, written by ``nirmaan eval rejudge --write``), and, for a design or
  verification skill, a must-fail control in every case it rests on. A group
  whose digest is not the skill's current one is stale and never counts.
  Replays and attested trials are refused (``load_evidence``); a trial judged
  by anything but a tool is listed apart and never counts.
* **Proven**: only from the product's own seat run records on delivered work
  that passed review. No such record kind exists yet, so no skill is Proven.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Any

from nirmaan.evals.cases import EvalError, load_cases, skill_digest
from nirmaan.evals.records import MANIFEST, load_evidence, wilson
from nirmaan.evals.scorers import scorer_spec
from nirmaan.models import EvalCase
from nirmaan.org import Organization

FORMAT = "nirmaan.capability-levels"
KNOWLEDGE_CHECK_FORMAT = "nirmaan.knowledge-check"
LEVELS = Path("capability") / "levels.json"
CHECKS = Path("capability") / "records" / "knowledge"
RESULTS = Path("evals") / "results"
REJUDGE = "rejudge.json"
REJUDGE_FORMAT = "nirmaan.eval-rejudge"
MIN_TRIALS = 5
MIN_LOWER = 0.5
#: Skill domains whose Practised level needs a must-fail control in every case (record section 9.7).
MUST_FAIL_DOMAINS = ("design", "verification")


class Level(str, Enum):
    KNOWLEDGE = "knowledge"
    PRACTISED = "practised"
    PROVEN = "proven"


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path, repo: Path) -> str:
    return path.resolve().relative_to(repo.resolve()).as_posix()


# --- Knowledge -------------------------------------------------------------------------------


def knowledge(skill_id: str, repo: Path) -> dict[str, Any] | None:
    """The skill's knowledge evidence, or None when it has neither a document nor a check record."""
    docs = sorted((repo / "knowledge").glob(f"*/{skill_id}.md"))
    check = repo / CHECKS / f"{skill_id}.json"
    if not docs and not check.is_file():
        return None
    problems: list[str] = []
    entry: dict[str, Any] = {"document": _rel(docs[0], repo) if docs else None,
                             "check_record": _rel(check, repo) if check.is_file() else None}
    if len(docs) != 1:
        problems.append(f"{len(docs)} documents for {skill_id}; there must be one")
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
        if docs and data.get("document") != entry["document"]:
            problems.append(f"the check record names {data.get('document')!r}, not {entry['document']}")
        writer, checker = data.get("writer"), data.get("checker")
        if not writer or not checker or writer == checker:
            problems.append("a check record needs a writer and a different checker")
        if not data.get("sources_read"):
            problems.append("the check record lists no source the checker read")
        if docs and data.get("document_sha256") != _sha256(docs[0]):
            problems.append("stale: the document changed after its check")
    entry["counts"] = not problems
    entry["problems"] = problems
    return entry


# --- Practised -------------------------------------------------------------------------------


def _tool_judged(case: EvalCase) -> bool:
    specs = [scorer_spec(c.scorer) for c in case.held_out]
    return bool(specs) and all(s is not None and s.requires_tool for s in specs)


def _must_fail(case: EvalCase) -> bool:
    return any(check.mutants for check in case.held_out)


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


def practised(org: Organization, repo: Path, cases: dict[str, EvalCase]) -> tuple[dict[str, list], list[str], list]:
    """Per skill, every (model, digest) group of tool-judged trials; the refused records; trials not tool-judged."""
    groups: dict[tuple[str, str | None, str | None], dict[str, Any]] = {}
    refused: list[str] = []
    not_tool_judged: list[dict[str, Any]] = []
    for manifest in sorted((repo / RESULTS).rglob(MANIFEST)):
        try:
            record = load_evidence(manifest.parent)
        except (EvalError, OSError, ValueError) as exc:
            refused.append(f"{_rel(manifest.parent, repo)}: {exc}")
            continue
        rejudged = _rejudged(manifest.parent)
        where = _rel(manifest.parent, repo)
        for trial in record.trials:
            case = cases.get(trial.result.case)
            if case is None:
                refused.append(f"{where}: case {trial.result.case} is not among the eval cases")
                continue
            if not _tool_judged(case) or not trial.judge_runs:
                not_tool_judged.append({"record": where, "case": case.id, "trial": trial.trial,
                                        "passed": trial.result.passed})
                continue
            for skill in case.skills:  # only the skills the case names get credit
                key = (skill, trial.model, trial.skills.get(skill))
                g = groups.setdefault(key, {"n": 0, "passed": 0, "records": set(), "cases": set(),
                                            "unrejudged": 0, "no_must_fail": set()})
                g["n"] += 1
                g["passed"] += int(trial.result.passed)
                g["records"].add(where)
                g["cases"].add(case.id)
                if not rejudged.get((case.id, trial.trial), False):
                    g["unrejudged"] += 1
                if not _must_fail(case):
                    g["no_must_fail"].add(case.id)
    out: dict[str, list] = defaultdict(list)
    for (skill, model, digest), g in sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        low = (wilson(g["passed"], g["n"]) or (0.0, 0.0))[0]
        current = skill_digest(org, skill, repo) if skill in org.skills else None
        reasons = []
        if skill not in org.skills:
            reasons.append("the skill is not in the catalog")
        if digest != current:
            reasons.append("stale: the skill card or document changed after these trials")
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
        out[skill].append({"model": model, "digest": digest, "n": g["n"], "passed": g["passed"],
                           "lower": round(low, 4), "records": sorted(g["records"]), "cases": sorted(g["cases"]),
                           "counts": not reasons, "reasons": reasons})
    return dict(out), refused, not_tool_judged


# --- Levels ----------------------------------------------------------------------------------


def compute(org: Organization, repo: Path) -> dict[str, Any]:
    """Every skill's evidence level from the repository's committed records, as ``capability/levels.json``."""
    repo = Path(repo)
    cases = {c.id: c for c in load_cases(repo / "evals")} if (repo / "evals").is_dir() else {}
    groups, refused, not_tool_judged = practised(org, repo, cases)
    skills: dict[str, Any] = {}
    for skill_id in sorted(set(org.skills) | set(groups)):
        know = knowledge(skill_id, repo)
        practice = groups.get(skill_id, [])
        if know is None and not practice:
            continue
        level = (Level.PRACTISED if any(g["counts"] for g in practice)
                 else Level.KNOWLEDGE if know and know["counts"] else None)
        skills[skill_id] = {"level": level.value if level else None, "knowledge": know, "practised": practice}
    totals = {lvl.value: sum(1 for s in skills.values() if s["level"] == lvl.value) for lvl in Level}
    return {"format": FORMAT, "totals": totals, "skills": skills,
            "refused_records": refused, "not_tool_judged": not_tool_judged,
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
