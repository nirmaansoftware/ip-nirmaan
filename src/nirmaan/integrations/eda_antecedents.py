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
* M37: a named property (``property p(x); ... endproperty``) used as a whole
  property body is inlined in the copy, its formal arguments replaced by the
  actual ones, and its declaration blanked; a use of a macro whose body asserts
  is expanded in the copy. Each is then derived as written code.
* Anything else is not derived: a sequence operator, a nested implication, a
  named property inside an expression, a named sequence, an action block, a
  deferred assertion, or a macro that asserts and cannot be expanded. Each is
  listed with its file, line, and reason, and the cover run refuses: an
  antecedent that could not be covered is not known to fire.

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
    for tok in body:
        if tok.text in named:
            return prefix, None, f"the named sequence {tok.text} is not expanded"
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


def derive(text: str, file: str, defs: Definitions | None = None) -> Derivation:
    """The file with an antecedent cover beside every assertion, and what was done for each.

    ``defs`` are the macros and properties of every file the run reads (``definitions``); by default, this
    file's own.
    """
    defs = defs or definitions([text])
    sites: list[Site] = []
    # Expansion and inlining never add or remove a line, but they move offsets: lines are counted after them.
    text = _expand_macros(text, file, defs, sites)
    text = _inline_properties(text, file, defs, sites)
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

    T, _ = _tokens(text)
    regions, named = _procedural(T)
    covers: list[tuple[int, int]] = []  # (index into sites, offset of the edit holding the cover)
    edits: list[tuple[int, str, int | None]] = []  # (offset, text, index of the cover keyword in text)

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


# --- M37: macros that assert, and named properties ---------------------------------------------------------

#: How deep a named property may name another, or a macro expand into another.
MAX_DEPTH = 8
_ASSERTING = re.compile(r"\bassert\b")


@dataclass(frozen=True)
class Macro:
    name: str
    formals: tuple[str, ...] | None  # None: used without parentheses
    body: str
    definitions: int = 1


@dataclass(frozen=True)
class Property:
    name: str
    formals: tuple[tuple[str, str | None], ...]  # each name, and its default
    body: str


@dataclass(frozen=True)
class Definitions:
    """The macros, named properties, and named sequences of every file a run reads."""

    macros: dict[str, Macro]
    properties: dict[str, Property]
    sequences: frozenset[str]

    @property
    def asserting(self) -> set[str]:
        """Macros whose body asserts, directly or through another macro."""
        found = {m.name for m in self.macros.values() if _ASSERTING.search(m.body)}
        while True:
            more = {m.name for m in self.macros.values() if m.name not in found
                    and any(re.search(rf"`{re.escape(n)}\b", m.body) for n in found)}
            if not more:
                return found
            found |= more


def _split_top(T: list[_Tok], lo: int, hi: int, text: str) -> list[str]:
    """The comma-separated parts of ``T[lo:hi]`` at bracket depth zero, as text."""
    parts, depth, start = [], 0, lo
    for k in range(lo, hi):
        t = T[k].text
        if t in ("(", "[", "{"):
            depth += 1
        elif t in (")", "]", "}"):
            depth -= 1
        elif t == "," and depth == 0:
            parts.append(text[T[start].start:T[k - 1].end] if k > start else "")
            start = k + 1
    if hi > start:
        parts.append(text[T[start].start:T[hi - 1].end])
    return [p.strip() for p in parts]


def _macro(directive: str) -> Macro | None:
    m = re.match(r"`define\s+([A-Za-z_]\w*)(\()?", directive)
    if not m:
        return None
    rest = directive[m.end():]
    formals = None
    if m[2]:
        close = rest.find(")")
        formals = tuple(f.split("=")[0].strip() for f in rest[:close].split(",") if f.strip())
        rest = rest[close + 1:]
    return Macro(m[1], formals, " ".join(rest.replace("\\\n", " ").split()))


def definitions(texts) -> Definitions:
    """The macros, named properties, and named sequences declared across these files' texts."""
    macros: dict[str, Macro] = {}
    properties: dict[str, Property] = {}
    sequences: set[str] = set()
    for text in texts:
        T, defines = _tokens(text)
        for d in defines:
            macro = _macro(d.text)
            if macro:
                seen = macros.get(macro.name)
                macros[macro.name] = Macro(macro.name, macro.formals, macro.body,
                                           (seen.definitions + 1) if seen else 1)
        for start, end in _declarations(T):
            name = T[start + 1].text
            if T[start].text == "sequence":
                sequences.add(name)
                continue
            j, formals = start + 2, ()
            if j < end and T[j].text == "(":
                close = _close(T, j)
                formals = tuple(_formal(f) for f in _split_top(T, j + 1, close - 1, text) if f)
                j = close
            body = T[j + 1:end - 1]  # after the header's ';', before endproperty
            if body and body[-1].text == ";":
                body = body[:-1]
            properties[name] = Property(name, formals,
                                        " ".join(text[body[0].start:body[-1].end].split()) if body else "")
    return Definitions(macros, properties, frozenset(sequences))


def _formal(text: str) -> tuple[str, str | None]:
    head, _, default = text.partition("=")
    return re.findall(r"[A-Za-z_][\w$]*", head)[-1], (default.strip() or None)


def _declarations(T: list[_Tok]) -> list[tuple[int, int]]:
    """Token ranges of ``property`` and ``sequence`` declarations (not ``assert property``)."""
    found, i = [], 0
    while i < len(T):
        t = T[i].text
        if t in ("property", "sequence") and (i == 0 or T[i - 1].text not in _STATEMENTS) and i + 1 < len(T):
            end = _match(T, i, {t}, {"end" + t})
            found.append((i, end))
            i = end
        else:
            i += 1
    return found


_STATEMENTS = ("assert", "assume", "cover", "restrict", "expect")


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _blank(text: str, start: int, end: int) -> str:
    """``text`` with ``[start, end)`` replaced by spaces, newlines kept."""
    return text[:start] + re.sub(r"[^\n]", " ", text[start:end]) + text[end:]


def _substitute(body: str, values: dict[str, str]) -> str:
    """``body`` with each word token named in ``values`` replaced (comments and strings untouched)."""
    T, _ = _tokens(body)
    out, last = [], 0
    for tok in T:
        if tok.text in values and _word(tok.text):
            out += [body[last:tok.start], values[tok.text]]
            last = tok.end
    return "".join(out) + body[last:]


def _expand_macros(text: str, file: str, defs: Definitions, sites: list[Site]) -> str:
    """Each use of a macro that asserts, expanded in place; a use that cannot be is refused and blanked."""
    asserting = defs.asserting
    for _ in range(MAX_DEPTH):
        T, _ = _tokens(text)
        uses = [k for k, tok in enumerate(T) if tok.text.startswith("`") and tok.text[1:] in asserting]
        if not uses:
            return text
        for k in reversed(uses):
            macro = defs.macros[T[k].text[1:]]
            end, actuals = k + 1, []
            if macro.formals is not None and end < len(T) and T[end].text == "(":
                close = _close(T, end)
                actuals = _split_top(T, end + 1, close - 1, text) if close - 1 > end + 1 else []
                end = close
            given = len(actuals) if macro.formals is not None and k + 1 < len(T) and T[k + 1].text == "(" else 0
            reason = None
            if macro.definitions > 1:
                reason = f"the macro {macro.name} is defined more than once"
            elif "``" in macro.body or '`"' in macro.body:
                reason = f"the macro {macro.name} pastes or stringifies tokens"
            elif macro.formals is not None and given != len(macro.formals):
                reason = f"the macro {macro.name} takes {len(macro.formals)} arguments, {given} given"
            if end < len(T) and T[end].text == ";":
                end += 1
            start, stop = T[k].start, T[end - 1].end
            if reason:
                sites.append(Site(file, _line(text, start), "underived", text[start:stop].split("\n")[0].strip(),
                                  reason=reason))
                text = _blank(text, start, stop)
                continue
            body = macro.body
            if macro.formals:
                body = _substitute(body, dict(zip(macro.formals, actuals)))
            expansion = body + (";" if T[end - 1].text == ";" else "")
            text = text[:start] + expansion + "\n" * text.count("\n", start, stop) + text[stop:]
    T, _ = _tokens(text)
    for tok in reversed([t for t in T if t.text.startswith("`") and t.text[1:] in asserting]):
        sites.append(Site(file, _line(text, tok.start), "underived", tok.text,
                          reason=f"the macro {tok.text[1:]} expands too deeply"))
        text = _blank(text, tok.start, tok.end)
    return text


def _clocked(T: list[_Tok], lo: int, hi: int) -> int:
    """The index after a leading clocking event and ``disable iff`` in ``T[lo:hi]``."""
    i = lo
    if i < hi and T[i].text == "@":
        i = _close(T, i + 1) if i + 1 < hi and T[i + 1].text == "(" else i + 2
    if i + 1 < hi and T[i].text == "disable" and T[i + 1].text == "iff":
        i = _close(T, i + 2)
    return i


def _inline(defs: Definitions, text: str, clocked: bool, depth: int = 0,
            top: str | None = None) -> tuple[str | None, str]:
    """A property body ``text`` (after any clocking) with named properties inlined, or None and a reason."""
    T, _ = _tokens(text)
    if not T or T[0].text not in defs.properties:
        for tok in T:
            if tok.text in defs.properties:
                return None, (f"the named property {tok.text} is used inside an expression; "
                              "only a whole property body is inlined")
        return text, ""
    prop = defs.properties[T[0].text]
    actuals: list[str] = []
    if len(T) > 1:
        if T[1].text != "(" or _close(T, 1) != len(T):
            return None, (f"the named property {prop.name} is used inside an expression; "
                          "only a whole property body is inlined")
        actuals = _split_top(T, 2, len(T) - 1, text) if len(T) > 3 else []
    top = top or prop.name
    if depth >= MAX_DEPTH:
        return None, f"property {top} is nested too deeply"
    if any(a.startswith(".") for a in actuals):
        return None, "named arguments to a property are not supported"
    if len(actuals) > len(prop.formals) or any(d is None for _, d in prop.formals[len(actuals):]):
        return None, f"property {prop.name} takes {len(prop.formals)} arguments, {len(actuals)} given"
    values = {name: f"({a})" for (name, _), a in zip(prop.formals, actuals)}
    values |= {name: f"({d})" for name, d in prop.formals[len(actuals):] if d is not None}
    body = _substitute(prop.body, values)
    B, _ = _tokens(body)
    after = _clocked(B, 0, len(B))
    if after and clocked and B[0].text == "@":
        return None, f"both the assertion and property {prop.name} name a clock"
    prefix = body[:B[after - 1].end] + " " if after else ""
    inner, why = _inline(defs, body[B[after].start:] if after < len(B) else "", clocked or after > 0, depth + 1, top)
    return (None, why) if inner is None else (prefix + inner, "")


def _inline_properties(text: str, file: str, defs: Definitions, sites: list[Site]) -> str:
    """Each assertion, assumption, or cover of a named property, inlined; the declarations blanked."""
    if not defs.properties:
        return text
    T, _ = _tokens(text)
    edits: list[tuple[int, int, str | None]] = []  # (start, end, replacement or None to blank)
    for k, tok in enumerate(T):
        if tok.text not in _STATEMENTS or k + 2 >= len(T) or T[k + 1].text != "property" or T[k + 2].text != "(":
            continue
        close = _close(T, k + 2)
        lo, hi = k + 3, close - 1
        after = _clocked(T, lo, hi)
        if not any(T[j].text in defs.properties for j in range(after, hi)):
            continue
        inlined, why = _inline(defs, text[T[after].start:T[hi - 1].end] if after < hi else "", after > lo)
        if inlined is None:
            if tok.text == "assert":
                stop = T[close].end if close < len(T) and T[close].text == ";" else T[close - 1].end
                sites.append(Site(file, _line(text, tok.start), "underived",
                                  text[tok.start:].split("\n", 1)[0].strip(), reason=why))
                edits.append((tok.start, stop, None))
            continue
        prefix = text[T[lo].start:T[after - 1].end] + " " if after > lo else ""
        edits.append((T[lo].start, T[hi - 1].end, prefix + " ".join(inlined.split())))
    edits += [(T[a].start, T[b - 1].end, None) for a, b in _declarations(T) if T[a].text == "property"]
    for start, end, replacement in sorted(edits, reverse=True):
        text = _blank(text, start, end) if replacement is None else (
            text[:start] + replacement + "\n" * text.count("\n", start, end) + text[end:])
    return text
