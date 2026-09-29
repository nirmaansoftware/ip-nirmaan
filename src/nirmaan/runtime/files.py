"""Files in a model's answer (M23): delimited blocks, taken verbatim, written with a digest.

A model answers with one JSON object. When its work is a file (a spec, RTL, a
testbench), the object's ``files`` list describes each one and the content
follows the object in a block::

    === FILE: axi4_lite_regs.v ===
    module axi4_lite_regs ...
    === END FILE ===

Blocks are split off before the JSON is parsed (Verilog is full of braces) and
their content is kept byte for byte: no JSON escaping, and a lint diagnostic's
line numbers are the lines the model wrote. A block with an unsafe path, a
duplicate, or no end line is rejected and reported, never guessed at.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

OPEN = re.compile(r"^=== FILE:(.*)===[ \t]*$")
CLOSE = re.compile(r"^=== END FILE ===[ \t]*$")
_SAFE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*(/[A-Za-z0-9_][A-Za-z0-9_.\-]*)*$")


def safe_path(path: str) -> bool:
    """Relative, no parent references, and only ordinary file-name characters."""
    return bool(_SAFE.match(path)) and ".." not in path.split("/")


def split_files(text: str) -> tuple[str, dict[str, str], list[str]]:
    """The answer without its file blocks, the files by path, and what was rejected."""
    rest: list[str] = []
    files: dict[str, str] = {}
    problems: list[str] = []
    path: str | None = None
    body: list[str] = []
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        if path is None:
            opened = OPEN.match(bare)
            if opened:
                path, body = opened.group(1).strip(), []
            elif CLOSE.match(bare):
                problems.append("an END FILE line with no open block")
            else:
                rest.append(line)
            continue
        if not CLOSE.match(bare):
            body.append(line)
            continue
        if not safe_path(path):
            problems.append(f"unsafe file path {path!r}")
        elif path in files:
            problems.append(f"file {path} appears twice; the first was kept")
        else:
            files[path] = "".join(body)
        path = None
    if path is not None:
        problems.append(f"file {path!r} has no END FILE line")
    return "".join(rest), files, problems


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def write_file(root: Path, path: str, content: str) -> tuple[Path, str]:
    """Write one file under ``root``; return where it went and its digest."""
    target = (root / path).resolve()
    if not safe_path(path) or not target.is_relative_to(root.resolve()):
        raise ValueError(f"unsafe file path {path!r}")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8")
    target.write_bytes(data)
    return target, digest(data)


def read_verified(location: str | None, expected: str | None) -> tuple[str | None, str]:
    """A recorded file's content, only if its bytes still match the recorded digest."""
    if not location or not expected:
        return None, ""
    try:
        data = Path(location).read_bytes()
    except OSError as exc:
        return None, f"unreadable ({type(exc).__name__})"
    if digest(data) != expected:
        return None, "digest mismatch: the file changed after it was recorded"
    return data.decode("utf-8", errors="replace"), ""


#: A log line worth showing a seat that is repairing its work (M26).
_NOTABLE = re.compile(r"error|warning|fail|fatal|assert|mismatch", re.IGNORECASE)


def excerpt(location: str | None, lines: int = 20, width: int = 240) -> tuple[list[str], str]:
    """A bounded excerpt of a recorded log: its notable lines in order, else its last lines.

    Returns the lines and a note on what they are, or no lines and why not.
    """
    if not location:
        return [], "the run recorded no log"
    try:
        text = Path(location).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [], f"its log is unreadable ({type(exc).__name__})"
    every = [line.rstrip()[:width] for line in text.splitlines() if line.strip()]
    notable = [line for line in every if _NOTABLE.search(line)]
    if notable:
        return notable[:lines], f"first {min(lines, len(notable))} of {len(notable)} notable lines"
    return every[-lines:], f"last {min(lines, len(every))} of {len(every)} lines"
