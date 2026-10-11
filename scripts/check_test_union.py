"""Fail when a test is skipped in every CI job that collected it (M46).

Each test job writes a JUnit report. The real-EDA job runs on Python 3.12, the
no-tools job on 3.11, and the physical-design job runs the PD tests, so a test
may skip in one job and run in another. This check reads every report and
lists the tests that ran nowhere, so splitting the suite across jobs can never
make a test silently disappear.

    python scripts/check_test_union.py reports/*.xml
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def outcomes(report: Path) -> dict[str, bool]:
    """Each test in one JUnit report, mapped to whether it ran (anything but a skip)."""
    ran = {}
    for case in ET.parse(report).getroot().iter("testcase"):
        test = f"{case.get('classname')}::{case.get('name')}"
        ran[test] = ran.get(test, False) or case.find("skipped") is None
    return ran


def never_ran(reports: list[Path]) -> list[str]:
    ran: dict[str, bool] = {}
    for report in reports:
        for test, did in outcomes(report).items():
            ran[test] = ran.get(test, False) or did
    return sorted(test for test, did in ran.items() if not did)


def main(argv: list[str]) -> int:
    reports = [Path(a) for a in argv]
    if not reports:
        print("usage: check_test_union.py REPORT.xml...", file=sys.stderr)
        return 2
    for report in reports:
        tests = outcomes(report)
        print(f"{report}: {len(tests)} tests, {sum(tests.values())} ran, {len(tests) - sum(tests.values())} skipped")
    missing = never_ran(reports)
    for test in missing:
        print(f"skipped in every job: {test}")
    print(f"{len(missing)} tests ran in no job" if missing else "every test ran in at least one job")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
