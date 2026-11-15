"""Scan committed seat answers for gate input M84 refuses (docs/GATE_INPUTS.md, section 3).

Reads every eval trial record under ``evals/results/`` and every JSON fixture under ``tests/fixtures/``, takes
each seat-written file from the answers' file blocks and each declared ``entry``, and runs them through
``nirmaan.integrations.eda_guard``: a Verilog file through ``verilog_problem``, a ``.sby`` through
``sby_problem``, an entry through ``name_problem``. It prints the counts and every refusal, and writes nothing.

    PYTHONPATH=src python scripts/gate_input_history.py [ROOT]
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

from nirmaan.integrations.eda_guard import name_problem, sby_problem, verilog_problem
from nirmaan.runtime.files import CLOSE, OPEN

_ENTRY_RE = re.compile(r'"entry"\s*:\s*"((?:\\.|[^"\\])*)"')


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, str):
        yield value


def _blocks(text: str) -> Iterator[tuple[str, str]]:
    """Each ``=== FILE: <path> ===`` block of an answer: its path and content."""
    lines, name, body = text.splitlines(), None, []
    for line in lines:
        if name is None:
            opened = OPEN.match(line)
            if opened:
                name, body = opened.group(1).strip(), []
        elif CLOSE.match(line):
            yield name, "\n".join(body) + "\n"
            name = None
        else:
            body.append(line)


def scan(root: Path) -> dict[str, object]:
    """The counts and refusals over every committed answer under ``root``."""
    records = sorted(root.glob("evals/results/**/*.json")) + sorted(root.glob("tests/fixtures/**/*.json"))
    answers = files = verilog = setups = entries = 0
    refused: list[str] = []
    for record in records:
        try:
            data = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for text in _strings(data):
            if "=== FILE:" not in text:
                continue
            answers += 1
            for entry in _ENTRY_RE.findall(text):
                entries += 1
                if name_problem(json.loads(f'"{entry}"')):
                    refused.append(f"{record.relative_to(root)}: entry {entry!r}")
            for name, body in _blocks(text):
                files += 1
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / Path(name).name
                    path.write_text(body, encoding="utf-8")
                    if path.suffix == ".sby":
                        setups += 1
                        why = sby_problem(path)
                    elif path.suffix in (".v", ".sv", ".vh", ".svh"):
                        verilog += 1
                        why = verilog_problem([path])
                    else:
                        why = None
                if why:
                    tasks = path.suffix == ".sby" and "[tasks]" in body
                    refused.append(f"{record.relative_to(root)}: {name}{' (declares [tasks])' if tasks else ''}: {why}")
    return {"records": len(records), "answers": answers, "files": files, "verilog": verilog, "setups": setups,
            "entries": entries, "refused": refused}


def main(argv: list[str]) -> int:
    found = scan(Path(argv[1]) if len(argv) > 1 else Path.cwd())
    print(f"records {found['records']}, answers with files {found['answers']}, seat files {found['files']} "
          f"({found['verilog']} Verilog, {found['setups']} .sby), entries {found['entries']}, "
          f"refused {len(found['refused'])}")
    for line in found["refused"]:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
