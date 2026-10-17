"""M46: the CI workflow's hardening, and the check that no test runs in no job.

The workflow is read as text (the suite has no YAML dependency): every action
is pinned by commit SHA with its version in a comment, every runner image is
pinned, and a newer push to a pull request cancels the older run.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github").rglob("*.yml"))


def _union():
    spec = importlib.util.spec_from_file_location("check_test_union", ROOT / "scripts" / "check_test_union.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report(path: Path, cases: dict[str, bool]) -> Path:
    body = "".join(f'<testcase classname="tests.test_x" name="{name}">{"" if ran else "<skipped/>"}</testcase>'
                   for name, ran in cases.items())
    path.write_text(f'<testsuites><testsuite name="pytest">{body}</testsuite></testsuites>', encoding="utf-8")
    return path


def test_a_test_skipped_in_every_job_is_reported(tmp_path, capsys):
    union = _union()
    eda = _report(tmp_path / "eda.xml", {"test_rtl": True, "test_sdk": False, "test_pd": False, "test_gone": False})
    bare = _report(tmp_path / "bare.xml", {"test_rtl": False, "test_sdk": True, "test_pd": False, "test_gone": False})
    pd = _report(tmp_path / "pd.xml", {"test_pd": True})
    assert union.never_ran([eda, bare, pd]) == ["tests.test_x::test_gone"]
    assert union.main([str(eda), str(bare), str(pd)]) == 1
    assert "skipped in every job: tests.test_x::test_gone" in capsys.readouterr().out
    assert union.main([str(eda), str(pd)]) == 1
    _report(bare, {"test_gone": True, "test_sdk": True})
    assert union.main([str(eda), str(bare), str(pd)]) == 0


def test_every_action_is_pinned_by_commit_with_its_version():
    uses = [(path.name, line.strip()) for path in WORKFLOWS for line in path.read_text(encoding="utf-8").splitlines()
            if re.match(r"\s*(- )?uses:", line)]
    assert uses
    for name, line in uses:
        if re.search(r"uses: \./", line):
            continue  # a local action is pinned by this commit
        assert re.fullmatch(r"(- )?uses: [\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+", line), (name, line)


def test_runners_are_pinned_and_pull_request_runs_cancel_older_ones():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    runners = re.findall(r"runs-on: (\S+)", text)
    assert runners and all(r == "ubuntu-24.04" for r in runners), runners
    assert re.search(r"^concurrency:\n  group: .+\n  cancel-in-progress: \$\{\{ github.event_name == 'pull_request' }}$",
                     text, re.MULTILINE)


# --- Workflow permissions and supply chain (council record 2026-10-17, rollout R2) ---------
#
# A workflow token that can write could post a review status or push, so every workflow
# reads by default; a job with no timeout can hold a runner for six hours; a required job
# with a path filter or a job-level `if:` can be skipped, and a skipped check passes; an
# event field expanded inside `run:` is shell injection from a branch name or PR title.

WORKFLOW_FILES = sorted(p for p in (ROOT / ".github" / "workflows").iterdir() if p.suffix in (".yml", ".yaml"))
REQUIRED_JOBS = ("test", "no-tools", "physical-design", "test-union", "dashes")
_INJECTABLE = re.compile(r"\$\{\{\s*github\.(event\.|head_ref)")


def _top_level_block(text: str, key: str) -> str | None:
    match = re.search(rf"^{key}:[^\n]*\n((?: [^\n]*\n|\n)*)", text, re.MULTILINE)
    return match.group(1) if match else None


def _jobs(text: str) -> dict[str, str]:
    block = _top_level_block(text, "jobs") or ""
    parts = re.split(r"^  ([\w-]+):\s*$", block, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2]))


def _run_blocks(text: str) -> list[str]:
    lines, blocks = text.splitlines(), []
    for i, line in enumerate(lines):
        match = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", line)
        if not match:
            continue
        indent, body = len(match.group(1)), [match.group(2)]
        for nxt in lines[i + 1:]:
            if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                break
            body.append(nxt)
        blocks.append("\n".join(body))
    return blocks


def workflow_problems(text: str) -> list[str]:
    problems = []
    if (_top_level_block(text, "permissions") or "").strip() != "contents: read":
        problems.append("top-level permissions is not exactly `contents: read`")
    if re.search(r"\bwrite(-all)?\s*$", text, re.MULTILINE):
        problems.append("a permission grants write")
    if "pull_request_target" in text:
        problems.append("pull_request_target")
    jobs = _jobs(text)
    if not jobs:
        problems.append("no jobs found")
    for job, body in jobs.items():
        if not re.search(r"^    timeout-minutes: \d+\s*$", body, re.MULTILINE):
            problems.append(f"job {job} has no timeout-minutes")
    problems += [f"event field in run: {b.strip()[:60]}" for b in _run_blocks(text) if _INJECTABLE.search(b)]
    problems += [f"image not pinned by digest: {i}" for i in re.findall(r"^\s*image:\s*(\S+)", text, re.MULTILINE)
                 if not re.search(r"@sha256:[0-9a-f]{64}$", i)]
    return problems


def test_every_workflow_reads_only_times_out_and_never_expands_event_fields_in_run():
    assert WORKFLOW_FILES
    for path in WORKFLOW_FILES:
        assert workflow_problems(path.read_text(encoding="utf-8")) == [], path.name


def test_no_run_block_anywhere_in_github_expands_an_event_field():
    for path in WORKFLOWS:
        text = path.read_text(encoding="utf-8")
        assert "pull_request_target" not in text, path.name
        assert not [b for b in _run_blocks(text) if _INJECTABLE.search(b)], path.name


def test_the_checks_catch_what_they_claim_to():
    bad = """name: bad
on:
  pull_request_target:
permissions: write-all
jobs:
  build:
    runs-on: ubuntu-24.04
    container:
      image: openroad/orfs:latest
    steps:
      - run: echo "${{ github.event.pull_request.title }}"
      - name: Branch
        run: |
          echo hello
          echo ${{ github.head_ref }}
"""
    problems = workflow_problems(bad)
    for expected in ("top-level permissions", "grants write", "pull_request_target", "job build has no timeout",
                     "image not pinned"):
        assert any(expected in p for p in problems), (expected, problems)
    assert sum(p.startswith("event field in run") for p in problems) == 2
    # A safe use (an env value, or the concurrency group) is not flagged.
    good = bad.replace("pull_request_target", "pull_request").replace("permissions: write-all",
                                                                         "permissions:\n  contents: read")
    good = good.replace('echo "${{ github.event.pull_request.title }}"', 'echo "$TITLE"')
    good = good.replace("echo ${{ github.head_ref }}", "echo done").replace("orfs:latest", "orfs@sha256:" + "a" * 64)
    good = good.replace("    runs-on: ubuntu-24.04\n", "    runs-on: ubuntu-24.04\n    timeout-minutes: 5\n")
    assert workflow_problems(good) == []


def test_required_jobs_run_on_every_pull_request_and_cannot_be_skipped():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    trigger = _top_level_block(text, "on") or ""
    assert re.search(r"^  pull_request:\s*$", trigger, re.MULTILINE), trigger
    assert not re.search(r"paths|branches-ignore|tags", trigger), trigger
    assert re.search(r"^  pull_request:\s*\n(?!    )", trigger, re.MULTILINE), "pull_request has a filter"
    jobs = _jobs(text)
    for job in REQUIRED_JOBS:
        assert job in jobs, job
        assert not re.search(r"^    if:", jobs[job], re.MULTILINE), f"required job {job} has a job-level if"
