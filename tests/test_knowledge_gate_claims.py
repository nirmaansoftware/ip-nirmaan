"""Gate claims in knowledge documents, checked mechanically (council record 2026-11-14, decision 3).

Two tests over every document under knowledge/:

* every ``.sby`` example embedded in a document (a fenced block whose info
  string starts with ``sby``, or whose lines include a ``.sby`` section header)
  passes the formal gate's own static checks, ``_sby_check`` (formal.run) and
  ``_sby_cover_check`` (formal.cover). An example the document shows as refused
  carries the word ``refused`` in its info string (```` ```sby refused ````),
  and must then be refused by at least one check, so the marker cannot hide a
  setup the gate accepts;
* a document that names a construct the gates refuse outright (``[tasks]``)
  states the refusal in the same paragraph or list item.

The refused constructs are listed here as data, and a test proves the gate
refuses each one, so the list cannot claim a refusal the code does not make.
Constructs refused only in some files (``$finish`` outside the testbench) are
left to the check record's ``gate_claims`` field: a sentence may name them for
the file that may use them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from nirmaan.integrations.eda import Job, _hdl_files, _sby_check, _sby_cover_check

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "knowledge"

#: The sections of a .sby file: a fenced block with one of these as a header line is a .sby example.
SBY_SECTIONS = ("options", "engines", "script", "files", "tasks")
#: The info-string word that marks an example the document shows as refused.
REFUSED_MARK = "refused"
#: Constructs the formal gate refuses before anything runs, whatever the rest of the setup, each with a
#: minimal setup that uses it (proved refused by ``test_each_listed_construct_is_refused_by_the_gate``).
REFUSED_CONSTRUCTS = {
    "[tasks]": "[tasks]\nprv\n\n[options]\nmode prove\n\n[engines]\nsmtbmc\n\n[script]\nread -formal top.v\n"
               "prep -top top\n\n[files]\ntop.v\n",
}
#: What a paragraph says when it states a refusal.
_REFUSAL_RE = re.compile(r"\brefus\w*", re.IGNORECASE)
_FENCE_RE = re.compile(r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")


def _documents() -> list[Path]:
    return sorted(KNOWLEDGE.rglob("*.md"))


def _name(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name


def _blocks(text: str) -> tuple[list[tuple[int, str, str]], list[tuple[int, str]]]:
    """The fenced blocks of a document (line, info string, body) and the lines outside them (line, text)."""
    fenced, prose, lines = [], [], text.splitlines()
    i = 0
    while i < len(lines):
        opened = _FENCE_RE.match(lines[i])
        if not opened:
            prose.append((i + 1, lines[i]))
            i += 1
            continue
        indent, fence = len(opened["indent"]), opened["fence"]
        body, j = [], i + 1
        while j < len(lines) and not re.match(rf"^\s*{re.escape(fence[0])}{{{len(fence)},}}\s*$", lines[j]):
            body.append(lines[j][indent:] if lines[j][:indent].strip() == "" else lines[j])
            j += 1
        fenced.append((i + 1, opened["info"].strip(), "\n".join(body) + "\n"))
        i = j + 1
    return fenced, prose


def _is_sby(info: str, body: str) -> bool:
    words = info.lower().split()
    headers = {ln.strip()[1:-1].strip() for ln in body.splitlines()
               if ln.strip().startswith("[") and ln.strip().endswith("]")}
    return bool(words and words[0] == "sby") or bool(headers & set(SBY_SECTIONS))


def sby_examples(path: Path) -> list[tuple[int, bool, str]]:
    """Each .sby example in a document: its line, whether it is marked refused, and its text."""
    fenced, _ = _blocks(path.read_text(encoding="utf-8"))
    return [(line, REFUSED_MARK in info.lower().split(), body) for line, info, body in fenced if _is_sby(info, body)]


def gate_problems(sby_text: str, root: Path) -> list[str]:
    """What the formal gate's static checks say about a setup, written two folders below ``root``.

    The RTL an example's ``[files]`` names is not in the document, so an empty file stands in for each one
    that is missing; the job's sources are the Verilog the setup reads, as a submission of exactly those files.
    """
    root = root.resolve()
    where = root / "a" / "b"
    sby = where / "example.sby"
    sby.parent.mkdir(parents=True, exist_ok=True)
    sby.write_text(sby_text, encoding="utf-8")
    for _, path in _hdl_files(sby):
        if not path.is_relative_to(root):
            return [f"[files] names {path}, outside the example's own folder"]
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
    sources = tuple(str(path) for _, path in _hdl_files(sby))
    problems = []
    for tool, check in (("formal.run", _sby_check), ("formal.cover", _sby_cover_check)):
        job = Job(tool, {"sby": str(sby)}, where, sources, None)
        problem = check(job)
        if problem:
            problems.append(f"{tool}: {problem}")
    return problems


def example_failures(path: Path, tmp_path: Path) -> list[str]:
    """Each example of a document that the gate refuses unmarked, or that is marked refused and passes."""
    failures = []
    for n, (line, refused, body) in enumerate(sby_examples(path)):
        problems = gate_problems(body, tmp_path / f"ex{n}")
        if problems and not refused:
            failures.append(f"{_name(path)}:{line}: {'; '.join(problems)}")
        elif refused and not problems:
            failures.append(f"{_name(path)}:{line}: marked {REFUSED_MARK}, but both checks accept it")
    return failures


def _paragraphs(path: Path) -> list[tuple[int, str]]:
    """The body's paragraphs and list items outside fenced blocks (front matter dropped), with their first line."""
    text = path.read_text(encoding="utf-8")
    _, prose = _blocks(text)
    if prose and prose[0][1].strip() == "---":
        end = next((k for k in range(1, len(prose)) if prose[k][1].strip() == "---"), 0)
        prose = prose[end + 1:]
    out, current = [], None
    for line, raw in prose:
        if not raw.strip() or _ITEM_RE.match(raw) or raw.lstrip().startswith("#"):
            if current:
                out.append(current)
            current = (line, raw) if raw.strip() else None
        else:
            current = (current[0], current[1] + "\n" + raw) if current else (line, raw)
    if current:
        out.append(current)
    return out


def unstated_refusals(path: Path) -> list[str]:
    """Each paragraph of a document that names a refused construct without stating the refusal."""
    return [f"{_name(path)}:{line}: names {construct} without stating that the gate refuses it"
            for line, text in _paragraphs(path)
            for construct in REFUSED_CONSTRUCTS
            if construct in text and not _REFUSAL_RE.search(text)]


# --- The repository -----------------------------------------------------------------------------


def test_every_sby_example_in_knowledge_passes_the_gate_checks(tmp_path):
    failures = [f for k, doc in enumerate(_documents()) for f in example_failures(doc, tmp_path / f"d{k}")]
    assert failures == []


def test_no_knowledge_document_names_a_refused_construct_without_the_refusal():
    assert [f for doc in _documents() for f in unstated_refusals(doc)] == []


def test_each_listed_construct_is_refused_by_the_gate(tmp_path):
    for k, (construct, setup) in enumerate(REFUSED_CONSTRUCTS.items()):
        problems = gate_problems(setup, tmp_path / f"c{k}")
        assert len(problems) == 2, (construct, problems)
        assert all(construct in p for p in problems), (construct, problems)


# --- The tests can fail -------------------------------------------------------------------------

GOOD_SBY = "[options]\nmode prove\n\n[engines]\nsmtbmc\n\n[script]\nread -formal top.v\nprep -top top\n\n[files]\ntop.v\n"


def _doc(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "doc.md"
    path.write_text("---\nid: design/x\nsources:\n  - open | [tasks] in a title | https://example.org\n---\n"
                    + body, encoding="utf-8")
    return path


def test_a_good_example_passes(tmp_path):
    doc = _doc(tmp_path, f"Text.\n\n```sby\n{GOOD_SBY}```\n")
    assert len(sby_examples(doc)) == 1
    assert example_failures(doc, tmp_path / "run") == []


def test_an_example_is_found_by_its_sections_without_the_info_string(tmp_path):
    doc = _doc(tmp_path, "- A setup:\n\n  ```text\n  " + GOOD_SBY.replace("\n", "\n  ") + "```\n")
    assert [refused for _, refused, _ in sby_examples(doc)] == [False]
    assert example_failures(doc, tmp_path / "run") == []


@pytest.mark.parametrize("setup, reason", [
    (REFUSED_CONSTRUCTS["[tasks]"], "declares [tasks]"),
    (GOOD_SBY.replace("[options]\nmode prove\n\n", ""), "no [options] section"),
    (GOOD_SBY.replace("[files]\ntop.v\n", "[files]\n/etc/top.v\n"), "outside the example's own folder"),
])
def test_an_unmarked_example_the_gate_refuses_fails(tmp_path, setup, reason):
    doc = _doc(tmp_path, f"```sby\n{setup}```\n")
    failures = example_failures(doc, tmp_path / "run")
    assert len(failures) == 1 and reason in failures[0], failures


def test_a_marked_negative_example_passes_only_if_the_gate_refuses_it(tmp_path):
    refused = _doc(tmp_path, f"```sby refused\n{REFUSED_CONSTRUCTS['[tasks]']}```\n")
    assert example_failures(refused, tmp_path / "run1") == []
    accepted = _doc(tmp_path, f"```sby refused\n{GOOD_SBY}```\n")
    assert ["both checks accept it" in f for f in example_failures(accepted, tmp_path / "run2")] == [True]


def test_naming_tasks_without_the_refusal_fails(tmp_path):
    doc = _doc(tmp_path, "# Proof\n\n- An optional `[tasks]` section runs a proof\n  and a cover from one file.\n"
                         "- `depth` defaults to 20; a refused run says why.\n")
    assert unstated_refusals(doc) == ["doc.md:8: names [tasks] without stating that the gate refuses it"]


def test_naming_tasks_with_the_refusal_passes(tmp_path):
    doc = _doc(tmp_path, "- Submit one `.sby` with no `[tasks]`: a setup with\n  `[tasks]` is refused and nothing runs.\n\n"
                         f"```sby refused\n{REFUSED_CONSTRUCTS['[tasks]']}```\n")
    assert unstated_refusals(doc) == []
