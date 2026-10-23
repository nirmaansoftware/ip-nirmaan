"""The review teams map (.github/review-teams.yml): loader, ownership, classification.

Shared by tests/test_review_teams.py (the coverage test) and scripts/pr_review.py
(the pull request review script). The suite and the script have no YAML
dependency, so the map is read by a small loader for the plain subset of YAML
the file uses (block maps and lists, one-line flow lists, quoted and plain
scalars, comments). The loader refuses anything else rather than guess.

`classify` computes what a pull request needs from the map on main: the owning
teams and which lead of each holds key 1, the founder classes, and the content
rule and section hits, from the changed files and the diff.
"""

from __future__ import annotations

import re


# --- A loader for the YAML subset the map uses -----------------------------------


class MapSyntaxError(ValueError):
    pass


def _strip_comment(line: str) -> str:
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def _split_flow(body: str) -> list[str]:
    items, current, quote = [], "", None
    for ch in body:
        if quote:
            current += ch
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            current += ch
        elif ch == ",":
            items.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        items.append(current.strip())
    return items


def _scalar(text: str, number: int):
    text = text.strip()
    if text.startswith("["):
        if not text.endswith("]"):
            raise MapSyntaxError(f"line {number}: unclosed flow list")
        return [_scalar(item, number) for item in _split_flow(text[1:-1])]
    if text.startswith("'"):
        if not text.endswith("'") or len(text) < 2:
            raise MapSyntaxError(f"line {number}: unclosed quote")
        return text[1:-1].replace("''", "'")
    if text.startswith('"'):
        if not text.endswith('"') or len(text) < 2 or "\\" in text:
            raise MapSyntaxError(f"line {number}: use single quotes for escapes")
        return text[1:-1]
    if not text or text[0] in "*&!{|>%@`-?:," or ": " in text or " #" in text:
        raise MapSyntaxError(f"line {number}: quote this scalar: {text!r}")
    if text.isdigit():
        return int(text)
    if text in ("true", "false", "null", "~", "yes", "no", "on", "off"):
        raise MapSyntaxError(f"line {number}: quote {text!r} or avoid it")
    return text


def load_map(text: str):
    lines = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if "\t" in raw:
            raise MapSyntaxError(f"line {number}: tab")
        stripped = _strip_comment(raw)
        if stripped.strip():
            lines.append((len(stripped) - len(stripped.lstrip(" ")), stripped.strip(), number))

    def key_value(content: str, number: int):
        match = re.fullmatch(r"([A-Za-z0-9_-]+):(?: (.*))?", content)
        if not match:
            raise MapSyntaxError(f"line {number}: expected 'key: value', got {content!r}")
        return match.group(1), match.group(2)

    def block(i: int, indent: int):
        if lines[i][1].startswith("- ") or lines[i][1] == "-":
            return seq(i, indent)
        return mapping(i, indent)

    def child(i: int, indent: int, number: int):
        if i < len(lines) and lines[i][0] > indent:
            return block(i, lines[i][0])
        raise MapSyntaxError(f"line {number}: empty value")

    def mapping(i: int, indent: int):
        out = {}
        while i < len(lines) and lines[i][0] == indent and not lines[i][1].startswith("- "):
            _, content, number = lines[i]
            key, rest = key_value(content, number)
            if key in out:
                raise MapSyntaxError(f"line {number}: duplicate key {key!r}")
            if rest is None or rest == "":
                out[key], i = child(i + 1, indent, number)
            else:
                out[key], i = _scalar(rest, number), i + 1
        if i < len(lines) and lines[i][0] > indent:
            raise MapSyntaxError(f"line {lines[i][2]}: unexpected indentation")
        return out, i

    def seq(i: int, indent: int):
        out = []
        while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
            _, content, number = lines[i]
            rest = content[2:]
            if re.match(r"[A-Za-z0-9_-]+:( |$)", rest):
                lines[i] = (indent + 2, rest, number)  # the item is a map
                item, i = mapping(i, indent + 2)
            else:
                item, i = _scalar(rest, number), i + 1
            out.append(item)
        if i < len(lines) and lines[i][0] > indent:
            raise MapSyntaxError(f"line {lines[i][2]}: unexpected indentation")
        return out, i

    if not lines:
        return {}
    value, end = block(0, lines[0][0])
    if end != len(lines):
        raise MapSyntaxError(f"line {lines[end][2]}: unexpected content")
    return value


# --- Globs and ownership --------------------------------------------------------------


def glob_regex(glob: str) -> re.Pattern:
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif glob.startswith("**", i):
            out, i = out + ".*", i + 2
        elif glob[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif glob[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(glob[i]), i + 1
    return re.compile(out)


def matches(glob: str, path: str) -> bool:
    return glob_regex(glob).fullmatch(path) is not None


def winning_rule(teams_map: dict, path: str):
    """The index of the last rule with a glob that matches the path, or None."""
    found = None
    for index, rule in enumerate(teams_map["rules"]):
        if any(matches(glob, path) for glob in rule["paths"]):
            found = index
    return found


def owning_teams(teams_map: dict, path: str) -> set[str]:
    index = winning_rule(teams_map, path)
    if index is None:
        return set()
    rule = teams_map["rules"][index]
    return {rule["team"], *rule.get("co_owners", [])}


# --- What a pull request needs, from the map on main -----------------------------


def parse_name_status(out: str) -> list[dict]:
    """`git diff --name-status -z -M` output as [{status, path, old}]."""
    parts = [p for p in out.split("\0") if p]
    files, i = [], 0
    while i < len(parts):
        status = parts[i]
        if status[0] in "RC":
            files.append({"status": status[0], "old": parts[i + 1], "path": parts[i + 2]})
            i += 3
        else:
            files.append({"status": status[0], "old": None, "path": parts[i + 1]})
            i += 2
    return files


def changed_lines(diff: str) -> dict[str, list[tuple[str, int, str]]]:
    """Changed lines per file of a unified diff: (sign, line number, text).

    Added lines carry their number at the head, removed lines their number at
    the base. Removed lines count: deleting a price or a gate limit matters too.
    """
    out: dict[str, list[tuple[str, int, str]]] = {}
    path = old_path = None
    old_no = new_no = 0
    in_header = False
    for raw in diff.split("\n"):
        if raw.startswith("diff --git "):
            in_header, path, old_path = True, None, None
            continue
        hunk = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
        if hunk:
            in_header = False
            old_no, new_no = int(hunk.group(1)), int(hunk.group(2))
            continue
        if in_header:
            if raw.startswith("--- "):
                old_path = None if raw == "--- /dev/null" else raw[4:].removeprefix("a/")
            elif raw.startswith("+++ "):
                path = None if raw == "+++ /dev/null" else raw[4:].removeprefix("b/")
            continue
        name = path or old_path
        if name is None:
            continue
        if raw.startswith("+"):
            out.setdefault(name, []).append(("+", new_no, raw[1:]))
            new_no += 1
        elif raw.startswith("-"):
            out.setdefault(name, []).append(("-", old_no, raw[1:]))
            old_no += 1
        elif raw.startswith(" "):
            old_no += 1
            new_no += 1
    return out


def marker_ranges(text: str, begin: str, end: str) -> list[tuple[int, int]]:
    """1-based inclusive line ranges bounded by a begin and an end marker."""
    ranges, start = [], None
    for number, line in enumerate(text.splitlines(), start=1):
        if start is None and begin in line:
            start = number
        elif start is not None and end in line:
            ranges.append((start, number))
            start = None
    return ranges


def _in_ranges(number: int, ranges: list[tuple[int, int]]) -> bool:
    return any(a <= number <= b for a, b in ranges)


def _applies(rule: dict, path: str) -> bool:
    return "in" not in rule or any(matches(glob, path) for glob in rule["in"])


def classify(teams_map: dict, files: list[dict], diff: str, read_head, read_base) -> dict:
    """Owning teams (with the lead or leads that hold key 1), founder classes and hits.

    `read_head(path)` and `read_base(path)` return a file's text or None; they
    are used to place changed lines inside marker sections.
    """
    teams = teams_map["teams"]
    lines = changed_lines(diff)
    owners: dict[str, set] = {}  # team -> named leads (empty: the team's default lead)
    founder: dict[str, list[str]] = {}
    hits: list[str] = []

    def add(team: str, lead: str | None, why: str):
        owners.setdefault(team, set())
        if lead:
            owners[team].add(lead)

    def flag(cls: str, why: str):
        founder.setdefault(cls, [])
        if why not in founder[cls]:
            founder[cls].append(why)

    def ranges(path: str, sign: str, begin: str, end: str):
        text = read_head(path) if sign == "+" else read_base(path)
        return marker_ranges(text or "", begin, end)

    def section_lines(path: str, section: dict) -> list:
        return [ln for ln in lines.get(path, []) if _in_ranges(ln[1], ranges(path, ln[0], section["begin"], section["end"]))]

    ledger = teams_map.get("ledger", {})
    paths = []
    for f in files:
        paths.extend([f["old"], f["path"]] if f["old"] else [f["path"]])

    def is_ledger(path: str) -> bool:
        if any(matches(glob, path) for glob in ledger.get("paths", [])):
            return True
        sections = [s for s in ledger.get("sections", []) if s["file"] == path]
        changed = lines.get(path, [])
        if not sections or not changed:
            return False
        return all(any(_in_ranges(ln[1], ranges(path, ln[0], s["begin"], s["end"])) for s in sections) for ln in changed)

    ledger_files = {p for p in paths if is_ledger(p)}
    skip = ledger_files if len(ledger_files) < len(set(paths)) else set()

    for path in paths:
        if path in skip:
            continue
        index = winning_rule(teams_map, path)
        if index is not None:
            rule = teams_map["rules"][index]
            add(rule["team"], rule.get("lead"), f"path {path}")
            for co in rule.get("co_owners", []):
                add(co, None, f"path {path}")
        for section in teams_map.get("sections", []):
            if section["file"] == path and section_lines(path, section):
                add(section["team"], section.get("lead"), f"section {section['id']}")
                for co in section.get("co_owners", []):
                    add(co, None, f"section {section['id']}")
                hits.append(f"section {section['id']} in {path}")
        for rule in teams_map.get("content_rules", []):
            if not _applies(rule, path):
                continue
            pattern = re.compile(rule["pattern"])
            if any(pattern.search(text) for _, _, text in lines.get(path, [])):
                add(rule["adds"], rule.get("lead"), f"content {rule['id']}")
                hits.append(f"{rule['id']} in {path}")

    # Founder classes look at every changed file, ledger files included.
    for cls in teams_map.get("founder_classes", []):
        for path in paths:
            if any(matches(glob, path) for glob in cls.get("paths", [])):
                flag(cls["id"], f"path {path}")
            for trigger in cls.get("content", []):
                if _applies(trigger, path) and any(re.search(trigger["pattern"], text) for _, _, text in lines.get(path, [])):
                    flag(cls["id"], f"content in {path}")
        for section_id in cls.get("sections", []):
            for section in teams_map.get("sections", []):
                if section["id"] == section_id and section["file"] in paths and section_lines(section["file"], section):
                    flag(cls["id"], f"section {section_id}")

    keys = []
    for team_id in teams:
        if team_id not in owners:
            continue
        leads = teams[team_id].get("leads", [])
        named = [lead for lead in leads if lead in owners[team_id]] or leads[:1]
        for lead in named:
            keys.append({"team": team_id, "name": teams[team_id]["name"], "lead": lead})
    return {
        "teams": [t for t in teams if t in owners],
        "keys": keys,
        "founder": founder,
        "hits": sorted(set(hits)),
        "ledger": sorted(ledger_files),
    }


# --- Composite key 1 (council record 2026-10-18, review loop, decision 1) ---------


def _member_team(teams: dict, seat: str) -> str | None:
    return next((t for t, team in teams.items() if seat in team.get("members", [])), None)


def _lead_team(teams: dict, seat: str) -> str | None:
    return next((t for t, team in teams.items() if seat in team.get("leads", [])), None)


def key1_plan(teams_map: dict, classification: dict, files: list[dict], diff: str, read_head, read_base) -> dict:
    """What one composite key-1 call loads, from the `composite_key1` data in
    main's map: the seat that speaks and every checklist, each with why it loaded.

    The speaker is the lead of the owning team that comes first in
    `precedence`; its seat file loads whole. Loaded: the "In a review" section
    of every owning team's lead (the teams `classify` found, plus the teams the
    composite content rules add), every member checklist whose trigger
    matches, and the `always` seats. Member checklists load by trigger, never
    by team membership, unless the trigger names the team. Returns
    {"speaker": {team, name, lead} or None, "checklists": [{seat, kind, team, why}]}.
    """
    data = teams_map.get("composite_key1") or {}
    teams = teams_map["teams"]
    lines = changed_lines(diff)
    paths: list[str] = []
    for f in files:
        paths.extend([f["old"], f["path"]] if f["old"] else [f["path"]])

    def content_hit(trigger: dict) -> str | None:
        pattern = re.compile(trigger["pattern"])
        for path in paths:
            if _applies(trigger, path) and any(pattern.search(text) for _, _, text in lines.get(path, [])):
                return path
        return None

    keys = list(classification["keys"])
    owning = list(classification["teams"])
    for rule in data.get("content_rules", []):
        path = content_hit(rule)
        if path is None:
            continue
        team = rule["adds"]
        lead = rule.get("lead") or teams[team].get("leads", [None])[0]
        if team not in owning:
            owning.append(team)
        if not any(k["team"] == team and k["lead"] == lead for k in keys):
            keys.append({"team": team, "name": teams[team]["name"], "lead": lead, "why": f"content {rule['id']} in {path}"})
    order = {team: i for i, team in enumerate(data.get("precedence", []))}
    keys.sort(key=lambda k: order.get(k["team"], len(order)))

    loaded: list[dict] = []

    def add(seat: str, kind: str, team: str | None, why: str):
        if not any(c["seat"] == seat for c in loaded):
            loaded.append({"seat": seat, "kind": kind, "team": team, "why": why})

    for k in keys:
        add(k["lead"], "lead", k["team"], k.get("why") or f"lead of the owning team {k['name']}")
    for member in data.get("members", []):
        whys = [f"team {team} owns the pull request" for team in member.get("teams", []) if team in owning]
        whys += [f"path {p}" for p in paths if any(matches(g, p) for g in member.get("paths", []))][:2]
        whys += [f"content in {p}" for p in [content_hit(t) for t in member.get("content", [])] if p]
        for r in member.get("ranges", []):
            if r["file"] not in lines:
                continue
            text_of = {"+": read_head(r["file"]), "-": read_base(r["file"])}
            spans = {sign: marker_ranges(text or "", r["begin"], r["end"]) for sign, text in text_of.items()}
            if any(_in_ranges(n, spans[sign]) for sign, n, _ in lines.get(r["file"], [])):
                whys.append(f"lines in {r['file']} from {r['begin'].strip()!r}")
        if whys:
            add(member["seat"], "member", _member_team(teams, member["seat"]), "; ".join(whys))
    for seat in data.get("always", []):
        add(seat, "always", _lead_team(teams, seat) or _member_team(teams, seat), "loads on every head")
    return {"speaker": ({k: keys[0][k] for k in ("team", "name", "lead")} if keys else None), "checklists": loaded}
