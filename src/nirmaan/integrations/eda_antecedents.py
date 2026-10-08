"""Automatic antecedent covers (M29): a proof whose assertions never fire does not count.

For every assertion in the RTL a cover run reads, a cover of the condition
under which that assertion is checked is written into a copy of the file in
the run's own directory. The seat's files are never edited.

* An assertion in procedural code (an ``always`` or ``initial`` block, a task,
  a function) is wrapped in place, as ``begin cover (A); <the assertion> end``.
  The cover then sits on exactly the procedural path the assertion sits on:
  every enclosing ``if`` and ``else``, ``case`` arm, loop iteration, generate
  instance, and task call. Yosys builds the cover's enable from those guards
  when it elaborates the design, so no guard is parsed here. ``A`` is ``1'b1``,
  or the antecedent of a top-level ``A |-> B`` or ``A |=> B``.
* A concurrent ``assert property (A |-> B)`` at module scope gains
  ``cover property (A);`` right after it, with its clocking and
  ``disable iff``.
* A module-scope assertion with no implication is checked on every cycle: it
  has no antecedent, and is counted as unguarded.
* Anything else is not derived: a sequence operator, a nested implication, a
  named property, an action block, a deferred assertion, or a macro whose body
  asserts. Each is listed with its file, line, and reason, and the cover run
  refuses: an antecedent that could not be covered is not known to fire.

Inserted text never adds a line, so every cover keeps its assertion's line; the
exact column of each inserted cover is recorded, so a run's report can tell the
derived covers from the seat's own.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

#: Site kinds: a cover was derived (``guarded``, ``implication``), none was needed, or none could be.
DERIVED = ("guarded", "implication")
#: The condition of a cover that is reached whenever its procedural path is.
ALWAYS = "1'b1"

_TOKEN = re.compile(r"""
    (?P<ws>\s+)
  | (?P<comment>//[^\n]*|/\*.*?\*/)
  | (?P<string>"(?:\\.|[^"\\\n])*")
  | (?P<define>`define\b(?:\\\n|[^\n])*)
  | (?P<line_directive>`(?:timescale|include|default_nettype|line|resetall|celldefine|endcelldefine)\b[^\n]*)
  | (?P<cond_directive>`(?:ifdef|ifndef|elsif|undef)\s+\w+|`(?:else|endif)\b)
  | (?P<attr>\(\*(?!\s*\)).*?\*\))
  | (?P<word>[A-Za-z_$][\w$]*|`[A-Za-z_]\w*|\\\S+)
  | (?P<number>\d[\d_]*(?:\.\d+)?|'[sS]?[bBoOdDhH]\s*[0-9a-fA-FxXzZ_?]+|'[01xXzZ])
  | (?P<op>\|->|\|=>|\#\#|::|\[\*|\[=|\[->|.)
""", re.S | re.X)

_SKIP = {"ws", "comment", "attr", "line_directive", "cond_directive"}
_PROCEDURAL = {"always", "always_ff", "always_comb", "always_latch", "initial", "final"}
_CASE = {"case", "casez", "casex", "randcase"}
_SEQUENCE_OPS = {"##", "[*", "[=", "[->"}
_SEQUENCE_WORDS = {"throughout", "within", "intersect", "until", "s_until", "until_with", "s_until_with",
                   "eventually", "s_eventually", "nexttime", "s_nexttime", "always", "s_always",
                   "first_match", "and", "or", "not", "implies", "if", "case", "strong", "weak",
                   "accept_on", "reject_on", "sync_accept_on", "sync_reject_on"}


@dataclass(frozen=True)
class Site:
    """One assertion, and what was derived for it."""

    file: str
    line: int
    kind: str  # guarded, implication, unguarded, or underived
    assertion: str
    #: The 1-based column of the derived cover in the copy (0 when none was derived).
    column: int = 0
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def where(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass(frozen=True)
class Derivation:
    text: str
    sites: tuple[Site, ...]

    @property
    def underived(self) -> list[Site]:
        return [s for s in self.sites if s.kind == "underived"]

    @property
    def derived(self) -> list[Site]:
        return [s for s in self.sites if s.kind in DERIVED]


@dataclass(frozen=True)
class _Tok:
    text: str
    start: int
    end: int


def _tokens(text: str) -> tuple[list[_Tok], list[_Tok]]:
    """Significant tokens, and ``define`` directives (kept apart: a macro body is not parsed)."""
    toks, defines = [], []
    for m in _TOKEN.finditer(text):
        kind = m.lastgroup
        if kind == "define":
            defines.append(_Tok(m.group(), m.start(), m.end()))
        elif kind not in _SKIP:
            toks.append(_Tok(m.group(), m.start(), m.end()))
    return toks, defines


def _close(T: list[_Tok], i: int) -> int:
    """``T[i]`` opens a parenthesis: the index after the one that closes it."""
    depth = 0
    for j in range(i, len(T)):
        if T[j].text == "(":
            depth += 1
        elif T[j].text == ")":
            depth -= 1
            if depth == 0:
                return j + 1
    return len(T)


def _match(T: list[_Tok], i: int, opens: set[str], closes: set[str]) -> int:
    depth = 0
    for j in range(i, len(T)):
        if T[j].text in opens:
            depth += 1
        elif T[j].text in closes:
            depth -= 1
            if depth == 0:
                return j + 1
    return len(T)


def _semi(T: list[_Tok], i: int) -> int:
    depth = 0
    for j in range(i, len(T)):
        t = T[j].text
        if t in "([{" and len(t) == 1:
            depth += 1
        elif t in ")]}" and len(t) == 1:
            depth -= 1
        elif t == ";" and depth <= 0:
            return j + 1
    return len(T)


def _labelled(T: list[_Tok], j: int) -> int:
    return j + 2 if j + 1 < len(T) and T[j].text == ":" else j


def _word(t: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][\w$]*", t))


def _statement(T: list[_Tok], i: int) -> int:
    """The index after the procedural statement that starts at ``T[i]``."""
    n = len(T)
    while i < n:
        t = T[i].text
        if t in ("unique", "unique0", "priority"):
            i += 1
        elif t in ("@", "#"):
            i = _close(T, i + 1) if i + 1 < n and T[i + 1].text == "(" else i + 2
        elif i + 1 < n and T[i + 1].text == ":" and _word(t) and t not in ("default",):
            i += 2  # a statement label
        else:
            break
    if i >= n:
        return n
    t = T[i].text
    if t == "begin":
        return _labelled(T, _match(T, i, {"begin"}, {"end"}))
    if t == "fork":
        return _labelled(T, _match(T, i, {"fork"}, {"join", "join_any", "join_none"}))
    if t in _CASE:
        return _match(T, i, _CASE, {"endcase"})
    if t == "if":
        j = _statement(T, _close(T, i + 1))
        return _statement(T, j + 1) if j < n and T[j].text == "else" else j
    if t in ("for", "while", "repeat", "foreach"):
        return _statement(T, _close(T, i + 1))
    if t == "forever":
        return _statement(T, i + 1)
    if t == "do":
        return _semi(T, _statement(T, i + 1))
    return _semi(T, i)


def _procedural(T: list[_Tok]) -> tuple[list[tuple[int, int]], set[str]]:
    """Token ranges of procedural code, and the names of declared properties and sequences."""
    regions, named, i = [], set(), 0
    while i < len(T):
        t = T[i].text
        if t in _PROCEDURAL:
            j = _statement(T, i + 1)
            regions.append((i, j))
            i = j
        elif t in ("task", "function"):
            j = _match(T, i, {t}, {"end" + t})
            regions.append((i, j))
            i = j
        elif t in ("property", "sequence") and (i == 0 or T[i - 1].text not in ("assert", "assume", "cover",
                                                                                "restrict", "expect")):
            if i + 1 < len(T):
                named.add(T[i + 1].text)
            i = _match(T, i, {t}, {"end" + t})
        else:
            i += 1
    return regions, named


def _split_property(T: list[_Tok], lo: int, hi: int, text: str, named: set[str]) -> tuple[str, str | None, str]:
    """A property body ``T[lo:hi]``: its clocking prefix, its antecedent (None if no implication), or a reason."""
    i, prefix_end = lo, None
    if i < hi and T[i].text == "@":
        i = _close(T, i + 1) if i + 1 < hi and T[i + 1].text == "(" else i + 2
        prefix_end = i
    if i + 1 < hi and T[i].text == "disable" and T[i + 1].text == "iff":
        i = _close(T, i + 2)
        prefix_end = i
    prefix = text[T[lo].start:T[prefix_end - 1].end] + " " if prefix_end else ""
    body = T[i:hi]
    if len(body) == 1 and body[0].text in named:
        return prefix, None, f"the named property {body[0].text} is not expanded"
    depth, arrows = 0, []
    for k, tok in enumerate(body):
        if tok.text in _SEQUENCE_OPS or tok.text in _SEQUENCE_WORDS:
            return prefix, None, f"the sequence operator {tok.text!r} is not supported"
        if tok.text == "(":
            depth += 1
        elif tok.text == ")":
            depth -= 1
        elif tok.text in ("|->", "|=>"):
            if depth:
                return prefix, None, "an implication inside parentheses is not supported"
            arrows.append(k)
    if len(arrows) > 1:
        return prefix, None, "a chain of implications is not supported"
    if not arrows:
        return prefix, None, ""
    k = arrows[0]
    if k == 0:
        return prefix, None, "an implication with no antecedent"
    return prefix, text[body[0].start:body[k - 1].end], ""


def derive(text: str, file: str) -> Derivation:
    """The file with an antecedent cover beside every assertion, and what was done for each."""
    T, defines = _tokens(text)
    regions, named = _procedural(T)
    starts = [0]
    starts += [m.end() for m in re.finditer("\n", text)]

    def line_of(offset: int) -> int:
        lo, hi = 0, len(starts)
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if starts[mid] <= offset:
                lo = mid
            else:
                hi = mid
        return lo + 1

    sites: list[Site] = []
    covers: list[tuple[int, int]] = []  # (index into sites, offset of the edit holding the cover)
    edits: list[tuple[int, str, int | None]] = []  # (offset, text, index of the cover keyword in text)
    for d in defines:
        if re.search(r"\bassert\b", d.text):
            name = re.match(r"`define\s+(\w*)", d.text)[1] or "?"
            sites.append(Site(file, line_of(d.start), "underived", d.text.strip()[:120],
                              reason=f"the macro {name} asserts, and a macro body is not expanded"))

    for k, tok in enumerate(T):
        if tok.text != "assert":
            continue
        procedural = any(a <= k < b for a, b in regions)
        line = line_of(tok.start)
        first = text[tok.start:].split("\n", 1)[0].strip()

        def refuse(reason: str) -> None:
            sites.append(Site(file, line, "underived", first, reason=reason))

        j = k + 1
        concurrent = j < len(T) and T[j].text == "property"
        if concurrent:
            j += 1
        if j < len(T) and T[j].text in ("final", "#"):
            refuse("a deferred assertion is not supported")
            continue
        if j >= len(T) or T[j].text != "(":
            refuse("not of the form assert (...) or assert property (...)")
            continue
        close = _close(T, j)
        if close >= len(T) or T[close].text != ";":
            refuse("an assertion with an action block is not supported")
            continue
        end = T[close].end
        statement = text[tok.start:end]
        if concurrent:
            prefix, antecedent, why = _split_property(T, j + 1, close - 1, text, named)
            if why:
                refuse(why)
                continue
        else:
            inner = {t.text for t in T[j + 1:close - 1]}
            if inner & ({"|->", "|=>"} | _SEQUENCE_OPS):
                refuse("an immediate assertion cannot hold a property operator")
                continue
            prefix, antecedent = "", None
        keyword = "cover property" if concurrent else "cover"
        if procedural:
            cover = f"{keyword} ({prefix}{antecedent or ALWAYS});"
            edits.append((tok.start, f"begin {cover} ", len("begin ")))
            edits.append((end, " end", None))
            kind = "implication" if antecedent else "guarded"
        elif antecedent:
            cover = f"{keyword} ({prefix}{antecedent});"
            edits.append((end, f" {cover}", 1))
            kind = "implication"
        else:
            sites.append(Site(file, line, "unguarded", first))
            continue
        covers.append((len(sites), edits[-2][0] if procedural else end))
        sites.append(Site(file, line, kind, first))

    # Apply the edits, and record the column (1-based, in the copy) where each derived cover landed.
    out, last, shift, landed = [], 0, 0, {}
    for offset, insert, at in sorted(edits, key=lambda e: e[0]):
        out.append(text[last:offset])
        if at is not None:
            landed[offset] = offset + shift + at
        out.append(insert)
        shift += len(insert)
        last = offset
    out.append(text[last:])
    copy = "".join(out)
    for index, offset in covers:
        pos = landed[offset]
        s = sites[index]
        sites[index] = Site(s.file, s.line, s.kind, s.assertion, pos - copy.rfind("\n", 0, pos), s.reason)
    return Derivation(copy, tuple(sorted(sites, key=lambda s: s.line)))
