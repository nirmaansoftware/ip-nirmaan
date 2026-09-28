"""Fail if any tracked text file contains an em dash or an en dash.

CLAUDE.md forbids both characters everywhere in this repository. This script
lists tracked files with `git ls-files`, skips binary files and the vendored
nirmaan.online files, and prints every offending line.
"""

from __future__ import annotations

import subprocess
import sys

DASHES = ("—", "–")

# nirmaan.online's own files, copied unchanged (see site/README.md); they
# follow that repository's conventions, not this one's.
VENDORED = {"site/nirmaan.css", "site/site.js", "site/hero.js"}


def main() -> int:
    paths = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True
    ).stdout.decode().split("\0")
    found = 0
    for path in paths:
        if not path or path in VENDORED:
            continue
        with open(path, "rb") as handle:
            data = handle.read()
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if any(dash in line for dash in DASHES):
                print(f"{path}:{number}: {line.strip()}")
                found += 1
    if found:
        print(f"{found} line(s) contain an em or en dash (U+2014, U+2013).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
