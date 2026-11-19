"""Gate SC5: the judge fails a wrong driver on the build the trials use, with the program run as the seat account.

Council record ``council/records/2026-11-19-seat-c-live-refusal.md``, decision 1, item 5: before the single-seat lift,
the four committed broken fixtures of the AXI4-Lite register block (three drivers and a wrong map header, the
``driver-*`` controls of ``evals/flow/controls.json``) are recorded failing the held-out checks of
``firmware/axi4-lite-driver``, with the program ``fw.test`` builds run as the seat account. The workflow runs this in
the ``replay`` job of that case, after the credential test, so through the same tools, the same account and the same
wrapper as its trials (``NIRMAAN_SEAT_EXEC``, gate SC2).

Each fixture, and the reference driver as the control, is staged under the names the case's seat writes and run
through every held-out check of the case exactly as the ``held-out-run`` scorer runs it (the check's tool and
parameters, the seat's files with the case's files). It passes only when the reference passes every check, each
broken fixture fails at least one check by a run that ran (not refused), and, with ``--require-seat``, every
``fw.test`` run's last step went through the wrapper. The result is written to ``--out``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAT = "nirmaan.fw-broken/1"
CASE = "firmware/axi4-lite-driver"
FW = ROOT / "tests" / "fixtures" / "fw" / "axi4_lite"
#: The seat's files, by the name the seat writes, from the reference answer.
REFERENCE = {"axi4_lite_regs_map.h": "axi4_lite_regs_map.h", "axi4_lite_regs_drv.h": "axi4_lite_regs_drv.h",
             "axi4_lite_regs_drv.c": "axi4_lite_regs_drv.c"}
#: The four broken fixtures (``evals/flow/controls.json``: driver-wrong-map, driver-swallowed-error,
#: driver-all-strobes, driver-sticky-response), each as the one file it puts in the reference's place.
BROKEN = {"wrong-map": {"axi4_lite_regs_map.h": "axi4_lite_regs_map_wrong.h"},
          "swallowed-error": {"axi4_lite_regs_drv.c": "axi4_lite_regs_drv_swallowed_error.c"},
          "all-strobes": {"axi4_lite_regs_drv.c": "axi4_lite_regs_drv_all_strobes.c"},
          "sticky-response": {"axi4_lite_regs_drv.c": "axi4_lite_regs_drv_sticky_response.c"}}


def stage(where: Path, swap: dict[str, str]) -> list[str]:
    """The seat's files under their own names in ``where``, with ``swap`` in place of the reference's."""
    where.mkdir(parents=True)
    for name, fixture in {**REFERENCE, **swap}.items():
        shutil.copyfile(FW / fixture, where / name)
    return [str(where / name) for name in REFERENCE]


def run_checks(seat: list[str], seat_exec: str | None) -> list[dict]:
    """Every held-out check of the case over the seat's files, as ``held-out-run`` runs it."""
    from nirmaan.evals.cases import load_cases
    from nirmaan.integrations import firmware  # noqa: F401  (registers fw.build and fw.test)
    from nirmaan.integrations.eda import execute, select_backend, temporary_runs

    case = next(c for c in load_cases(ROOT / "evals") if c.id == CASE)
    results = []
    for check in case.held_out:
        params: dict[str, object] = dict(check.params)
        for param in check.seat_files:
            params[param] = list(seat)
        for param, paths in check.case_files.items():
            params.setdefault(param, [])
            params[param] = [*params[param], *(str(ROOT / p) for p in paths)]  # type: ignore[misc]
        params = {k: ",".join(v) if isinstance(v, list) else v for k, v in params.items()}
        backend, why = select_backend(str(check.tool), params)
        if backend is None:
            results.append({"check": check.name, "tool": check.tool, "ran": False, "succeeded": False,
                            "summary": f"no backend: {why}", "run_step": []})
            continue
        with temporary_runs():
            outcome = execute(backend, params)
        step = ((outcome.data or {}).get("commands") or [[]])[-1]
        results.append({"check": check.name, "tool": check.tool, "ran": bool(outcome.references),
                        "succeeded": outcome.succeeded, "summary": outcome.summary, "run_step": step[:1],
                        "through_wrapper": bool(seat_exec) and step[:1] == [seat_exec]})
    return results


def problems(found: dict[str, list[dict]], require_seat: bool) -> list[str]:
    """What the record does not show: the reference passing, each broken fixture failed by a run, the wrapper."""
    out = []
    reference = found.get("reference") or []
    if not reference or not all(r["succeeded"] for r in reference):
        out.append("the reference driver does not pass every held-out check, so a failure proves nothing")
    for name in BROKEN:
        runs = found.get(name) or []
        if not any(r["ran"] and not r["succeeded"] for r in runs):
            out.append(f"{name}: no held-out check failed it by a run that ran")
    if require_seat:
        tested = [r for runs in found.values() for r in runs if r["tool"] == "fw.test"]
        if not tested or not all(r["through_wrapper"] for r in tested):
            out.append("an fw.test run did not go through the seat account's wrapper")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record the broken driver fixtures failing the held-out checks.")
    parser.add_argument("--out", type=Path, required=True, help="where the result is written (JSON)")
    parser.add_argument("--require-seat", action="store_true", help="fail unless every fw.test run used the wrapper")
    args = parser.parse_args(argv)
    seat_exec = os.environ.get("NIRMAAN_SEAT_EXEC", "").strip() or None
    work = Path(tempfile.mkdtemp(prefix="fw-broken-"))
    try:
        found = {"reference": run_checks(stage(work / "reference", {}), seat_exec)}
        for name, swap in BROKEN.items():
            found[name] = run_checks(stage(work / name, swap), seat_exec)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    wrong = problems(found, args.require_seat)
    result = {"format": FORMAT, "case": CASE, "seat_exec": seat_exec, "require_seat": args.require_seat,
              "fixtures": {"reference": REFERENCE, **{n: {**REFERENCE, **s} for n, s in BROKEN.items()}},
              "results": found, "problems": wrong,
              "run": {k: os.environ.get(v) for k, v in (("id", "GITHUB_RUN_ID"), ("attempt", "GITHUB_RUN_ATTEMPT"),
                                                         ("job", "GITHUB_JOB"), ("ref", "GITHUB_REF"))}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name, runs in found.items():
        for r in runs:
            print(f"FW-BROKEN {name}: {r['check']}: {'passed' if r['succeeded'] else 'failed'}"
                  f"{' (through the wrapper)' if r.get('through_wrapper') else ''}: {r['summary']}", flush=True)
    if wrong:
        print(f"::error::broken driver control: {'; '.join(wrong)}", flush=True)
        return 1
    print(f"broken driver control: the reference passes and each of {len(BROKEN)} broken fixtures fails a held-out "
          "check" + (", every fw.test run as the seat account" if args.require_seat else ""), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
