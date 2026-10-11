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
