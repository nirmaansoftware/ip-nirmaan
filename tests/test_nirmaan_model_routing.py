"""The role-to-model defaults in docs/MODEL_SELECTION.md, and the review tooling that must match them."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pr_loop  # noqa: E402
import pr_review  # noqa: E402

EXPECTED = {
    "fable": "claude-fable-5-2",
    "opus": "claude-opus-5-5",
    "sonnet": "claude-sonnet-5-5",
    "haiku": "claude-haiku-5-5",
}


def _table() -> dict[str, tuple[str, str]]:
    """alias -> (model id, work column), read from the Role-to-model section of the doc."""
    text = (ROOT / "docs" / "MODEL_SELECTION.md").read_text()
    section = text.split("## Role-to-model defaults", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| (.+?) \| `(\w+)` \| `([\w.-]+)` \|$", section, re.M)
    return {alias: (model, work) for work, alias, model in rows}


def test_the_documented_defaults_are_the_four_models():
    assert {a: m for a, (m, _) in _table().items()} == EXPECTED


def test_each_kind_of_work_sits_on_its_model():
    work = {a: w for a, (_, w) in _table().items()}
    assert "wave plans" in work["fable"] and "chairing a council meeting" in work["fable"]
    assert "RTL" in work["opus"] and "key 2" in work["opus"] and "Founder Proxy" in work["opus"]
    assert "key 1" in work["sonnet"] and "eval cases" in work["sonnet"]
    assert "explore" in work["haiku"]


def test_the_review_loop_defaults_match_the_table():
    table = _table()
    d = pr_loop.loop_defaults({})
    assert d["models"]["key1"] == "sonnet" and "key 1" in table["sonnet"][1]
    assert d["models"]["key2"] == "opus" and "key 2" in table["opus"][1]
    assert d["models"]["proxy"] == "opus" and "Founder Proxy" in table["opus"][1]
    assert d["fixer_model"] == "sonnet"
    assert pr_review.defaults({})["models"] == d["models"]
    for alias in [*d["models"].values(), d["fixer_model"]]:
        assert alias in table
