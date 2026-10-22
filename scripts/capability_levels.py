"""Compute every skill's evidence level from committed records (M63).

    python scripts/capability_levels.py           # print the levels
    python scripts/capability_levels.py --write   # write capability/levels.json
    python scripts/capability_levels.py --check   # exit 1 when the committed file differs

Knowledge, Practised and Proven come only from records in the repository
(`src/nirmaan/evals/levels.py`, `docs/CAPABILITY_LEVELS.md`). Nothing here is
typed by hand.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nirmaan.company import build_organization  # noqa: E402
from nirmaan.evals.levels import LEVELS, compute, render  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="write capability/levels.json")
    mode.add_argument("--check", action="store_true", help="fail when capability/levels.json is out of date")
    args = parser.parse_args(argv)
    text = render(compute(build_organization(), ROOT))
    target = ROOT / LEVELS
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print(f"wrote {LEVELS}")
        return 0
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != text:
            print(f"{LEVELS} is out of date: run python scripts/capability_levels.py --write", file=sys.stderr)
            return 1
        print(f"{LEVELS} matches the records")
        return 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
