"""Check that every model-labelled failed live trial of a batch is answered (G5, M86).

The rule is in docs/CAPABILITY_LEVELS.md ("Failures feed the curriculum"). A failed live evidence trial that the
failure labeller (H2: the `causes.md` beside a run record) marks "model" must be answered, in the pull request that
commits the batch, by one of:

    note: <path>       a new knowledge note (a file that exists in the repository)
    must-fail: <path>  a new must-fail case (a file that exists in the repository)
    no: <reason>       a written reason why neither (at least 20 characters)

Each answer is one line, `- <failure id>: <answer>`, in the answers text (the PR body or a file). The failure id is
`<record key>:trial-NN`, as this script prints it. The key is the record folder's path under evals/results:
its bare name, or `g3-timer/slot-NN/<name>` for a record nested under a slot folder.

    python scripts/failure_curriculum.py                          list every model failure and its answer
    python scripts/failure_curriculum.py --records A B            only the batch of these record keys
    python scripts/failure_curriculum.py --body-file body.md      answers from a file (`-` is stdin)
    python scripts/failure_curriculum.py --pr 123                 answers from that PR's body (gh)

Exit 2 when a --records key matches no record (a path where a key belongs, a typo, no key at all).
Exit 1 when a model failure in scope has no valid answer. With no answers given it lists and exits 0 (the dry run);
`--require` makes that an error too. Failed trials that carry no label at all are listed and fail with `--strict`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evals" / "results"

MIN_REASON = 20
ANSWER = re.compile(r"^\s*[-*]\s*`?(?P<id>[\w./+-]+:trial-\d+)`?\s*:\s*(?P<kind>note|must-fail|no)\s*:\s*(?P<text>.+?)\s*$",
                    re.IGNORECASE)


@dataclass(frozen=True)
class Failure:
    id: str  # "<record key>:trial-NN"
    record: str  # the record key: the folder's path under evals/results, so a nested slot record is unique
    trial: int
    cause: str  # the label text from causes.md, or "" when none
    source: str  # the causes.md it came from, or ""

    @property
    def is_model(self) -> bool:
        return self.cause.strip().lower().startswith("model")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _key(folder: Path, results: Path) -> str:
    """A record's key: its path under `results`. A flat record is its bare folder name, as before; a record
    nested under a slot folder (evals/results/g3-timer/slot-NN/<name>) is `g3-timer/slot-NN/<name>`, so two
    slots of one arm on one day, which share a record name, never share a key."""
    return folder.relative_to(results).as_posix()


def _resolve(folder: Path, cell: str, results: Path) -> str | None:
    """The record key a row's Record cell names: empty or `this` is the folder itself; `-11` or
    `-without-knowledge-11` is a sibling (in the same folder) named by the same stem."""
    cell = cell.strip().strip("`")
    if cell in ("", "this"):
        return _key(folder, results)
    name = folder.name
    stems = [name, re.sub(r"-\d+$", "", name), re.sub(r"-without-knowledge(?:-\d+)?$", "", name),
             re.sub(r"-limit(?:-\d+)?$", "", name)]
    for stem in stems:
        for guess in (stem + cell, re.sub(r"-\d+$", "", stem) + cell):
            if (folder.parent / guess).is_dir():
                return _key(folder.parent / guess, results)
    return None


def labels(results: Path) -> tuple[list[Failure], list[str]]:
    """Every labelled row of every `causes.md` under `results` (at any depth), plus the rows that could not be placed."""
    found: list[Failure] = []
    problems: list[str] = []
    for causes in sorted(results.rglob("causes.md")):
        header: list[str] = []
        for line in causes.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                header = [] if header and not line.strip() else header
                continue
            cells = _cells(line)
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                continue
            lowered = [c.lower() for c in cells]
            if "cause" in lowered:
                header = lowered
                continue
            if not header:
                continue
            row = dict(zip(header, cells))
            cause = row.get("cause", "")
            record = _resolve(causes.parent, row.get("record", ""), results)
            trials = [int(t) for t in re.findall(r"\d+", row.get("trial", "").split(" in all")[0])]
            if record is None or not trials:
                if cause.lower().startswith("model"):
                    problems.append(f"{causes.relative_to(results)}: cannot place the row: {line[:90]}")
                continue
            for t in trials:
                found.append(Failure(f"{record}:trial-{t:02d}", record, t, cause, str(causes.relative_to(results))))
    return found, problems


def failed_trials(results: Path) -> list[tuple[str, int]]:
    """Every failed live evidence trial in the committed records: not passed, not a replay, not an ablation or calibration."""
    out: list[tuple[str, int]] = []
    for path in sorted(results.rglob("trial-*.json")):
        trial = json.loads(path.read_text(encoding="utf-8"))
        result = trial.get("result", {})
        if result.get("passed") or result.get("replay") or trial.get("purpose", "evidence") != "evidence":
            continue
        out.append((_key(path.parent.parent, results), int(trial.get("trial", 0))))
    return out


def record_keys(results: Path) -> set[str]:
    """The key of every committed record: a folder that holds a trial or a causes.md, passing trials included."""
    keys = {_key(p.parent.parent, results) for p in results.rglob("trial-*.json")}
    return keys | {_key(p.parent, results) for p in results.rglob("causes.md")}


def parse_answers(text: str) -> dict[str, tuple[str, str]]:
    answers: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        m = ANSWER.match(line)
        if m:
            answers[m["id"]] = (m["kind"].lower(), m["text"])
    return answers


def judge(failure: Failure, answers: dict[str, tuple[str, str]], root: Path) -> str | None:
    """None when answered, else why not."""
    if failure.id not in answers:
        return "no answer"
    kind, text = answers[failure.id]
    if kind == "no":
        return None if len(text) >= MIN_REASON else f"reason shorter than {MIN_REASON} characters"
    path = text.strip("` ").split()[0]
    if not (root / path).is_file():
        return f"{kind} names {path}, which is not a file in the repository"
    return None


def run(results: Path, root: Path, records: list[str] | None, answers_text: str | None, require: bool, strict: bool,
        out) -> int:
    if records is not None:
        known = record_keys(results)
        unknown = [r for r in records if r not in known] or ([] if records else ["(no key given)"])
        if unknown:
            print("--records matches no record: " + ", ".join(repr(r) for r in unknown), file=out)
            print("A record key is the folder's path under evals/results (its bare name, or "
                  "g3-timer/slot-NN/<name>), not a file path.", file=out)
            return 2
    rows, problems = labels(results)
    scope = (lambda r: records is None or r in records)
    model = [f for f in rows if f.is_model and scope(f.record)]
    labelled = {f.id for f in rows}
    unlabelled = [f"{r}:trial-{t:02d}" for r, t in failed_trials(results) if scope(r) and f"{r}:trial-{t:02d}" not in labelled]
    answers = parse_answers(answers_text or "")
    bad = 0
    print(f"model-labelled failures in scope: {len(model)}", file=out)
    for f in model:
        why = judge(f, answers, root)
        state = "answered" if why is None else f"UNANSWERED ({why})"
        print(f"  {f.id}  [{f.source}]  {state}", file=out)
        bad += why is not None
    for p in problems:
        print(f"  problem: {p}", file=out)
    print(f"failed trials with no label in any causes.md: {len(unlabelled)}", file=out)
    for u in unlabelled:
        print(f"  {u}", file=out)
    print(f"unanswered: {bad} of {len(model)}", file=out)
    fail = (bad and (answers_text is not None or require)) or problems or (strict and unlabelled)
    return 1 if fail else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--results", type=Path, default=RESULTS)
    ap.add_argument("--records", nargs="*", help="record keys of the batch (default: all)")
    ap.add_argument("--body-file", help="answers text; `-` is stdin")
    ap.add_argument("--pr", type=int, help="read the answers from this PR's body with gh")
    ap.add_argument("--require", action="store_true", help="fail on an unanswered failure even with no answers given")
    ap.add_argument("--strict", action="store_true", help="also fail on a failed trial no causes.md labels")
    args = ap.parse_args(argv)
    text = None
    if args.body_file:
        text = sys.stdin.read() if args.body_file == "-" else Path(args.body_file).read_text(encoding="utf-8")
    elif args.pr:
        text = subprocess.run(["gh", "pr", "view", str(args.pr), "--json", "body", "-q", ".body"], check=True,
                              capture_output=True, text=True).stdout
    return run(args.results, ROOT, args.records, text, args.require, args.strict, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
