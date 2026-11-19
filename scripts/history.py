"""Milestone history fragments: a follow-up pull request's history entry as its own file.

A milestone's first pull request writes `docs/history/MNN-<slug>.md` and its line in
`docs/history/README.md`. A later pull request on the same milestone never edits that
file: it adds a fragment,

    docs/history/fragments/MNN-<slug>/<YYYY-MM-DD>-<topic>.md

one or a few paragraphs in the file's own style (a bold lead-in, no heading). Two pull
requests then add two new files, so they never conflict on the shared one (the M87 and
G3 pull requests did, many times). A milestone's whole history is its file followed by
its fragments in name order (the date first, then the topic):

    python scripts/history.py show M87-whole-flow-label
    python scripts/history.py check

`check` is what tests/test_status_docs.py runs. See docs/STATUS_DOCS.md.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "docs" / "history"
FRAGMENT_NAME = re.compile(r"\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*\.md")


def fragments(stem: str, history: Path = HISTORY) -> list[Path]:
    folder = history / "fragments" / stem
    return sorted(folder.glob("*.md")) if folder.is_dir() else []


def show(stem: str, history: Path = HISTORY) -> str:
    """The milestone's file, then each fragment in name order, a blank line between."""
    parts = [(history / f"{stem}.md").read_text(encoding="utf-8")]
    parts += [p.read_text(encoding="utf-8") for p in fragments(stem, history)]
    return "\n".join(part.rstrip("\n") + "\n" for part in parts)


def check(history: Path = HISTORY) -> list[str]:
    """Every problem with the fragments: a folder that names no history file, a
    file not named <YYYY-MM-DD>-<topic>.md, an empty fragment, or one with a
    heading line (the heading is the history file's own)."""
    problems = []
    root = history / "fragments"
    if not root.exists():
        return problems
    for item in sorted(root.iterdir()):
        if not item.is_dir():
            problems.append(f"{item.relative_to(history)}: only folders named after a history file go here")
            continue
        if not (history / f"{item.name}.md").is_file():
            problems.append(f"{item.relative_to(history)}: no docs/history/{item.name}.md")
        for frag in sorted(item.iterdir()):
            rel = frag.relative_to(history)
            if not FRAGMENT_NAME.fullmatch(frag.name):
                problems.append(f"{rel}: name it <YYYY-MM-DD>-<topic>.md")
                continue
            text = frag.read_text(encoding="utf-8")
            if not text.strip():
                problems.append(f"{rel}: empty")
            elif any(line.startswith("#") for line in text.splitlines()):
                problems.append(f"{rel}: no heading in a fragment (paragraphs with a bold lead-in)")
    return problems


def main(argv: list[str]) -> int:
    if argv[:1] == ["show"] and len(argv) == 2 and (HISTORY / f"{argv[1]}.md").is_file():
        sys.stdout.write(show(argv[1]))
        return 0
    if argv == ["check"]:
        problems = check()
        for p in problems:
            print(p, file=sys.stderr)
        return 1 if problems else 0
    print("usage: python scripts/history.py (show MNN-<slug> | check)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
