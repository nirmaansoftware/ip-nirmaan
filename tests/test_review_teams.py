"""The review teams map (.github/review-teams.yml) against the tracked tree.

Council record 2026-10-17 (teams and the PR review mechanism), rollout R1:
every tracked file maps to a team; no rule is dead (a glob that matches no
tracked file, as the draft's `src/nirmaan/design*` and `src/nirmaan/tools*`
did, or a rule that later rules shadow everywhere); every seat the map names
has a file in council/; every marker comment a section relies on exists; and
.github/CODEOWNERS names the founder on exactly the founder class path globs.

The suite has no YAML dependency, so the map is read by a small loader for the
plain subset of YAML the file uses (block maps and lists, one-line flow lists,
quoted and plain scalars, comments). The loader refuses anything else rather
than guess. The pull request review script (rollout R5) will reuse this logic.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / ".github" / "review-teams.yml"
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
FOUNDER = "@nirmaansoftware"

# The founder approved these Silicon Design seats on 2026-10-17; their files
# are added by the council/new-seats pull request (T17). Until it is merged a
# missing file is tolerated for these three names only; once the files exist
# they are checked like every other seat.
PENDING_SEATS = {"dft-engineer", "physical-design-engineer", "firmware-engineer"}


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


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout
    return [p for p in out.decode().split("\0") if p]


def problems(teams_map: dict, files: list[str], seat_files: set[str]) -> list[str]:
    """Every way the map can disagree with the tree. Empty means the map is sound."""
    found: list[str] = []
    teams = teams_map["teams"]
    for index, rule in enumerate(teams_map["rules"]):
        for team in [rule["team"], *rule.get("co_owners", [])]:
            if team not in teams:
                found.append(f"rule {index}: unknown team {team!r}")
        lead = rule.get("lead")
        if lead is not None and lead not in teams.get(rule["team"], {}).get("leads", []):
            found.append(f"rule {index}: {lead!r} is not a lead of {rule['team']!r}")
        if len(teams.get(rule["team"], {}).get("leads", [])) > 1 and lead is None:
            found.append(f"rule {index}: team {rule['team']!r} has several leads; name one")
    winners = {path: winning_rule(teams_map, path) for path in files}
    for path, index in winners.items():
        if index is None:
            found.append(f"unmapped file: {path}")
    won = set(winners.values())
    for index, rule in enumerate(teams_map["rules"]):
        for glob in rule["paths"]:
            if not any(matches(glob, path) for path in files):
                found.append(f"dead glob (matches no tracked file): {glob}")
        if index not in won:
            found.append(f"dead rule {index} {rule['paths']}: later rules win every file it matches")
    for team_id, team in teams.items():
        named = list(team.get("leads", [])) + list(team.get("members", []))
        if "key2" in team:
            named.append(team["key2"])
        if not team.get("leads"):
            found.append(f"team {team_id!r} has no lead")
        for seat in named:
            if seat not in seat_files and seat not in PENDING_SEATS:
                found.append(f"team {team_id!r} names {seat!r}, which has no council/{seat}.md")
    for glob in teams_map["ledger"]["paths"]:
        if not any(matches(glob, path) for path in files):
            found.append(f"dead ledger glob: {glob}")
    for founder_class in teams_map["founder_classes"]:
        for glob in founder_class.get("paths", []):
            if not any(matches(glob, path) for path in files):
                found.append(f"dead founder class glob ({founder_class['id']}): {glob}")
    return found


@pytest.fixture(scope="module")
def teams_map() -> dict:
    return load_map(MAP.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def files() -> list[str]:
    return tracked_files()


def _seat_files() -> set[str]:
    return {p.stem for p in (ROOT / "council").glob("*.md") if p.name != "README.md"}


# --- The map against the tree --------------------------------------------------------


def test_the_map_is_sound_against_the_tracked_tree(teams_map, files):
    assert MAP.relative_to(ROOT).as_posix() in files
    assert problems(teams_map, files, _seat_files()) == []


def test_every_tracked_file_maps_to_a_team(teams_map, files):
    unmapped = [p for p in files if not owning_teams(teams_map, p)]
    assert unmapped == []


def test_the_check_catches_the_drafts_dead_globs(teams_map, files):
    import copy

    broken = copy.deepcopy(teams_map)
    broken["rules"].append({"team": "silicon-design", "paths": ["src/nirmaan/design*", "src/nirmaan/tools*"]})
    found = problems(broken, files, _seat_files())
    assert "dead glob (matches no tracked file): src/nirmaan/design*" in found
    assert "dead glob (matches no tracked file): src/nirmaan/tools*" in found


def test_the_check_catches_a_shadowed_rule_and_an_unmapped_file(teams_map, files):
    import copy

    shadowed = copy.deepcopy(teams_map)
    shadowed["rules"].append({"team": "eda-platform", "paths": ["**"]})
    assert any(p.startswith("dead rule 0 ") for p in problems(shadowed, files, _seat_files()))

    no_catch_all = copy.deepcopy(teams_map)
    assert no_catch_all["rules"][0]["paths"] == ["**"]
    del no_catch_all["rules"][0]
    assert any(p.startswith("unmapped file: ") for p in problems(no_catch_all, files, _seat_files()))


def test_the_check_catches_a_seat_with_no_file(teams_map, files):
    import copy

    broken = copy.deepcopy(teams_map)
    broken["teams"]["business"]["members"].append("cto")
    assert "team 'business' names 'cto', which has no council/cto.md" in problems(broken, files, _seat_files())


def test_only_the_three_approved_seats_may_wait_for_their_files(teams_map):
    assert PENDING_SEATS == set(teams_map["teams"]["silicon-design"]["members"])
    named = {s for t in teams_map["teams"].values() for s in [*t["leads"], *t["members"]]}
    missing = {s for s in named if not (ROOT / "council" / f"{s}.md").exists()}
    assert missing <= PENDING_SEATS


@pytest.mark.parametrize(
    "path, teams",
    [
        ("tests/fixtures/rtl/axi4_lite/axi4_lite_regs.v", {"silicon-design", "verification"}),
        ("tests/fixtures/fw/axi4_lite/driver.c", {"silicon-design"}),
        ("src/nirmaan/integrations/physical.py", {"silicon-design", "eda-platform"}),
        ("src/nirmaan/integrations/dft_atpg.py", {"silicon-design"}),
        ("src/nirmaan/integrations/firmware_soc/picorv32.v", {"silicon-design", "business"}),
        ("src/nirmaan/integrations/firmware_soc/serv/serv_alu.v", {"silicon-design", "business"}),
        ("src/nirmaan/integrations/firmware_soc/serv/LICENSE", {"business"}),
        ("src/nirmaan/integrations/firmware_soc/core_serv.v", {"silicon-design"}),
        ("src/veritriage/design/x.py", {"verification", "silicon-design"}),
        ("src/veritriage/engine.py", {"verification"}),
        ("evals/rtl/sync_fifo.json", {"verification", "silicon-design"}),
        ("evals/README.md", {"verification"}),
        ("src/nirmaan/integrations/eda.py", {"eda-platform", "verification"}),
        ("src/nirmaan/integrations/eda_parsers.py", {"eda-platform"}),
        ("src/nirmaan/work/policy.py", {"eda-platform", "verification"}),
        ("src/nirmaan/runtime/tools.py", {"eda-platform", "verification"}),
        ("src/nirmaan/runtime/loop.py", {"eda-platform"}),
        ("scripts/check_dashes.py", {"eda-platform", "verification"}),
        ("scripts/status.py", {"eda-platform", "product-site"}),
        (".github/workflows/ci.yml", {"eda-platform"}),
        (".github/review-teams.yml", {"council"}),
        ("CLAUDE.md", {"council"}),
        ("council/README.md", {"council"}),
        ("council/records/2026-10-16-commercial-model-and-design-partners.md", {"business"}),
        ("site/index.html", {"product-site"}),
        ("site/assets/fonts/OFL-archivo.txt", {"business"}),
        ("README.md", {"product-site"}),
        ("LICENSE", {"business"}),
        ("src/nirmaan/company/org_chart.py", {"eda-platform"}),
        ("docs/ROADMAP.md", {"eda-platform"}),
    ],
)
def test_the_council_records_rows(teams_map, path, teams):
    assert owning_teams(teams_map, path) == teams


def test_the_lead_is_named_where_a_team_has_two(teams_map):
    def lead(path):
        return teams_map["rules"][winning_rule(teams_map, path)].get("lead")

    assert lead("council/chair.md") == "qa-evidence"
    assert lead(".github/review-teams.yml") == "security"
    assert lead("CLAUDE.md") == "security"
    assert lead("NOTICE") == "legal-compliance"
    assert lead("council/records/2026-10-16-commercial-model-and-design-partners.md") == "finance-licensing"


def test_teams_and_seats_follow_the_record(teams_map):
    teams = teams_map["teams"]
    assert set(teams) == {"council", "silicon-design", "verification", "eda-platform", "product-site", "business"}
    assert teams["council"]["key2"] == "chair"
    assert teams["silicon-design"]["leads"] == ["design-architect"]
    assert teams["verification"]["leads"] == ["verification-lead"]
    assert teams["eda-platform"]["leads"] == ["eda-tooling"]
    assert teams["product-site"]["leads"] == ["product-lead"]
    assert teams["business"]["leads"] == ["legal-compliance", "finance-licensing"]
    # Members hold no key: no seat is a member of a team it leads.
    for team in teams.values():
        assert not set(team["leads"]) & set(team["members"])
    # The catch-all is the first rule, so every later rule takes precedence.
    assert teams_map["rules"][0] == {"team": "eda-platform", "paths": ["**"]}
    assert all(rule["paths"] != ["**"] for rule in teams_map["rules"][1:])


# --- Sections, ledger and content rules -----------------------------------------------


def _pairs(text: str, begin: str, end: str) -> int:
    """How many begin/end pairs, in order and not nested; raises when unbalanced."""
    tokens = sorted([(m.start(), "b") for m in re.finditer(re.escape(begin), text)]
                    + [(m.start(), "e") for m in re.finditer(re.escape(end), text)])
    kinds = "".join(kind for _, kind in tokens)
    assert re.fullmatch(r"(be)*", kinds), (begin, kinds)
    return len(kinds) // 2


def test_every_marker_section_exists_in_its_file(teams_map, files):
    sections = teams_map["sections"] + teams_map["ledger"]["sections"]
    for section in sections:
        assert section["file"] in files, section
        text = (ROOT / section["file"]).read_text(encoding="utf-8")
        assert _pairs(text, section["begin"], section["end"]) >= 1, section
    ids = [s["id"] for s in teams_map["sections"]]
    assert len(ids) == len(set(ids))
    for section in teams_map["sections"]:
        assert {section["team"], *section.get("co_owners", [])} <= set(teams_map["teams"])


def test_the_partner_section_markers_bound_the_partner_section():
    text = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    start = text.index("<!-- review:partners:begin")
    end = text.index("<!-- review:partners:end -->")
    inside = text[start:end]
    assert '<section class="section" id="partners"' in inside
    assert inside.rstrip().endswith("</section>")
    assert 'id="partners"' not in text[:start] + text[end:]


def test_the_roadmap_markers_bound_the_named_sections():
    text = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
    numbers = re.search(r"<!-- review:milestone-numbers:begin.*?<!-- review:milestone-numbers:end -->", text, re.S)
    assert numbers and "## Milestone numbers" in numbers.group(0) and "| M55 |" in numbers.group(0)
    scope = re.findall(r"<!-- review:roadmap-scope:begin.*?<!-- review:roadmap-scope:end -->", text, re.S)
    assert [s.split("\n")[1] for s in scope] == ["## Next milestones", "## Side work (any time; owner-driven)"]
    for block in scope:
        assert "| M" not in block and "status:begin" not in block


def test_every_content_pattern_compiles_and_matches_its_example(teams_map):
    rules = list(teams_map["content_rules"])
    for founder_class in teams_map["founder_classes"]:
        rules += founder_class.get("content", [])
    assert rules
    for rule in rules:
        assert re.search(rule["pattern"], rule["example"]), rule
        for glob in rule.get("in", []):
            assert glob_regex(glob)
    for rule in teams_map["content_rules"]:
        assert rule["adds"] in teams_map["teams"]
        if "lead" in rule:
            assert rule["lead"] in teams_map["teams"][rule["adds"]]["leads"]


def test_content_patterns_do_not_fire_on_ordinary_words(teams_map):
    by_id = {r["id"]: re.compile(r["pattern"]) for r in teams_map["content_rules"]}
    assert not by_id["commercial-wording"].search("the syntax of a taxonomy")
    assert not by_id["currency-amount"].search("M55 and v1.25.0")
    assert by_id["currency-amount"].search("\u20b9 9999")


# --- Founder classes and CODEOWNERS ---------------------------------------------------


def test_the_six_founder_classes_are_kept(teams_map):
    assert [c["id"] for c in teams_map["founder_classes"]] == [
        "control-plane", "gate-semantics", "licence-and-third-party",
        "commercial", "public-names-and-claims", "export-control",
    ]
    for founder_class in teams_map["founder_classes"]:
        assert founder_class.get("paths") or founder_class.get("content") or founder_class.get("sections") \
            or founder_class.get("note"), founder_class["id"]
    section_ids = {s["id"] for s in teams_map["sections"]}
    for founder_class in teams_map["founder_classes"]:
        assert set(founder_class.get("sections", [])) <= section_ids


def test_gate_files_are_founder_class_and_reviewed_by_verification(teams_map):
    gates = next(c for c in teams_map["founder_classes"] if c["id"] == "gate-semantics")["paths"]
    for glob in gates:
        for path in [p for p in tracked_files() if matches(glob, p)]:
            assert "verification" in owning_teams(teams_map, path), path


def _codeowners() -> list[tuple[str, list[str]]]:
    entries = []
    for line in CODEOWNERS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pattern, *owners = line.split()
            entries.append((pattern, owners))
    return entries


def test_codeowners_names_the_founder_on_exactly_the_founder_class_globs(teams_map):
    entries = _codeowners()
    assert entries
    for pattern, owners in entries:
        assert owners == [FOUNDER], pattern
    patterns = [p[1:] if p.startswith("/") else p for p, _ in entries]
    assert len(patterns) == len(set(patterns))
    for pattern, _ in entries:
        # Anchored at the root, except a "**/" glob, which means any directory.
        assert pattern.startswith("/") or pattern.startswith("**/"), pattern
    founder_globs = {g for c in teams_map["founder_classes"] for g in c.get("paths", [])}
    assert set(patterns) == founder_globs


def test_every_codeowners_pattern_matches_a_tracked_file(files):
    for pattern, _ in _codeowners():
        glob = pattern[1:] if pattern.startswith("/") else pattern
        assert any(matches(glob, p) for p in files), pattern


# --- The loader and the globs ---------------------------------------------------------


def test_the_loader_reads_the_subset():
    text = """# comment
a: 1
b: plain text # trailing comment
c: ['**', "x y", it''s]
d:
  - one
  - k: v
    l: [p, q]
e:
  f: 'a # not a comment'
"""
    assert load_map(text) == {
        "a": 1, "b": "plain text", "c": ["**", "x y", "it''s"],
        "d": ["one", {"k": "v", "l": ["p", "q"]}], "e": {"f": "a # not a comment"},
    }
    assert load_map("p: 'it''s'") == {"p": "it's"}


@pytest.mark.parametrize("text", [
    "a: **/x",          # an alias indicator: must be quoted
    "a: true",          # YAML would read a boolean
    "a:\n\tb: 1",       # tab
    "a: 1\na: 2",       # duplicate key
    "a:\n  b: 1\n    c: 2",  # stray indentation
    "a: [x",            # unclosed flow list
    'a: "x\\ny"',       # escapes in double quotes
    "a:",               # empty value
])
def test_the_loader_refuses_what_it_does_not_read(text):
    with pytest.raises(MapSyntaxError):
        load_map(text)


@pytest.mark.parametrize("glob, path, expected", [
    ("**", "a/b/c.py", True),
    ("site/**", "site/index.html", True),
    ("site/**", "site", False),
    ("**/LICENSE*", "LICENSE", True),
    ("**/LICENSE*", "src/x/serv/LICENSE", True),
    ("**/LICENSE*", "src/x/NOTLICENSE", False),
    ("docs/*FIRMWARE*.md", "docs/RISCV_FIRMWARE.md", True),
    ("docs/*FIRMWARE*.md", "docs/sub/FIRMWARE.md", False),
    ("scripts/check_*.py", "scripts/check_dashes.py", True),
    ("scripts/check_*.py", "scripts/status.py", False),
    ("src/nirmaan/integrations/eda*.py", "src/nirmaan/integrations/eda_parsers.py", True),
    ("council/records/*commercial*", "council/records/2026-10-16-commercial-model.md", True),
    ("CLAUDE.md", "docs/CLAUDE.md", False),
])
def test_globs(glob, path, expected):
    assert matches(glob, path) is expected
